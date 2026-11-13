import json
import re
from datetime import datetime
from pathlib import Path

import yaml

from masking import mask

AUDIT = Path("data/logs/kb_audit.log")
DEFAULT = {
    "roles": {"viewer": ["status"], "operator": ["status", "run"], "admin": ["status", "run", "rollback"]},
    "users": {"guest": "viewer", "ops_user": "operator", "admin_user": "admin", "scheduler": "admin"},
}
INJECTION = [
    r"ignore (all |any )?(previous|prior|above) (instructions|rules)",
    r"disregard .{0,30}(instructions|rules|polic)",
    r"reveal .{0,40}(admin|secret|password|system prompt|api key)",
    r"system prompt",
    r"you are now",
    r"pretend (to be|you are)",
    r"act as .{0,20}(admin|root)",
    r"override .{0,20}(policy|rules|instructions)",
]
INJECTION_RX = [re.compile(p, re.I) for p in INJECTION]


def _access():
    try:
        cfg = yaml.safe_load(Path("config/config.yaml").read_text(encoding="utf-8-sig")) or {}
        return cfg.get("access") or DEFAULT
    except Exception:
        return DEFAULT


def audit(event, **fields):
    """Audit log. Every value is masked (emails, phone numbers, card numbers)."""
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    entry = {"time": datetime.now().isoformat(timespec="seconds"), "event": event}
    entry.update({k: mask(str(v)) for k, v in fields.items()})
    with AUDIT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def can(user, action):
    access = _access()
    role = access["users"].get(user)
    return role is not None and action in access["roles"].get(role, [])


def authorize(user, action):
    """Raises PermissionError (and writes an audit entry) unless the user's role allows the action."""
    if not can(user, action):
        audit("DENIED", user=user, action=action)
        raise PermissionError(f"user '{user}' is not allowed to '{action}'")
    audit("ALLOWED", user=user, action=action)


def scan(text):
    """Returns the prompt-injection patterns found in a document."""
    return [rx.pattern for rx in INJECTION_RX if rx.search(text)]
