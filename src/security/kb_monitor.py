import json
from datetime import datetime
from pathlib import Path

from masking import mask

LOG = Path("data/logs/kb_metrics.jsonl")
LATENCY_ALERT_MS = 1500
ESCALATION_ALERT_RATE = 0.5
FAILURE_ALERT_COUNT = 3


def record(kind, **fields):
    """Never raises: monitoring must not break the chatbot."""
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {"time": datetime.now().isoformat(timespec="seconds"), "kind": kind}
        entry.update({k: mask(v) if isinstance(v, str) else v for k, v in fields.items()})
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception:
        pass


def load():
    if not LOG.exists():
        return []
    return [json.loads(line) for line in LOG.read_text(encoding="utf-8").splitlines() if line.strip()]


def summary_data():
    rows = load()
    requests = [r for r in rows if r["kind"] == "request"]
    count = lambda kind: sum(1 for r in rows if r["kind"] == kind)
    data = {"requests": len(requests), "update_failures": count("update_failure"),
            "health_failures": count("health_failure"), "rollbacks": count("rollback"),
            "quarantined": count("quarantine"), "alerts": []}
    if requests:
        lat = sorted(r["latency_ms"] for r in requests)
        confs = [r["confidence"] for r in requests if r.get("confidence") is not None]
        data["latency_avg_ms"] = round(sum(lat) / len(lat), 1)
        data["latency_p95_ms"] = lat[int(0.95 * (len(lat) - 1))]
        data["confidence_avg"] = round(sum(confs) / len(confs), 2) if confs else None
        data["request_failures"] = sum(r.get("failures", 0) for r in requests)
        data["escalations"] = sum(1 for r in requests if r.get("escalated"))
        if data["latency_avg_ms"] > LATENCY_ALERT_MS:
            data["alerts"].append("High latency")
        if data["escalations"] / len(requests) > ESCALATION_ALERT_RATE:
            data["alerts"].append("High escalation rate")
    if data["update_failures"] + data["health_failures"] >= FAILURE_ALERT_COUNT:
        data["alerts"].append("Repeated update failures")
    return data


def summary():
    d = summary_data()
    print("=== Monitoring summary ===")
    print(f"Requests: {d['requests']}")
    if d["requests"]:
        print(f"Latency: avg {d['latency_avg_ms']} ms, p95 {d['latency_p95_ms']} ms")
        print(f"Confidence (sentiment): avg {d['confidence_avg']}")
        print(f"Request failures: {d['request_failures']}, escalations: {d['escalations']}")
    print(f"Update failures: {d['update_failures']}, health-check failures: {d['health_failures']}, "
          f"rollbacks: {d['rollbacks']}, quarantined documents: {d['quarantined']}")
    print("ALERTS: " + (", ".join(d["alerts"]) if d["alerts"] else "none"))


if __name__ == "__main__":
    summary()
