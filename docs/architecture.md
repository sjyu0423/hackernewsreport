# QwenNews Architecture (M0 + M1)

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

Scheduling, notifications, semantic dedupe, and a dashboard remain deferred.

## Package layout

| Module | Responsibility |
| --- | --- |
| `qwennews.config` | Env-based configuration and verified source endpoint registry |
| `qwennews.models` | Typed domain objects (`Article`, run stats, extraction status) |
| `qwennews.urls` | Canonicalization, tracking-param stripping, SSRF checks |
| `qwennews.http_client` | Shared HTTP client, size limits, safe redirects |
| `qwennews.robots` | Cached robots.txt decisions |
| `qwennews.extract` | HTML → article text extraction |
| `qwennews.sources.*` | Source adapters (HN Firebase API, RSS/Atom) |
| `qwennews.storage` | SQLite schema + idempotent upserts |
| `qwennews.collect` | End-to-end collection orchestration |
| `qwennews.ollama_client` | Local Ollama `/api/chat` adapter + metrics |
| `qwennews.analysis_schema` | Pydantic analysis models + JSON schema |
| `qwennews.analyze` | Prompting, validation, cache-aware analysis |
| `qwennews.report` | Deterministic Markdown briefing + ranking |
| `qwennews.cli` | `init-db`, `collect`, `recent`, `stats`, `analyze`, `report` |

## Data model

- **articles**: one row per canonical URL (stable SHA-256-based id).
- **article_sources**: many-to-many sightings so the same story can appear on HN and an RSS feed without duplicate article rows.
- **collection_runs** / **collection_run_sources**: run history for later hourly delta reports.
- **article_analyses**: cached structured analyses keyed by article + content hash + model + config version.
- **reports**: persisted on-demand Markdown briefings.

Timestamps are stored as UTC ISO-8601 strings.

### Ranking (M1)

```
rank = 0.45 * relevance + 0.40 * significance + 0.15 * hn_attention
```

`hn_attention` is a clamped log-scaled HN score in `[1,5]` (neutral 2.5 if absent). Popularity is never treated as truth.

## Failure policy

- A failing source records an error and is skipped; other sources continue.
- Extraction failures preserve title/metadata/URL.
- Unsafe destinations and private redirect targets are rejected.
- robots.txt / HTTP 401·403·429·451 are treated as blocked, not crashes.

## Extension points (later milestones)

- M1: scheduling + hourly delta reports
- M2: semantic dedupe / topic tracking
- M3+: local Qwen ranking, summarization, daily briefing, dashboard
