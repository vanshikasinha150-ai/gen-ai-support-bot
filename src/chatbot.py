import sys
from datetime import datetime
from pathlib import Path

# Make existing service modules importable without changing their code.
ROOT = Path(__file__).resolve().parent.parent

for folder in (
    "language",
    "tickets",
    "sentiment",
    "rag",
    "multimodal",
    "security",
):
    path = str(ROOT / "src" / folder)
    if path not in sys.path:
        sys.path.insert(0, path)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from language_service import process_message as detect_message
from language_service import SUPPORTED_LANGUAGES
from session_manager import SessionManager

import sent_service
import ticket_service
import ticket_extract
import retriever
import mm_service


class CustomerServiceBot:
    """Coordinates the existing customer-service modules."""

    def __init__(self, config_path=None, translator=None):
        self.config_path = Path(
            config_path or ROOT / "config" / "config.yaml"
        )
        self.sessions = SessionManager(str(self.config_path))
        self.translator = translator

    @staticmethod
    def _timestamp(now=None):
        if now is None:
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if isinstance(now, datetime):
            return now.strftime("%Y-%m-%d %H:%M:%S")

        return str(now)

    def start_session(self, customer_id, language="en"):
        """Start or restore a customer session."""
        return self.sessions.start_session(customer_id, language)

    def close_session(self, customer_id, summary=None):
        return self.sessions.close_session(customer_id, summary)

    def get_session(self, customer_id):
        return self.sessions.get_session(customer_id)

    def process_message(
        self,
        customer_id,
        message,
        file_path=None,
        role="public",
        region="IN",
        now=None,
    ):
        """Process one customer message across the available services."""

        if not isinstance(customer_id, str) or not customer_id.strip():
            raise ValueError("Valid customer ID is required")

        if not isinstance(message, str) or not message.strip():
            if file_path is None:
                raise ValueError("Message or file attachment is required")

        timestamp = self._timestamp(now)

        session = self.sessions.get_session(customer_id)
        if session is None:
            session = self.sessions.start_session(customer_id)

        language_info = detect_message(message or "")
        detected_language = language_info.get("language")

        if detected_language in SUPPORTED_LANGUAGES:
            self.sessions.switch_language(
                customer_id, detected_language
            )

        if message and message.strip():
            self.sessions.add_message(
                customer_id, "user", message
            )

        sentiment = None
        rag_answer = None
        ticket_results = []
        file_result = None
        errors = []

        # 1. Sentiment analysis and escalation.
        if message and message.strip():
            try:
                sentiment = sent_service.handle_message(
                    customer_id, message, timestamp
                )
            except Exception as exc:
                errors.append({
                    "service": "sentiment",
                    "error": str(exc),
                })

        # 2. Knowledge-base retrieval.
        if message and message.strip():
            try:
                rag_answer = retriever.answer(
                    message,
                    role=role,
                    region=region,
                    as_of=timestamp,
                )
            except Exception as exc:
                errors.append({
                    "service": "rag",
                    "error": str(exc),
                })

        # 3. Create tickets only when a support issue is detected.
        if message and message.strip():
            try:
                current_session = self.sessions.get_session(
                    customer_id
                )

                customer_messages = [
                    {
                        "from": "customer",
                        "text": item["content"],
                        "time": self._timestamp(item["timestamp"]),
                    }
                    for item in current_session["messages"]
                    if item["role"] == "user"
                ]

                full_text = " ".join(
                    item["text"] for item in customer_messages
                )

                categories = ticket_extract.detect_categories(
                    full_text
                )

                if categories != ["other"]:
                    conversation = {
                        "messages": customer_messages,
                        "attachments": (
                            [Path(file_path).name]
                            if file_path else []
                        ),
                    }

                    ticket_results = ticket_service.process(
                        conversation, now=timestamp
                    )

            except Exception as exc:
                errors.append({
                    "service": "tickets",
                    "error": str(exc),
                })

        # 4. Process an optional image or PDF attachment.
        if file_path is not None:
            try:
                file_result = mm_service.submit(
                    customer_id,
                    message=message or "",
                    file_path=file_path,
                    now=timestamp,
                )
            except Exception as exc:
                errors.append({
                    "service": "multimodal",
                    "error": str(exc),
                })

        # 5. Build a unified response.
        replies = []

        if language_info.get("needs_clarification"):
            replies.append(language_info["message"])

        if sentiment and sentiment.get("tone"):
            replies.append(sentiment["tone"])

        if rag_answer:
            replies.append(rag_answer)

        if ticket_results:
            for result in ticket_results:
                if result["status"] == "NEEDS_INFO":
                    replies.append(result["ask"])
                elif result["status"] == "CREATED":
                    ticket = result["ticket"]
                    replies.append(
                        f"Your support ticket {ticket['id']} "
                        f"has been created with {ticket['priority']} priority."
                    )
                elif result["status"] == "DUPLICATE":
                    replies.append(
                        f"This issue is already recorded under ticket "
                        f"{result['of']}."
                    )

        if file_result:
            replies.append(file_result.get("reply", "File received."))

        if not replies:
            replies.append(
                "I received your message. How can I help you?"
            )

        response_text = "\n\n".join(
            str(reply) for reply in replies if reply
        )

        self.sessions.add_message(
            customer_id, "assistant", response_text
        )

        return {
            "customer_id": customer_id,
            "language": language_info,
            "session": self.sessions.get_session(customer_id),
            "sentiment": sentiment,
            "answer": rag_answer,
            "tickets": ticket_results,
            "file": file_result,
            "response": response_text,
            "errors": errors,
        }


# Simple reusable entry point.
_default_bot = None


def get_bot():
    global _default_bot

    if _default_bot is None:
        _default_bot = CustomerServiceBot()

    return _default_bot


def chat(customer_id, message, **kwargs):
    return get_bot().process_message(
        customer_id, message, **kwargs
    )
