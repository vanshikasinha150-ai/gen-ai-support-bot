
import hashlib
import json
import shutil
import yaml

from pathlib import Path
from schema import DocMetadata, validate


RAW = Path("data/raw")
QUAR = Path("data/quarantine")
REGISTRY = Path("data/registry.json")


def parse(path):
    text = path.read_text(encoding="utf-8")

    parts = text.split("---", 2)

    if len(parts) != 3 or parts[0].strip():
        raise ValueError("Invalid YAML frontmatter")

    meta = yaml.safe_load(parts[1])
    body = parts[2].strip()

    if not isinstance(meta, dict):
        raise ValueError("Invalid document metadata")

    if not body:
        raise ValueError("Document body is empty")

    return meta, body


def get_content_hash(body):
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def get_identity(record):
    return (
        str(record.get("doc_id", "")),
        str(record.get("version", "")),
        str(record.get("product", "")),
        str(record.get("region", ""))
    )


def save_registry(registry):
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)

    temp_file = REGISTRY.with_name("registry.tmp")

    temp_file.write_text(
        json.dumps(registry, indent=2, default=str),
        encoding="utf-8"
    )

    temp_file.replace(REGISTRY)


def run():
    registry = (
        json.loads(REGISTRY.read_text(encoding="utf-8"))
        if REGISTRY.exists()
        else {}
    )

    if not isinstance(registry, dict):
        raise ValueError("Registry must contain a JSON object")

    for file_path in sorted(RAW.glob("*.md")):
        try:
            meta, body = parse(file_path)

            content_hash = get_content_hash(body)
            identity = get_identity(meta)

            if not all(identity):
                raise ValueError("Missing document identity fields")

            existing = [
                (name, record)
                for name, record in registry.items()
                if get_identity(record) == identity
            ]

            if existing:
                existing_hashes = {
                    str(record.get("content_hash", "")).lower()
                    for _, record in existing
                }

                if content_hash.lower() in existing_hashes:
                    print(f"DUPLICATE skipped: {file_path.name}")
                    continue

                print(
                    f"CONFLICT: {file_path.name} "
                    f"has an existing doc_id/version with different content"
                )
                continue

            if file_path.name in registry:
                print(
                    f"CONFLICT: Registry key already exists: "
                    f"{file_path.name}"
                )
                continue

            metadata = DocMetadata(
                doc_id=meta["doc_id"],
                title=meta["title"],
                doc_type=meta["doc_type"],
                version=str(meta["version"]),
                product=meta["product"],
                region=meta["region"],
                access_level=meta["access_level"],
                effective_date=meta["effective_date"],
                expiry_date=meta.get("expiry_date"),
                content_hash=content_hash,
                source_path=str(file_path)
            )

            validate(metadata)

            registry[file_path.name] = {
                **meta,
                "version": str(meta["version"]),
                "content_hash": content_hash,
                "body": body
            }

            print(f"INGESTED: {file_path.name}")

        except Exception as error:
            QUAR.mkdir(parents=True, exist_ok=True)

            destination = QUAR / file_path.name

            if destination.exists():
                print(
                    f"QUARANTINE ERROR: {file_path.name} "
                    f"already exists in quarantine: {error}"
                )
                continue

            shutil.move(str(file_path), str(destination))

            print(
                f"QUARANTINED: {file_path.name} ({error})"
            )

    save_registry(registry)


if __name__ == "__main__":
    run()
