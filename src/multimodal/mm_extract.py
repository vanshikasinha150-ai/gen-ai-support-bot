import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import yaml

ORDER_RX = re.compile(r"\bORD-?(\d{4,10})\b", re.I)
ORDER_WORD_RX = re.compile(r"\border\s*(?:id|number|no\.?|#)?\s*[:#-]?\s*(\d{4,10})\b", re.I)
MONTHS = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
DATE_RX = re.compile(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{1,2}\s+" + MONTHS + r"\.?,?\s+\d{4}\b", re.I)
AMOUNT_RX = [
    re.compile(r"(?:\u20b9|rs\.?|inr|\$|usd)\s*([\d,]+(?:\.\d{1,2})?)", re.I),
    re.compile(r"\b(?:total|amount|paid|price)\b\s*(?:due|paid)?\s*[:=-]?\s*(?:\u20b9|rs\.?|inr|\$)?\s*([\d,]+(?:\.\d{1,2})?)", re.I),
]
ERROR_RX = re.compile(r"\b(?:ERR(?:OR)?[-_ ]?\d{3,5}|E-?\d{3,5}|0x[0-9A-Fa-f]{4,8})\b", re.I)
PRODUCT_LINE_RX = re.compile(r"(?im)^\s*(?:product|item)\s*[:\-]\s*(.+)$")
KEYS = ("order_id", "date", "amount", "product", "error_code")


def load_products():
    try:
        cfg = yaml.safe_load(Path("config/config.yaml").read_text(encoding="utf-8-sig"))
        return list(cfg["tickets"]["products"])
    except Exception:
        return []


def _norm_date(text):
    cleaned = text.replace(".", "").replace(",", "").strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(cleaned, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _norm_amount(text):
    try:
        return f"{Decimal(text.replace(',', '')):.2f}"
    except (InvalidOperation, ValueError):
        return None


def _add(items, value):
    if value and value not in items:
        items.append(value)


def extract_fields(text, products=()):
    """Only what is really written in the text is returned. Missing values stay empty, nothing is guessed."""
    f = {k: [] for k in KEYS}
    for m in ORDER_RX.finditer(text):
        _add(f["order_id"], "ORD-" + m.group(1))
    if not f["order_id"]:
        for m in ORDER_WORD_RX.finditer(text):
            _add(f["order_id"], "ORD-" + m.group(1))
    for m in DATE_RX.finditer(text):
        _add(f["date"], _norm_date(m.group(0)))
    for rx in AMOUNT_RX:
        for m in rx.finditer(text):
            _add(f["amount"], _norm_amount(m.group(1)))
    low = text.lower()
    for p in products:
        if p.lower() in low:
            _add(f["product"], p)
    for m in PRODUCT_LINE_RX.finditer(text):
        _add(f["product"], m.group(1).strip()[:60])
    for m in ERROR_RX.finditer(text):
        _add(f["error_code"], re.sub(r"\s+", " ", m.group(0).upper()))
    return f


def _same_key(field, value):
    value = value.lower()
    if field == "error_code":                       # "E-404", "E 404" and "e404" are the same code
        value = re.sub(r"[\s_-]", "", value)
        value = re.sub(r"^(error|err|e)(?=\d)", "", value)
    return value


def compare(message_fields, file_fields):
    """A conflict means the message and the file both state a value, and none of the values agree."""
    conflicts = []
    for key in KEYS:
        said, shown = message_fields[key], file_fields[key]
        if said and shown and not ({_same_key(key, v) for v in said} & {_same_key(key, v) for v in shown}):
            conflicts.append({"field": key, "message": ", ".join(said), "file": ", ".join(shown)})
    return conflicts


LABELS = {"order_id": "order ID", "date": "date", "amount": "amount", "product": "product", "error_code": "error code"}


def describe(fields):
    found = [f"{LABELS[k]} {', '.join(v)}" for k, v in fields.items() if v]
    missing = [LABELS[k] for k, v in fields.items() if not v]
    return found, missing
