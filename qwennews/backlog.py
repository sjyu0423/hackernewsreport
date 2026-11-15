"""Durable hourly backlog enqueue / drain helpers (M3.1)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from qwennews.models import ensure_utc
from qwennews.storage import ArticleStore
from qwennews.story_models import StoryDecision

# Active analysis backlog (articles) — watermark must not advance while any remain.
ARTICLE_ACTIVE = ("pending", "failed")
# Story report readiness
STORY_ACTIVE = ("pending", "ready", "failed")


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    return ensure_utc(datetime.fromisoformat(ts.replace("Z", "+00:00")))


def _after_watermark(ts: str | None, watermark: datetime | None, as_of: datetime) -> bool:
    dt = _parse(ts)
    if dt is None or dt > as_of:
        return False
    if watermark is None:
        return True
    return dt > watermark


def story_is_cycle_eligible(
    store: ArticleStore,
    story: dict[str, Any],
    *,
    mode: str,
    watermark: datetime | None,
    as_of: datetime,
) -> bool:
    sid = story["id"]
    state = store.get_story_processing(sid, mode)
    if state and state["status"] in STORY_ACTIVE:
        return True
    if state and state["status"] == "reported":
        sig = _parse(story.get("significant_update_at"))
        last_rep = _parse(store.get_story_reported_at(sid, mode))
        if sig and last_rep and sig > last_rep and sig <= as_of:
            return True
        return False

    events = store.list_story_events(sid, limit=20)
    decisions = {e["decision"] for e in events}
    first = story.get("first_seen_at")
    sig = story.get("significant_update_at")
    is_new = _after_watermark(first, watermark, as_of) and (
        StoryDecision.NEW_STORY.value in decisions or not decisions
    )
    is_changed = _after_watermark(sig, watermark, as_of) and (
        StoryDecision.MEANINGFUL_UPDATE.value in decisions
        or StoryDecision.NEW_SOURCE_SAME_STORY.value in decisions
    )
    if is_new or is_changed:
        return True
    if watermark is None and store.get_story_reported_at(sid, mode) is None:
        return True
    return False


def enqueue_hourly_backlog(
    store: ArticleStore,
    *,
    watermark: datetime | None,
    as_of: datetime,
    limit_stories: int = 500,
) -> dict[str, int]:
    """
    Enqueue eligible stories and their uncached articles into durable queues.

    Articles: pending until analyzed (or failed for retry).
    Stories: pending while articles remain; ready when ≥1 analysis exists.
    """
    counts = {
        "enqueued_articles": 0,
        "enqueued_stories": 0,
        "unchanged": 0,
        "active_articles": 0,
        "active_stories": 0,
    }
    for story in store.list_stories(limit=limit_stories):
        if not story_is_cycle_eligible(
            store, story, mode="hourly", watermark=watermark, as_of=as_of
        ):
            counts["unchanged"] += 1
            continue

        sid = story["id"]
        arts = store.list_story_articles(sid)
        missing = 0
        for art in arts:
            aid = str(art["id"])
            if store.get_latest_analysis(aid) is not None:
                store.upsert_article_processing(aid, "hourly", "done")
                continue
            store.upsert_article_processing(aid, "hourly", "pending")
            missing += 1
            counts["enqueued_articles"] += 1

        if missing:
            store.upsert_story_processing(sid, "hourly", "pending")
        else:
            # All articles analyzed (or none) — ready for report if any analysis
            has_any = any(
                store.get_latest_analysis(str(a["id"])) is not None for a in arts
            )
            if has_any:
                existing = store.get_story_processing(sid, "hourly")
                if not existing or existing["status"] not in ("reported", "skipped"):
                    store.upsert_story_processing(sid, "hourly", "ready")
            else:
                store.upsert_story_processing(sid, "hourly", "pending")
        counts["enqueued_stories"] += 1

    counts["active_articles"] = store.count_article_processing(
        "hourly", list(ARTICLE_ACTIVE)
    )
    counts["active_stories"] = store.count_story_processing("hourly", list(STORY_ACTIVE))
    return counts


def select_articles_for_analysis(
    store: ArticleStore, *, mode: str, limit: int
) -> tuple[list[str], list[str]]:
    """Return up to ``limit`` pending/failed article ids (and parent story ids)."""
    article_ids: list[str] = []
    story_ids: list[str] = []
    for row in store.list_article_processing(
        mode, statuses=["pending", "failed"], limit=max(limit * 4, limit)
    ):
        aid = str(row["article_id"])
        if store.get_latest_analysis(aid) is not None:
            store.upsert_article_processing(aid, mode, "done")
            continue
        article_ids.append(aid)
        # Best-effort parent story
        for story in store.list_stories(limit=500):
            arts = store.list_story_articles(story["id"])
            if any(str(a["id"]) == aid for a in arts):
                if story["id"] not in story_ids:
                    story_ids.append(story["id"])
                break
        if len(article_ids) >= limit:
            break
    return article_ids, story_ids


def refresh_processing_after_analyze(
    store: ArticleStore,
    article_ids: list[str],
    story_ids: list[str],
    *,
    mode: str,
    failed_article_ids: set[str],
) -> None:
    for aid in article_ids:
        if store.get_latest_analysis(aid) is not None:
            store.upsert_article_processing(aid, mode, "done")
        elif aid in failed_article_ids:
            store.upsert_article_processing(
                aid, mode, "failed", error="analysis failed", bump_attempts=True
            )
        else:
            store.upsert_article_processing(aid, mode, "pending")

    for sid in story_ids:
        arts = store.list_story_articles(sid)
        missing = [
            str(a["id"])
            for a in arts
            if store.get_latest_analysis(str(a["id"])) is None
        ]
        has_any = any(store.get_latest_analysis(str(a["id"])) is not None for a in arts)
        if not missing and has_any:
            store.upsert_story_processing(sid, mode, "ready")
        elif has_any and missing:
            # Partial analysis: still reportable, but backlog remains for articles
            store.upsert_story_processing(sid, mode, "ready")
        elif missing and all(m in failed_article_ids for m in missing):
            store.upsert_story_processing(
                sid, mode, "failed", error="analysis failed", bump_attempts=True
            )
        else:
            store.upsert_story_processing(sid, mode, "pending")


def mark_stories_reported(store: ArticleStore, story_ids: list[str], *, mode: str) -> None:
    for sid in story_ids:
        store.upsert_story_processing(sid, mode, "reported")


def mark_ready_skipped(store: ArticleStore, *, mode: str) -> int:
    n = 0
    for row in store.list_story_processing(mode, statuses=["ready"], limit=500):
        store.upsert_story_processing(row["story_id"], mode, "skipped")
        n += 1
    return n


def backlog_counts(store: ArticleStore, mode: str) -> dict[str, int]:
    pending_a = store.count_article_processing(mode, ["pending"])
    failed_a = store.count_article_processing(mode, ["failed"])
    pending_s = store.count_story_processing(mode, ["pending"])
    ready_s = store.count_story_processing(mode, ["ready"])
    failed_s = store.count_story_processing(mode, ["failed"])
    # Active means watermark must wait: unfinished articles OR unreported ready/pending stories
    active = pending_a + failed_a + pending_s + ready_s + failed_s
    return {
        "pending": pending_a + pending_s,
        "ready": ready_s,
        "failed": failed_a + failed_s,
        "active": active,
        "pending_articles": pending_a,
        "failed_articles": failed_a,
        "pending_stories": pending_s,
        "ready_stories": ready_s,
    }
