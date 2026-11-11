
import json
import re
import uuid
from pathlib import Path
from datetime import datetime, timedelta

import yaml

SESSION_DIR = Path("data/sessions")
CONFIG_PATH = Path("config/config.yaml")

SESSION_DIR.mkdir(parents=True, exist_ok=True)


def load_session_config():
    config = yaml.safe_load(
        CONFIG_PATH.read_text(encoding="utf-8-sig")
    ) or {}

    return config.get("session", {})


def now():
    return datetime.now()


def parse_time(value):
    return datetime.fromisoformat(value)


def create_session(user_id):
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("Valid user_id is required")

    session_id = f"{user_id}_{uuid.uuid4().hex}"

    session = {
        "session_id": session_id,
        "user_id": user_id,
        "created_at": now().isoformat(),
        "last_activity": now().isoformat(),
        "messages": [],
        "summary": ""
    }

    save_session(session)
    return session


def save_session(session):
    path = SESSION_DIR / f"{session['session_id']}.json"

    path.write_text(
        json.dumps(session, indent=4, ensure_ascii=False),
        encoding="utf-8"
    )


def read_session_file(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def get_session(session_id):
    if not isinstance(session_id, str):
        return None

    if Path(session_id).name != session_id:
        return None

    path = SESSION_DIR / f"{session_id}.json"

    if not path.is_file():
        return None

    session = read_session_file(path)

    if session is None:
        return None

    settings = load_session_config()
    expiry = int(settings.get("inactivity_minutes", 30))

    try:
        last_activity = parse_time(session["last_activity"])
    except (KeyError, ValueError, TypeError):
        return None

    if now() - last_activity > timedelta(minutes=expiry):
        return None

    return session


def add_message(session_id, role, content):
    if not isinstance(role, str) or not isinstance(content, str):
        raise ValueError("Role and content must be strings")

    session = get_session(session_id)

    if session is None:
        return None

    session["messages"].append({
        "role": role,
        "content": content,
        "timestamp": now().isoformat()
    })

    session["last_activity"] = now().isoformat()
    save_session(session)

    return session


def get_context(session_id):
    session = get_session(session_id)

    if session is None:
        return []

    settings = load_session_config()
    limit = max(1, int(settings.get("min_context_messages", 10)))

    return session["messages"][-limit:]


def generate_summary(messages):
    if not messages:
        return ""

    recent_messages = messages[-10:]

    return "\n".join(
        f"{message.get('role', 'unknown')}: "
        f"{message.get('content', '')}"
        for message in recent_messages
    )


def restore_session(user_id):
    if not isinstance(user_id, str) or not user_id.strip():
        return None

    settings = load_session_config()
    restore_hours = int(settings.get("restore_window_hours", 24))

    candidates = []

    for path in SESSION_DIR.glob("*.json"):
        session = read_session_file(path)

        if not session or session.get("user_id") != user_id:
            continue

        try:
            last_activity = parse_time(session["last_activity"])
        except (KeyError, ValueError, TypeError):
            continue

        age = now() - last_activity

        if timedelta(0) <= age <= timedelta(hours=restore_hours):
            candidates.append((last_activity, session))

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[0], reverse=True)

    session = candidates[0][1]
    session["summary"] = generate_summary(session.get("messages", []))
    session["restored"] = True

    return session


def delete_session(session_id):
    if not isinstance(session_id, str):
        return False

    if Path(session_id).name != session_id:
        return False

    path = SESSION_DIR / f"{session_id}.json"

    if path.is_file():
        path.unlink()
        return True

    return False

class SessionManager:
    def __init__(self, config_path="config/config.yaml", clock=None):
        self.config_path = Path(config_path)
        self.clock = clock or datetime.now
        self.active_sessions = {}
        self.archives = {}
        self.settings = self._load_config()

    def _load_config(self):
        config = yaml.safe_load(
            self.config_path.read_text(encoding="utf-8-sig")
        ) or {}
        return config.get("session", {})

    def _now(self):
        return self.clock()

    def _archive(self, customer_id, session):
        session["active"] = False
        session["archived_at"] = self._now()
        self.archives[customer_id] = session

    def _cleanup_customer_archive(self, customer_id):
        session = self.archives.get(customer_id)

        if session is None:
            return

        archived_at = session.get("archived_at")

        if archived_at is None:
            return

        hours = int(self.settings.get("restore_window_hours", 24))

        if self._now() - archived_at > timedelta(hours=hours):
            self.archives.pop(customer_id, None)

    def start_session(self, customer_id, language="en"):
        if not isinstance(customer_id, str) or not customer_id.strip():
            raise ValueError("Valid customer ID is required")

        existing = self.get_session(customer_id)

        if existing is not None:
            return existing

        self._cleanup_customer_archive(customer_id)

        archived = self.archives.pop(customer_id, None)

        if archived is not None:
            session = archived.copy()
            session.pop("archived_at", None)
            session["active"] = True
            session["last_activity"] = self._now()
            return self._activate(customer_id, session)

        session = {
            "customer_id": customer_id,
            "language": language,
            "active": True,
            "created_at": self._now(),
            "last_activity": self._now(),
            "messages": [],
            "summary": ""
        }

        return self._activate(customer_id, session)

    def _activate(self, customer_id, session):
        session["active"] = True
        self.active_sessions[customer_id] = session
        return session

    def get_session(self, customer_id):
        session = self.active_sessions.get(customer_id)

        if session is None:
            return None

        last_activity = session["last_activity"]
        inactivity = int(
            self.settings.get("inactivity_minutes", 30)
        )

        if self._now() - last_activity >= timedelta(minutes=inactivity):
            self.active_sessions.pop(customer_id, None)
            self._archive(customer_id, session)
            return None

        return session

    def add_message(self, customer_id, role, content):
        session = self.get_session(customer_id)

        if session is None:
            return None

        if not isinstance(content, str) or not content.strip():
            raise ValueError("Message cannot be empty")

        if not isinstance(role, str) or not role.strip():
            raise ValueError("Valid role is required")

        session["messages"].append({
            "role": role,
            "content": content,
            "timestamp": self._now()
        })

        limit = max(
            1,
            int(self.settings.get("min_context_messages", 10))
        )

        session["messages"] = session["messages"][-limit:]
        session["last_activity"] = self._now()

        return session

    def switch_language(self, customer_id, language):
        session = self.get_session(customer_id)

        if session is None:
            return None

        session["language"] = language
        session["last_activity"] = self._now()

        return session

    def close_session(self, customer_id, summary=None):
        session = self.active_sessions.pop(customer_id, None)

        if session is None:
            return False

        if summary is not None:
            session["summary"] = summary

        self._archive(customer_id, session)
        return True

    def cleanup_expired_archives(self):
        expired = []

        hours = int(self.settings.get("restore_window_hours", 24))

        for customer_id, session in self.archives.items():
            archived_at = session.get("archived_at")

            if archived_at is None:
                expired.append(customer_id)
            elif self._now() - archived_at > timedelta(hours=hours):
                expired.append(customer_id)

        for customer_id in expired:
            self.archives.pop(customer_id, None)

        return len(expired)
