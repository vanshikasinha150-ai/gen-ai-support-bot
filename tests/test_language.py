
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, "src/language")

from language_service import (
    detect_language,
    translate_text,
    process_message,
)
from session_manager import SessionManager


# ---------------- LANGUAGE DETECTION ----------------

def test_english_detection():
    result = detect_language("Hello, how are you doing today?")
    assert result["language"] == "en"


def test_hindi_detection():
    result = detect_language("मुझे मदद चाहिए")
    assert result["language"] == "hi"


def test_kannada_detection():
    result = detect_language("ನನಗೆ ಸಹಾಯ ಬೇಕು")
    assert result["language"] == "kn"


def test_tamil_detection():
    result = detect_language("எனக்கு உதவி வேண்டும்")
    assert result["language"] == "ta"


def test_hinglish_detection():
    result = detect_language("Mujhe paisa chahiye")
    assert result["language"] == "hi"


def test_mixed_language_detection():
    result = detect_language("Hello मुझे ನಮಸ್ಕಾರ")
    assert result["language"] == "mixed"
    assert "hi" in result["languages"]
    assert "kn" in result["languages"]


def test_empty_message():
    result = detect_language("")
    assert result["language"] is None
    assert result["needs_clarification"] is True


def test_invalid_input():
    result = detect_language(None)
    assert result["language"] is None
    assert result["needs_clarification"] is True


def test_process_message_requests_clarification():
    result = process_message("Hi")
    assert result["needs_clarification"] is True
    assert result["message"] is not None


# ---------------- TRANSLATION ----------------

def test_translation_with_mock_engine():
    def translator(text, source, target):
        return "Translated: " + text

    result = translate_text(
        "Hello",
        "en",
        "hi",
        translator=translator
    )

    assert result == "Translated: Hello"


def test_same_language_skips_translation():
    result = translate_text("Hello", "en", "en")
    assert result == "Hello"


def test_missing_translation_engine():
    with pytest.raises(RuntimeError):
        translate_text("Hello", "en", "hi")


def test_unsupported_source_language():
    with pytest.raises(ValueError):
        translate_text("Hello", "fr", "hi")


def test_unsupported_target_language():
    with pytest.raises(ValueError):
        translate_text("Hello", "en", "fr")


def test_non_string_translation_input():
    with pytest.raises(TypeError):
        translate_text(123, "en", "hi")


def test_order_id_is_protected():
    def translator(text, source, target):
        return "Translated: " + text

    result = translate_text(
        "My order ORD-12345 is delayed",
        "en",
        "hi",
        translator=translator
    )

    assert "ORD-12345" in result


def test_custom_protected_term():
    def translator(text, source, target):
        return "Translated: " + text

    result = translate_text(
        "Product Smart Speaker is defective",
        "en",
        "hi",
        translator=translator,
        protected_terms=["Smart Speaker"]
    )

    assert "Smart Speaker" in result


def test_modified_protected_data_is_rejected():
    def translator(text, source, target):
        return "Translated without placeholder"

    with pytest.raises(ValueError):
        translate_text(
            "Order ORD-12345",
            "en",
            "hi",
            translator=translator
        )


def test_invalid_translator_output():
    def translator(text, source, target):
        return None

    with pytest.raises(ValueError):
        translate_text("Hello", "en", "hi", translator=translator)


# ---------------- SESSION MANAGEMENT ----------------

class FakeClock:
    def __init__(self):
        self.current = datetime(
            2026, 11, 10, 10, 0, tzinfo=timezone.utc
        )

    def __call__(self):
        return self.current

    def advance(self, **kwargs):
        self.current += timedelta(**kwargs)


@pytest.fixture
def manager(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(
        """
session:
  inactivity_minutes: 30
  restore_window_hours: 24
  min_context_messages: 3
""",
        encoding="utf-8"
    )

    clock = FakeClock()
    return SessionManager(str(config), clock=clock), clock


def test_session_creation(manager):
    session_manager, clock = manager

    session = session_manager.start_session("customer1", "en")

    assert session["customer_id"] == "customer1"
    assert session["language"] == "en"
    assert session["active"] is True


def test_session_message_storage(manager):
    session_manager, clock = manager

    session_manager.start_session("customer1")
    session = session_manager.add_message(
        "customer1", "user", "Hello"
    )

    assert len(session["messages"]) == 1
    assert session["messages"][0]["content"] == "Hello"


def test_language_switch(manager):
    session_manager, clock = manager

    session_manager.start_session("customer1")
    session = session_manager.switch_language("customer1", "hi")

    assert session["language"] == "hi"


def test_inactivity_archives_session(manager):
    session_manager, clock = manager

    session_manager.start_session("customer1")
    clock.advance(minutes=30)

    assert session_manager.get_session("customer1") is None
    assert "customer1" in session_manager.archives


def test_session_restoration(manager):
    session_manager, clock = manager

    session_manager.start_session("customer1", "hi")
    session_manager.add_message("customer1", "user", "नमस्ते")
    session_manager.close_session("customer1", "Previous conversation")

    restored = session_manager.start_session("customer1")

    assert restored["language"] == "hi"
    assert restored["summary"] == "Previous conversation"
    assert len(restored["messages"]) == 1


def test_old_session_is_not_restored(manager):
    session_manager, clock = manager

    session_manager.start_session("customer1", "hi")
    session_manager.close_session("customer1")

    clock.advance(hours=25)

    new_session = session_manager.start_session("customer1", "en")

    assert new_session["language"] == "en"
    assert len(new_session["messages"]) == 0


def test_message_history_limit(manager):
    session_manager, clock = manager

    session_manager.start_session("customer1")

    for i in range(5):
        session_manager.add_message(
            "customer1", "user", f"Message {i}"
        )

    session = session_manager.get_session("customer1")

    assert len(session["messages"]) == 3
    assert session["messages"][-1]["content"] == "Message 4"


def test_empty_message_rejected(manager):
    session_manager, clock = manager

    session_manager.start_session("customer1")

    with pytest.raises(ValueError):
        session_manager.add_message("customer1", "user", "")


def test_missing_customer_id_rejected(manager):
    session_manager, clock = manager

    with pytest.raises(ValueError):
        session_manager.start_session("")


def test_closing_session(manager):
    session_manager, clock = manager

    session_manager.start_session("customer1")

    result = session_manager.close_session(
        "customer1", "Conversation completed"
    )

    assert result is True
    assert session_manager.get_session("customer1") is None


def test_cleanup_expired_archives(manager):
    session_manager, clock = manager

    session_manager.start_session("customer1")
    session_manager.close_session("customer1")

    clock.advance(hours=25)

    removed = session_manager.cleanup_expired_archives()

    assert removed == 1
    assert "customer1" not in session_manager.archives
