"""Collection orchestration: sources → normalize → dedupe → extract → store."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from qwennews.config import ALL_SOURCES, Config
from qwennews.extract import ContentExtractor
from qwennews.http_client import build_client
from qwennews.models import Article, CollectionStats, ContentExtractionStatus
from qwennews.sources.base import get_adapter
from qwennews.storage import ArticleStore
from qwennews.urls import canonicalize_url

logger = logging.getLogger(__name__)


def _merge_by_canonical(articles: list[Article]) -> tuple[list[Article], int]:
    """
    Collapse exact duplicates (same canonical URL) within a run.

    Preserves multi-source membership on a single article record.
    Returns (merged_articles, duplicate_count).
    """
    by_url: dict[str, Article] = {}
    duplicates = 0
    for article in articles:
        try:
            canonical = canonicalize_url(article.canonical_url)
        except ValueError:
            canonical = article.canonical_url
        article.canonical_url = canonical

        existing = by_url.get(canonical)
        if existing is None:
            by_url[canonical] = article
            continue

        duplicates += 1
        if article.source not in existing.extra_sources and article.source != existing.source:
            existing.extra_sources.append(article.source)
        # Prefer richer HN metadata when present.
        if existing.hn_score is None and article.hn_score is not None:
            existing.hn_score = article.hn_score
            existing.hn_comment_count = article.hn_comment_count
            existing.hn_discussion_url = article.hn_discussion_url
        if existing.author is None and article.author:
            existing.author = article.author
        if existing.published_at is None and article.published_at:
            existing.published_at = article.published_at
        # Prefer a non-discussion original URL when available.
        if article.original_url and "news.ycombinator.com/item" not in article.original_url:
            if "news.ycombinator.com/item" in (existing.original_url or ""):
                existing.original_url = article.original_url

    return list(by_url.values()), duplicates


def collect_news(
    store: ArticleStore,
    config: Config,
    *,
    sources: list[str] | None = None,
) -> CollectionStats:
    """
    Run a single collection pass.

    Source failures are recorded and skipped; they do not abort the run.
    """
    started = time.perf_counter()
    selected = list(sources) if sources else list(config.enabled_sources)
    stats = CollectionStats()
    source_results: dict[str, dict[str, object]] = {}
    gathered: list[Article] = []

    run_id = store.start_run()
    logger.info("Collection run %s starting for sources: %s", run_id, ", ".join(selected))

    with build_client(config) as client:
        for name in selected:
            if name not in ALL_SOURCES:
                stats.source_errors[name] = "unknown source"
                source_results[name] = {
                    "status": "error",
                    "items_fetched": 0,
                    "error": "unknown source",
                }
                continue
            if not config.is_source_enabled(name) and sources is None:
                stats.disabled_sources.append(name)
                source_results[name] = {
                    "status": "disabled",
                    "items_fetched": 0,
                    "error": None,
                }
                continue

            try:
                adapter = get_adapter(name)
            except Exception as exc:  # noqa: BLE001
                stats.source_errors[name] = str(exc)
                source_results[name] = {
                    "status": "error",
                    "items_fetched": 0,
                    "error": str(exc),
                }
                continue

            result = adapter.fetch(client, config)
            if result.disabled:
                stats.disabled_sources.append(name)
                source_results[name] = {
                    "status": "disabled",
                    "items_fetched": 0,
                    "error": result.error,
                }
                continue
            if result.error:
                stats.source_errors[name] = result.error
                source_results[name] = {
                    "status": "error",
                    "items_fetched": result.items_fetched,
                    "error": result.error,
                }
                logger.error("Source %s failed: %s", name, result.error)
                # Keep any partial articles that were successfully normalized.
                gathered.extend(result.articles)
                continue

            source_results[name] = {
                "status": "ok",
                "items_fetched": result.items_fetched,
                "error": None,
            }
            logger.info("Source %s fetched %s items", name, result.items_fetched)
            gathered.extend(result.articles)

        merged, in_run_dupes = _merge_by_canonical(gathered)
        stats.duplicates += in_run_dupes
        stats.articles_seen = len(merged)

        # Persist metadata first so extraction failures never lose titles/URLs.
        pending_extraction: list[Article] = []
        for article in merged:
            outcome = store.upsert_article(article)
            if outcome == "new":
                stats.articles_new += 1
            elif outcome == "updated":
                stats.articles_updated += 1
            else:
                stats.duplicates += 1

            if config.extract_content and article.content_extraction_status in {
                ContentExtractionStatus.PENDING,
                ContentExtractionStatus.FAILED,
            }:
                pending_extraction.append(article)

        if config.extract_content and pending_extraction:
            extractor = ContentExtractor(client, config)

            def run_extract(article: Article) -> tuple[Article, ContentExtractionStatus]:
                result = extractor.extract(article.original_url)
                article.article_text = result.text
                article.content_extraction_status = result.status
                store.update_extraction(
                    article.id,
                    text=result.text,
                    status=result.status,
                )
                return article, result.status

            workers = max(1, min(config.max_concurrency, len(pending_extraction)))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(run_extract, article) for article in pending_extraction]
                for future in as_completed(futures):
                    try:
                        _article, status = future.result()
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("Extraction worker failed: %s", exc)
                        stats.extraction_failed += 1
                        continue
                    if status == ContentExtractionStatus.SUCCESS:
                        stats.extraction_success += 1
                    elif status == ContentExtractionStatus.BLOCKED:
                        stats.extraction_blocked += 1
                    elif status in {
                        ContentExtractionStatus.SKIPPED,
                        ContentExtractionStatus.UNSAFE_URL,
                    }:
                        stats.extraction_skipped += 1
                    else:
                        stats.extraction_failed += 1

    stats.elapsed_seconds = round(time.perf_counter() - started, 3)
    store.finish_run(run_id, stats, source_results=source_results)
    logger.info(
        "Collection run %s finished: seen=%s new=%s updated=%s dupes=%s "
        "extract_ok=%s extract_fail=%s errors=%s elapsed=%.3ss",
        run_id,
        stats.articles_seen,
        stats.articles_new,
        stats.articles_updated,
        stats.duplicates,
        stats.extraction_success,
        stats.extraction_failed,
        list(stats.source_errors.keys()),
        stats.elapsed_seconds,
    )
    return stats
