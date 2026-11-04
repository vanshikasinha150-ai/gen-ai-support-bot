import re

NEGATIVE_LABELS = {"negative", "frustrated", "sarcastic", "urgent"}

LEX = {
    "negative": [
        # English
        "bad", "worst", "terrible", "horrible", "awful", "disappointed", "disappointing", "unacceptable",
        "poor", "useless", "broken", "damaged", "complaint", "unhappy", "waste", "pathetic", "rude",
        "scam", "cheated", "not good", "not happy", "not great", "not satisfied", "not helpful", "never again",
        # Hinglish / Hindi
        "bakwas", "bekar", "ganda", "kharab", "bura", "dhokha", "bahut bura", "paisa waste",
        "\u0916\u0930\u093e\u092c", "\u092c\u0947\u0915\u093e\u0930", "\u0927\u094b\u0916\u093e",
        # Spanish / French
        "malo", "pesimo", "decepcionado", "inaceptable", "estafa", "mauvais", "nul", "decu", "arnaque", "inacceptable",
    ],
    "frustrated": [
        "frustrated", "frustrating", "fed up", "annoyed", "annoying", "irritated", "tired of", "again and again",
        "how many times", "still waiting", "no response", "nobody helps", "sick of", "waste of time",
        "third time", "pareshan", "tang aa gaya", "kitni baar", "baar baar", "koi jawab nahi",
        "\u092a\u0930\u0947\u0936\u093e\u0928", "harto", "cansado", "nadie responde", "marre", "enerve", "toujours pas",
    ],
    "urgent": [
        "urgent", "urgently", "asap", "immediately", "right now", "emergency", "as soon as possible",
        "critical", "today itself", "jaldi", "turant", "\u091c\u0932\u094d\u0926\u0940", "\u0924\u0941\u0930\u0902\u0924",
        "urgente", "ahora mismo", "inmediatamente", "tout de suite", "immediatement",
    ],
    "positive": [
        "thanks", "thank you", "great", "good", "happy", "love", "excellent", "amazing", "wonderful",
        "perfect", "awesome", "appreciate", "helpful", "shukriya", "dhanyavaad", "badhiya", "accha", "mast",
        "\u0927\u0928\u094d\u092f\u0935\u093e\u0926", "\u0936\u0941\u0915\u094d\u0930\u093f\u092f\u093e", "\u092c\u0922\u093c\u093f\u092f\u093e",
        "gracias", "excelente", "perfecto", "genial", "merci", "parfait", "super",
    ],
    "sarcasm": [
        "yeah right", "thanks for nothing", "thank you for nothing", "oh great", "just great", "love how",
        "nice job", "oh wow", "so helpful", "great service", "wonderful service", "brilliant service",
        "wah kya", "waah", "kya baat hai", "que maravilla",
    ],
    "context": [
        "again", "still", "another", "late", "delay", "delayed", "not delivered", "never", "nothing",
        "not working", "broken", "phir se", "dobara", "otra vez", "encore", "yet again",
    ],
    "resolution": [
        "resolved", "solved", "fixed", "works now", "working now", "got it", "received it", "issue is over",
        "theek ho gaya", "mil gaya",
    ],
}
RX = {k: [re.compile(r"(?<!\w)" + re.escape(p) + r"(?!\w)", re.I) for p in v] for k, v in LEX.items()}

RISK = {
    "account_compromise": [
        r"\bhack(ed|ing)?\b", r"compromised", r"unauthori[sz]ed (login|access|transaction|purchase|activity)",
        r"someone (else )?(logged|accessed|got into|used my)", r"account (was|got|has been) (stolen|accessed)",
        r"password (was )?changed (without|by someone)", r"account hack", r"hack ho", r"cuenta (hackeada|comprometida)",
    ],
    "duplicate_payment": [
        r"charged (me )?twice", r"double[- ]charged", r"paid twice", r"duplicate (payment|charge)",
        r"deducted twice", r"do baar (paise|paisa|charge|payment)", r"do baar .{0,20}kat", r"cobrado dos veces",
        r"d\u00e9bit\u00e9 deux fois", r"debite deux fois",
    ],
    "legal_threat": [
        r"legal (action|notice|case)", r"\blawyer\b", r"consumer (court|forum)", r"\bsue\b",
        r"take .{0,20}to court", r"\badvocate\b", r"police complaint", r"\babogado\b", r"\bavocat\b",
        "\u0915\u093e\u0928\u0942\u0928\u0940", "\u0935\u0915\u0940\u0932",
    ],
}
RISK_RX = {k: [re.compile(p, re.I) for p in v] for k, v in RISK.items()}

HINGLISH = {"hai", "nahi", "nahin", "mera", "meri", "mujhe", "kya", "bahut", "paisa", "paise", "aap", "hua",
            "kab", "abhi", "phir", "bakwas", "jaldi", "kyun", "raha", "rahi", "hain", "baar", "kat", "gaya"}
SPANISH = {"el", "la", "los", "que", "por", "pero", "muy", "mi", "gracias", "pedido", "cuenta", "hola", "una", "con"}
FRENCH = {"le", "les", "des", "une", "est", "pas", "mon", "merci", "commande", "compte", "je", "tres", "avec", "pour"}


def detect_language(text):
    if re.search(r"[\u0900-\u097F]", text):
        return "hi"
    words = set(re.findall(r"[a-z\u00e0-\u00ff]+", text.lower()))
    for lang, vocab in (("hi-Latn", HINGLISH), ("es", SPANISH), ("fr", FRENCH)):
        if len(words & vocab) >= 2:
            return lang
    return "en"


def find_risk(text):
    for kind, patterns in RISK_RX.items():
        if any(p.search(text) for p in patterns):
            return kind
    return None


def analyze(text, history=()):
    """history: list of (text, label) for earlier customer messages. Returns the sentiment result."""
    low = text.lower()
    hits = {k: sum(1 for rx in RX[k] if rx.search(low)) for k in RX}
    scores = {
        "negative": hits["negative"] * 1.0,
        "frustrated": hits["frustrated"] * 1.5,
        "urgent": hits["urgent"] * 2.0,
        "positive": hits["positive"] * 1.0,
        "sarcastic": hits["sarcasm"] * 2.0,
    }
    if text.count("!") >= 2:
        scores["frustrated"] += 1
    letters = [c for c in text if c.isalpha()]
    if len(letters) >= 12 and sum(c.isupper() for c in letters) / len(letters) > 0.6:
        scores["frustrated"] += 1

    resolved = hits["resolution"] > 0
    prev_negative = bool(history) and history[-1][1] in NEGATIVE_LABELS
    context_only = False
    if scores["positive"] > 0 and not resolved:
        if hits["context"] > 0:                       # praise next to a bad event: "great, late again"
            scores["sarcastic"] += 2.5
        elif prev_negative:                           # praise right after a complaint (uses history)
            scores["sarcastic"] += 2.0
            context_only = True
    if scores["sarcastic"] >= 2.0:
        scores["positive"] = 0.0                      # the praise was ironic

    top = max(scores.values())
    if top < 1.0:
        label, conf = "neutral", 0.6
    else:
        label = next(k for k in ("urgent", "sarcastic", "frustrated", "negative", "positive") if scores[k] == top)
        second = sorted(scores.values())[-2]
        conf = max(0.5, min(0.95, 0.5 + 0.1 * top + 0.1 * (top - second)))
        if label == "sarcastic" and context_only:
            conf = min(conf, 0.6)
    return {
        "label": label,
        "confidence": round(conf, 2),
        "scores": scores,
        "urgent": hits["urgent"] > 0,
        "high_risk": find_risk(low),
        "language": detect_language(text),
    }


TONE = {
    "urgent": "I understand this is urgent, and I am treating it as a priority.",
    "frustrated": "I am sorry for the repeated trouble, and I understand how frustrating this is.",
    "negative": "I am sorry about this experience, and I will do my best to help.",
    "sarcastic": "I can tell this has been a frustrating experience, and I want to put it right.",
    "positive": "Glad to hear that!",
    "neutral": "",
}


def tone_prefix(result):
    prefix = TONE[result["label"]]
    if result["high_risk"]:
        prefix = (prefix + " " if prefix else "") + "Thank you for flagging this. It has been passed to our specialist team."
    return prefix


def respond(policy_answer, result):
    """Only the tone changes. The business answer is passed through untouched."""
    prefix = tone_prefix(result)
    return f"{prefix} {policy_answer}".strip()
