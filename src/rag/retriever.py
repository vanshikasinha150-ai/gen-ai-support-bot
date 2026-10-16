import json, re, yaml
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
from sklearn.metrics.pairwise import cosine_similarity
from policy_selector import select_policy

CFG = yaml.safe_load(Path("config/config.yaml").read_text())
REGISTRY = Path("data/registry.json")
RANK = {"public": 0, "customer": 1, "agent": 2, "admin": 3}
INJECTION = re.compile(
    r"ignore (all |any )?(previous|prior) instructions|reveal .*(admin|secret|password)|system prompt",
    re.I)
REFUSE = "Sorry, I could not find reliable information for this. Could you rephrase or share more details?"

def tokenize(s):
    words = re.findall(r"[a-z0-9]+", s.lower())
    return [w[:-1] if len(w) > 3 and w.endswith("s") else w
            for w in words if w not in ENGLISH_STOP_WORDS]

def load_docs():
    reg = json.loads(REGISTRY.read_text())
    docs = []
    for name, m in reg.items():
        exp = m.get("expiry_date")
        docs.append(SimpleNamespace(
            file=name, doc_id=m["doc_id"], title=m["title"], version=str(m["version"]),
            region=m["region"], product=m["product"], access_level=m["access_level"],
            effective_date=date.fromisoformat(str(m["effective_date"])),
            expiry_date=date.fromisoformat(str(exp)) if exp else None,
            body=m["body"]))
    return docs

def sanitize(text):
    lines = text.splitlines()
    safe = [l for l in lines if not INJECTION.search(l)]
    return "\n".join(safe).strip(), len(safe) != len(lines)

HISTORICAL = re.compile(r"\b(was|were|previous|previously|earlier|before|old|last year)\b", re.I)

def retrieve(query, role="public", region="IN", as_of=None):
    """Returns {"doc","text","flagged","cite"}, or {"clarify": msg}, or None."""
    if not tokenize(query):
        return {"clarify": "Could you tell me a bit more about what you need?"}
    if as_of is None and HISTORICAL.search(query):
        return {"clarify": "Which date should I check? Please share it as YYYY-MM-DD."}
    ref = as_of or date.today()
    # 1. metadata filter first: access + region
    pool = [d for d in load_docs()
            if RANK[d.access_level] <= RANK[role] and d.region in (region, "global")]
    # 2. per document family, pick the policy active on the reference date
    groups = {}
    for d in pool:
        groups.setdefault(d.doc_id, []).append(d)
    chosen = [s for g in groups.values() if (s := select_policy(g, ref))]
    if not chosen:
        return None
    # 3. similarity search on the filtered docs only
    texts = [sanitize(d.body)[0] for d in chosen]
    vec = TfidfVectorizer(tokenizer=tokenize, lowercase=False, token_pattern=None).fit(texts)
    sims = cosine_similarity(vec.transform([query]), vec.transform(texts))[0]
    order = sims.argsort()[::-1]
    best = order[0]
    if sims[best] < CFG["rag"]["min_similarity"]:
        return None
    # 4. ambiguous if the runner-up is almost as good
    if len(order) > 1 and sims[order[1]] >= CFG["rag"]["min_similarity"] \
            and sims[best] - sims[order[1]] < 0.1:
        a, b = chosen[best].title, chosen[order[1]].title
        return {"clarify": f"Your question could be about '{a}' or '{b}'. Which one do you mean?"}
    d = chosen[best]
    text, flagged = sanitize(d.body)
    cite = f"[Source: {d.title}, v{d.version}, effective {d.effective_date}]"
    return {"doc": d, "text": text, "flagged": flagged, "cite": cite}

def answer(query, role="public", region="IN", as_of=None):
    hit = retrieve(query, role, region, as_of)
    if hit is None:
        return REFUSE
    if "clarify" in hit:
        return hit["clarify"]
    out = f"{hit['text']}\n{hit['cite']}"
    if hit["flagged"]:
        out += "\n(Note: unsafe instruction found in this document was ignored.)"
    return out

def check_claim(claim, role="public", region="IN", as_of=None):
    """Checks a statement against the knowledge base: SUPPORTED / CONTRADICTED / UNSUPPORTED."""
    hit = retrieve(claim, role, region, as_of)
    if hit is None or "clarify" in hit:
        return "UNSUPPORTED: no evidence found"
    doc_nums = set(re.findall(r"\d+", hit["text"]))
    claim_nums = set(re.findall(r"\d+", claim))
    if claim_nums - doc_nums:
        return f"CONTRADICTED: {hit['text']} {hit['cite']}"
    return f"SUPPORTED {hit['cite']}"

if __name__ == "__main__":
    tests = [
        ("What is the refund window?", {}),
        ("What was the refund window?", {"as_of": date(2026, 3, 1)}),
        ("Who are the escalation contacts?", {"role": "public"}),
        ("Who are the escalation contacts?", {"role": "admin"}),
        ("How do I reset my device?", {}),
        ("Do you offer laptop warranty?", {}),
        ("What was the refund window?", {}),
        ("?", {}),
    ]
    for q, kw in tests:
        print(f"\nQ: {q} {kw}\nA: {answer(q, **kw)}")
    print("\n--- claim checks ---")
    for c in ["Refunds are allowed within 14 days of delivery.",
              "Refunds are allowed within 30 days of delivery.",
              "We offer free laptop insurance."]:
        print(f"{c}\n -> {check_claim(c)}")