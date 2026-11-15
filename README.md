# QwenNews

Local AI news reporting system.

- **M0:** news ingestion (HN + AI lab/blog feeds → SQLite)
- **M1:** local Qwen3 4B analysis via Ollama + on-demand Markdown briefing
- **M2:** story memory, conservative near-dupe linking, improved ranking, hourly/daily delta reports
- **M3:** automated hourly/daily orchestration, mode-specific report state, LaunchAgent + notifications
- **M4:** local read-only news dashboard (FastAPI + Next.js)

No cloud inference, model fine-tuning, or mobile app.

## Requirements

- Python 3.11+ (developed/verified with 3.15)
- Node.js 20+ for the dashboard UI
- Network access for live collection (unit tests mock HTTP)
- For analysis: local [Ollama](https://ollama.com) with a Qwen3 4B model installed (this environment uses `qwen3:4b`)
- macOS for LaunchAgent scheduling and optional notifications

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
cp .env.example .env   # optional

cd dashboard && npm install && cd ..
```

## CLI

```bash
python -m qwennews init-db
python -m qwennews collect
python -m qwennews recent --hours 24
python -m qwennews stats

# Analysis + reports
python -m qwennews analyze --limit 10
python -m qwennews sync-stories
python -m qwennews report --mode hourly --limit 10
python -m qwennews report --mode daily --limit 15

# Automation
python -m qwennews run-hourly --max-analyze 5
python -m qwennews run-daily
python -m qwennews status

# Dashboard API (127.0.0.1 only)
python -m qwennews dashboard-api --port 8765
```

### Local dashboard

```bash
# Terminal A
python -m qwennews dashboard-api --host 127.0.0.1 --port 8765

# Terminal B
cd dashboard
npm run dev   # http://127.0.0.1:3000
```

Details: [docs/milestones/m4.md](docs/milestones/m4.md).

### Hourly / daily scheduling (macOS)

```bash
python scripts/generate_launchagent.py --both --time 07:00
```

Install / enable / disable: [docs/milestones/m3.md](docs/milestones/m3.md).

## Architecture

See [docs/architecture.md](docs/architecture.md) and `docs/milestones/`.

```
Sources → SQLite → story memory → Ollama analysis → reports
                                      ↓
                         LaunchAgents (hourly/daily)
                                      ↓
                         Dashboard API (read-only) → Next.js UI
```

## Tests

```bash
pytest
ruff check qwennews tests scripts
cd dashboard && npm run typecheck && npm test && npm run lint && npm run build
```

## License / use notes

- Respects `robots.txt` and does not bypass paywalls, auth, or anti-bot controls.
- Rejects local/private/unsafe URLs and unsafe redirects (SSRF protection).
- HN discussion comments are never treated as article body text.
- Article bodies are treated as untrusted data in analysis prompts and the dashboard.
