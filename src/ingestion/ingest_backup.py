import hashlib, json, shutil, yaml
from pathlib import Path
from schema import DocMetadata, validate

RAW, QUAR = Path("data/raw"), Path("data/quarantine")
REGISTRY = Path("data/registry.json")

def parse(path):
    text = path.read_text(encoding="utf-8")
    _, front, body = text.split("---", 2)
    return yaml.safe_load(front), body.strip()

def run():
    registry = json.loads(REGISTRY.read_text()) if REGISTRY.exists() else {}
    seen = {v["content_hash"] for v in registry.values()}
    for f in sorted(RAW.glob("*.md")):
        try:
            meta, body = parse(f)
            h = hashlib.sha256(body.encode()).hexdigest()
            if h in seen:
                print(f"DUPLICATE skipped: {f.name}")
                continue
            m = DocMetadata(
                doc_id=meta["doc_id"], title=meta["title"], doc_type=meta["doc_type"],
                version=str(meta["version"]), product=meta["product"], region=meta["region"],
                access_level=meta["access_level"],
                effective_date=meta["effective_date"],
                expiry_date=meta.get("expiry_date"),
                content_hash=h, source_path=str(f))
            validate(m)
            registry[f.name] = {**meta, "content_hash": h, "body": body}
            seen.add(h)
            print(f"INGESTED: {f.name}")
        except Exception as e:
            QUAR.mkdir(exist_ok=True)
            shutil.move(str(f), QUAR / f.name)
            print(f"QUARANTINED: {f.name} ({e})")
    REGISTRY.write_text(json.dumps(registry, indent=2, default=str))

if __name__ == "__main__":
    run()