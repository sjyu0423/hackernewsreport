"""M3.1 reliability: outcome taxonomy, backlog drain, daily launchd, ollama health."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from qwennews.analysis_schema import ANALYSIS_CONFIG_VERSION, ArticleAnalysis
from qwennews.analyze import AnalysisOutcome, AnalyzeRunStats, content_hash_for_article
from qwennews.backlog import backlog_counts
from qwennews.config import Config
from qwennews.launchd import generate_daily_plist, generate_user_plist, validate_plist
from qwennews.models import Article, ContentExtractionStatus
from qwennews.ollama_health import check_ollama
from qwennews.orchestrate import run_orchestration
from qwennews.storage import ArticleStore
from qwennews.story_memory import link_article
from qwennews.urls import article_id_for_url, canonicalize_url


def _uncached(
    store: ArticleStore,
    *,
    n: int,
    as_of: datetime,
    prefix: str = "backlog",
) -> list[str]:
    ids: list[str] = []
    for i in range(n):
        url = f"https://example.com/{prefix}-{i}"
        canonical = canonicalize_url(url)
        article = Article(
            id=article_id_for_url(canonical),
            source="openai",
            title=f"Acme{i} Labs Ships Orion{i} Chip With Unique Benchmark Suite",
            original_url=url,
            canonical_url=canonical,
            discovered_at=as_of - timedelta(minutes=30 - (i % 25)),
            article_text=(
                f"Acme{i} Labs published Orion{i} results with unique entity names "
                f"and product codes ORION-{i}-X so near-dupe linking keeps stories separate. "
                "This body is long enough for grounded analysis fixtures in tests."
            ),
            content_extraction_status=ContentExtractionStatus.SUCCESS,
        )
        store.upsert_article(article)
        row = store.get_article(article.id)
        assert row is not None
        row["sources"] = "openai"
        link_article(store, row)
        ids.append(article.id)
    return ids


def _save_analysis(store: ArticleStore, article_id: str) -> None:
    row = store.get_article(article_id)
    assert row is not None
    row["sources"] = row.get("sources") or "openai"
    analysis = ArticleAnalysis(
        article_id=article_id,
        category="models",
        summary="Grounded summary based on the supplied fixture article text content.",
        why_it_matters="Matters for evaluating backlog drain behavior in tests.",
        relevance_score=5,
        significance_score=5,
        evidence_sufficiency="sufficient",
        key_claims=["Fixture claim drawn from article text."],
        limitations="Fixture limitations note.",
    )
    store.save_analysis(
        article_id=article_id,
        content_hash=content_hash_for_article(row),
        model_id="test-model",
        config_version=ANALYSIS_CONFIG_VERSION,
        analysis=analysis,
    )


class _FakeClient:
    def ensure_model(self) -> None:
        return None


def test_empty_success_vs_backlog_remaining(
    store: ArticleStore, config: Config, tmp_path: Path
) -> None:
    """Incomplete backlog cycles must not be labeled empty_success."""
    config.report_dir = tmp_path / "reports"
    as_of = datetime.fromisoformat("2026-11-17T12:00:00+00:00")
    _uncached(store, n=3, as_of=as_of)

    analyzed = {"ids": []}

    def analyze_five(store_, cfg, **kwargs):  # noqa: ANN001, ANN003
        ids = list(kwargs.get("article_ids") or [])
        stats = AnalyzeRunStats()
        for aid in ids[:5]:
            _save_analysis(store_, aid)
            analyzed["ids"].append(aid)
            stats.attempted += 1
            stats.succeeded += 1
            stats.inferred += 1
            stats.outcomes.append(
                AnalysisOutcome(
                    article_id=aid, analysis=None, cached=False, content_hash="x"
                )
            )
        return stats

    # First cycle with max_analyze=1 leaves backlog
    r1 = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of,
        skip_collect=True,
        max_analyze=1,
        analyze_fn=analyze_five,
        ollama_client=_FakeClient(),  # type: ignore[arg-type]
        notify=False,
    )
    assert r1.ok
    assert r1.outcome == "backlog_remaining"
    assert r1.watermark_advanced is False
    assert r1.empty_cycle is False
    assert store.get_watermark("hourly") is None
    assert backlog_counts(store, "hourly")["active"] >= 1

    # Truly empty DB-adjacent: drain then empty cycle
    while backlog_counts(store, "hourly")["active"] > 0:
        run_orchestration(
            "hourly",
            config=config,
            store=store,
            as_of=as_of + timedelta(hours=1),
            skip_collect=True,
            max_analyze=5,
            analyze_fn=analyze_five,
            ollama_client=_FakeClient(),  # type: ignore[arg-type]
            notify=False,
        )
    r_empty = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of + timedelta(hours=2),
        skip_collect=True,
        skip_analyze=True,
        notify=False,
    )
    assert r_empty.outcome == "empty_success"
    assert r_empty.watermark_advanced is True


def test_backlog_25_with_max_analyze_5(
    store: ArticleStore, config: Config, tmp_path: Path
) -> None:
    config.report_dir = tmp_path / "reports"
    config.hourly_report_limit = 30
    as_of = datetime.fromisoformat("2026-11-17T15:00:00+00:00")
    ids = _uncached(store, n=25, as_of=as_of, prefix="drain")
    assert len(ids) == 25

    def analyze_batch(store_, cfg, **kwargs):  # noqa: ANN001, ANN003
        batch = list(kwargs.get("article_ids") or [])
        assert len(batch) <= 5
        stats = AnalyzeRunStats()
        for aid in batch:
            _save_analysis(store_, aid)
            stats.attempted += 1
            stats.succeeded += 1
            stats.inferred += 1
            stats.outcomes.append(
                AnalysisOutcome(
                    article_id=aid, analysis=None, cached=False, content_hash="x"
                )
            )
        return stats

    seen: set[str] = set()
    published_titles: list[str] = []
    for cycle in range(6):
        result = run_orchestration(
            "hourly",
            config=config,
            store=store,
            as_of=as_of + timedelta(minutes=cycle),
            skip_collect=True,
            max_analyze=5,
            analyze_fn=analyze_batch,
            ollama_client=_FakeClient(),  # type: ignore[arg-type]
            notify=False,
        )
        assert result.ok
        inferred = int(result.counts.get("inferred", 0))
        assert inferred <= 5
        for aid in ids:
            if store.get_latest_analysis(aid):
                seen.add(aid)
        if result.report_path:
            text = Path(result.report_path).read_text(encoding="utf-8")
            published_titles.append(text)
        if cycle < 4:
            assert result.outcome == "backlog_remaining"
            assert result.watermark_advanced is False
            assert store.get_watermark("hourly") is None
            # Remaining eligible still active
            assert backlog_counts(store, "hourly")["active"] > 0
        if len(seen) == 25:
            break

    assert len(seen) == 25
    # Final drain should advance watermark eventually
    final = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of + timedelta(hours=1),
        skip_collect=True,
        max_analyze=5,
        analyze_fn=analyze_batch,
        ollama_client=_FakeClient(),  # type: ignore[arg-type]
        notify=False,
    )
    assert backlog_counts(store, "hourly")["active"] == 0
    assert final.watermark_advanced is True
    assert store.get_watermark("hourly") is not None

    # Re-run same window: no duplicate story republication noise
    again = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of + timedelta(hours=1),
        skip_collect=True,
        skip_analyze=True,
        notify=False,
    )
    assert again.outcome == "empty_success"
    assert again.report_path is not None
    body = Path(again.report_path).read_text(encoding="utf-8")
    assert "No significant updates" in body


def test_failed_analysis_retry(
    store: ArticleStore, config: Config, tmp_path: Path
) -> None:
    config.report_dir = tmp_path / "reports"
    as_of = datetime.fromisoformat("2026-11-17T18:00:00+00:00")
    ids = _uncached(store, n=1, as_of=as_of, prefix="retry")

    def fail_once(store_, cfg, **kwargs):  # noqa: ANN001, ANN003
        aid = (kwargs.get("article_ids") or [ids[0]])[0]
        return AnalyzeRunStats(
            attempted=1,
            failed=1,
            errors=[f"{aid}: boom"],
            outcomes=[
                AnalysisOutcome(
                    article_id=aid, analysis=None, cached=False, error="boom", content_hash="x"
                )
            ],
        )

    bad = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of,
        skip_collect=True,
        analyze_fn=fail_once,
        ollama_client=_FakeClient(),  # type: ignore[arg-type]
        notify=False,
    )
    assert not bad.ok
    assert bad.outcome == "analyze_failed"
    assert store.get_watermark("hourly") is None
    assert backlog_counts(store, "hourly")["failed"] >= 1 or backlog_counts(store, "hourly")[
        "pending"
    ] >= 1

    def succeed(store_, cfg, **kwargs):  # noqa: ANN001, ANN003
        aid = (kwargs.get("article_ids") or ids)[0]
        _save_analysis(store_, aid)
        return AnalyzeRunStats(
            attempted=1,
            succeeded=1,
            inferred=1,
            outcomes=[
                AnalysisOutcome(
                    article_id=aid, analysis=None, cached=False, content_hash="x"
                )
            ],
        )

    good = run_orchestration(
        "hourly",
        config=config,
        store=store,
        as_of=as_of + timedelta(minutes=5),
        skip_collect=True,
        analyze_fn=succeed,
        ollama_client=_FakeClient(),  # type: ignore[arg-type]
        notify=False,
    )
    assert good.ok
    assert store.get_latest_analysis(ids[0]) is not None


def test_daily_launchagent_generation(tmp_path: Path) -> None:
    py = tmp_path / "bin" / "python3"
    py.parent.mkdir(parents=True)
    py.write_text("#!/bin/sh\n", encoding="utf-8")
    root = tmp_path / "proj"
    root.mkdir()
    logs = tmp_path / "logs"
    path, problems = generate_daily_plist(
        output=tmp_path / "daily.plist",
        python_exe=py,
        working_directory=root,
        log_dir=logs,
        local_time="07:30",
    )
    assert problems == []
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "run-daily" in text
    assert "<integer>7</integer>" in text
    assert "<integer>30</integer>" in text
    assert "StartCalendarInterval" in text
    assert validate_plist(path) == []

    # Template must fail validation (placeholders)
    tmpl = (
        Path(__file__).resolve().parents[1]
        / "packaging"
        / "launchd"
        / "com.qwennews.daily.plist.template"
    )
    assert validate_plist(tmpl)


def test_hourly_and_daily_plists_independent(tmp_path: Path) -> None:
    py = tmp_path / "python"
    py.write_text("x", encoding="utf-8")
    root = tmp_path / "root"
    root.mkdir()
    h, hp = generate_user_plist(
        output=tmp_path / "h.plist",
        python_exe=py,
        working_directory=root,
        log_dir=tmp_path / "logs",
    )
    d, dp = generate_daily_plist(
        output=tmp_path / "d.plist",
        python_exe=py,
        working_directory=root,
        log_dir=tmp_path / "logs",
        hour=8,
        minute=0,
    )
    assert hp == [] and dp == []
    assert "run-hourly" in h.read_text(encoding="utf-8")
    assert "run-daily" in d.read_text(encoding="utf-8")


def test_ollama_health_detect_only(monkeypatch: pytest.MonkeyPatch, config: Config) -> None:
    class _Resp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"models": [{"name": "qwen3:4b"}]}

    class _Client:
        def __init__(self, *a, **k):  # noqa: ANN002, ANN003
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):  # noqa: ANN002
            return False

        def get(self, path: str):
            assert path == "/api/tags"
            return _Resp()

    monkeypatch.setattr("qwennews.ollama_health.httpx.Client", _Client)
    health = check_ollama(config)
    assert health.reachable is True
    assert health.model_present is True
    assert health.to_dict()["ok"] is True

    # Down server
    class _Down:
        def __init__(self, *a, **k):  # noqa: ANN002, ANN003
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):  # noqa: ANN002
            return False

        def get(self, path: str):
            raise ConnectionError("refused")

    monkeypatch.setattr("qwennews.ollama_health.httpx.Client", _Down)
    down = check_ollama(config)
    assert down.reachable is False
    assert down.to_dict()["ok"] is False
