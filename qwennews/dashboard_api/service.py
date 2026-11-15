"""Assemble dashboard DTOs from the read-only store."""

from __future__ import annotations

from typing import Any

from qwennews.readonly_store import ReadOnlyStore, parse_analysis_json, safe_http_url


def classify_report_kind(row: dict[str, Any]) -> str:
    md = (row.get("markdown") or row.get("markdown_preview") or "").lower()
    if "no significant updates" in md or (row.get("story_count") or 0) == 0:
        if row.get("mode") == "hourly":
            return "empty"
    if "new developments" in md:
        return "new"
    if "ongoing" in md or "significant" in md:
        return "update"
    if (row.get("story_count") or 0) > 0:
        return "new"
    return "unknown"


def report_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "mode": row.get("mode"),
        "created_at": row.get("created_at"),
        "as_of": row.get("as_of"),
        "window_start": row.get("window_start"),
        "story_count": int(row.get("story_count") or 0),
        "significant_only": bool(row.get("significant_only")),
        "status": row.get("status"),
        "markdown_preview": row.get("markdown_preview") or (row.get("markdown") or "")[:400],
        "kind": classify_report_kind(row),
    }


def report_detail(row: dict[str, Any]) -> dict[str, Any]:
    base = report_summary(row)
    base["markdown"] = row.get("markdown") or ""
    base["hours"] = row.get("hours")
    return base


def _article_card(store: ReadOnlyStore, art: dict[str, Any]) -> dict[str, Any]:
    analysis_row = store.get_latest_analysis(str(art["id"]))
    parsed = parse_analysis_json(analysis_row.get("analysis_json") if analysis_row else None)
    url = safe_http_url(art.get("canonical_url") or art.get("original_url"))
    return {
        "id": str(art["id"]),
        "title": art.get("title") or "Untitled",
        "canonical_url": url,
        "sources": art.get("sources"),
        "discovered_at": art.get("discovered_at"),
        "published_at": art.get("published_at"),
        "link_reason": art.get("link_reason"),
        "summary": (parsed or {}).get("summary"),
        "why_it_matters": (parsed or {}).get("why_it_matters"),
        "category": (parsed or {}).get("category") or None,
        "relevance_score": (parsed or {}).get("relevance_score"),
        "significance_score": (parsed or {}).get("significance_score"),
    }


def story_card(
    store: ReadOnlyStore,
    story: dict[str, Any],
    *,
    include_articles: bool = True,
) -> dict[str, Any]:
    arts = store.list_story_articles(story["id"])
    cards = [_article_card(store, a) for a in arts]
    primary = None
    if cards:
        # Prefer article with analysis and highest significance
        scored = sorted(
            cards,
            key=lambda c: (
                1 if c.get("summary") else 0,
                c.get("significance_score") or 0,
                c.get("relevance_score") or 0,
            ),
            reverse=True,
        )
        primary = scored[0]
    return {
        "id": story["id"],
        "title": story.get("title") or (primary or {}).get("title") or "Untitled",
        "category": story.get("category") or (primary or {}).get("category"),
        "first_seen_at": story.get("first_seen_at"),
        "last_seen_at": story.get("last_seen_at"),
        "significant_update_at": story.get("significant_update_at"),
        "article_count": len(arts),
        "primary": primary,
        "articles": cards if include_articles else [],
    }


def build_today(store: ReadOnlyStore, *, story_limit: int = 15) -> dict[str, Any]:
    daily = store.latest_report(mode="daily")
    source = "daily"
    fallback_reason = None
    report = daily
    if report is None:
        report = store.latest_report(mode="hourly")
        source = "fallback"
        fallback_reason = "No completed daily briefing found; showing latest hourly report."
        if report is None:
            report = store.latest_report(mode=None)
            if report is not None:
                fallback_reason = (
                    "No daily or hourly briefing found; showing latest available report."
                )
    stories = [
        story_card(store, s, include_articles=False)
        for s in store.list_stories(limit=story_limit)
    ]
    # Prefer stories that have analysis summaries
    stories = sorted(
        stories,
        key=lambda s: (
            1 if (s.get("primary") or {}).get("summary") else 0,
            (s.get("primary") or {}).get("significance_score") or 0,
            s.get("last_seen_at") or "",
        ),
        reverse=True,
    )
    return {
        "source": source if report else "empty",
        "fallback_reason": fallback_reason if report else "No reports available yet.",
        "report": report_detail(report) if report else None,
        "stories": stories[:story_limit],
    }


def _last_successful_run(
    runs: list[dict[str, Any]], *, mode: str
) -> dict[str, Any] | None:
    for run in runs:
        if run.get("mode") != mode:
            continue
        if run.get("status") == "completed" and run.get("outcome") in {
            "success",
            "empty_success",
        }:
            return {
                "id": run.get("id"),
                "started_at": run.get("started_at"),
                "finished_at": run.get("finished_at"),
                "outcome": run.get("outcome"),
                "trigger_source": run.get("trigger_source") or "unrecorded",
                "empty_cycle": bool(run.get("empty_cycle")),
            }
    return None


def build_status(store: ReadOnlyStore, *, probe_ollama: bool = True) -> dict[str, Any]:
    from qwennews.production import (
        db_identity,
        inspect_scheduler,
        project_volume_mounted,
    )

    hourly = store.latest_report(mode="hourly")
    daily = store.latest_report(mode="daily")
    recent = store.recent_orchestration_runs(limit=20)
    ollama: dict[str, Any] | None = None
    ollama_live = False
    if probe_ollama:
        try:
            from qwennews.config import load_config
            from qwennews.ollama_health import check_ollama

            ollama = check_ollama(load_config(), timeout=2.0).to_dict()
            ollama_live = True
        except Exception as exc:  # noqa: BLE001
            ollama = {"ok": False, "error": str(exc), "reachable": False}
            ollama_live = True

    scheduler = inspect_scheduler()
    db_stats = store.stats()
    identity = db_identity(store.db_path)
    db_stats.update(identity)

    return {
        "db": db_stats,
        "watermarks": {
            "hourly": store.get_watermark("hourly"),
            "daily": store.get_watermark("daily"),
        },
        "backlog": store.backlog_counts(),
        "recent_runs": recent[:8],
        "last_hourly_report": report_summary(hourly) if hourly else None,
        "last_daily_report": report_summary(daily) if daily else None,
        "last_successful_hourly_run": _last_successful_run(recent, mode="hourly"),
        "last_successful_daily_run": _last_successful_run(recent, mode="daily"),
        "scheduler": scheduler,
        "volume": project_volume_mounted(),
        "ollama": ollama,
        "ollama_live": ollama_live,
        "note": (
            "Watermarks, backlog, and recent runs are last-known values from SQLite. "
            "Scheduler verification is independent of 'loaded' LaunchAgent state. "
            "trigger_source=launchd means XPC_SERVICE_NAME matched a QwenNews agent; "
            "cli/unrecorded means manual or pre-M4.2. Ollama fields are a bounded live probe."
        ),
    }
