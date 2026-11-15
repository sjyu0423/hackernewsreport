"""M3 orchestration, mode-specific report state, locking, launchd, notify."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from qwennews.analysis_schema import ANALYSIS_CONFIG_VERSION, ArticleAnalysis
from qwennews.analyze import AnalyzeRunStats, content_hash_for_article
from qwennews.config import Config
from qwennews.launchd import generate_user_plist, render_plist, validate_plist
from qwennews.locking import RunLock
from qwennews.models import Article, CollectionStats, ContentExtractionStatus, utc_now
from qwennews.notify import notify_macos
from qwennews.orchestrate import run_orchestration
from qwennews.storage import ArticleStore
from qwennews.story_memory import link_article
from qwennews.urls import article_id_for_url, canonicalize_url

FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures" / "m2_stories.json").read_text(encoding="utf-8")
)


def _insert(
    store: ArticleStore,
    *,
    title: str,
    source: str,
    url: str,
    text: str,
    discovered_at=None,
) -> dict:
    canonical = canonicalize_url(url)
    article = Article(
        id=article_id_for_url(canonical),
        source=source,
        title=title,
        original_url=url,
        canonical_url=canonical,
        discovered_at=discovered_at or utc_now(),
        article_text=text,
        content_extraction_status=ContentExtractionStatus.SUCCESS,
    )
    store.upsert_article(article)
    row = store.get_article(article.id)
    assert row is not None
    row["sources"] = source
    analysis = ArticleAnalysis(
        article_id=article.id,
        category="models",
        summary="Grounded summary based on the supplied fixture article text content.",
        why_it_matters="Matters for evaluating orchestration behavior in tests.",
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
    return row


def _ok_collect(store, config):  # noqa: ANN001
    return CollectionStats(articles_seen=3, articles_new=1, elapsed_seconds=0.1)


def _fail_collect(store, config):  # noqa: ANN001
    stats = CollectionStats(articles_seen=0, elapsed_seconds=0.05)
    stats.source_errors = {"hackernews": "boom", "openai": "boom"}
    return stats


def _ok_analyze(*args, **kwargs):  # noqa: ANN002, ANN003
    return AnalyzeRunStats(attempted=1, succeeded=1, cached=1, inferred=0, elapsed_seconds=0.01)


def _fail_all_analyze(*args, **kwargs):  # noqa: ANN002, ANN003
    return AnalyzeRunStats(
        attempted=2,
        succeeded=0,
        failed=2,
        errors=["a1: parse", "a2: parse"],
        elapsed_seconds=0.01,
    )


def _partial_analyze(*args, **kwargs):  # noqa: ANN002, ANN003
    return AnalyzeRunStats(
        attempted=2,
        succeeded=1,
        failed=1,
        cached=0,
        inferred=1,
        errors=["a2: isolated failure"],
        elapsed_seconds=0.02,
    )


def _ollama_down_analyze(*args, **kwargs):  # noqa: ANN002, ANN003
    return AnalyzeRunStats(
        attempted=0,
        succeeded=0,
        failed=0,
        errors=["Ollama unavailable at http://127.0.0.1:9"],
        elapsed_seconds=0.0,
    )


class _FakeClient:
    def ensure_model(self) -> None:
        return None


class _DownClient:
    def ensure_model(self) -> None:
        from qwennews.ollama_client import OllamaUnavailableError

        raise OllamaUnavailableError("Ollama unavailable")


def _insert_uncached(
    store: ArticleStore,
    *,
    title: str = "Uncached Fresh Model Release",
    url: str = "https://example.com/uncached-fresh",
    discovered_at=None,
) -> dict:
    """Insert an article with body text but no cached analysis."""
    canonical = canonicalize_url(url)
    article = Article(
        id=article_id_for_url(canonical),
        source="openai",
        title=title,
        original_url=url,
        canonical_url=canonical,
        discovered_at=discovered_at or utc_now(),
        article_text="Fresh article body about a model release with enough text for analysis.",
        content_extraction_status=ContentExtractionStatus.SUCCESS,
    )
    store.upsert_article(article)
    row = store.get_article(article.id)
    assert row is not None
    row["sources"] = "openai"
    link_article(store, row)
    return row


def test_orchestration_sequence_order(store: ArticleStore, config: Config, tmp_path: Path) -> None:
    config.report_dir = tmp_path / "reports"
    config.db_path = store.db_path
    _insert_uncached(store)
    order: list[str] = []

    def collect(store_, cfg):  # noqa: ANN001
        order.append("collect")
        return _ok_collect(store_, cfg)

    def analyze(*a, **k):  # noqa: ANN002, ANN003
        order.append("analyze")
        return _ok_analyze()

    def report(*a, **k):  # noqa: ANN002, ANN003
        order.append("report")
        path = config.report_dir / "t.md"
        config.report_dir.mkdir(parents=True, exist_ok=True)
        path.write_text("# ok\n", encoding="utf-8")
        return "# ok\n", path, {"watermark_advanced": True, "story_count": 0, "new_count": 0}

    result = run_orchestration(
        "hourly",
        config=config,
        store=store,
        skip_collect=False,
        collect_fn=collect,
        analyze_fn=analyze,
        report_fn=report,
        ollama_client=_FakeClient(),  # type: ignore[arg-type]
        notify=False,
        acquire_lock=True,
    )
    assert result.ok
    assert order == ["collect", "analyze", "report"]
    assert any(s.name == "sync_stories" for s in result.stages)


def test_successful_hourly_report(store: ArticleStore, config: Config, tmp_path: Path) -> None:
    config.report_dir = tmp_path / "reports"
    as_of = datetime.fromisoformat("2026-11-15T18:00:00+00:00")
    row = _insert(
        store,
        title=FIXTURES["gemini_hydrogen"]["title"],
        source=FIXTURES["gemini_hydrogen"]["source"],
        url=FIXTURES["gemini_hydrogen"]["url"],
        text=FIXTURES["gemini_hydrogen"]["text"],
        discovered_at=as_of - timedelta(hours=1),
    )
    link_article(store, row)

    result = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of,
        skip_collect=True,
        skip_analyze=True,
        notify=False,
    )
    assert result.ok
    assert result.outcome == "success"
    assert result.report_path is not None
    assert result.watermark_advanced is True
    assert Path(result.report_path).is_file()
    assert store.get_watermark("hourly") is not None


def test_empty_but_successful_cycle(store: ArticleStore, config: Config, tmp_path: Path) -> None:
    config.report_dir = tmp_path / "reports"
    as_of = datetime.fromisoformat("2026-11-15T19:00:00+00:00")
    result = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of,
        skip_collect=True,
        skip_analyze=True,
        notify=False,
    )
    assert result.ok
    assert result.empty_cycle is True
    assert result.outcome == "empty_success"
    assert result.watermark_advanced is True


def test_source_failure_and_recovery(store: ArticleStore, config: Config, tmp_path: Path) -> None:
    config.report_dir = tmp_path / "reports"
    as_of = datetime.fromisoformat("2026-11-15T20:00:00+00:00")
    bad = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of,
        collect_fn=_fail_collect,
        skip_analyze=True,
        notify=False,
    )
    assert not bad.ok
    assert bad.outcome == "collect_failed"
    assert store.get_watermark("hourly") is None

    row = _insert(
        store,
        title=FIXTURES["gemini_hydrogen"]["title"],
        source=FIXTURES["gemini_hydrogen"]["source"],
        url=FIXTURES["gemini_hydrogen"]["url"],
        text=FIXTURES["gemini_hydrogen"]["text"],
        discovered_at=as_of - timedelta(minutes=30),
    )
    link_article(store, row)
    good = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of,
        collect_fn=_ok_collect,
        skip_analyze=True,
        notify=False,
    )
    assert good.ok
    assert good.watermark_advanced is True


def test_ollama_unavailable(store: ArticleStore, config: Config, tmp_path: Path) -> None:
    config.report_dir = tmp_path / "reports"
    _insert_uncached(store, url="https://example.com/needs-ollama")
    result = run_orchestration(
        "hourly",
        config=config,
        store=store,
        skip_collect=True,
        analyze_fn=_ollama_down_analyze,
        ollama_client=_DownClient(),  # type: ignore[arg-type]
        notify=False,
    )
    assert not result.ok
    assert result.outcome == "ollama_unavailable"
    assert store.get_watermark("hourly") is None


def test_partial_analysis_failure_continues(
    store: ArticleStore, config: Config, tmp_path: Path
) -> None:
    config.report_dir = tmp_path / "reports"
    as_of = datetime.fromisoformat("2026-11-15T21:00:00+00:00")
    row = _insert(
        store,
        title=FIXTURES["gemini_hydrogen"]["title"],
        source=FIXTURES["gemini_hydrogen"]["source"],
        url=FIXTURES["gemini_hydrogen"]["url"],
        text=FIXTURES["gemini_hydrogen"]["text"],
        discovered_at=as_of - timedelta(hours=1),
    )
    link_article(store, row)
    _insert_uncached(
        store,
        url="https://example.com/partial-fail",
        discovered_at=as_of - timedelta(minutes=30),
    )
    result = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of,
        skip_collect=True,
        analyze_fn=_partial_analyze,
        ollama_client=_FakeClient(),  # type: ignore[arg-type]
        notify=False,
    )
    assert result.ok
    assert result.counts["analysis_failed"] == 1
    assert result.counts["inferred"] == 1


def test_report_persist_failure_no_watermark(
    store: ArticleStore, config: Config, tmp_path: Path
) -> None:
    config.report_dir = tmp_path / "reports"
    as_of = datetime.fromisoformat("2026-11-15T22:00:00+00:00")
    row = _insert(
        store,
        title=FIXTURES["gemini_hydrogen"]["title"],
        source=FIXTURES["gemini_hydrogen"]["source"],
        url=FIXTURES["gemini_hydrogen"]["url"],
        text=FIXTURES["gemini_hydrogen"]["text"],
        discovered_at=as_of - timedelta(hours=1),
    )
    link_article(store, row)

    def boom_report(*a, **k):  # noqa: ANN002, ANN003
        return "# x\n", None, {"persist_failed": True, "watermark_advanced": False}

    result = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of,
        skip_collect=True,
        skip_analyze=True,
        report_fn=boom_report,
        notify=False,
    )
    assert not result.ok
    assert result.outcome == "report_persist_failed"
    assert result.watermark_advanced is False
    assert store.get_watermark("hourly") is None


def test_watermark_rollback_independent_modes(
    store: ArticleStore, config: Config, tmp_path: Path
) -> None:
    """Hourly publication must not suppress daily and vice versa."""
    config.report_dir = tmp_path / "reports"
    as_of = datetime.fromisoformat("2026-11-15T23:00:00+00:00")
    row = _insert(
        store,
        title=FIXTURES["gemini_hydrogen"]["title"],
        source=FIXTURES["gemini_hydrogen"]["source"],
        url=FIXTURES["gemini_hydrogen"]["url"],
        text=FIXTURES["gemini_hydrogen"]["text"],
        discovered_at=as_of - timedelta(hours=2),
    )
    link_article(store, row)

    h = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of,
        skip_collect=True,
        skip_analyze=True,
        notify=False,
    )
    assert h.ok and h.watermark_advanced
    # Second hourly empties delta
    h2 = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of + timedelta(hours=1),
        skip_collect=True,
        skip_analyze=True,
        notify=False,
    )
    assert h2.ok and h2.empty_cycle

    d = run_orchestration(
        "daily",
        config=config,
        store=store,
        as_of=as_of + timedelta(hours=1),
        skip_collect=True,
        skip_analyze=True,
        notify=False,
    )
    assert d.ok
    assert d.watermark_advanced
    assert "Gemini" in Path(d.report_path).read_text(encoding="utf-8")  # type: ignore[arg-type]
    # Mode-specific story marks
    stories = store.list_stories()
    assert stories
    sid = stories[0]["id"]
    assert store.get_story_reported_at(sid, "hourly") is not None
    assert store.get_story_reported_at(sid, "daily") is not None


def test_overlapping_run_prevention(store: ArticleStore, config: Config, tmp_path: Path) -> None:
    config.report_dir = tmp_path / "reports"
    lock_path = Path(config.db_path).parent / "locks" / "orchestrate.lock"
    holder = RunLock(lock_path)
    holder.acquire(blocking=False)
    try:
        result = run_orchestration(
            "hourly",
            config=config,
            store=store,
            skip_collect=True,
            skip_analyze=True,
            notify=False,
            acquire_lock=True,
        )
        assert not result.ok
        assert result.outcome == "lock_busy"
    finally:
        holder.release()


def test_same_window_duplicate_daily(store: ArticleStore, config: Config, tmp_path: Path) -> None:
    config.report_dir = tmp_path / "reports"
    as_of = datetime.fromisoformat("2026-11-16T12:00:00+00:00")
    row = _insert(
        store,
        title=FIXTURES["gemini_hydrogen"]["title"],
        source=FIXTURES["gemini_hydrogen"]["source"],
        url=FIXTURES["gemini_hydrogen"]["url"],
        text=FIXTURES["gemini_hydrogen"]["text"],
        discovered_at=as_of - timedelta(hours=3),
    )
    link_article(store, row)
    first = run_orchestration(
        "daily",
        config=config,
        store=store,
        as_of=as_of,
        skip_collect=True,
        skip_analyze=True,
        notify=False,
    )
    assert first.ok and first.report_path
    second = run_orchestration(
        "daily",
        config=config,
        store=store,
        as_of=as_of,
        skip_collect=True,
        skip_analyze=True,
        notify=False,
    )
    assert second.ok
    assert second.outcome == "duplicate_window_skipped"
    assert second.report_path is None


def test_missed_schedule_no_burst(store: ArticleStore, config: Config, tmp_path: Path) -> None:
    """Wake recovery: a single run advances one watermark, no catch-up loop."""
    config.report_dir = tmp_path / "reports"
    as_of = datetime.fromisoformat("2026-11-16T08:00:00+00:00")
    row = _insert(
        store,
        title=FIXTURES["gemini_hydrogen"]["title"],
        source=FIXTURES["gemini_hydrogen"]["source"],
        url=FIXTURES["gemini_hydrogen"]["url"] + "?v=wake",
        text=FIXTURES["gemini_hydrogen"]["text"],
        discovered_at=as_of - timedelta(hours=5),
    )
    link_article(store, row)
    # Simulate missed hours by jumping as_of forward once — one orchestration only
    result = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of,
        skip_collect=True,
        skip_analyze=True,
        notify=False,
    )
    assert result.ok
    runs = store.recent_orchestration_runs(mode="hourly", limit=20)
    assert len(runs) == 1
    assert store.get_watermark("hourly")["watermark_at"].startswith("2026-11-16T08:00:00")


def test_unchanged_skips_inference(
    store: ArticleStore, config: Config, tmp_path: Path
) -> None:
    """With a watermark, unchanged stories must not trigger model calls."""
    config.report_dir = tmp_path / "reports"
    as_of = datetime.fromisoformat("2026-11-16T09:30:00+00:00")
    row = _insert(
        store,
        title=FIXTURES["gemini_hydrogen"]["title"],
        source=FIXTURES["gemini_hydrogen"]["source"],
        url=FIXTURES["gemini_hydrogen"]["url"] + "?unchanged=1",
        text=FIXTURES["gemini_hydrogen"]["text"],
        discovered_at=as_of - timedelta(hours=3),
    )
    link_article(store, row)
    # Establish watermark after the story
    run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of - timedelta(hours=1),
        skip_collect=True,
        skip_analyze=True,
        notify=False,
    )
    calls = {"n": 0}

    def counting_analyze(*a, **k):  # noqa: ANN002, ANN003
        calls["n"] += 1
        return AnalyzeRunStats(attempted=1, succeeded=1, inferred=1)

    result = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of,
        skip_collect=True,
        analyze_fn=counting_analyze,
        ollama_client=_FakeClient(),  # type: ignore[arg-type]
        notify=False,
    )
    assert result.ok
    assert calls["n"] == 0
    assert result.counts["inferred"] == 0
    assert result.counts["classified_unchanged"] >= 1


def test_cache_reuse(store: ArticleStore, config: Config, tmp_path: Path) -> None:
    config.report_dir = tmp_path / "reports"
    as_of = datetime.fromisoformat("2026-11-16T09:00:00+00:00")
    row = _insert_uncached(
        store,
        url="https://example.com/cache-reuse",
        discovered_at=as_of - timedelta(hours=1),
    )
    analyze_calls = {"n": 0}

    def counting_analyze(store_, cfg, **kwargs):  # noqa: ANN001, ANN003
        analyze_calls["n"] += 1
        # Persist analysis so the article leaves the pending queue (cache reuse)
        aid = (kwargs.get("article_ids") or [row["id"]])[0]
        from qwennews.analysis_schema import ANALYSIS_CONFIG_VERSION, ArticleAnalysis
        from qwennews.analyze import content_hash_for_article

        art = store_.get_article(aid)
        art["sources"] = "openai"
        analysis = ArticleAnalysis(
            article_id=aid,
            category="models",
            summary="Grounded summary based on the supplied fixture article text content.",
            why_it_matters="Matters for evaluating cache reuse behavior in tests.",
            relevance_score=5,
            significance_score=5,
            evidence_sufficiency="sufficient",
            key_claims=["Fixture claim drawn from article text."],
            limitations="Fixture limitations note.",
        )
        store_.save_analysis(
            article_id=aid,
            content_hash=content_hash_for_article(art),
            model_id="test-model",
            config_version=ANALYSIS_CONFIG_VERSION,
            analysis=analysis,
        )
        return AnalyzeRunStats(attempted=1, succeeded=1, cached=1, inferred=0)

    r1 = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of,
        skip_collect=True,
        analyze_fn=counting_analyze,
        ollama_client=_FakeClient(),  # type: ignore[arg-type]
        notify=False,
    )
    # Second cycle: drained / unchanged → analyze skipped
    r2 = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of + timedelta(hours=1),
        skip_collect=True,
        analyze_fn=counting_analyze,
        ollama_client=_FakeClient(),  # type: ignore[arg-type]
        notify=False,
    )
    assert r1.ok and r2.ok
    assert analyze_calls["n"] == 1
    assert r1.counts["cache_hits"] == 1
    assert r2.counts["inferred"] == 0


def test_launchagent_generation_safe(tmp_path: Path) -> None:
    py = tmp_path / "bin" / "python3"
    py.parent.mkdir(parents=True)
    py.write_text("#!/bin/sh\n", encoding="utf-8")
    root = tmp_path / "proj"
    root.mkdir()
    logs = tmp_path / "logs"
    path, problems = generate_user_plist(
        output=tmp_path / "out.plist",
        python_exe=py,
        working_directory=root,
        log_dir=logs,
    )
    assert problems == []
    assert path.is_file()
    # Template with placeholders must fail validation
    tmpl = Path(__file__).resolve().parents[1] / "packaging" / "launchd" / (
        "com.qwennews.hourly.plist.template"
    )
    assert validate_plist(tmpl)
    # Aggressive interval rejected
    with pytest.raises(ValueError):
        render_plist(
            python_exe=py,
            working_directory=root,
            log_dir=logs,
            start_interval_seconds=60,
        )


def test_notification_failure_does_not_invalidate(
    store: ArticleStore, config: Config, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config.report_dir = tmp_path / "reports"
    as_of = datetime.fromisoformat("2026-11-16T10:00:00+00:00")
    row = _insert(
        store,
        title=FIXTURES["gemini_hydrogen"]["title"],
        source=FIXTURES["gemini_hydrogen"]["source"],
        url=FIXTURES["gemini_hydrogen"]["url"] + "?notify=1",
        text=FIXTURES["gemini_hydrogen"]["text"],
        discovered_at=as_of - timedelta(hours=1),
    )
    link_article(store, row)

    def boom_notify(*a, **k):  # noqa: ANN002, ANN003
        raise RuntimeError("osascript exploded")

    # notify_macos swallows exceptions; force True path that still returns False
    monkeypatch.setattr(
        "qwennews.orchestrate.notify_macos",
        lambda *a, **k: False,
    )
    result = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of,
        skip_collect=True,
        skip_analyze=True,
        notify=True,
    )
    assert result.ok
    assert result.report_path is not None
    assert result.watermark_advanced is True

    # Direct unit: failure returns False, never raises
    monkeypatch.setattr("qwennews.notify.shutil.which", lambda _: "/usr/bin/osascript")
    monkeypatch.setattr(
        "qwennews.notify.subprocess.run",
        MagicMock(side_effect=RuntimeError("fail")),
    )
    assert notify_macos("t", "b", enabled=True) is False


def test_failed_all_analyze_stops_report(
    store: ArticleStore, config: Config, tmp_path: Path
) -> None:
    config.report_dir = tmp_path / "reports"
    _insert_uncached(store, url="https://example.com/all-fail")
    result = run_orchestration(
        "hourly",
        config=config,
        store=store,
        skip_collect=True,
        analyze_fn=_fail_all_analyze,
        ollama_client=_FakeClient(),  # type: ignore[arg-type]
        notify=False,
    )
    assert not result.ok
    assert result.outcome == "analyze_failed"
    assert store.get_watermark("hourly") is None


def test_articles_during_cycle_not_marked_reported(
    store: ArticleStore, config: Config, tmp_path: Path
) -> None:
    """Articles inserted after cutoff must not be marked reported by this cycle."""
    config.report_dir = tmp_path / "reports"
    as_of = datetime.fromisoformat("2026-11-16T11:00:00+00:00")
    row = _insert(
        store,
        title=FIXTURES["gemini_hydrogen"]["title"],
        source=FIXTURES["gemini_hydrogen"]["source"],
        url=FIXTURES["gemini_hydrogen"]["url"] + "?cut=1",
        text=FIXTURES["gemini_hydrogen"]["text"],
        discovered_at=as_of - timedelta(hours=1),
    )
    link_article(store, row)
    late = _insert(
        store,
        title="Late Arriving Story About Widgets",
        source="openai",
        url="https://example.com/late-widgets",
        text="Late article body about widgets that arrived mid-cycle and should not be marked.",
        discovered_at=as_of + timedelta(minutes=5),
    )
    link_article(store, late)

    result = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of,
        skip_collect=True,
        skip_analyze=True,
        notify=False,
    )
    assert result.ok
    late_stories = [
        s
        for s in store.list_stories()
        if "Late" in (s.get("title") or "") or "Widget" in (s.get("title") or "")
    ]
    for s in late_stories:
        assert store.get_story_reported_at(s["id"], "hourly") is None
    # Late article was after cutoff; cycle may still hold backlog for in-window work
    assert result.outcome in {
        "success",
        "empty_success",
        "backlog_remaining",
        "no_significant_updates",
    }
