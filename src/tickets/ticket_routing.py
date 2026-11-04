import json
from pathlib import Path

from ticket_common import load_cfg, in_business_hours, next_business_open

AGENTS = Path("data/agents.json")
DEFAULT_AGENTS = [
    {"name": "Asha", "skills": ["payment", "account"], "available": True, "workload": 1, "on_call": False},
    {"name": "Ravi", "skills": ["delivery", "defect", "other"], "available": True, "workload": 2, "on_call": False},
    {"name": "Meera", "skills": ["payment", "delivery", "defect", "account", "other"],
     "available": True, "workload": 0, "on_call": True},
]


def reset_agents():
    AGENTS.parent.mkdir(parents=True, exist_ok=True)
    AGENTS.write_text(json.dumps(DEFAULT_AGENTS, indent=2), encoding="utf-8")


def load_agents():
    if not AGENTS.exists():
        reset_agents()
    return json.loads(AGENTS.read_text(encoding="utf-8"))


def route(ticket, now):
    cfg = load_cfg()
    agents = load_agents()                 # re-read every time: availability can change at runtime
    skilled = [a for a in agents if ticket["category"] in a["skills"]]
    if in_business_hours(now, cfg):
        free = sorted((a for a in skilled if a["available"]), key=lambda a: a["workload"])
        if free:
            free[0]["workload"] += 1
            AGENTS.write_text(json.dumps(agents, indent=2), encoding="utf-8")
            return {"queue": "agent", "agent": free[0]["name"]}
        return {"queue": "unassigned", "agent": None, "escalate": True,
                "reason": "no available agent with the required skill"}
    if ticket["priority"] in ("P1", "P2"):
        oncall = [a for a in skilled if a.get("on_call") and a["available"]]
        if oncall:
            return {"queue": "on-call", "agent": oncall[0]["name"]}
        return {"queue": "on-call", "agent": None, "escalate": True, "reason": "no on-call agent available"}
    return {"queue": "scheduled", "agent": None,
            "scheduled_for": next_business_open(now, cfg).strftime("%Y-%m-%d %H:%M")}
