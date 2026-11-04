import re

from ticket_common import load_cfg, working_hours_between

NEGATIVE = ["angry", "worst", "terrible", "unacceptable", "disappointed", "frustrated", "furious",
            "horrible", "useless", "fed up", "ridiculous", "pathetic"]
RISK = [r"legal action", r"lawyer", r"consumer court", r"\bsue\b", r"fraud", r"unauthori[sz]ed", r"hack"]
IMPACT_WORDS = [r"\ball\b", r"everyone", r"multiple orders", r"bulk", r"my business", r"whole team"]
AMOUNT = re.compile(r"(?i)(?:\u20b9|rs\.?|inr)\s*([\d,]+)")


def sentiment_score(text):
    hits = sum(word in text.lower() for word in NEGATIVE)
    return min(5.0, 1.5 * hits + 0.5 * text.count("!"))


def severity_score(category, text, cfg):
    if any(re.search(p, text.lower()) for p in RISK):
        return 5.0
    return float(cfg["severity"].get(category, 1))


def impact_score(text, tier):
    score = 4.0 if tier == "premium" else 1.0
    if any(re.search(p, text.lower()) for p in IMPACT_WORDS):
        score = max(score, 4.0)
    for m in AMOUNT.finditer(text):
        amount = int((m.group(1).replace(",", "") or "0"))
        score = max(score, 4.0 if amount >= 5000 else 2.5 if amount >= 1000 else 1.0)
    return score


def waiting_score(created, now, cfg):
    waited = working_hours_between(created, now, cfg)
    return min(5.0, 5.0 * waited / cfg["waiting_scale_hours"])


def compute(category, text, created, now, tier="standard"):
    cfg = load_cfg()
    parts = {
        "severity": severity_score(category, text, cfg),
        "sentiment": sentiment_score(text),
        "waiting": waiting_score(created, now, cfg),
        "impact": impact_score(text, tier),
    }
    score = sum(cfg["weights"][k] * v for k, v in parts.items())
    th = cfg["thresholds"]
    level = "P1" if score >= th["P1"] else "P2" if score >= th["P2"] else "P3" if score >= th["P3"] else "P4"
    if parts["severity"] >= 5:          # high-risk issues are always P1
        level = "P1"
    return level, round(score, 2), parts
