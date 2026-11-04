import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "src/security")
from masking import mask

import ticket_extract as ex
import ticket_priority as pr
import ticket_routing as rt
from ticket_common import load_cfg, parse_dt, fmt, working_hours_between, due_time

STORE = Path("data/tickets.json")


def load():
    return json.loads(STORE.read_text(encoding="utf-8")) if STORE.exists() else []


def save(tickets):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(tickets, indent=2), encoding="utf-8")


def find_duplicate(tickets, order_id, category, created, cfg):
    for t in tickets:
        if t["status"] == "CLOSED" or t["order_id"] != order_id or t["category"] != category:
            continue
        gap = abs((created - parse_dt(t["created"])).total_seconds()) / 3600
        if gap <= cfg["duplicate_window_hours"]:
            return t
    return None


def process(conv, now=None):
    """Turns one unresolved conversation into one or more tickets."""
    cfg = load_cfg()
    now = parse_dt(now) if now else datetime.now()
    fields, missing = ex.extract(conv)
    if missing:
        return [{"status": "NEEDS_INFO", "missing": missing, "ask": ex.clarification(missing)}]
    first = conv["messages"][0].get("time")
    created = parse_dt(first) if first else now
    text = ex.customer_text(conv)
    tickets, results = load(), []
    for category in fields["categories"]:               # one ticket per separate issue
        dup = find_duplicate(tickets, fields["order_id"], category, created, cfg)
        if dup:
            dup["duplicates"] = dup.get("duplicates", 0) + 1
            dup["events"].append(f"{fmt(now)} duplicate request merged")
            results.append({"status": "DUPLICATE", "of": dup["id"]})
            continue
        level, score, parts = pr.compute(category, text, created, now, conv.get("tier", "standard"))
        ticket = {
            "id": f"T-{len(tickets) + 1:04d}",
            "customer": fields["customer"], "order_id": fields["order_id"], "product": fields["product"],
            "category": category, "issue": fields["issue"], "evidence": fields["evidence"],
            "contact": fields["contact"], "priority": level, "score": score, "parts": parts,
            "created": fmt(created), "group_id": f"G-{fields['order_id']}",
            "status": "OPEN", "duplicates": 0, "events": [],
        }
        ticket["routing"] = rt.route(ticket, now)
        if ticket["routing"].get("escalate"):
            ticket["status"] = "ESCALATED"
            ticket["events"].append(f"{fmt(now)} escalated: {ticket['routing']['reason']}")
        tickets.append(ticket)
        results.append({"status": "CREATED", "ticket": ticket})
    save(tickets)
    return results


def handoff(t):
    """Masked summary for the agent."""
    parts = (t["customer"] or "Customer").split()
    name = parts[0] + (f" {parts[-1][0]}." if len(parts) > 1 else "")
    r = t["routing"]
    where = r["queue"] + (f" ({r['agent']})" if r.get("agent") else "") + \
        (f", scheduled for {r['scheduled_for']}" if r.get("scheduled_for") else "")
    return "\n".join([
        f"Ticket {t['id']} | {t['priority']} | {t['category']} | order {t['order_id']} | group {t['group_id']}",
        f"Customer: {name} | Contact: {mask(t['contact'])}",
        f"Issue: {mask(t['issue'])}",
        f"Evidence: {', '.join(t['evidence']) or 'none'}",
        f"Routed to: {where}",
    ])


def check_sla(now):
    """Warning at 75% of the SLA, automatic escalation after a breach. Config is re-read every call."""
    cfg = load_cfg()
    now = parse_dt(now)
    tickets, report = load(), []
    for t in tickets:
        if t["status"] == "CLOSED":
            continue
        allowed = cfg["sla_hours"][t["priority"]]
        created = parse_dt(t["created"])
        used = working_hours_between(created, now, cfg)
        frac = used / allowed
        state = "OK"
        if frac >= 1:
            state = "BREACHED"
            if not t.get("breached"):
                t["breached"], t["status"] = True, "ESCALATED"
                t["events"].append(f"{fmt(now)} SLA breached: escalated to team lead")
        elif frac >= cfg["warn_at"]:
            state = "WARNING"
            if not t.get("warned"):
                t["warned"] = True
                t["events"].append(f"{fmt(now)} SLA warning: {round(frac * 100)}% of time used")
        report.append({"id": t["id"], "priority": t["priority"], "used_pct": round(frac * 100),
                       "due": fmt(due_time(created, allowed, cfg)), "state": state})
    save(tickets)
    return report


SAMPLES = [
    ("1. Complete complaint (Mon 10:00)", "2026-11-02 10:00",
     "My name is Asha Rao. I was charged twice for order ORD-1001 (Rs 5,000) for my Smart Speaker. "
     "Screenshot attached. Please refund, this is unacceptable! Email asha.rao@example.com"),
    ("2. Same complaint again", "2026-11-02 11:00",
     "My name is Asha Rao. Charged twice for order ORD-1001, please fix. asha.rao@example.com"),
    ("3. Missing information", "2026-11-02 11:30",
     "My earbuds stopped working, please help."),
    ("4. Two separate issues, one order", "2026-11-02 12:00",
     "My name is Ravi Kumar. For order ORD-2002 I was charged twice and the delivery is also delayed. "
     "Call me on +91 98765 43210"),
    ("5. After hours, urgent (Sat 22:00)", "2026-11-07 22:00",
     "My name is Neha Singh. My account was hacked, order ORD-3003 was placed without me. neha@example.com"),
    ("6. After hours, normal (Sat 22:30)", "2026-11-07 22:30",
     "My name is Karan Mehta. My order ORD-4004 delivery is late. karan@example.com"),
]


def show(results):
    for r in results:
        if r["status"] == "CREATED":
            t = r["ticket"]
            print(f"  CREATED {t['id']} {t['priority']} (score {t['score']}) {t['category']} -> {t['routing']}")
            print("  " + handoff(t).replace("\n", "\n  "))
        elif r["status"] == "DUPLICATE":
            print(f"  DUPLICATE of {r['of']}")
        else:
            print(f"  NEEDS_INFO {r['missing']}: {r['ask']}")


def demo():
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text("[]", encoding="utf-8")
    rt.reset_agents()
    for title, when, text in SAMPLES:
        print(f"\n{title}")
        show(process({"messages": [{"from": "customer", "text": text, "time": when}]}, now=when))
    print("\n7. Unavailable team (Mon 10:00, every payment agent unavailable)")
    agents = rt.load_agents()
    for a in agents:
        if "payment" in a["skills"]:
            a["available"] = False
    rt.AGENTS.write_text(json.dumps(agents, indent=2), encoding="utf-8")
    show(process({"messages": [{"from": "customer", "time": "2026-11-09 10:00",
                                "text": "My name is Dev Rao. Refund for order ORD-5005 is pending. dev@example.com"}]},
                 now="2026-11-09 10:00"))
    rt.reset_agents()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    if cmd == "demo":
        demo()
    elif cmd == "sla":
        now = sys.argv[sys.argv.index("--now") + 1]
        print(f"SLA check at {now}")
        for r in check_sla(now):
            print(f"  {r['id']} {r['priority']} {r['used_pct']}% used, due {r['due']} -> {r['state']}")
    else:
        print("usage: ticket_service.py demo | sla --now \"YYYY-MM-DD HH:MM\"")
