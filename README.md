# QwenNews

Local AI news reporting system. **Milestone 0** implements the news ingestion foundation only: source adapters, normalization, polite content extraction, deduplication, SQLite storage, and a CLI.

Later milestones will add local Qwen3 ranking/summarization via Ollama, hourly deltas, daily briefings, and a dashboard. Those are intentionally out of scope for M0.

## Requirements

- Python 3.11+ (developed/verified with 3.15)
- Network access for live collection (unit tests use mocks; no live HTTP)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
cp .env.example .env   # optional
```

## CLI

```bash
python -m qwennews init-db
python -m qwennews collect
python -m qwennews collect --source hackernews
python -m qwennews collect --source openai --source deepmind --no-extract
python -m qwennews recent --hours 24
python -m qwennews stats
```

Configuration is via environment variables (see `.env.example`): database path, timeouts, per-source limits, concurrency, User-Agent, and source enablement. No API keys are required for public feeds.

## Architecture

See [docs/architecture.md](docs/architecture.md) and the M0 implementation record in [docs/milestones/m0.md](docs/milestones/m0.md).

```
Sources (HN API / RSS) → normalize → canonicalize/dedupe → SQLite
                                         ↓
                              polite article extraction (optional)
```

## Tests

```bash
pytest
ruff check qwennews tests
```

## License / use notes

- Respects `robots.txt` and does not bypass paywalls, auth, or anti-bot controls.
- Rejects local/private/unsafe URLs and unsafe redirects (SSRF protection).
- HN discussion comments are never treated as article body text.
