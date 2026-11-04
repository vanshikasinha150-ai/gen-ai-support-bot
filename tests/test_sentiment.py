import sys

sys.path.insert(0, "src/sentiment")
sys.path.insert(0, "src/tickets")
sys.path.insert(0, "src/security")

import pytest

import sent_analyzer as an
import sent_service as svc


@pytest.fixture(autouse=True)
def clean(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "CONV", tmp_path / "conv.json")
    monkeypatch.setattr(svc, "ESC", tmp_path / "esc.json")


def label(text, history=()):
    return an.analyze(text, history)["label"]


def test_six_labels():
    assert label("Thank you, this was really helpful and excellent") == "positive"
    assert label("I would like to know the status of my order") == "neutral"
    assert label("This product is terrible and I am disappointed") == "negative"
    assert label("I am so frustrated, I am fed up of waiting") == "frustrated"
    assert label("I need a replacement urgently, asap") == "urgent"
    assert label("Oh great, my order is late again. Wonderful service.") == "sarcastic"


def test_sarcasm_uses_history():
    history = [("My order is late", "negative")]
    assert label("Great, thanks a lot", history) == "sarcastic"
    assert label("Great, thanks a lot") == "positive"
    assert label("Thanks, the issue is resolved now", history) == "positive"


def test_multilingual_labels():
    assert label("Ye service bahut bakwas hai") == "negative"
    assert label("\u092f\u0939 \u092c\u0939\u0941\u0924 \u0916\u0930\u093e\u092c \u0939\u0948") == "negative"
    assert label("Muchas gracias, excelente servicio") == "positive"
    assert label("Je suis tres decu, c'est une arnaque") == "negative"
    assert an.analyze("Mera order kab aayega, mujhe jaldi chahiye")["urgent"] is True
    assert an.analyze("Ye service bahut bakwas hai")["language"] == "hi-Latn"


def test_confidence_range():
    for text in ["hello", "worst service ever!!", "thanks", "urgent urgent asap immediately"]:
        assert 0 <= an.analyze(text)["confidence"] <= 1


def test_tone_changes_but_policy_does_not():
    policy = "Refunds are allowed within 14 days of delivery."
    angry = an.analyze("This is terrible, I am fed up")
    calm = an.analyze("What is the refund window?")
    assert policy in an.respond(policy, angry)
    assert an.respond(policy, angry) != policy
    assert an.respond(policy, calm) == policy


def test_calm_high_risk_still_escalates():
    r = svc.handle_message("a", "Hello, I noticed my account was accessed by someone else. Please check.",
                           "2026-11-02 10:00")
    assert r["label"] == "neutral" and r["high_risk"] == "account_compromise"
    assert r["escalation"]["condition"] == "high_risk:account_compromise"


def test_duplicate_payment_and_legal_threat_escalate():
    r1 = svc.handle_message("b", "I was charged twice for my order", "2026-11-02 10:00")
    r2 = svc.handle_message("c", "I will take legal action if this is not fixed", "2026-11-02 10:00")
    assert r1["escalation"]["condition"] == "high_risk:duplicate_payment"
    assert r2["escalation"]["condition"] == "high_risk:legal_threat"


def test_repeated_negative_escalates_on_third():
    r1 = svc.handle_message("d", "The product is bad.", "2026-11-02 10:00")
    r2 = svc.handle_message("d", "Support is useless.", "2026-11-02 10:01")
    r3 = svc.handle_message("d", "This is unacceptable.", "2026-11-02 10:02")
    assert r1["escalation"] is None and r2["escalation"] is None
    assert r3["escalation"]["condition"] == "repeated_negative"


def test_unresolved_15_minutes_with_simulated_time():
    svc.handle_message("e", "My earphones are broken and terrible.", "2026-11-02 10:00")
    assert svc.check_timeouts("2026-11-02 10:14") == []
    done = svc.check_timeouts("2026-11-02 10:16")
    assert len(done) == 1 and done[0]["condition"] == "negative_unresolved"
    assert done[0]["reason"] and done[0]["summary"]
    assert svc.check_timeouts("2026-11-02 10:30") == []          # not escalated twice


def test_resolved_conversation_is_not_escalated():
    svc.handle_message("f", "My earphones are broken and terrible.", "2026-11-02 10:00")
    svc.resolve("f")
    assert svc.check_timeouts("2026-11-02 11:00") == []


def test_after_hours_queues():
    urgent = svc.handle_message("g", "Urgent! My package has not arrived, need it asap", "2026-11-07 22:00")
    normal = svc.handle_message("h", "My delivery is late and I am disappointed", "2026-11-07 22:30")
    day = svc.handle_message("i", "My delivery is late and I am disappointed", "2026-11-02 11:00")
    assert urgent["queue"]["queue"] == "on-call"
    assert normal["queue"] == {"queue": "scheduled", "scheduled_for": "2026-11-09 09:00"}
    assert day["queue"]["queue"] == "agent"


def test_non_complaint_has_no_queue():
    assert svc.handle_message("j", "Thank you so much, great help!", "2026-11-07 22:00")["queue"] is None


def test_summary_is_masked():
    svc.handle_message("k", "I was charged twice, mail me at asha@example.com", "2026-11-02 10:00")
    esc = svc._load(svc.ESC, [])
    assert "asha@example.com" not in esc[0]["summary"] and "[EMAIL]" in esc[0]["summary"]
