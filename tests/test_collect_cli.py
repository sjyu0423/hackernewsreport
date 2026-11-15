"""Collection orchestration and CLI behavior tests."""

from __future__ import annotations

from pathlib import Path

from qwennews.cli import main
from qwennews.collect import _merge_by_canonical, collect_news
from qwennews.config import Config
from qwennews.models import Article, ContentExtractionStatus, utc_now
from qwennews.storage import ArticleStore
from qwennews.urls import article_id_for_url, canonicalize_url


def test_merge_by_canonical_preserves_sources() -> None:
    def make(url: str, source: str) -> Article:
        canonical = canonicalize_url(url)
        return Article(
            id=article_id_for_url(canonical),
            source=source,
            title="Same",
            original_url=url,
            canonical_url=canonical,
            discovered_at=utc_now(),
            content_extraction_status=ContentExtractionStatus.PENDING,
        )

    merged, dupes = _merge_by_canonical(
        [
            make("https://example.com/x?utm_source=1", "hackernews"),
            make("https://example.com/x", "openai"),
        ]
    )
    assert dupes == 1
    assert len(merged) == 1
    assert merged[0].source == "hackernews"
    assert "openai" in merged[0].extra_sources


def test_failed_source_does_not_abort_run(httpx_mock, store: ArticleStore, config: Config) -> None:
    # OpenAI feed fails
    httpx_mock.add_response(
        url="https://openai.com/news/rss.xml",
        status_code=500,
    )
    # DeepMind succeeds
    httpx_mock.add_response(
        url="https://deepmind.google/blog/rss.xml",
        text="""<?xml version="1.0"?>
        <rss version="2.0"><channel><title>DM</title>
        <item>
          <title>DeepMind Post</title>
          <link>https://deepmind.google/blog/post-1</link>
          <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
        </item>
        </channel></rss>""",
        headers={"Content-Type": "application/rss+xml"},
    )
    # Skip extraction network for the single article
    config.extract_content = False
    config.enabled_sources = ("openai", "deepmind")

    stats = collect_news(store, config, sources=["openai", "deepmind"])
    assert "openai" in stats.source_errors
    assert stats.articles_new == 1
    assert store.stats()["article_count"] == 1


def test_cli_init_stats_recent(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "cli.db"
    monkeypatch.setenv("QWENNEWS_DB_PATH", str(db_path))
    monkeypatch.chdir(tmp_path)

    assert main(["init-db"]) == 0
    assert db_path.exists()
    assert main(["stats"]) == 0
    assert main(["recent", "--hours", "24"]) == 0


def test_cli_collect_requires_db(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("QWENNEWS_DB_PATH", str(tmp_path / "missing.db"))
    assert main(["collect", "--source", "openai"]) == 1


def test_cli_help() -> None:
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
