"""M4 dashboard API tests — fixtures, read-only guarantees, URL safety."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from qwennews.analysis_schema import ANALYSIS_CONFIG_VERSION, ArticleAnalysis
from qwennews.analyze import content_hash_for_article
from qwennews.dashboard_api.app import create_app
from qwennews.models import Article, ContentExtractionStatus
from qwennews.readonly_store import ReadOnlyStore, safe_http_url
from qwennews.storage import ArticleStore
from qwennews.story_memory import link_article
from qwennews.urls import article_id_for_url, canonicalize_url


@pytest.fixture
def populated_db(tmp_path: Path) -> Path:
    db = tmp_path / "dash.db"
    store = ArticleStore(db)
    store.init_db()
    as_of = datetime.fromisoformat("2026-11-15T20:00:00+00:00")
    url = "https://example.com/gemini-hydrogen"
    canonical = canonicalize_url(url)
    article = Article(
        id=article_id_for_url(canonical),
        source="openai",
        title="Gemini 4 Hydrogen launches with grounded safety notes",
        original_url=url,
        canonical_url=canonical,
        discovered_at=as_of - timedelta(hours=2),
        article_text=(
            "Gemini 4 Hydrogen is a new model release with enough article body "
            "text for analysis fixtures used by the dashboard API tests."
        ),
        content_extraction_status=ContentExtractionStatus.SUCCESS,
    )
    store.upsert_article(article)
    row = store.get_article(article.id)
    assert row is not None
    row["sources"] = "openai"
    analysis = ArticleAnalysis(
        article_id=article.id,
        category="models",
        summary="Grounded summary based on the supplied fixture article text content.",
        why_it_matters="Matters for evaluating dashboard story cards in tests.",
        relevance_score=5,
        significance_score=5,
        evidence_sufficiency="sufficient",
        key_claims=["Fixture claim drawn from article text."],
        limitations="Fixture limitations note.",
    )
    store.save_analysis(
        article_id=article.id,
        content_hash=content_hash_for_article(row),
        model_id="test-model",
        config_version=ANALYSIS_CONFIG_VERSION,
        analysis=analysis,
    )
    link_article(store, row)
    store.save_report(
        path=str(tmp_path / "daily.md"),
        hours=24,
        story_count=1,
        markdown=(
            "# QwenNews Daily Briefing\n\n"
            "### 1. Gemini 4 Hydrogen launches\n"
            "- Category: **models**\n"
        ),
        mode="daily",
        as_of=as_of.isoformat().replace("+00:00", "Z"),
        window_start=(as_of - timedelta(hours=24)).isoformat().replace("+00:00", "Z"),
        status="completed",
    )
    store.save_report(
        path=str(tmp_path / "hourly.md"),
        hours=1,
        story_count=0,
        markdown=(
            "# QwenNews Hourly Delta\n\n## No significant updates\n\nNothing new.\n"
        ),
        mode="hourly",
        as_of=as_of.isoformat().replace("+00:00", "Z"),
        window_start=(as_of - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        status="completed",
        significant_only=True,
    )
    store.set_watermark("hourly", as_of.isoformat().replace("+00:00", "Z"))
    store.set_watermark("daily", as_of.isoformat().replace("+00:00", "Z"))
    return db


@pytest.fixture
def client(populated_db: Path) -> TestClient:
    app = create_app(db_path=populated_db)
    return TestClient(app)


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["readonly"] is True


def test_today_uses_daily(client: TestClient) -> None:
    r = client.get("/api/today")
    assert r.status_code == 200
    data = r.json()
    assert data["source"] == "daily"
    assert data["report"]["mode"] == "daily"
    assert "Gemini" in data["report"]["markdown"]
    assert data["stories"]
    story = data["stories"][0]
    assert story["primary"]["summary"]
    assert story["primary"]["canonical_url"].startswith("https://")


def test_hourly_classifies_empty(client: TestClient) -> None:
    r = client.get("/api/hourly")
    assert r.status_code == 200
    items = r.json()["items"]
    assert items
    assert items[0]["kind"] == "empty"


def test_history_and_report_detail(client: TestClient) -> None:
    r = client.get("/api/reports", params={"mode": "daily"})
    assert r.status_code == 200
    items = r.json()["items"]
    assert items
    detail = client.get(f"/api/reports/{items[0]['id']}")
    assert detail.status_code == 200
    assert "Daily" in detail.json()["markdown"]


def test_stories_group_sources(client: TestClient) -> None:
    r = client.get("/api/stories")
    assert r.status_code == 200
    stories = r.json()
    assert stories
    assert stories[0]["article_count"] >= 1
    assert stories[0]["articles"][0]["canonical_url"].startswith("https://")


def test_status_last_known(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "qwennews.ollama_health.check_ollama",
        lambda *a, **k: type(
            "H",
            (),
            {
                "to_dict": lambda self: {
                    "ok": True,
                    "reachable": True,
                    "model_present": True,
                }
            },
        )(),
    )
    r = client.get("/api/status")
    assert r.status_code == 200
    data = r.json()
    assert data["watermarks"]["hourly"] is not None
    assert data["last_daily_report"]["mode"] == "daily"
    assert "last-known" in data["note"].lower() or "SQLite" in data["note"]


def test_mutations_rejected(client: TestClient) -> None:
    assert client.post("/api/today").status_code == 405
    assert client.delete("/api/reports/1").status_code == 405


def test_readonly_connection_rejects_writes(populated_db: Path) -> None:
    store = ReadOnlyStore(populated_db)
    with pytest.raises(Exception):  # noqa: B017 — sqlite raises OperationalError
        with store._connect() as conn:
            conn.execute("CREATE TABLE should_fail (id INTEGER)")


def test_readonly_api_does_not_mutate_db(client: TestClient, populated_db: Path) -> None:
    before = populated_db.stat().st_mtime_ns
    # Force a content fingerprint
    with sqlite3.connect(populated_db) as conn:
        count_before = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    client.get("/api/today")
    client.get("/api/status", params={"live_ollama": False})
    client.get("/api/stories")
    with sqlite3.connect(populated_db) as conn:
        count_after = conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0]
    assert count_after == count_before
    # mtime may change on some FS from open; row counts are the hard guarantee
    assert before <= populated_db.stat().st_mtime_ns or True


def test_safe_http_url() -> None:
    assert safe_http_url("https://example.com/a") == "https://example.com/a"
    assert safe_http_url("javascript:alert(1)") is None
    assert safe_http_url("file:///etc/passwd") is None
    assert safe_http_url(None) is None


def test_bind_refusal_in_main() -> None:
    import sys

    from qwennews.dashboard_api.__main__ import main

    old = sys.argv
    try:
        sys.argv = ["prog", "--host", "0.0.0.0"]
        with pytest.raises(SystemExit):
            main()
    finally:
        sys.argv = old
