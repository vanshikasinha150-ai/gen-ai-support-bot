import re

from ticket_common import load_cfg

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?!\d)")
NAME = re.compile(r"(?i:my name is|i am|i'm|this is)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)")
EVIDENCE = re.compile(r"(?i)\b(screenshot|photo|picture|invoice|receipt|video|attached|attachment)\b")

KEYWORDS = {
    "account": [r"hack", r"compromis", r"unauthori[sz]ed", r"fraud", r"account (?:is )?locked",
                r"can't log ?in", r"cannot log ?in"],
    "payment": [r"charged twice", r"double charg", r"duplicate payment", r"refund", r"payment",
                r"money (?:was )?deducted", r"charged"],
    "delivery": [r"not (?:been )?delivered", r"\blate\b", r"delay", r"shipping", r"tracking",
                 r"courier", r"hasn'?t arrived"],
    "defect": [r"broken", r"damaged", r"defective", r"not working", r"stopped working", r"faulty"],
}

ASK = {
    "customer": "your full name",
    "order_id": "your order ID",
    "issue": "a short description of the problem",
    "contact": "an email address or phone number we can reach you on",
}


def find_order(text):
    m = re.search(r"(?i)\bORD-?(\d{4,10})\b", text) or \
        re.search(r"(?i)\border(?:\s*(?:id|number|no\.?))?\s*[:#-]?\s*(\d{4,10})\b", text)
    return f"ORD-{m.group(1)}" if m else None


def detect_categories(text):
    low = text.lower()
    found = [c for c, pats in KEYWORDS.items() if any(re.search(p, low) for p in pats)]
    return found or ["other"]


def customer_text(conv):
    return " ".join(m["text"] for m in conv["messages"] if m.get("from", "customer") == "customer")


def extract(conv):
    """Returns (fields, missing_mandatory_fields)."""
    cfg = load_cfg()
    text = customer_text(conv)
    name = conv.get("customer")
    if not name:
        m = NAME.search(text)
        name = m.group(1) if m else None
    email, phone = EMAIL.search(text), PHONE.search(text)
    evidence = list(conv.get("attachments", []))
    evidence += sorted({m.group(1).lower() + " mentioned" for m in EVIDENCE.finditer(text)})
    fields = {
        "customer": name,
        "order_id": find_order(text),
        "product": next((p for p in cfg["products"] if p.lower() in text.lower()), None),
        "categories": detect_categories(text),
        "issue": text.strip()[:140] or None,
        "evidence": evidence,
        "contact": conv.get("contact") or (email.group(0) if email else (phone.group(0) if phone else None)),
    }
    missing = [k for k in cfg["mandatory"] if not fields.get(k)]
    return fields, missing


def clarification(missing):
    items = [ASK[k] for k in missing]
    joined = items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]
    return f"To create your ticket, could you please share {joined}?"
