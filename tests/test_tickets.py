import json
import sys

sys.path.insert(0, "src/tickets")
sys.path.insert(0, "src/security")

import pytest

import ticket_common as tc
import ticket_routing as rt
import ticket_service as svc


@pytest.fixture(autouse=True)
def clean(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "STORE", tmp_path / "tickets.json")
    monkeypatch.setattr(rt, "AGENTS", tmp_path / "agents.json")
    rt.reset_agents()


def conv(text, when="2026-11-02 10:00"):
    return {"messages": [{"from": "customer", "text": text, "time": when}]}


FULL = ("My name is Asha Rao. I was charged twice for order ORD-1001 (Rs 5,000) for my Smart Speaker. "
        "Screenshot attached. Email asha.rao@example.com")


def test_fields_extracted():
    r = svc.process(conv(FULL), now="2026-11-02 10:00")[0]
    t = r["ticket"]
    assert t["customer"] == "Asha Rao" and t["order_id"] == "ORD-1001"
    assert t["product"] == "Smart Speaker" and t["contact"] == "asha.rao@example.com"
    assert t["category"] == "payment" and t["evidence"]


def test_missing_info_requested():
    r = svc.process(conv("My earbuds stopped working."), now="2026-11-02 10:00")[0]
    assert r["status"] == "NEEDS_INFO"
    assert "order_id" in r["missing"] and "contact" in r["missing"]
    assert svc.load() == []


def test_duplicate_detected():
    svc.process(conv(FULL), now="2026-11-02 10:00")
    r = svc.process(conv(FULL, "2026-11-02 12:00"), now="2026-11-02 12:00")[0]
    assert r["status"] == "DUPLICATE" and len(svc.load()) == 1


def test_two_issues_split_but_grouped():
    text = "My name is Ravi Kumar. Order ORD-2002: I was charged twice and delivery is delayed. ravi@example.com"
    res = svc.process(conv(text), now="2026-11-02 10:00")
    tickets = [r["ticket"] for r in res]
    assert {t["category"] for t in tickets} == {"payment", "delivery"}
    assert len({t["group_id"] for t in tickets}) == 1


def test_unrelated_orders_not_grouped():
    a = svc.process(conv(FULL), now="2026-11-02 10:00")[0]["ticket"]
    other = FULL.replace("ORD-1001", "ORD-9999")
    b = svc.process(conv(other), now="2026-11-02 10:00")[0]["ticket"]
    assert a["group_id"] != b["group_id"]


def test_high_risk_is_p1():
    text = "My name is Neha Singh. My account was hacked, order ORD-3003. neha@example.com"
    assert svc.process(conv(text), now="2026-11-02 10:00")[0]["ticket"]["priority"] == "P1"


def test_after_hours_urgent_goes_to_on_call():
    text = "My name is Neha Singh. My account was hacked, order ORD-3003. neha@example.com"
    t = svc.process(conv(text, "2026-11-07 22:00"), now="2026-11-07 22:00")[0]["ticket"]
    assert t["routing"]["queue"] == "on-call"


def test_after_hours_normal_scheduled_next_working_day():
    text = "My name is Karan Mehta. Order ORD-4004 delivery is late. karan@example.com"
    t = svc.process(conv(text, "2026-11-07 22:30"), now="2026-11-07 22:30")[0]["ticket"]
    assert t["routing"]["queue"] == "scheduled"
    assert t["routing"]["scheduled_for"] == "2026-11-09 09:00"


def test_unavailable_team_escalates():
    agents = rt.load_agents()
    for a in agents:
        if "payment" in a["skills"]:
            a["available"] = False
    rt.AGENTS.write_text(json.dumps(agents), encoding="utf-8")
    t = svc.process(conv(FULL), now="2026-11-02 10:00")[0]["ticket"]
    assert t["routing"]["queue"] == "unassigned" and t["status"] == "ESCALATED"


def test_sla_excludes_weekend_and_holiday():
    cfg = {"weekend_days": [5, 6], "holidays": ["2026-11-10"]}
    fri_night = tc.parse_dt("2026-11-06 22:00")
    assert tc.working_hours_between(fri_night, tc.parse_dt("2026-11-09 02:00"), cfg) == 4
    mon_noon = tc.parse_dt("2026-11-09 12:00")
    assert tc.working_hours_between(mon_noon, tc.parse_dt("2026-11-11 12:00"), cfg) == 24


def _seed_p2():
    ticket = {"id": "T-0001", "priority": "P2", "created": "2026-11-02 10:00", "status": "OPEN",
              "events": [], "order_id": "ORD-1", "category": "payment"}
    svc.save([ticket])


def test_sla_warning_then_breach():
    _seed_p2()                                          # P2 = 8 hours
    assert svc.check_sla("2026-11-02 16:30")[0]["state"] == "WARNING"     # 6.5h = 81%
    assert svc.check_sla("2026-11-02 19:00")[0]["state"] == "BREACHED"
    assert svc.load()[0]["status"] == "ESCALATED"


def test_runtime_sla_change_takes_effect(monkeypatch):
    _seed_p2()
    assert svc.check_sla("2026-11-02 15:00")[0]["state"] == "OK"
    cfg = dict(tc.load_cfg())
    cfg["sla_hours"] = dict(cfg["sla_hours"], P2=4)      # SLA tightened while running
    monkeypatch.setattr(svc, "load_cfg", lambda: cfg)
    assert svc.check_sla("2026-11-02 15:00")[0]["state"] == "BREACHED"


def test_handoff_is_masked():
    t = svc.process(conv(FULL), now="2026-11-02 10:00")[0]["ticket"]
    summary = svc.handoff(t)
    assert "asha.rao@example.com" not in summary and "[EMAIL]" in summary
