"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from qwennews.config import Config
from qwennews.storage import ArticleStore


@pytest.fixture(autouse=True)
def _fake_public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid live DNS in unit tests while still exercising IP policy checks."""

    def fake_getaddrinfo(host: str, *args, **kwargs):  # noqa: ANN002, ANN003
        # Resolve hostnames to a public address (avoid TEST-NET / reserved ranges).
        return [(2, 1, 6, "", ("8.8.8.8", 0))]

    monkeypatch.setattr("socket.getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr("qwennews.urls.socket.getaddrinfo", fake_getaddrinfo)


@pytest.fixture
def config(tmp_path: Path) -> Config:
    return Config(
        db_path=tmp_path / "test.db",
        user_agent="QwenNews-Test/0.1",
        connect_timeout=2.0,
        read_timeout=5.0,
        max_response_bytes=100_000,
        hn_limit=10,
        rss_limit=10,
        max_concurrency=2,
        enabled_sources=(
            "hackernews",
            "openai",
            "deepmind",
            "huggingface",
            "techcrunch",
        ),
        extract_content=True,
        respect_robots=True,
    )


@pytest.fixture
def store(config: Config) -> ArticleStore:
    article_store = ArticleStore(config.db_path)
    article_store.init_db()
    return article_store
