import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
CARD = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")


def mask(text):
    """Hide emails, card numbers and phone numbers."""
    text = EMAIL.sub("[EMAIL]", text)
    text = CARD.sub("[CARD]", text)
    text = PHONE.sub("[PHONE]", text)
    return text
