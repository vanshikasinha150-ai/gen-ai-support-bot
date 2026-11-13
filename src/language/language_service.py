
import re
from typing import Callable, Optional

SUPPORTED_LANGUAGES = {
    "en": "English",
    "hi": "Hindi",
    "kn": "Kannada",
    "ta": "Tamil",
}

LANGUAGE_PATTERNS = {
    "hi": re.compile(r"[\u0900-\u097F]"),
    "kn": re.compile(r"[\u0C80-\u0CFF]"),
    "ta": re.compile(r"[\u0B80-\u0BFF]"),
}

HINGLISH_WORDS = {
    "hai", "hain", "nahi", "nahin", "mujhe", "mera",
    "meri", "aap", "kya", "kaise", "bahut", "paisa",
    "paise", "chahiye", "karna", "kyun", "abhi",
    "gaya", "raha", "rahi", "theek"
}

def detect_language(text: str) -> dict:
    """Detect language, mixed-language messages and confidence."""

    if not isinstance(text, str) or not text.strip():
        return {
            "language": None,
            "languages": [],
            "confidence": 0.0,
            "needs_clarification": True
        }

    detected = []

    for lang, pattern in LANGUAGE_PATTERNS.items():
        if pattern.search(text):
            detected.append(lang)

    words = re.findall(r"[a-zA-Z]+", text.lower())
    hinglish_count = sum(word in HINGLISH_WORDS for word in words)

    if hinglish_count >= 2:
        detected.append("hi")

    latin_words = len(words)
    script_chars = sum(
        1 for char in text
        if "\u0900" <= char <= "\u097F"
        or "\u0B80" <= char <= "\u0BFF"
        or "\u0C80" <= char <= "\u0CFF"
    )

    if len(set(detected)) > 1:
        language = "mixed"
        confidence = 0.85
    elif detected:
        language = detected[0]
        confidence = 0.95 if script_chars else 0.80
    elif latin_words >= 3:
        language = "en"
        confidence = 0.75
    else:
        language = None
        confidence = 0.30

    return {
        "language": language,
        "languages": sorted(set(detected)) if detected else (
            ["en"] if language == "en" else []
        ),
        "confidence": confidence,
        "needs_clarification": confidence < 0.60
    }


NAME_RX = re.compile(
    r"(?i:my name is|i am|i'm|this is|mera naam|me llamo|je m'appelle)\s+([A-Z][^\s.,!?]*)"
)


def translate_text(
    text: str,
    source: str,
    target: str,
    translator: Optional[Callable] = None,
    protected_terms=()
) -> str:
    """
    Translate using an injected translation engine.

    Protects order IDs, dates, amounts and product codes.
    Does not pretend to translate when no engine is configured.
    """

    if source not in SUPPORTED_LANGUAGES:
        raise ValueError("Unsupported source language")

    if target not in SUPPORTED_LANGUAGES:
        raise ValueError("Unsupported target language")

    if not isinstance(text, str):
        raise TypeError("Text must be a string")

    if source == target or not text.strip():
        return text

    if translator is None:
        raise RuntimeError("Translation engine is not configured")

    protected = re.compile(
        r"(?<![\w-])(?:ORD[-_]?\d+|[A-Z]{2,5}-?\d{2,}|E-?\d{3,5}|"
        r"\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
        r"(?:\u20b9|Rs\.?|INR|\$)\s?[\d,]+(?:\.\d{1,2})?)(?![\w-])"
    )

    values = []
    terms = list(protected_terms) + NAME_RX.findall(text)

    def save(match):
        token = f"ZXQPROTECT{len(values)}QXZ"
        values.append(match.group(0))
        return token

    text = protected.sub(save, text)

    for term in sorted(terms, key=len, reverse=True):
        if term and term in text:
            token = f"ZXQPROTECT{len(values)}QXZ"
            text = text.replace(term, token)
            values.append(term)

    result = translator(text, source, target)

    if not isinstance(result, str):
        raise ValueError("Translation engine returned invalid output")

    for index, value in enumerate(values):
        token = f"ZXQPROTECT{index}QXZ"

        if token not in result:
            raise ValueError("Translation engine modified protected data")

        result = result.replace(token, value)

    return result


def process_message(text: str) -> dict:
    """Analyze an incoming customer message."""

    result = detect_language(text)

    if result["needs_clarification"]:
        result["message"] = (
            "Please clarify your preferred language or rephrase your message."
        )
    else:
        result["message"] = None

    return result
