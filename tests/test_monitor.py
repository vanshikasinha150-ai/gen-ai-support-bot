
from datetime import datetime

from src.monitoring import monitor


def test_run_once_calls_both_services(monkeypatch):
    sentiment_result = [{"conversation_id": "C-001"}]
    ticket_result = [{"id": "T-001", "state": "BREACHED"}]

    monkeypatch.setattr(
        monitor.sent_service,
        "check_timeouts",
        lambda now: sentiment_result,
    )
    monkeypatch.setattr(
        monitor.ticket_service,
        "check_sla",
        lambda now: ticket_result,
    )

    report = monitor.run_once(datetime(2026, 11, 10, 10, 0))

    assert report["sentiment_escalations"] == sentiment_result
    assert report["ticket_sla"] == ticket_result
    assert report["errors"] == []


def test_run_once_handles_sentiment_failure(monkeypatch):
    def fail_sentiment(now):
        raise RuntimeError("Sentiment service failed")

    monkeypatch.setattr(
        monitor.sent_service,
        "check_timeouts",
        fail_sentiment,
    )
    monkeypatch.setattr(
        monitor.ticket_service,
        "check_sla",
        lambda now: [{"id": "T-001"}],
    )

    report = monitor.run_once()

    assert report["sentiment_escalations"] == []
    assert report["ticket_sla"] == [{"id": "T-001"}]
    assert report["errors"][0]["service"] == "sentiment"


def test_run_once_handles_ticket_failure(monkeypatch):
    def fail_ticket(now):
        raise RuntimeError("Ticket service failed")

    monkeypatch.setattr(
        monitor.sent_service,
        "check_timeouts",
        lambda now: [{"conversation_id": "C-001"}],
    )
    monkeypatch.setattr(
        monitor.ticket_service,
        "check_sla",
        fail_ticket,
    )

    report = monitor.run_once()

    assert report["sentiment_escalations"] == [
        {"conversation_id": "C-001"}
    ]
    assert report["ticket_sla"] == []
    assert report["errors"][0]["service"] == "tickets"


def test_daemon_rejects_invalid_interval():
    import pytest

    with pytest.raises(ValueError):
        monitor.daemon(interval_seconds=0)
