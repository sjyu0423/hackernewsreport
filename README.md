# QwenNews

Local AI news reporting system.

- **M0:** news ingestion (HN + AI lab/blog feeds → SQLite)
- **M1:** local Qwen3 4B analysis via Ollama + on-demand Markdown briefing
- **M2:** story memory, conservative near-dupe linking, improved ranking, hourly/daily delta reports

Background scheduling, notifications, and a dashboard remain out of scope.

## Requirements

- Python 3.11+ (developed/verified with 3.15)
- Network access for live collection (unit tests mock HTTP)
- For analysis: local [Ollama](https://ollama.com) with a Qwen3 4B model installed (this environment uses `qwen3:4b`)

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
python -m qwennews recent --hours 24
python -m qwennews stats

# M1 — local analysis + on-demand briefing
python -m qwennews analyze --limit 10
python -m qwennews report --mode ondemand --hours 24 --limit 10

# M2 — story memory + delta reports
python -m qwennews sync-stories
python -m qwennews report --mode hourly --limit 10
python -m qwennews report --mode daily --limit 15
```

Configuration is via environment variables (see `.env.example`). No API keys are required for public feeds. Analysis uses only the configured local Ollama endpoint (no cloud fallback).

## Architecture

See [docs/architecture.md](docs/architecture.md), [docs/milestones/m0.md](docs/milestones/m0.md), and [docs/milestones/m1.md](docs/milestones/m1.md).

```
Sources → normalize/dedupe → SQLite → (optional) extract text
                                      ↓
                         Ollama qwen3:4b structured analysis (cached)
                                      ↓
                         deterministic Markdown briefing
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
- Article bodies are treated as untrusted data in analysis prompts.
