import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, "src/tickets")
sys.path.insert(0, "src/security")
from masking import mask
from ticket_common import load_cfg as ticket_cfg, in_business_hours, next_business_open, parse_dt, fmt

import sent_analyzer as an

CONV = Path("data/conversations.json")
ESC = Path("data/escalations.json")


def cfg():
    return yaml.safe_load(Path("config/config.yaml").read_text(encoding="utf-8-sig"))["sentiment"]


def _load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def queue_for(now, urgent):
    """Business hours: agent. After hours: urgent -> on-call queue, normal -> next working day."""
    tc = ticket_cfg()
    if in_business_hours(now, tc):
        return {"queue": "agent"}
    if urgent:
        return {"queue": "on-call"}
    return {"queue": "scheduled", "scheduled_for": fmt(next_business_open(now, tc))}


def summarize(conv):
    msgs = conv["messages"]
    negatives = sum(m["label"] in an.NEGATIVE_LABELS for m in msgs)
    trend = " -> ".join(m["label"] for m in msgs[-4:])
    return (f"{len(msgs)} customer message(s), {negatives} negative. Trend: {trend}. "
            f"Latest: {mask(msgs[-1]['text'])[:100]}")


def escalate(conv_id, conv, key, reason, now):
    if key in conv["escalated"]:
        return None
    conv["escalated"].append(key)
    escalations = _load(ESC, [])
    record = {
        "id": f"E-{len(escalations) + 1:04d}", "time": fmt(now), "conversation_id": conv_id,
        "reason": reason, "condition": key, "summary": summarize(conv),
        "routing": queue_for(now, urgent=True),
    }
    escalations.append(record)
    _save(ESC, escalations)
    return record


def handle_message(conv_id, text, now):
    c = cfg()
    now = parse_dt(now)
    convs = _load(CONV, {})
    conv = convs.setdefault(conv_id, {"messages": [], "negative_since": None, "resolved": False, "escalated": []})
    history = [(m["text"], m["label"]) for m in conv["messages"]]
    result = an.analyze(text, history)
    conv["messages"].append({"text": text, "time": fmt(now), "label": result["label"],
                             "confidence": result["confidence"]})
    conv["resolved"] = False

    complaint = result["label"] in an.NEGATIVE_LABELS or bool(result["high_risk"])
    if complaint and conv["negative_since"] is None:
        conv["negative_since"] = fmt(now)
    if result["label"] == "positive" and not result["high_risk"]:
        conv["negative_since"] = None                       # customer calmed down

    escalation = None
    if result["high_risk"]:
        kind = result["high_risk"].replace("_", " ")
        escalation = escalate(conv_id, conv, f"high_risk:{result['high_risk']}",
                              f"High-risk issue reported ({kind})", now)
    negative_count = sum(m["label"] in an.NEGATIVE_LABELS for m in conv["messages"])
    if escalation is None and negative_count >= c["repeated_negative_count"]:
        escalation = escalate(conv_id, conv, "repeated_negative",
                              f"{negative_count} negative messages in one conversation", now)
    if escalation is None and conv["negative_since"]:
        waited = (now - parse_dt(conv["negative_since"])).total_seconds() / 60
        if waited > c["unresolved_minutes"]:
            escalation = escalate(conv_id, conv, "negative_unresolved",
                                  f"Negative conversation unresolved for {int(waited)} minutes", now)

    _save(CONV, convs)
    return {
        "label": result["label"], "confidence": result["confidence"], "urgent": result["urgent"],
        "high_risk": result["high_risk"], "language": result["language"],
        "tone": an.tone_prefix(result),
        "queue": queue_for(now, result["urgent"]) if complaint else None,
        "escalation": escalation,
    }


def check_timeouts(now):
    """Run periodically (or with a simulated clock): escalate negative chats unresolved too long."""
    c = cfg()
    now = parse_dt(now)
    convs = _load(CONV, {})
    done = []
    for conv_id, conv in convs.items():
        if conv["resolved"] or not conv["negative_since"]:
            continue
        waited = (now - parse_dt(conv["negative_since"])).total_seconds() / 60
        if waited > c["unresolved_minutes"]:
            rec = escalate(conv_id, conv, "negative_unresolved",
                           f"Negative conversation unresolved for {int(waited)} minutes", now)
            if rec:
                done.append(rec)
    _save(CONV, convs)
    return done


def resolve(conv_id):
    convs = _load(CONV, {})
    if conv_id in convs:
        convs[conv_id]["resolved"] = True
        convs[conv_id]["negative_since"] = None
        _save(CONV, convs)


def show(title, text, r):
    print(f"\n{title}\n  \"{text}\"")
    print(f"  -> {r['label']} (confidence {r['confidence']}), language {r['language']}, "
          f"urgent={r['urgent']}, high_risk={r['high_risk']}")
    print(f"  tone: {r['tone'] or '(none)'}")
    print(f"  queue: {r['queue']}")
    if r["escalation"]:
        e = r["escalation"]
        print(f"  ESCALATED {e['id']}: {e['reason']}")
        print(f"    condition: {e['condition']} | routing: {e['routing']}")
        print(f"    summary: {e['summary']}")


def demo():
    _save(CONV, {})
    _save(ESC, [])
    steps = [
        ("1. Sarcasm", "c1", "2026-11-02 10:00", "Oh great, my order is late again. Wonderful service."),
        ("2. Hinglish + duplicate payment", "c2", "2026-11-02 10:00",
         "Bahut bakwas service hai, mera paisa do baar kat gaya"),
        ("3. Calm high-risk complaint", "c3", "2026-11-02 10:00",
         "Hello, I noticed my account was accessed by someone else. Please check."),
        ("4a. Repeated negative (1st)", "c4", "2026-11-02 10:00", "The product is bad."),
        ("4b. Repeated negative (2nd)", "c4", "2026-11-02 10:02", "Support is useless, nobody helps."),
        ("4c. Repeated negative (3rd)", "c4", "2026-11-02 10:04", "This is unacceptable."),
        ("5. After hours, urgent (Sat 22:00)", "c5", "2026-11-07 22:00",
         "Urgent! My package has not arrived, I need it asap."),
        ("6. After hours, normal complaint (Sat 22:30)", "c6", "2026-11-07 22:30",
         "My delivery is late and I am disappointed."),
        ("7. Positive", "c7", "2026-11-02 10:00", "Thank you so much, great help!"),
    ]
    for title, conv_id, when, text in steps:
        show(title, text, handle_message(conv_id, text, when))
    for conv_id in ("c1", "c2", "c3", "c4", "c5", "c6", "c7"):      # close the earlier chats
        resolve(conv_id)
    text = "My earphones are broken, this is terrible."
    show("8a. Unresolved timer starts (10:00)", text, handle_message("c8", text, "2026-11-02 10:00"))
    print("\n8b. Time check at 10:10 (10 minutes)")
    print("  escalations:", [e["id"] for e in check_timeouts("2026-11-02 10:10")] or "none")
    print("8c. Time check at 10:16 (16 minutes)")
    for e in check_timeouts("2026-11-02 10:16"):
        print(f"  ESCALATED {e['id']}: {e['reason']} | condition: {e['condition']}")
        print(f"    summary: {e['summary']}")
if __name__ == "__main__":
    demo()
