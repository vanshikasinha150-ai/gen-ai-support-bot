
import json
import re
import yaml

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

from sklearn.feature_extraction.text import (
    TfidfVectorizer,
    ENGLISH_STOP_WORDS
)
from sklearn.metrics.pairwise import cosine_similarity

from policy_selector import select_policy


CFG = yaml.safe_load(
    Path("config/config.yaml").read_text(encoding="utf-8")
)

REGISTRY = Path("data/registry.json")

RANK = {
    "public": 0,
    "customer": 1,
    "agent": 2,
    "admin": 3
}

INJECTION = re.compile(
    r"ignore (all |any )?(previous|prior) instructions"
    r"|reveal .*(admin|secret|password)"
    r"|system prompt",
    re.I
)

HISTORICAL = re.compile(
    r"\b(was|were|previous|previously|earlier|before|old|last year)\b",
    re.I
)

REFUSE = (
    "Sorry, I could not find reliable information for this. "
    "Could you rephrase or share more details?"
)


def tokenize(text):
    """Normalize words and remove stop words."""

    if not isinstance(text, str):
        return []

    words = re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())

    normalized = []

    for word in words:
        # Basic plural normalization
        if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
            word = word[:-1]

        if word not in ENGLISH_STOP_WORDS:
            normalized.append(word)

    return normalized


def expand_query(query):
    """Expand common customer phrases into FAQ search terms."""

    expanded = query.lower()

    if re.search(
        r"\b(arriv\w*|deliver\w*|shipment|shipping|ship|courier|tracking|track|late|delay\w*)\b",
        expanded
    ):
        expanded += " shipping delivery tracking courier arrived delayed shipment"

    if re.search(r"\b(return|returns|pickup|exchange)\b", expanded):
        expanded += " returns return pickup exchange"

    if re.search(r"\b(refund|refunds|reimburse\w*|money back)\b", expanded):
        expanded += " refund refunds reimbursement money back"

    return expanded



def sanitize(text):
    """Remove unsafe instruction lines."""

    lines = text.splitlines()

    safe = [
        line for line in lines
        if not INJECTION.search(line)
    ]

    return "\n".join(safe).strip(), len(safe) != len(lines)



def parse_reference_date(value):
    """Convert date strings and datetime values into date objects."""

    if value is None:
        return date.today()

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if isinstance(value, str):
        try:
            # Supports YYYY-MM-DD and datetime ISO formats.
            return datetime.fromisoformat(
                value.replace("Z", "+00:00")
            ).date()
        except ValueError:
            raise ValueError(
                "Invalid date. Use YYYY-MM-DD or ISO datetime format."
            )

    raise TypeError("Invalid reference date type.")


def load_docs():
    """Load and normalize documents from registry.json."""

    if not REGISTRY.exists():
        return []

    data = json.loads(
        REGISTRY.read_text(encoding="utf-8")
    )

    # Support both dictionary and list registry formats
    if isinstance(data, dict):
        if "documents" in data:
            records = data["documents"]
        else:
            records = list(data.values())
    elif isinstance(data, list):
        records = data
    else:
        return []

    docs = []

    for item in records:
        if not isinstance(item, dict):
            continue

        item = item.copy()

        try:
            item["effective_date"] = parse_reference_date(
                item["effective_date"]
            )

            item["expiry_date"] = (
                parse_reference_date(item["expiry_date"])
                if item.get("expiry_date")
                else None
            )

            docs.append(SimpleNamespace(**item))

        except (KeyError, ValueError, TypeError):
            continue

    return docs



def retrieve(query, role="public", region="IN", as_of=None):
    """Retrieve the most relevant active policy document."""

    if not isinstance(query, str) or not tokenize(query):
        return {
            "clarify": "Could you tell me a bit more about what you need?"
        }

    if role not in RANK:
        return {"clarify": "Invalid access role."}

    if as_of is None and HISTORICAL.search(query):
        return {
            "clarify": (
                "Which date should I check? "
                "Please share it as YYYY-MM-DD."
            )
        }

    # 1. Load documents
    docs = load_docs()

    if not docs:
        return None

    # 2. Resolve reference date
    try:
        ref = parse_reference_date(as_of)
    except (ValueError, TypeError):
        return None

    # 3. Apply access and region filters
    pool = [
        d for d in docs
        if getattr(d, "access_level", None) in RANK
        and RANK[d.access_level] <= RANK[role]
        and getattr(d, "region", None) in (region, "global")
    ]

    if not pool:
        return None

    # 4. Group documents by document family
    groups = {}

    for doc in pool:
        groups.setdefault(doc.doc_id, []).append(doc)

    # 5. Select policy active on reference date
    chosen = []

    for group in groups.values():
        selected = select_policy(group, ref)

        if selected:
            chosen.append(selected)

    if not chosen:
        return None

    # 6. Sanitize documents
    valid = []

    for doc in chosen:
        clean_text, _ = sanitize(doc.body)

        if clean_text and tokenize(clean_text):
            valid.append((doc, clean_text))

    if not valid:
        return None

    # 7. Deduplicate identical evidence
    doc_priority = {
        "policy": 3,
        "faq": 2,
        "guide": 1,
        "product_doc": 0
    }

    unique_evidence = {}

    for doc, text in valid:
        normalized = " ".join(text.lower().split())
        existing = unique_evidence.get(normalized)

        if (
            existing is None
            or doc_priority.get(doc.doc_type, 0)
            > doc_priority.get(existing[0].doc_type, 0)
        ):
            unique_evidence[normalized] = (doc, text)

    valid = list(unique_evidence.values())

    chosen = [item[0] for item in valid]
    texts = [item[1] for item in valid]

    # 8. TF-IDF similarity search using title and body
    try:
        search_texts = [
            f"{doc.title} {doc.doc_type} {text}"
            for doc, text in valid
        ]

        vectorizer = TfidfVectorizer(
            tokenizer=tokenize,
            lowercase=False,
            token_pattern=None
        )

        document_vectors = vectorizer.fit_transform(search_texts)

        expanded_query = expand_query(query)
        query_vector = vectorizer.transform([expanded_query])

        similarities = cosine_similarity(
            query_vector,
            document_vectors
        )[0]

    except ValueError:
        return None

    # 9. Rank documents
    order = similarities.argsort()[::-1]

    if len(order) == 0:
        return None

    best = order[0]
    minimum = CFG["rag"]["min_similarity"]

    if similarities[best] < minimum:
        return None

    # 10. Handle ambiguous results
    if len(order) > 1:
        second = order[1]

        if (
            similarities[second] >= minimum
            and similarities[best] - similarities[second] < 0.1
        ):
            a = chosen[best].title
            b = chosen[second].title

            return {
                "clarify": (
                    f"Your question could be about '{a}' "
                    f"or '{b}'. Which one do you mean?"
                )
            }

    # 11. Return selected document
    doc = chosen[best]

    clean_text, flagged = sanitize(doc.body)

    cite = (
        f"[Source: {doc.title}, "
        f"v{doc.version}, "
        f"effective {doc.effective_date}]"
    )

    return {
        "doc": doc,
        "text": clean_text,
        "flagged": flagged,
        "cite": cite
    }


def answer(query, role="public", region="IN", as_of=None):
    """Generate an answer from retrieved policy documents."""

    hit = retrieve(query, role, region, as_of)

    if hit is None:
        return REFUSE

    if "clarify" in hit:
        return hit["clarify"]

    output = f"{hit['text']}\n{hit['cite']}"

    if hit["flagged"]:
        output += (
            "\n(Note: unsafe instruction found in this "
            "document was ignored.)"
        )

    return output


def check_claim(claim, role="public", region="IN", as_of=None):
    """
    Check a claim against retrieved policy evidence.

    Returns SUPPORTED, CONTRADICTED or UNSUPPORTED.
    """

    hit = retrieve(
        claim,
        role=role,
        region=region,
        as_of=as_of
    )

    if hit is None or "clarify" in hit:
        return "UNSUPPORTED: no evidence found"

    claim_terms = {
        word for word in tokenize(claim)
        if not word.isdigit()
    }

    doc_terms = {
        word for word in tokenize(hit["text"])
        if not word.isdigit()
    }

    if not claim_terms:
        return "UNSUPPORTED: no meaningful claim terms"

    # Detect conflicting numeric values with matching units
    number_pattern = re.compile(
        r"\b(\d+)\s*(days?|weeks?|months?|years?)\b",
        re.I
    )

    claim_numbers = {
        (int(n), u.lower().rstrip("s"))
        for n, u in number_pattern.findall(claim)
    }

    doc_numbers = {
        (int(n), u.lower().rstrip("s"))
        for n, u in number_pattern.findall(hit["text"])
    }

    for claim_number, claim_unit in claim_numbers:
        for doc_number, doc_unit in doc_numbers:
            if (
                claim_unit == doc_unit
                and claim_number != doc_number
            ):
                return (
                    "CONTRADICTED: numeric value does not "
                    "match the policy evidence"
                )

    # Check meaningful word overlap
    overlap = claim_terms.intersection(doc_terms)

    coverage = len(overlap) / len(claim_terms)

    if coverage >= 0.8:
        return "SUPPORTED"

    return "UNSUPPORTED: insufficient matching evidence"
