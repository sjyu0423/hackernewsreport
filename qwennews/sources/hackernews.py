"""Hacker News Firebase API adapter (topstories + newstories)."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from typing import Any

import httpx

from qwennews.config import SOURCE_ENDPOINTS, Config
from qwennews.http_client import get_json
from qwennews.models import Article, ContentExtractionStatus, SourceFetchResult, utc_now
from qwennews.urls import article_id_for_url, canonicalize_url

logger = logging.getLogger(__name__)


class HackerNewsSource:
    name = "hackernews"

    def fetch(self, client: httpx.Client, config: Config) -> SourceFetchResult:
        endpoints = SOURCE_ENDPOINTS[self.name]
        limit = config.source_limit(self.name)
        try:
            top_ids = get_json(
                client,
                endpoints["topstories"],
                max_bytes=config.max_response_bytes,
            )
            new_ids = get_json(
                client,
                endpoints["newstories"],
                max_bytes=config.max_response_bytes,
            )
        except Exception as exc:  # noqa: BLE001 — isolate source failures
            logger.exception("Hacker News list fetch failed")
            return SourceFetchResult(source=self.name, error=str(exc))

        if not isinstance(top_ids, list) or not isinstance(new_ids, list):
            return SourceFetchResult(
                source=self.name,
                error="Unexpected HN API response: expected JSON arrays",
            )

        # Preserve topstories order preference, then append unseen newstories.
        ordered_ids: list[int] = []
        seen: set[int] = set()
        for raw in list(top_ids) + list(new_ids):
            try:
                item_id = int(raw)
            except (TypeError, ValueError):
                continue
            if item_id in seen:
                continue
            seen.add(item_id)
            ordered_ids.append(item_id)
            if len(ordered_ids) >= limit:
                break

        articles: list[Article] = []
        errors: list[str] = []

        def fetch_one(item_id: int) -> Article | None:
            url = endpoints["item"].format(id=item_id)
            payload = get_json(client, url, max_bytes=config.max_response_bytes)
            if not isinstance(payload, dict):
                return None
            return self._normalize_item(payload)

        workers = max(1, min(config.max_concurrency, len(ordered_ids) or 1))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(fetch_one, item_id): item_id for item_id in ordered_ids}
            for future in as_completed(futures):
                item_id = futures[future]
                try:
                    article = future.result()
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"item {item_id}: {exc}")
                    logger.warning("HN item %s failed: %s", item_id, exc)
                    continue
                if article is not None:
                    articles.append(article)

        error = None
        if errors and not articles:
            error = "; ".join(errors[:5])
        elif errors:
            logger.warning("HN partial item failures: %s", "; ".join(errors[:5]))

        return SourceFetchResult(
            source=self.name,
            articles=articles,
            error=error,
            items_fetched=len(articles),
        )

    def _normalize_item(self, payload: dict[str, Any]) -> Article | None:
        if payload.get("type") not in {"story", "job"}:
            return None
        if payload.get("dead") or payload.get("deleted"):
            return None

        hn_id = payload.get("id")
        title = (payload.get("title") or "").strip()
        if not title or hn_id is None:
            return None

        discussion_url = f"https://news.ycombinator.com/item?id={hn_id}"
        external_url = (payload.get("url") or "").strip()

        # Ask/Show HN without external URL: the discussion page is the original URL,
        # but we do not treat comments as article body (extraction will skip).
        original_url = external_url or discussion_url
        try:
            canonical = canonicalize_url(original_url)
        except ValueError:
            canonical = canonicalize_url(discussion_url)
            original_url = discussion_url

        published_at = None
        if isinstance(payload.get("time"), (int, float)):
            published_at = datetime.fromtimestamp(float(payload["time"]), tz=UTC)

        return Article(
            id=article_id_for_url(canonical),
            source=self.name,
            title=title,
            original_url=original_url,
            canonical_url=canonical,
            published_at=published_at,
            discovered_at=utc_now(),
            author=(payload.get("by") or None),
            article_text=None,
            content_extraction_status=ContentExtractionStatus.PENDING,
            hn_score=payload.get("score") if isinstance(payload.get("score"), int) else None,
            hn_comment_count=(
                payload.get("descendants") if isinstance(payload.get("descendants"), int) else None
            ),
            hn_discussion_url=discussion_url,
            source_item_id=str(hn_id),
        )
