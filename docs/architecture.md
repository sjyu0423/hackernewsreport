# QwenNews Architecture (M0–M4.2)

## Goals

M0 establishes a durable ingestion pipeline:

1. Pull stories from verified public sources.
2. Normalize into a shared article model.
3. Deduplicate by canonical URL.
4. Optionally extract article text when allowed.
5. Persist articles, source sightings, and collection-run metrics in SQLite.
6. Expose the workflow through a small CLI.

M1 adds local analysis:

7. Call Ollama `/api/chat` with the installed Qwen3 4B model (no cloud fallback).
8. Validate structured JSON with Pydantic and cache by article/content/model/config.
9. Render an on-demand Markdown briefing with deterministic ranking templates.

M2 adds durable story memory and delta reporting:

10. Link articles into developing stories with conservative near-duplicate detection.
11. Classify NEW_STORY / NEW_SOURCE_SAME_STORY / MEANINGFUL_UPDATE / UNCHANGED.
12. Rank with category priorities + capped HN signal + diversity limits.
13. Emit hourly deltas and daily digests with independent watermarks.

M3 adds Mac mini automation:

14. Orchestrate `collect → sync → analyze → report` via `run-hourly` / `run-daily`.
15. Mode-specific story report state + crash-safe watermarks (schema v5).
16. Single-instance locking so hourly and daily never run Qwen concurrently.
17. LaunchAgent templates for hourly + daily (install is opt-in).
18. Optional macOS notifications that never invalidate persisted reports.

M4 adds a local dashboard:

19. FastAPI read-only API bound to `127.0.0.1` over SQLite `mode=ro`.
20. Next.js editorial UI for Today / Hourly / Stories / History / Status.
21. No new inference; no LaunchAgent changes from the dashboard path.

M4.1 polishes the product surface:

22. One-command localhost launcher (`qwennews dashboard` / `scripts/run_dashboard.py`) for API + Next.
23. Safe Markdown rendering (sanitize + http(s)-only links); clearer generation vs publication times.
24. Explicit operational verification of LaunchAgent schedules (do not claim timer success without `runs` / logs).

M4.2 production reliability:

25. Canonical production DB `data/live_m0.db` (override with `QWENNEWS_DB_PATH`); fail visibly if missing.
26. Orchestration `trigger_source` provenance (`launchd` vs `cli`).
27. Status API surfaces scheduler verification, DB identity, last successful runs, backlog, volume probe.

Cloud inference, fine-tuning, and embedding-based clustering remain deferred.

## Package layout

| Module | Responsibility |
| --- | --- |
| `qwennews.config` | Env-based configuration and verified source endpoint registry |
| `qwennews.models` | Typed domain objects (`Article`, run stats, extraction status) |
| `qwennews.urls` | Canonicalization, tracking-param stripping, SSRF checks |
| `qwennews.http_client` | Shared HTTP client, size limits, safe redirects, bounded retries |
| `qwennews.robots` | Cached robots.txt decisions |
| `qwennews.extract` | HTML → article text extraction |
| `qwennews.sources.*` | Source adapters (HN Firebase API, RSS/Atom) |
| `qwennews.storage` | SQLite schema + idempotent upserts (schema v5) |
| `qwennews.collect` | End-to-end collection orchestration |
| `qwennews.ollama_client` | Local Ollama `/api/chat` adapter + metrics |
| `qwennews.analysis_schema` | Pydantic analysis models + JSON schema |
| `qwennews.analyze` | Prompting, validation, cache-aware analysis (concurrency=1) |
| `qwennews.ranking` | M2 deterministic ranking + diversity |
| `qwennews.similarity` | Headline/entity/content similarity helpers |
| `qwennews.story_memory` | Story linking + update classification |
| `qwennews.report` | Ondemand / hourly / daily Markdown reports |
| `qwennews.orchestrate` | M3 collect→sync→analyze→report pipeline |
| `qwennews.locking` | Advisory single-instance file lock |
| `qwennews.notify` | Optional macOS `osascript` notifications |
| `qwennews.launchd` | LaunchAgent plist render + validate |
| `qwennews.cli` | CLI including `run-hourly`, `run-daily`, `status`, `dashboard-api`, `dashboard` |
| `qwennews.readonly_store` | SQLite read-only access for the dashboard |
| `qwennews.dashboard_api` | FastAPI app (localhost, GET-only) |
| `qwennews.dashboard_launcher` | Parent process: start/stop API + Next on localhost |
| `qwennews.production` | Production DB path, scheduler inspect, port diagnose |
| `dashboard/` | Next.js TypeScript UI |
| `scripts/run_dashboard.py` | Convenience entry for the launcher |

## Data model

- **articles**: one row per canonical URL (stable SHA-256-based id).
- **article_sources**: many-to-many sightings so the same story can appear on HN and an RSS feed without duplicate article rows.
- **collection_runs** / **collection_run_sources**: run history.
- **article_analyses**: cached structured analyses keyed by article + content hash + model + config version.
- **stories** / **story_articles** / **story_events**: durable story memory.
- **reports**: persisted Markdown briefings (`mode`, `as_of`, `window_start`, `status`).
- **report_watermarks**: per-mode publication watermarks.
- **story_report_state**: per-mode `last_reported_at` (hourly vs daily independent).
- **orchestration_runs**: per-cycle timing, counts, errors, outcomes, `trigger_source` (M4.2).

Timestamps are stored as UTC ISO-8601 strings. Existing databases migrate in place (schema version 6 adds
`orchestration_runs.trigger_source`; v5 added backlog processing state tables).

### Ranking (M2)

```
rank = 0.35*significance + 0.25*relevance + 0.25*category_priority
     + 0.10*ai_signal + 0.05*hn_attention_capped
```

Popularity is never treated as truth. HN score-only changes are UNCHANGED.

## Orchestration failure policy

| Condition | Outcome | Watermark |
| --- | --- | --- |
| All sources fail, 0 articles | `collect_failed` | not advanced |
| Ollama down / model missing | `ollama_unavailable` | not advanced |
| All analyses fail | `analyze_failed` | not advanced |
| Partial analysis failures | continue if any succeeded | normal |
| Persist failure | `report_persist_failed` | not advanced |
| Truly nothing new / backlog drained | `empty_success` | advanced |
| Analyzed but not reportable | `no_significant_updates` | advanced when drained |
| Cap left pending work | `backlog_remaining` | **not** advanced |
| Same daily window again | `duplicate_window_skipped` | unchanged |
| Concurrent run | `lock_busy` | n/a |

## Extension points (later milestones)

- M4+: richer daily LaunchAgent, delivery channels, operator dashboard, evaluation harness upgrades.
