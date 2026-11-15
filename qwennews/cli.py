"""Command-line interface for QwenNews (M0 ingestion + M1 analysis)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from qwennews import __version__
from qwennews.analyze import analyze_articles
from qwennews.collect import collect_news
from qwennews.config import ALL_SOURCES, load_config
from qwennews.logging_config import setup_logging
from qwennews.report import generate_report
from qwennews.storage import ArticleStore


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qwennews",
        description="QwenNews — local news ingestion and Qwen3 analysis",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Create/initialize the SQLite database schema")

    collect_parser = sub.add_parser("collect", help="Fetch and store articles from sources")
    collect_parser.add_argument(
        "--source",
        action="append",
        dest="sources",
        choices=list(ALL_SOURCES),
        help="Limit collection to one or more sources (repeatable)",
    )
    collect_parser.add_argument(
        "--no-extract",
        action="store_true",
        help="Skip article body extraction for this run",
    )

    recent_parser = sub.add_parser("recent", help="Show recently discovered/updated articles")
    recent_parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Lookback window in hours (default: 24)",
    )
    recent_parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum rows to print (default: 50)",
    )

    sub.add_parser("stats", help="Print database and collection statistics")

    analyze_parser = sub.add_parser(
        "analyze",
        help="Analyze stored articles with local Qwen via Ollama",
    )
    analyze_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum articles to analyze (default: 10)",
    )
    analyze_parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Only consider articles from the last N hours (default: 24)",
    )
    analyze_parser.add_argument(
        "--force",
        action="store_true",
        help="Ignore analysis cache and re-run inference",
    )

    report_parser = sub.add_parser(
        "report",
        help="Generate on-demand, hourly-delta, or daily Markdown briefings",
    )
    report_parser.add_argument(
        "--mode",
        choices=["ondemand", "hourly", "daily"],
        default="ondemand",
        help="Report mode (default: ondemand)",
    )
    report_parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Lookback window in hours for ondemand mode (default: 24)",
    )
    report_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum stories in the briefing (default: 10; daily often uses 15)",
    )
    report_parser.add_argument(
        "--as-of",
        dest="as_of",
        default=None,
        help="UTC timestamp for deterministic reports (ISO-8601, e.g. 2026-11-15T20:00:00Z)",
    )
    report_parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for persisted Markdown reports (default: config report_dir)",
    )
    report_parser.add_argument(
        "--stdout-only",
        action="store_true",
        help="Print Markdown without writing a file",
    )

    sync_parser = sub.add_parser(
        "sync-stories",
        help="Link stored articles into story memory (near-duplicate aware)",
    )
    sync_parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Maximum recent articles to sync (default: 500)",
    )
    return parser


def cmd_init_db(store: ArticleStore) -> int:
    store.init_db()
    print(f"Database initialized at {store.db_path}")
    return 0


def cmd_collect(store: ArticleStore, args: argparse.Namespace) -> int:
    config = load_config()
    if args.no_extract:
        config.extract_content = False

    if not store.db_path.exists():
        print(
            f"Database not found at {store.db_path}. Run `python -m qwennews init-db` first.",
            file=sys.stderr,
        )
        return 1

    print("Starting collection…")
    stats = collect_news(store, config, sources=args.sources)
    print()
    print("Collection complete")
    print(f"  Articles seen:          {stats.articles_seen}")
    print(f"  New articles:           {stats.articles_new}")
    print(f"  Updated articles:       {stats.articles_updated}")
    print(f"  Duplicates:             {stats.duplicates}")
    print(f"  Extraction success:     {stats.extraction_success}")
    print(f"  Extraction failed:      {stats.extraction_failed}")
    print(f"  Extraction skipped:     {stats.extraction_skipped}")
    print(f"  Extraction blocked:     {stats.extraction_blocked}")
    print(f"  Elapsed seconds:        {stats.elapsed_seconds}")
    if stats.disabled_sources:
        print(f"  Disabled sources:       {', '.join(stats.disabled_sources)}")
    if stats.source_errors:
        print("  Source errors:")
        for source, error in stats.source_errors.items():
            print(f"    - {source}: {error}")
        print("  (Source failures did not abort the overall run.)")
    else:
        print("  Source errors:           none")
    return 0


def cmd_recent(store: ArticleStore, args: argparse.Namespace) -> int:
    if args.hours < 1:
        print("--hours must be >= 1", file=sys.stderr)
        return 1
    if not store.db_path.exists():
        print(f"Database not found at {store.db_path}", file=sys.stderr)
        return 1

    rows = store.recent_articles(hours=args.hours, limit=args.limit)
    if not rows:
        print(f"No articles found in the last {args.hours} hour(s).")
        return 0

    print(f"Recent articles (last {args.hours}h, showing {len(rows)}):")
    print()
    for row in rows:
        published = row.get("published_at") or row.get("discovered_at") or "?"
        sources = row.get("sources") or "?"
        status = row.get("content_extraction_status")
        print(f"- {row['title']}")
        print(f"  id: {row['id']}")
        print(f"  sources: {sources}")
        print(f"  url: {row['canonical_url']}")
        print(f"  published/discovered: {published}")
        print(f"  extraction: {status}")
        if row.get("hn_score") is not None:
            print(
                f"  hn: score={row['hn_score']} comments={row.get('hn_comment_count')} "
                f"discussion={row.get('hn_discussion_url')}"
            )
        print()
    return 0


def cmd_stats(store: ArticleStore) -> int:
    if not store.db_path.exists():
        print(f"Database not found at {store.db_path}", file=sys.stderr)
        return 1

    data = store.stats()
    print(f"Database: {data['db_path']}")
    print(f"Articles: {data['article_count']}")
    print(f"Cached analyses: {store.analysis_count()}")
    print("By source:")
    if data["by_source"]:
        for source, count in data["by_source"].items():
            print(f"  - {source}: {count}")
    else:
        print("  (none)")
    print("By extraction status:")
    if data["by_extraction_status"]:
        for status, count in data["by_extraction_status"].items():
            print(f"  - {status}: {count}")
    else:
        print("  (none)")
    print("Recent collection runs:")
    if data["recent_runs"]:
        for run in data["recent_runs"]:
            print(
                f"  - #{run['id']} {run['status']} started={run['started_at']} "
                f"seen={run['articles_seen']} new={run['articles_new']} "
                f"dupes={run['duplicates']} extract_ok={run['extraction_success']} "
                f"extract_fail={run['extraction_failed']} elapsed={run['elapsed_seconds']}"
            )
    else:
        print("  (none)")
    return 0


def cmd_analyze(store: ArticleStore, args: argparse.Namespace) -> int:
    config = load_config()
    if not store.db_path.exists():
        print(
            f"Database not found at {store.db_path}. Run `python -m qwennews init-db` first.",
            file=sys.stderr,
        )
        return 1
    # Ensure M1 tables exist on older DBs.
    store.init_db()

    print(
        f"Analyzing up to {args.limit} article(s) with model={config.ollama_model} "
        f"think={config.ollama_think} (concurrency=1)…"
    )
    stats = analyze_articles(
        store,
        config,
        limit=args.limit,
        hours=args.hours,
        force=args.force,
    )
    print()
    print("Analysis complete")
    print(f"  Attempted:   {stats.attempted}")
    print(f"  Succeeded:   {stats.succeeded}")
    print(f"  Failed:      {stats.failed}")
    print(f"  Cached hits: {stats.cached}")
    print(f"  Inferred:    {stats.inferred}")
    print(f"  Elapsed:     {stats.elapsed_seconds}s")
    if stats.errors:
        print("  Errors:")
        for err in stats.errors[:20]:
            print(f"    - {err}")
        return 1 if stats.succeeded == 0 else 0
    return 0


def cmd_report(store: ArticleStore, args: argparse.Namespace) -> int:
    from datetime import datetime

    from qwennews.config import default_ranking_config_from_env
    from qwennews.models import ensure_utc

    config = load_config()
    if not store.db_path.exists():
        print(f"Database not found at {store.db_path}", file=sys.stderr)
        return 1
    store.init_db()

    as_of = None
    if args.as_of:
        try:
            as_of = ensure_utc(datetime.fromisoformat(args.as_of.replace("Z", "+00:00")))
        except ValueError:
            print(f"Invalid --as-of timestamp: {args.as_of}", file=sys.stderr)
            return 2

    limit = args.limit
    if args.mode == "daily" and args.limit == 10:
        limit = 15

    output_dir = None if args.stdout_only else (args.output_dir or config.report_dir)
    markdown, path, meta = generate_report(
        store,
        hours=args.hours,
        limit=limit,
        output_dir=output_dir,
        mode=args.mode,
        as_of=as_of,
        ranking_config=default_ranking_config_from_env(),
    )
    print(markdown)
    if path is not None:
        print(f"[saved] {path}", file=sys.stderr)
    if meta.get("persist_failed"):
        print("[warn] report persistence failed; watermark not advanced", file=sys.stderr)
        return 1
    return 0


def cmd_sync_stories(store: ArticleStore, args: argparse.Namespace) -> int:
    from collections import Counter

    from qwennews.story_memory import sync_stories

    if not store.db_path.exists():
        print(f"Database not found at {store.db_path}", file=sys.stderr)
        return 1
    store.init_db()
    decisions = sync_stories(store, limit=args.limit)
    counts = Counter(d.decision.value for d in decisions)
    print(f"Synced {len(decisions)} article(s) into story memory:")
    for key, value in sorted(counts.items()):
        print(f"  - {key}: {value}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    setup_logging(verbose=args.verbose)

    try:
        config = load_config()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    store = ArticleStore(config.db_path)

    if args.command == "init-db":
        return cmd_init_db(store)
    if args.command == "collect":
        return cmd_collect(store, args)
    if args.command == "recent":
        return cmd_recent(store, args)
    if args.command == "stats":
        return cmd_stats(store)
    if args.command == "analyze":
        return cmd_analyze(store, args)
    if args.command == "report":
        return cmd_report(store, args)
    if args.command == "sync-stories":
        return cmd_sync_stories(store, args)

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
