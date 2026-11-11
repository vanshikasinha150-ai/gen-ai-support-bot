from src import chatbot as bot_module


def make_bot(tmp_path):
    config = tmp_path / "config.yaml"
    config.write_text(
        """
session:
  inactivity_minutes: 30
  restore_window_hours: 24
  min_context_messages: 10
""",
        encoding="utf-8"
    )
    return bot_module.CustomerServiceBot(config_path=config)


def test_chatbot_orchestrates_services(tmp_path, monkeypatch):
    bot = make_bot(tmp_path)

    monkeypatch.setattr(
        bot_module,
        "detect_message",
        lambda message: {
            "language": "en",
            "needs_clarification": False,
        },
    )
    monkeypatch.setattr(
        bot_module.sent_service,
        "handle_message",
        lambda *args: {
            "label": "neutral",
            "tone": "I understand your concern.",
            "escalation": None,
        },
    )
    monkeypatch.setattr(
        bot_module.retriever,
        "answer",
        lambda *args, **kwargs: "Here is the knowledge-base answer.",
    )
    monkeypatch.setattr(
        bot_module.ticket_extract,
        "detect_categories",
        lambda text: ["other"],
    )

    result = bot.process_message(
        "customer1",
        "Hello, how can I track my order?",
        now="2026-11-10 10:00:00",
    )

    assert result["customer_id"] == "customer1"
    assert result["sentiment"]["label"] == "neutral"
    assert result["answer"] == "Here is the knowledge-base answer."
    assert result["errors"] == []
    assert result["response"]


def test_chatbot_creates_ticket_for_detected_issue(tmp_path, monkeypatch):
    bot = make_bot(tmp_path)

    monkeypatch.setattr(
        bot_module,
        "detect_message",
        lambda message: {
            "language": "en",
            "needs_clarification": False,
        },
    )
    monkeypatch.setattr(
        bot_module.sent_service,
        "handle_message",
        lambda *args: {"tone": "We understand."},
    )
    monkeypatch.setattr(
        bot_module.retriever,
        "answer",
        lambda *args, **kwargs: "Please check your payment.",
    )
    monkeypatch.setattr(
        bot_module.ticket_extract,
        "detect_categories",
        lambda text: ["payment"],
    )

    ticket_call = {}

    def fake_ticket_process(conversation, now=None):
        ticket_call["conversation"] = conversation
        ticket_call["now"] = now
        return [{
            "status": "CREATED",
            "ticket": {
                "id": "T-TEST-001",
                "priority": "P2",
            },
        }]

    monkeypatch.setattr(
        bot_module.ticket_service,
        "process",
        fake_ticket_process,
    )

    result = bot.process_message(
        "customer2",
        "I was charged twice for my order.",
        now="2026-11-10 10:00:00",
    )

    assert ticket_call["now"] == "2026-11-10 10:00:00"
    assert ticket_call["conversation"]["messages"]
    assert result["tickets"][0]["status"] == "CREATED"
    assert "T-TEST-001" in result["response"]


def test_chatbot_processes_file_attachment(tmp_path, monkeypatch):
    bot = make_bot(tmp_path)

    monkeypatch.setattr(
        bot_module,
        "detect_message",
        lambda message: {
            "language": "en",
            "needs_clarification": False,
        },
    )

    monkeypatch.setattr(
        bot_module.mm_service,
        "submit",
        lambda *args, **kwargs: {
            "reply": "File processed successfully."
        },
    )

    result = bot.process_message(
        "customer3",
        "Please check this document.",
        file_path="sample.pdf",
        now="2026-11-10 10:00:00",
    )

    assert result["file"]["reply"] == "File processed successfully."
    assert "File processed successfully." in result["response"]


def test_chatbot_continues_when_service_fails(tmp_path, monkeypatch):
    bot = make_bot(tmp_path)

    monkeypatch.setattr(
        bot_module,
        "detect_message",
        lambda message: {
            "language": "en",
            "needs_clarification": False,
        },
    )

    def fail_sentiment(*args, **kwargs):
        raise RuntimeError("Sentiment service unavailable")

    monkeypatch.setattr(
        bot_module.sent_service,
        "handle_message",
        fail_sentiment,
    )
    monkeypatch.setattr(
        bot_module.retriever,
        "answer",
        lambda *args, **kwargs: "Fallback knowledge answer.",
    )
    monkeypatch.setattr(
        bot_module.ticket_extract,
        "detect_categories",
        lambda text: ["other"],
    )

    result = bot.process_message(
        "customer4",
        "I need help with my order.",
        now="2026-11-10 10:00:00",
    )

    assert result["sentiment"] is None
    assert result["answer"] == "Fallback knowledge answer."
    assert any(
        error["service"] == "sentiment"
        for error in result["errors"]
    )
