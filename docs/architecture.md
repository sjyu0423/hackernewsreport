# QwenNews Architecture (M0)

## Goals

M0 establishes a durable ingestion pipeline:

1. Pull stories from verified public sources.
2. Normalize into a shared article model.
3. Deduplicate by canonical URL.
4. Optionally extract article text when allowed.
5. Persist articles, source sightings, and collection-run metrics in SQLite.
6. Expose the workflow through a small CLI.

No LLM calls, ranking, scheduling, notifications, or dashboard are included yet.

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
| `qwennews.cli` | `init-db`, `collect`, `recent`, `stats` |

## Data model

- **articles**: one row per canonical URL (stable SHA-256-based id).
- **article_sources**: many-to-many sightings so the same story can appear on HN and an RSS feed without duplicate article rows.
- **collection_runs** / **collection_run_sources**: run history for later hourly delta reports.

Timestamps are stored as UTC ISO-8601 strings.

## Failure policy

- A failing source records an error and is skipped; other sources continue.
- Extraction failures preserve title/metadata/URL.
- Unsafe destinations and private redirect targets are rejected.
- robots.txt / HTTP 401·403·429·451 are treated as blocked, not crashes.

## Extension points (later milestones)

- M1: scheduling + hourly delta reports
- M2: semantic dedupe / topic tracking
- M3+: local Qwen ranking, summarization, daily briefing, dashboard
