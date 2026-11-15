"""Normalized article and collection domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def utc_now() -> datetime:
    """Return current UTC time (timezone-aware)."""
    return datetime.now(UTC)


def ensure_utc(value: datetime | None) -> datetime | None:
    """Normalize datetimes to timezone-aware UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class ContentExtractionStatus(StrEnum):
    """Lifecycle status for article body extraction."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    UNSAFE_URL = "unsafe_url"


@dataclass(slots=True)
class Article:
    """Normalized article record used across sources and storage."""

    id: str
    source: str
    title: str
    original_url: str
    canonical_url: str
    discovered_at: datetime
    published_at: datetime | None = None
    author: str | None = None
    article_text: str | None = None
    content_extraction_status: ContentExtractionStatus = ContentExtractionStatus.PENDING
    hn_score: int | None = None
    hn_comment_count: int | None = None
    hn_discussion_url: str | None = None
    source_item_id: str | None = None
    extra_sources: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.discovered_at = ensure_utc(self.discovered_at) or utc_now()
        self.published_at = ensure_utc(self.published_at)
        if isinstance(self.content_extraction_status, str):
            self.content_extraction_status = ContentExtractionStatus(self.content_extraction_status)


@dataclass(slots=True)
class SourceFetchResult:
    """Outcome of fetching a single news source."""

    source: str
    articles: list[Article] = field(default_factory=list)
    error: str | None = None
    disabled: bool = False
    items_fetched: int = 0

    @property
    def ok(self) -> bool:
        return self.error is None and not self.disabled


@dataclass(slots=True)
class CollectionStats:
    """Aggregate metrics for one collection run."""

    articles_seen: int = 0
    articles_new: int = 0
    articles_updated: int = 0
    duplicates: int = 0
    extraction_success: int = 0
    extraction_failed: int = 0
    extraction_skipped: int = 0
    extraction_blocked: int = 0
    source_errors: dict[str, str] = field(default_factory=dict)
    disabled_sources: list[str] = field(default_factory=list)
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "articles_seen": self.articles_seen,
            "articles_new": self.articles_new,
            "articles_updated": self.articles_updated,
            "duplicates": self.duplicates,
            "extraction_success": self.extraction_success,
            "extraction_failed": self.extraction_failed,
            "extraction_skipped": self.extraction_skipped,
            "extraction_blocked": self.extraction_blocked,
            "source_errors": self.source_errors,
            "disabled_sources": self.disabled_sources,
            "elapsed_seconds": self.elapsed_seconds,
        }
