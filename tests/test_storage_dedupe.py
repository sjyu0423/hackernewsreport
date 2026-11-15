"""SQLite idempotency and canonical URL deduplication tests."""

from __future__ import annotations

from qwennews.models import Article, ContentExtractionStatus, utc_now
from qwennews.storage import ArticleStore
from qwennews.urls import article_id_for_url, canonicalize_url


def _article(url: str, source: str, title: str = "T") -> Article:
    canonical = canonicalize_url(url)
    return Article(
        id=article_id_for_url(canonical),
        source=source,
        title=title,
        original_url=url,
        canonical_url=canonical,
        discovered_at=utc_now(),
        content_extraction_status=ContentExtractionStatus.PENDING,
        source_item_id=f"{source}-1",
    )


def test_idempotent_upsert_and_cross_source_dedupe(store: ArticleStore) -> None:
    first = _article("https://example.com/story?utm_source=a", "hackernews", "Story")
    first.hn_score = 11
    first.hn_discussion_url = "https://news.ycombinator.com/item?id=1"

    assert store.upsert_article(first) == "new"
    assert store.upsert_article(first) == "duplicate"

    second = _article("https://example.com/story", "openai", "Story")
    # Same canonical URL → same id; should attach second source, not duplicate row.
    assert second.id == first.id
    outcome = store.upsert_article(second)
    assert outcome in {"updated", "duplicate"}

    stats = store.stats()
    assert stats["article_count"] == 1
    assert stats["by_source"]["hackernews"] == 1
    assert stats["by_source"]["openai"] == 1

    row = store.get_article(first.id)
    assert row is not None
    assert row["title"] == "Story"
    assert row["hn_score"] == 11


def test_update_merges_extraction_success(store: ArticleStore) -> None:
    article = _article("https://example.com/extract", "techcrunch")
    store.upsert_article(article)
    store.update_extraction(
        article.id,
        text="Hello world body",
        status=ContentExtractionStatus.SUCCESS,
    )
    # Later failure must not wipe successful text.
    store.update_extraction(
        article.id,
        text=None,
        status=ContentExtractionStatus.FAILED,
    )
    row = store.get_article(article.id)
    assert row is not None
    assert row["article_text"] == "Hello world body"
    assert row["content_extraction_status"] == "success"
