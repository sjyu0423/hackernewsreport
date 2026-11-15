"""End-to-end hourly/daily orchestration for Mac mini automation (M3/M3.1)."""

from __future__ import annotations

import logging
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from qwennews.analyze import analyze_articles
from qwennews.backlog import (
    backlog_counts,
    enqueue_hourly_backlog,
    mark_ready_skipped,
    mark_stories_reported,
    refresh_processing_after_analyze,
    select_articles_for_analysis,
)
from qwennews.collect import collect_news
from qwennews.config import Config, default_ranking_config_from_env, load_config
from qwennews.locking import LockBusyError, RunLock, _pid_alive
from qwennews.models import ensure_utc, utc_now
from qwennews.notify import notify_macos
from qwennews.ollama_client import OllamaClient, OllamaModelMissingError, OllamaUnavailableError
from qwennews.report import generate_report
from qwennews.storage import ArticleStore
from qwennews.story_memory import sync_stories

logger = logging.getLogger(__name__)


@dataclass
class StageResult:
    name: str
    ok: bool
    elapsed_seconds: float = 0.0
    detail: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    critical: bool = False


@dataclass
class OrchestrationResult:
    mode: str
    ok: bool
    outcome: str
    empty_cycle: bool = False
    report_path: str | None = None
    watermark_advanced: bool = False
    stages: list[StageResult] = field(default_factory=list)
    counts: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    elapsed_seconds: float = 0.0
    run_id: int | None = None


def _run_stage(
    name: str,
    fn: Callable[[], dict[str, Any]],
    *,
    critical: bool = False,
) -> StageResult:
    started = time.perf_counter()
    try:
        detail = fn()
        return StageResult(
            name=name,
            ok=True,
            elapsed_seconds=round(time.perf_counter() - started, 3),
            detail=detail,
            critical=critical,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Stage %s failed", name)
        return StageResult(
            name=name,
            ok=False,
            elapsed_seconds=round(time.perf_counter() - started, 3),
            error=str(exc),
            critical=critical,
        )


def _hourly_watermark(store: ArticleStore) -> datetime | None:
    wm_row = store.get_watermark("hourly")
    if not wm_row or not wm_row.get("watermark_at"):
        return None
    return ensure_utc(
        datetime.fromisoformat(str(wm_row["watermark_at"]).replace("Z", "+00:00"))
    )


def _classify_outcome(
    *,
    mode: str,
    meta: dict[str, Any],
    empty_report: bool,
    published: bool,
    backlog: dict[str, int],
    inferred: int,
    analysis_failed: int,
) -> tuple[str, bool]:
    """
    Return (outcome, empty_cycle).

    Distinguishes true empties from backlog / insignificant / incomplete cycles.
    """
    if meta.get("duplicate_window"):
        return "duplicate_window_skipped", True

    active = int(backlog.get("active", 0))
    pending = int(backlog.get("pending", 0)) + int(backlog.get("failed", 0))
    ready = int(backlog.get("ready", 0))

    if mode == "hourly":
        if active > 0:
            # Incomplete drain — never call this a fully successful empty cycle
            if published:
                return "backlog_remaining", False
            if pending > 0 and inferred == 0 and analysis_failed == 0:
                # Eligible awaiting analysis but this cycle analyzed none (cap?)
                return "backlog_remaining", False
            if pending > 0:
                return "backlog_remaining", False
            if ready > 0 and empty_report:
                # Ready stories existed but report selected none → insignificant
                return "no_significant_updates", False
            return "backlog_remaining", False

        if published and not empty_report:
            return "success", False
        if empty_report:
            # Fully drained, nothing to publish
            if inferred > 0 or analysis_failed > 0:
                # Analyzed this cycle but nothing reportable after drain
                return "no_significant_updates", True
            return "empty_success", True
        return "success", False

    # daily
    if meta.get("duplicate_window"):
        return "duplicate_window_skipped", True
    if published and not empty_report:
        return "success", False
    if empty_report:
        return "empty_success", True
    return "success", False


def _finalize(
    store: ArticleStore,
    run_id: int,
    result: OrchestrationResult,
    stages: list[StageResult],
    counts: dict[str, Any],
    started: float,
) -> None:
    result.stages = stages
    result.counts = counts
    result.elapsed_seconds = round(time.perf_counter() - started, 3)
    store.finish_orchestration_run(
        run_id,
        status="completed" if result.ok else "failed",
        outcome=result.outcome,
        stages={
            s.name: {
                "ok": s.ok,
                "elapsed": s.elapsed_seconds,
                "error": s.error,
                "detail": s.detail,
            }
            for s in stages
        },
        counts=counts,
        error=result.error,
        report_path=result.report_path,
        watermark_advanced=result.watermark_advanced,
        empty_cycle=result.empty_cycle,
    )


def run_orchestration(
    mode: str,
    *,
    config: Config | None = None,
    store: ArticleStore | None = None,
    as_of: datetime | None = None,
    skip_collect: bool = False,
    skip_analyze: bool = False,
    notify: bool | None = None,
    max_analyze: int | None = None,
    collect_fn: Callable[..., Any] | None = None,
    analyze_fn: Callable[..., Any] | None = None,
    report_fn: Callable[..., Any] | None = None,
    ollama_client: OllamaClient | None = None,
    acquire_lock: bool = True,
) -> OrchestrationResult:
    """
    Run collect → sync → analyze → report for hourly or daily mode.

    M3.1: hourly uses durable story_processing_state so max_analyze caps never
    discard unprocessed stories via watermark advancement.
    """
    started = time.perf_counter()
    cfg = config or load_config()
    article_store = store or ArticleStore(cfg.db_path)
    article_store.init_db()
    as_of_dt = ensure_utc(as_of or utc_now())
    assert as_of_dt is not None
    mode = mode.lower().strip()
    if mode not in {"hourly", "daily"}:
        raise ValueError(f"Unsupported orchestration mode: {mode}")

    lock_path = Path(cfg.db_path).parent / "locks" / "orchestrate.lock"
    lock = RunLock(lock_path)
    if acquire_lock:
        try:
            lock.acquire(blocking=False)
        except LockBusyError as exc:
            return OrchestrationResult(
                mode=mode,
                ok=False,
                outcome="lock_busy",
                error=str(exc),
                elapsed_seconds=round(time.perf_counter() - started, 3),
            )

    run_id = article_store.start_orchestration_run(
        mode=mode, cutoff_at=as_of_dt.isoformat().replace("+00:00", "Z")
    )
    stages: list[StageResult] = []
    counts: dict[str, Any] = {
        "articles_fetched": 0,
        "articles_new": 0,
        "cache_hits": 0,
        "inferred": 0,
        "analysis_failed": 0,
        "classified_new": 0,
        "classified_changed": 0,
        "classified_unchanged": 0,
        "backlog_pending": 0,
        "backlog_ready": 0,
        "backlog_failed": 0,
        "backlog_active": 0,
        "token_prompt_eval": 0,
        "token_eval": 0,
    }
    result = OrchestrationResult(mode=mode, ok=False, outcome="started", run_id=run_id)

    try:
        if not skip_collect:

            def _collect() -> dict[str, Any]:
                fn = collect_fn or collect_news
                stats = fn(article_store, cfg)
                counts["articles_fetched"] = stats.articles_seen
                counts["articles_new"] = stats.articles_new
                return {
                    "seen": stats.articles_seen,
                    "new": stats.articles_new,
                    "updated": stats.articles_updated,
                    "duplicates": stats.duplicates,
                    "source_errors": dict(stats.source_errors),
                    "elapsed": stats.elapsed_seconds,
                }

            stage = _run_stage("collect", _collect, critical=True)
            stages.append(stage)
            if not stage.ok:
                result.outcome = "collect_failed"
                result.error = stage.error
                _finalize(article_store, run_id, result, stages, counts, started)
                return result
            if stage.detail.get("source_errors") and stage.detail.get("seen", 0) == 0:
                stage.ok = False
                stage.error = f"All sources failed: {stage.detail['source_errors']}"
                stages[-1] = stage
                result.outcome = "collect_failed"
                result.error = stage.error
                _finalize(article_store, run_id, result, stages, counts, started)
                return result

        def _sync() -> dict[str, Any]:
            decisions = sync_stories(article_store, limit=500)
            c = Counter(d.decision.value for d in decisions)
            detail: dict[str, Any] = {"synced": len(decisions), "decisions": dict(c)}
            if mode == "hourly":
                watermark = _hourly_watermark(article_store)
                enq = enqueue_hourly_backlog(
                    article_store, watermark=watermark, as_of=as_of_dt
                )
                detail["enqueue"] = enq
                counts["classified_unchanged"] = enq.get("unchanged", 0)
                counts["classified_new"] = enq.get("enqueued_stories", 0)
                counts["classified_changed"] = enq.get("enqueued_articles", 0)
                bc = backlog_counts(article_store, "hourly")
                counts["backlog_pending"] = bc["pending"]
                counts["backlog_ready"] = bc["ready"]
                counts["backlog_failed"] = bc["failed"]
                counts["backlog_active"] = bc["active"]
            return detail

        stages.append(_run_stage("sync_stories", _sync, critical=True))
        if not stages[-1].ok:
            result.outcome = "sync_failed"
            result.error = stages[-1].error
            _finalize(article_store, run_id, result, stages, counts, started)
            return result

        if not skip_analyze:
            max_n = max_analyze if max_analyze is not None else cfg.max_analyze_per_cycle

            def _analyze() -> dict[str, Any]:
                article_ids: list[str] | None = None
                story_ids: list[str] = []
                if mode == "hourly":
                    article_ids, story_ids = select_articles_for_analysis(
                        article_store, mode="hourly", limit=max_n
                    )
                    if not article_ids:
                        bc = backlog_counts(article_store, "hourly")
                        counts["backlog_pending"] = bc["pending"]
                        counts["backlog_ready"] = bc["ready"]
                        counts["backlog_failed"] = bc["failed"]
                        counts["backlog_active"] = bc["active"]
                        return {
                            "attempted": 0,
                            "succeeded": 0,
                            "failed": 0,
                            "cached": 0,
                            "inferred": 0,
                            "errors": [],
                            "elapsed": 0.0,
                            "skipped_no_eligible": True,
                            "backlog": bc,
                        }

                client = ollama_client or OllamaClient(
                    base_url=cfg.ollama_base_url,
                    model=cfg.ollama_model,
                    timeout_seconds=cfg.ollama_timeout,
                    num_predict=cfg.ollama_num_predict,
                    think=cfg.ollama_think,
                    temperature=cfg.ollama_temperature,
                )
                try:
                    client.ensure_model()
                except (OllamaUnavailableError, OllamaModelMissingError):
                    raise

                fn = analyze_fn or analyze_articles
                stats = fn(
                    article_store,
                    cfg,
                    limit=max_n,
                    hours=24,
                    force=False,
                    article_ids=article_ids,
                    client=client,
                )
                counts["cache_hits"] = stats.cached
                counts["inferred"] = stats.inferred
                counts["analysis_failed"] = stats.failed
                prompt_tok = 0
                eval_tok = 0
                failed_ids: set[str] = set()
                for outcome in getattr(stats, "outcomes", []) or []:
                    if outcome.analysis is None and not outcome.cached:
                        failed_ids.add(str(outcome.article_id))
                    metrics = getattr(outcome, "metrics", None)
                    if metrics is None:
                        continue
                    if metrics.prompt_eval_count:
                        prompt_tok += metrics.prompt_eval_count
                    if metrics.eval_count:
                        eval_tok += metrics.eval_count
                counts["token_prompt_eval"] = prompt_tok
                counts["token_eval"] = eval_tok

                if mode == "hourly" and (story_ids or article_ids):
                    refresh_processing_after_analyze(
                        article_store,
                        list(article_ids or []),
                        story_ids,
                        mode="hourly",
                        failed_article_ids=failed_ids,
                    )
                    bc = backlog_counts(article_store, "hourly")
                    counts["backlog_pending"] = bc["pending"]
                    counts["backlog_ready"] = bc["ready"]
                    counts["backlog_failed"] = bc["failed"]
                    counts["backlog_active"] = bc["active"]

                if stats.errors and stats.attempted == 0:
                    err0 = stats.errors[0].lower()
                    if "unavailable" in err0 or "not installed" in err0:
                        raise OllamaUnavailableError(stats.errors[0])
                return {
                    "attempted": stats.attempted,
                    "succeeded": stats.succeeded,
                    "failed": stats.failed,
                    "cached": stats.cached,
                    "inferred": stats.inferred,
                    "errors": list(stats.errors),
                    "elapsed": stats.elapsed_seconds,
                    "story_ids": story_ids,
                }

            stage = _run_stage("analyze", _analyze, critical=True)
            stages.append(stage)
            if not stage.ok:
                err = (stage.error or "").lower()
                if (
                    "unavailable" in err
                    or "not installed" in err
                    or "missing" in err
                    or "timed out" in err
                ):
                    result.outcome = "ollama_unavailable"
                else:
                    result.outcome = "analyze_failed"
                result.error = stage.error
                _finalize(article_store, run_id, result, stages, counts, started)
                return result
            if (
                stage.detail.get("failed", 0)
                and stage.detail.get("succeeded", 0) == 0
                and stage.detail.get("attempted", 0) > 0
            ):
                result.outcome = "analyze_failed"
                result.error = "All analyses failed"
                stages[-1].ok = False
                _finalize(article_store, run_id, result, stages, counts, started)
                return result

        # Refresh backlog counts before report / watermark decision
        if mode == "hourly":
            bc = backlog_counts(article_store, "hourly")
            counts["backlog_pending"] = bc["pending"]
            counts["backlog_ready"] = bc["ready"]
            counts["backlog_failed"] = bc["failed"]
            counts["backlog_active"] = bc["active"]

        def _report() -> dict[str, Any]:
            fn = report_fn or generate_report
            limit = cfg.hourly_report_limit if mode == "hourly" else cfg.daily_report_limit
            # Hourly: orchestrator owns watermark advancement after backlog drain.
            advance = mode != "hourly"
            markdown, path, meta = fn(
                article_store,
                hours=1 if mode == "hourly" else 24,
                limit=limit,
                output_dir=cfg.report_dir,
                mode=mode,
                as_of=as_of_dt,
                ranking_config=default_ranking_config_from_env(),
                sync=False,
                advance_watermark=advance,
            )
            reported_ids = list(meta.get("reported_story_ids") or [])
            if mode == "hourly" and reported_ids and path is not None:
                mark_stories_reported(article_store, reported_ids, mode="hourly")

            empty = bool(meta.get("duplicate_window")) or (
                int(meta.get("new_count", 0)) == 0
                and int(meta.get("ongoing_count", 0)) == 0
                and int(meta.get("story_count", 0)) == 0
            ) or ("No significant updates" in markdown)

            skipped = 0
            if mode == "hourly":
                bc_mid = backlog_counts(article_store, "hourly")
                # Ready stories with empty selection and no article backlog left →
                # treated as not significant (do not leave them blocking the watermark).
                if (
                    empty
                    and bc_mid.get("pending_articles", 0) == 0
                    and bc_mid.get("failed_articles", 0) == 0
                    and bc_mid["ready"] > 0
                ):
                    skipped = mark_ready_skipped(article_store, mode="hourly")
                    bc_mid = backlog_counts(article_store, "hourly")

                counts["backlog_pending"] = bc_mid["pending"]
                counts["backlog_ready"] = bc_mid["ready"]
                counts["backlog_failed"] = bc_mid["failed"]
                counts["backlog_active"] = bc_mid["active"]

                # Advance watermark only when no active backlog remains and persist ok
                if bc_mid["active"] == 0 and path is not None and not meta.get(
                    "persist_failed"
                ):
                    article_store.set_watermark(
                        "hourly",
                        as_of_dt.isoformat().replace("+00:00", "Z"),
                        last_report_id=None,
                    )
                    # Also mark reported timestamps for stories already handled above
                    meta["watermark_advanced"] = True
                else:
                    meta["watermark_advanced"] = False

            return {
                "path": str(path) if path else None,
                "meta": meta,
                "markdown_len": len(markdown),
                "empty": empty,
                "skipped_ready": skipped,
            }

        stage = _run_stage("report", _report, critical=True)
        stages.append(stage)
        if not stage.ok or stage.detail.get("meta", {}).get("persist_failed"):
            result.outcome = "report_persist_failed"
            result.error = stage.error or "persist_failed"
            result.watermark_advanced = False
            _finalize(article_store, run_id, result, stages, counts, started)
            return result

        # Final backlog snapshot
        if mode == "hourly":
            bc = backlog_counts(article_store, "hourly")
            counts["backlog_pending"] = bc["pending"]
            counts["backlog_ready"] = bc["ready"]
            counts["backlog_failed"] = bc["failed"]
            counts["backlog_active"] = bc["active"]

        meta = stage.detail.get("meta") or {}
        result.report_path = stage.detail.get("path")
        result.watermark_advanced = bool(meta.get("watermark_advanced"))
        empty_report = bool(stage.detail.get("empty"))
        published = result.report_path is not None and not meta.get("persist_failed")

        outcome, empty_cycle = _classify_outcome(
            mode=mode,
            meta=meta,
            empty_report=empty_report,
            published=published and not empty_report,
            backlog={
                "pending": counts.get("backlog_pending", 0),
                "ready": counts.get("backlog_ready", 0),
                "failed": counts.get("backlog_failed", 0),
                "active": counts.get("backlog_active", 0),
            },
            inferred=int(counts.get("inferred", 0)),
            analysis_failed=int(counts.get("analysis_failed", 0)),
        )
        # Special case: empty report published, backlog drained → empty_success /
        # no_significant_updates already classified; published flag for empty file
        if (
            outcome == "empty_success"
            and empty_report
            and int(counts.get("inferred", 0)) == 0
            and int(counts.get("backlog_active", 0)) == 0
        ):
            pass
        result.outcome = outcome
        result.empty_cycle = empty_cycle
        result.ok = True

        do_notify = cfg.notify_on_success if notify is None else notify
        if result.ok and result.report_path and do_notify:
            if result.outcome == "backlog_remaining":
                body = (
                    f"{mode}: backlog remaining "
                    f"(pending={counts.get('backlog_pending', 0)})"
                )
            elif empty_cycle or result.outcome in {
                "empty_success",
                "no_significant_updates",
            }:
                body = f"{mode} cycle: {result.outcome}"
            else:
                n = meta.get("story_count") or (
                    int(meta.get("new_count", 0)) + int(meta.get("ongoing_count", 0))
                )
                body = f"{mode} report published ({n} stories)"
            notify_macos("QwenNews", body, enabled=True)

        _finalize(article_store, run_id, result, stages, counts, started)
        return result
    finally:
        if acquire_lock:
            lock.release()


def orchestration_status(store: ArticleStore, config: Config) -> dict[str, Any]:
    """Summary for `python -m qwennews status`."""
    store.init_db()
    lock_path = Path(config.db_path).parent / "locks" / "orchestrate.lock"
    lock_held = False
    holder = None
    if lock_path.exists():
        raw = lock_path.read_text(encoding="utf-8").strip()
        holder = raw
        if raw:
            lock_held = _pid_alive(raw.split("|", 1)[0])
    bc = backlog_counts(store, "hourly")
    return {
        "db_path": str(store.db_path),
        "report_dir": str(config.report_dir),
        "model": config.ollama_model,
        "hourly_watermark": store.get_watermark("hourly"),
        "daily_watermark": store.get_watermark("daily"),
        "hourly_backlog": bc,
        "lock_path": str(lock_path),
        "lock_held": lock_held,
        "lock_holder": holder,
        "recent_runs": store.recent_orchestration_runs(limit=8),
        "article_count": store.stats().get("article_count"),
        "analysis_count": store.analysis_count(),
        "daily_local_time": config.daily_local_time,
        "daily_timezone": config.daily_timezone,
        "notify_on_success": config.notify_on_success,
        "max_analyze_per_cycle": config.max_analyze_per_cycle,
    }


def next_daily_as_of(config: Config, *, now: datetime | None = None) -> datetime:
    """Compute the daily report as-of instant for today's configured local delivery time."""
    tz = ZoneInfo(config.daily_timezone)
    local_now = (now or utc_now()).astimezone(tz)
    hour, minute = [int(x) for x in config.daily_local_time.split(":", 1)]
    local_target = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return local_target.astimezone(ZoneInfo("UTC"))
