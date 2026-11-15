"""Generic RSS/Atom feed adapter for verified public endpoints."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import mktime
from typing import Any

import feedparser
import httpx

from qwennews.config import Config
from qwennews.http_client import get_text
from qwennews.models import Article, ContentExtractionStatus, SourceFetchResult, utc_now
from qwennews.urls import article_id_for_url, canonicalize_url

logger = logging.getLogger(__name__)


def _parse_struct_time(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(mktime(value), tz=UTC)
    except (OverflowError, TypeError, ValueError):
        return None


def _parse_published(entry: dict[str, Any]) -> datetime | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        dt = _parse_struct_time(entry.get(key))
        if dt is not None:
            return dt
    for key in ("published", "updated", "created"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(str(raw))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            return dt.astimezone(UTC)
        except (TypeError, ValueError, IndexError):
            continue
    return None


def _entry_link(entry: dict[str, Any]) -> str | None:
    link = (entry.get("link") or "").strip()
    if link:
        return link
    # Hugging Face feed historically uses guid as permalink without <link>.
    guid = entry.get("id") or entry.get("guid")
    if isinstance(guid, str) and guid.startswith("http"):
        return guid.strip()
    links = entry.get("links") or []
    for item in links:
        if isinstance(item, dict) and item.get("href"):
            rel = (item.get("rel") or "alternate").lower()
            if rel in {"alternate", "self"} or item.get("type", "").startswith("text/html"):
                return str(item["href"]).strip()
    return None


def _entry_author(entry: dict[str, Any]) -> str | None:
    author = entry.get("author")
    if isinstance(author, str) and author.strip():
        return author.strip()
    authors = entry.get("authors") or []
    names = []
    for item in authors:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]).strip())
        elif isinstance(item, str) and item.strip():
            names.append(item.strip())
    return ", ".join(names) if names else None


def parse_feed_bytes(content: bytes | str, *, source: str, limit: int) -> list[Article]:
    """Parse RSS/Atom content into normalized articles (pure; used by tests)."""
    parsed = feedparser.parse(content)
    if getattr(parsed, "bozo", False) and not parsed.entries:
        raise ValueError(
            f"Failed to parse feed for {source}: {getattr(parsed, 'bozo_exception', 'unknown')}"
        )

    articles: list[Article] = []
    for entry in parsed.entries[:limit]:
        title = (entry.get("title") or "").strip()
        link = _entry_link(entry)
        if not title or not link:
            continue
        try:
            canonical = canonicalize_url(link)
        except ValueError as exc:
            logger.warning("Skipping %s entry with bad URL %r: %s", source, link, exc)
            continue

        source_item_id = None
        if entry.get("id"):
            source_item_id = str(entry.get("id"))
        elif entry.get("guid"):
            source_item_id = str(entry.get("guid"))

        articles.append(
            Article(
                id=article_id_for_url(canonical),
                source=source,
                title=title,
                original_url=link,
                canonical_url=canonical,
                published_at=_parse_published(entry),
                discovered_at=utc_now(),
                author=_entry_author(entry),
                article_text=None,
                content_extraction_status=ContentExtractionStatus.PENDING,
                source_item_id=source_item_id,
            )
        )
    return articles


class RssSource:
    """Adapter for a single verified RSS/Atom endpoint."""

    def __init__(self, name: str, feed_url: str, label: str | None = None) -> None:
        self.name = name
        self.feed_url = feed_url
        self.label = label or name

    def fetch(self, client: httpx.Client, config: Config) -> SourceFetchResult:
        limit = config.source_limit(self.name)
        try:
            _final_url, text = get_text(
                client,
                self.feed_url,
                max_bytes=config.max_response_bytes,
                allowed_content_types=(
                    "application/rss+xml",
                    "application/atom+xml",
                    "application/xml",
                    "text/xml",
                    "text/html",
                    "text/plain",
                ),
            )
            articles = parse_feed_bytes(text, source=self.name, limit=limit)
        except Exception as exc:  # noqa: BLE001 — isolate source failures
            logger.exception("%s feed fetch failed (%s)", self.label, self.feed_url)
            return SourceFetchResult(source=self.name, error=str(exc))

        return SourceFetchResult(
            source=self.name,
            articles=articles,
            items_fetched=len(articles),
        )
