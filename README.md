# Gen AI Customer Service Bot

Internship extension of my training project (Real Time Gen AI Customer Service Bot).
Tasks: knowledge-base update pipeline, multimodal analysis, ticketing, RAG assistant,
sentiment and escalation, multilingual sessions.

## Status
| Task | Status |
|---|---|
| 4. RAG knowledge assistant | Done (core) |
| 1. Knowledge-base update pipeline | In progress (versioning, quality gate, rollback done) |
| 2, 3, 5, 6 | Planned |

## Project structure
- `config/config.yaml`: thresholds, roles, session settings
- `src/ingestion/`: metadata schema and ingestion (hashing, duplicate detection, quarantine)
- `src/rag/`: policy selector, retriever, citations, injection sanitising
- `src/pipeline/`: update pipeline (new/modified detection, versions, quality gate, rollback)
- `data/raw/`: sample documents (conflicting, expired, future-dated, restricted, duplicate, injected)
- `tests/`: automated tests and golden questions for the quality gate

## How to run
```
pip install pyyaml scikit-learn pytest
python src/ingestion/ingest.py
python src/rag/retriever.py
python src/pipeline/update.py run
python src/pipeline/update.py rollback
python src/pipeline/update.py status
python -m pytest tests -v
```

## RAG behaviour
- Metadata filter first (access level, region), then the policy active on the reference date
- Future-dated and expired policies are ignored for current questions; historical dates supported
- Every answer carries a source citation; the bot refuses or asks for clarification when evidence is missing
- Prompt-injection lines inside documents are removed; unsupported claims are detected

## Update pipeline behaviour
- Processes only new or modified documents; duplicates are skipped, invalid files quarantined
- Every update is saved as a numbered version
- A quality gate (accuracy and grounding on fixed questions) rejects updates that reduce quality
- Rollback restores the previous version