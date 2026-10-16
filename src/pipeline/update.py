import sys, json, shutil, hashlib
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, "src/ingestion")
sys.path.insert(0, "src/rag")
import ingest, retriever
from schema import DocMetadata, validate

RAW, QUAR = Path("data/raw"), Path("data/quarantine")
LIVE = Path("data/registry.json")          # the registry the chatbot reads
VERSIONS = Path("data/versions")           # v0001.json, v0002.json, ... + state.json
STATE = VERSIONS / "state.json"
GOLDEN = Path("tests/golden.json")         # fixed test questions for the quality gate


def load_json(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def save_state(state):
    STATE.write_text(json.dumps(state, indent=2))


def same_meta(meta, stored):
    keys = ["doc_id", "title", "doc_type", "version", "product", "region",
            "access_level", "effective_date", "expiry_date"]
    return all(str(meta.get(k)) == str(stored.get(k)) for k in keys)


def build_candidate(live):
    """Process only new or modified documents; skip unchanged and duplicate ones."""
    cand = dict(live)
    hashes = {v["content_hash"]: k for k, v in live.items()}
    changes = []
    for f in sorted(RAW.glob("*.md")):
        try:
            meta, body = ingest.parse(f)
            h = hashlib.sha256(body.encode()).hexdigest()
            if f.name in live and live[f.name]["content_hash"] == h and same_meta(meta, live[f.name]):
                continue                                   # unchanged
            if h in hashes and hashes[h] != f.name:
                print(f"DUPLICATE skipped: {f.name}")
                continue
            m = DocMetadata(
                doc_id=meta["doc_id"], title=meta["title"], doc_type=meta["doc_type"],
                version=str(meta["version"]), product=meta["product"], region=meta["region"],
                access_level=meta["access_level"], effective_date=meta["effective_date"],
                expiry_date=meta.get("expiry_date"), content_hash=h, source_path=str(f))
            validate(m)
            label = "MODIFIED" if f.name in live else "NEW"
            cand[f.name] = {**meta, "content_hash": h, "body": body}
            hashes[h] = f.name
            changes.append(f"{label}: {f.name}")
        except Exception as e:
            QUAR.mkdir(exist_ok=True)
            shutil.move(str(f), QUAR / f.name)
            print(f"QUARANTINED: {f.name} ({e})")
    return cand, changes


def evaluate(registry_path):
    """Quality gate: run golden questions against a registry. Returns (accuracy, grounding)."""
    old = retriever.REGISTRY
    retriever.REGISTRY = Path(registry_path)
    try:
        cases = json.loads(GOLDEN.read_text())
        ok = grounded = 0
        for c in cases:
            as_of = date.fromisoformat(c["as_of"]) if c.get("as_of") else None
            ans = retriever.answer(c["q"], role=c.get("role", "public"), as_of=as_of)
            ok += c["expect"] in ans
            grounded += c.get("source", "") in ans
        return ok / len(cases), grounded / len(cases)
    finally:
        retriever.REGISTRY = old


def activate(version, state):
    shutil.copy(VERSIONS / f"{version}.json", LIVE)
    state["active"] = version
    state["history"].append(version)


def next_version():
    return f"v{len(list(VERSIONS.glob('v*.json'))) + 1:04d}"


def log(state, version, status, acc, grd):
    state["log"].append({"version": version, "status": status, "accuracy": acc,
                         "grounding": grd, "time": datetime.now().isoformat(timespec="seconds")})


def run_update():
    VERSIONS.mkdir(parents=True, exist_ok=True)
    state = load_json(STATE, {"active": None, "history": [], "log": []})
    live = load_json(LIVE, {})

    if state["active"] is None and live:                 # first run: current registry = baseline
        v = next_version()
        shutil.copy(LIVE, VERSIONS / f"{v}.json")
        activate(v, state)
        log(state, v, "BASELINE", *evaluate(VERSIONS / f"{v}.json"))
        print(f"Baseline saved as {v}")

    cand, changes = build_candidate(live)
    if not changes:
        print("No new or modified documents. Nothing to do.")
        save_state(state)
        return
    for c in changes:
        print(c)

    v = next_version()
    (VERSIONS / f"{v}.json").write_text(json.dumps(cand, indent=2, default=str))
    acc, grd = evaluate(VERSIONS / f"{v}.json")
    base_acc, base_grd = (0.0, 0.0)
    if state["active"]:
        base_acc, base_grd = evaluate(VERSIONS / f"{state['active']}.json")
    print(f"Quality gate {v}: accuracy {acc:.0%} (current {base_acc:.0%}), "
          f"grounding {grd:.0%} (current {base_grd:.0%})")

    if acc < base_acc or grd < base_grd:
        print(f"REJECTED {v}: quality dropped. Live version unchanged ({state['active']}).")
        log(state, v, "REJECTED", acc, grd)
    else:
        activate(v, state)
        log(state, v, "ACTIVATED", acc, grd)
        print(f"ACTIVATED {v}")
    save_state(state)


def rollback():
    state = load_json(STATE, {"active": None, "history": [], "log": []})
    if len(state["history"]) < 2:
        print("No earlier version to roll back to.")
        return
    bad = state["history"].pop()
    prev = state["history"][-1]
    shutil.copy(VERSIONS / f"{prev}.json", LIVE)
    state["active"] = prev
    state["log"].append({"version": bad, "status": f"ROLLED BACK to {prev}",
                         "time": datetime.now().isoformat(timespec="seconds")})
    save_state(state)
    print(f"Rolled back {bad} -> {prev}")


def status():
    state = load_json(STATE, {"active": None, "history": [], "log": []})
    print(f"Active version: {state['active']}")
    for e in state["log"]:
        extra = f" acc={e['accuracy']:.0%} grounding={e['grounding']:.0%}" if "accuracy" in e else ""
        print(f"  {e['time']}  {e['version']}  {e['status']}{extra}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    {"run": run_update, "rollback": rollback, "status": status}[cmd]()