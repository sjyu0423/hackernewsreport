"""Markdown briefing generation: on-demand, hourly delta, and daily digests."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from qwennews.analysis_schema import ArticleAnalysis
from qwennews.models import ensure_utc, utc_now
from qwennews.ranking import (
    RankingConfig,
    apply_diversity,
    compute_rank_score_m2,
    default_ranking_config,
)
from qwennews.storage import ArticleStore
from qwennews.story_memory import sync_stories
from qwennews.story_models import ReportMode, StoryDecision, StoryView

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RankedStory:
    """Legacy M1 article-centric ranked item (ondemand compatibility)."""

    article: dict[str, Any]
    analysis: ArticleAnalysis
    rank_score: float


def compute_rank_score(article: dict[str, Any], analysis: ArticleAnalysis) -> float:
    """Backward-compatible wrapper → M2 ranking function."""
    return compute_rank_score_m2(article, analysis)


def select_ranked_stories(
    store: ArticleStore,
    *,
    hours: int = 24,
    limit: int = 10,
    ranking_config: RankingConfig | None = None,
    as_of: datetime | None = None,
) -> list[RankedStory]:
    cfg = ranking_config or default_ranking_config()
    as_of_dt = ensure_utc(as_of or utc_now())
    assert as_of_dt is not None
    cutoff = as_of_dt - timedelta(hours=hours)
    articles = store.recent_articles(hours=max(hours, 1), limit=max(limit * 8, limit))
    scored: list[tuple[float, dict[str, Any], ArticleAnalysis]] = []
    for article in articles:
        discovered = article.get("discovered_at") or article.get("published_at")
        if discovered and str(discovered) > as_of_dt.isoformat().replace("+00:00", "Z"):
            continue
        if discovered and str(discovered) < cutoff.isoformat().replace("+00:00", "Z"):
            # recent_articles already filters loosely; keep soft
            pass
        row = store.get_latest_analysis(str(article["id"]))
        if row is None:
            continue
        try:
            analysis = ArticleAnalysis.model_validate_json(row["analysis_json"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping corrupt analysis for %s: %s", article["id"], exc)
            continue
        score = compute_rank_score_m2(article, analysis, config=cfg)
        scored.append((score, article, analysis))

    scored.sort(
        key=lambda item: (
            -item[0],
            -(item[2].significance_score),
            -(item[2].relevance_score),
            str(item[1].get("published_at") or ""),
            str(item[1]["id"]),
        )
    )
    diversified = apply_diversity(scored, limit=limit, config=cfg)
    return [
        RankedStory(article=article, analysis=analysis, rank_score=score)
        for score, article, analysis in diversified
    ]


def _fmt_ts(value: str | datetime | None) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, datetime):
        dt = ensure_utc(value)
        assert dt is not None
        return dt.isoformat().replace("+00:00", "Z")
    return str(value)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return ensure_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _analysis_for_article(store: ArticleStore, article_id: str) -> ArticleAnalysis | None:
    row = store.get_latest_analysis(article_id)
    if row is None:
        return None
    try:
        return ArticleAnalysis.model_validate_json(row["analysis_json"])
    except Exception:  # noqa: BLE001
        return None


def build_story_views(
    store: ArticleStore,
    *,
    ranking_config: RankingConfig | None = None,
) -> list[StoryView]:
    cfg = ranking_config or default_ranking_config()
    views: list[StoryView] = []
    for story in store.list_stories(limit=1000):
        articles = store.list_story_articles(story["id"])
        if not articles:
            continue
        # Prefer primary analyzed article with highest M2 rank
        best_analysis: ArticleAnalysis | None = None
        best_article: dict[str, Any] | None = None
        best_score = -1.0
        for art in articles:
            analysis = _analysis_for_article(store, str(art["id"]))
            if analysis is None:
                continue
            score = compute_rank_score_m2(art, analysis, config=cfg)
            if score > best_score:
                best_score = score
                best_analysis = analysis
                best_article = art
        if best_analysis is None or best_article is None:
            # Still include story shell with uncertainty
            primary = articles[0]
            views.append(
                StoryView(
                    id=story["id"],
                    title=story.get("title") or primary.get("title") or "Untitled",
                    category=story.get("category"),
                    first_seen_at=story.get("first_seen_at"),
                    last_seen_at=story.get("last_seen_at"),
                    last_reported_at=story.get("last_reported_at"),
                    significant_update_at=story.get("significant_update_at"),
                    primary_article_id=story.get("primary_article_id"),
                    articles=articles,
                    rank_score=0.0,
                    evidence_sufficiency="insufficient",
                    summary="No validated analysis is available for this story yet.",
                    limitations="Analysis missing; claims cannot be grounded.",
                )
            )
            continue
        events = store.list_story_events(story["id"], limit=1)
        latest_decision = None
        if events:
            try:
                latest_decision = StoryDecision(events[0]["decision"])
            except ValueError:
                latest_decision = None
        views.append(
            StoryView(
                id=story["id"],
                title=story.get("title") or best_article.get("title") or "Untitled",
                category=best_analysis.category,
                first_seen_at=story.get("first_seen_at"),
                last_seen_at=story.get("last_seen_at"),
                last_reported_at=story.get("last_reported_at"),
                significant_update_at=story.get("significant_update_at"),
                primary_article_id=story.get("primary_article_id") or best_article["id"],
                articles=articles,
                latest_decision=latest_decision,
                rank_score=best_score,
                relevance_score=best_analysis.relevance_score,
                significance_score=best_analysis.significance_score,
                evidence_sufficiency=best_analysis.evidence_sufficiency.value,
                summary=best_analysis.summary,
                why_it_matters=best_analysis.why_it_matters,
                limitations=best_analysis.limitations,
                key_claims=list(best_analysis.key_claims),
            )
        )
    views.sort(
        key=lambda v: (
            -v.rank_score,
            -(v.significance_score or 0),
            -(v.relevance_score or 0),
            v.id,
        )
    )
    return views


def _within_window(ts: str | None, start: datetime | None, end: datetime) -> bool:
    if not ts:
        return False
    dt = _parse_iso(ts)
    if dt is None:
        return False
    if start is not None and dt < start:
        return False
    return dt <= end


def select_hourly_delta(
    views: list[StoryView],
    store: ArticleStore,
    *,
    as_of: datetime,
    watermark: datetime | None,
    limit: int,
) -> tuple[list[StoryView], list[StoryView]]:
    """
    Return (new_developments, ongoing_updates).

    Uses story first_seen / significant_update timestamps (aligned to article
    discovery times) so --as-of tests remain deterministic. Event logs remain
    available for debugging but do not depend on wall-clock insert time.
    """
    new_dev: list[StoryView] = []
    ongoing: list[StoryView] = []
    for view in views:
        # Ignore stories that only exist after as_of
        first = _parse_iso(view.first_seen_at)
        sig = _parse_iso(view.significant_update_at)
        last_rep = _parse_iso(view.last_reported_at)
        if first and first > as_of:
            continue

        # Articles discovered by as_of
        visible_articles = [
            a
            for a in view.articles
            if (_parse_iso(a.get("discovered_at")) or first) is not None
            and (_parse_iso(a.get("discovered_at")) or first) <= as_of  # type: ignore[operator]
        ]
        if not visible_articles:
            continue

        link_reasons = {
            (a.get("link_reason") or "") for a in visible_articles if a.get("link_reason")
        }

        def _after_wm(ts: datetime | None) -> bool:
            if ts is None or ts > as_of:
                return False
            if watermark is None:
                return True
            return ts > watermark

        is_new = _after_wm(first) and (
            StoryDecision.NEW_STORY.value in link_reasons or not link_reasons
        )
        is_meaningful = _after_wm(sig) and (
            StoryDecision.MEANINGFUL_UPDATE.value in link_reasons
            or (sig is not None and first is not None and sig > first)
        )
        is_new_source = any(
            (a.get("link_reason") == StoryDecision.NEW_SOURCE_SAME_STORY.value)
            and _after_wm(_parse_iso(a.get("linked_at") or a.get("discovered_at")))
            for a in visible_articles
        )

        # Already reported at/after watermark ⇒ skip unchanged repeats
        if last_rep is not None and watermark is not None and last_rep > watermark:
            if not is_meaningful and not is_new_source:
                continue
        if last_rep is not None and watermark is None:
            # First hourly after stories were marked reported by another mode:
            # still allow if never hourly-reported; last_reported_at is shared.
            # Only skip if last_reported_at >= first_seen (already covered).
            pass

        if is_new and (last_rep is None or (watermark is not None and last_rep <= watermark)):
            new_dev.append(view)
        elif is_meaningful:
            ongoing.append(view)
        elif is_new_source and (
            last_rep is None or (watermark is not None and last_rep <= watermark)
        ):
            ongoing.append(view)
        elif watermark is None and last_rep is None and first and first <= as_of:
            # First ever hourly: include unreported stories
            new_dev.append(view)

    # De-dupe while preserving order
    def _uniq(items: list[StoryView]) -> list[StoryView]:
        seen: set[str] = set()
        out: list[StoryView] = []
        for item in items:
            if item.id in seen:
                continue
            seen.add(item.id)
            out.append(item)
        return out

    new_dev = _uniq(new_dev)
    ongoing = _uniq([v for v in ongoing if v.id not in {x.id for x in new_dev}])
    return new_dev[:limit], ongoing[: max(0, limit - len(new_dev))]


def select_daily_stories(
    views: list[StoryView],
    *,
    as_of: datetime,
    limit: int,
) -> list[StoryView]:
    start = as_of - timedelta(hours=24)
    selected = [
        v
        for v in views
        if _within_window(v.last_seen_at, start, as_of)
        or _within_window(v.significant_update_at, start, as_of)
        or _within_window(v.first_seen_at, start, as_of)
    ]
    return selected[:limit]


def render_markdown_report(
    stories: list[RankedStory],
    *,
    hours: int,
    generated_at: datetime | None = None,
) -> str:
    """Legacy on-demand article briefing template."""
    generated = ensure_utc(generated_at or utc_now())
    assert generated is not None
    lines: list[str] = []
    lines.append("# QwenNews Briefing")
    lines.append("")
    lines.append(f"- Generated (UTC): `{generated.isoformat().replace('+00:00', 'Z')}`")
    lines.append("- Mode: **ondemand**")
    lines.append(f"- Lookback window: last **{hours}** hour(s)")
    lines.append(f"- Stories included: **{len(stories)}**")
    lines.append(
        "- Ranking (M2): `0.35*significance + 0.25*relevance + 0.25*category_priority "
        "+ 0.10*ai_signal + 0.05*hn_attention_capped`"
    )
    lines.append("")

    if not stories:
        lines.append("## No stories available")
        lines.append("")
        lines.append(
            "No validated analyses were available for this window. "
            "Run `python -m qwennews analyze` after collecting articles."
        )
        lines.append("")
        lines.append("## Limitations")
        lines.append("")
        lines.append("- Empty report: ingestion or analysis may not have been run yet.")
        return "\n".join(lines).rstrip() + "\n"

    lines.append("## Top stories")
    lines.append("")
    for idx, item in enumerate(stories, start=1):
        a = item.analysis
        art = item.article
        url = art.get("canonical_url") or art.get("original_url")
        sources = art.get("sources") or "unknown"
        freshness = art.get("published_at") or art.get("discovered_at") or "unknown"
        lines.append(f"### {idx}. {art.get('title') or '(untitled)'}")
        lines.append("")
        lines.append(f"- Category: **{a.category}**")
        lines.append(
            f"- Rank score: `{item.rank_score}` "
            f"(relevance={a.relevance_score}, significance={a.significance_score})"
        )
        lines.append(f"- Evidence: `{a.evidence_sufficiency.value}`")
        lines.append(f"- Sources: {sources}")
        lines.append(f"- Freshness (UTC): {_fmt_ts(freshness)}")
        lines.append(f"- Original URL: {url}")
        if art.get("hn_discussion_url"):
            lines.append(
                f"- HN discussion: {art['hn_discussion_url']} "
                f"(score={art.get('hn_score')}, comments={art.get('hn_comment_count')})"
            )
        lines.append("")
        lines.append(a.summary)
        lines.append("")
        lines.append(f"**Why it matters:** {a.why_it_matters}")
        lines.append("")
        if a.key_claims:
            lines.append("**Key claims (from source text):**")
            for claim in a.key_claims:
                lines.append(f"- {claim}")
            lines.append("")
        lines.append(f"**Limitations / uncertainty:** {a.limitations}")
        lines.append("")

    by_cat: dict[str, list[RankedStory]] = {}
    for item in stories:
        by_cat.setdefault(item.analysis.category.lower(), []).append(item)

    lines.append("## By category")
    lines.append("")
    for category in sorted(by_cat.keys()):
        lines.append(f"### {category}")
        lines.append("")
        for item in by_cat[category]:
            url = item.article.get("canonical_url") or item.article.get("original_url")
            lines.append(f"- [{item.article.get('title')}]({url})")
        lines.append("")

    lines.append("## Sources and freshness")
    lines.append("")
    for item in stories:
        art = item.article
        url = art.get("canonical_url") or art.get("original_url")
        when = _fmt_ts(art.get("published_at") or art.get("discovered_at"))
        lines.append(f"- `{art['id']}` — {art.get('sources')} — {when} — {url}")
    lines.append("")
    lines.append("## Limitations")
    lines.append("")
    lines.append("- Analyses are local LLM interpretations of extracted text; they can be wrong.")
    lines.append("- Thin or blocked extractions force uncertainty labels rather than invention.")
    lines.append("- HN popularity is a capped secondary signal, not proof of truth.")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _render_story_block(idx: int, view: StoryView) -> list[str]:
    lines: list[str] = []
    lines.append(f"### {idx}. {view.title}")
    lines.append("")
    if view.category:
        lines.append(f"- Category: **{view.category}**")
    lines.append(f"- Rank score: `{view.rank_score}`")
    if view.relevance_score is not None and view.significance_score is not None:
        lines.append(f"- Relevance/significance: {view.relevance_score}/{view.significance_score}")
    if view.evidence_sufficiency:
        lines.append(f"- Evidence: `{view.evidence_sufficiency}`")
    if view.latest_decision:
        lines.append(f"- Latest memory decision: `{view.latest_decision.value}`")
    lines.append(f"- First seen: {_fmt_ts(view.first_seen_at)}")
    lines.append(f"- Last seen: {_fmt_ts(view.last_seen_at)}")
    lines.append("")
    if view.summary:
        lines.append(view.summary)
        lines.append("")
    if view.why_it_matters:
        lines.append(f"**Why it matters:** {view.why_it_matters}")
        lines.append("")
    if view.key_claims:
        lines.append("**Key claims (grounded):**")
        for claim in view.key_claims:
            lines.append(f"- {claim}")
        lines.append("")
    lines.append("**Sources / original URLs:**")
    for art in view.articles:
        url = art.get("canonical_url") or art.get("original_url")
        src = art.get("sources") or "unknown"
        lines.append(f"- ({src}) {art.get('title')} — {url}")
    lines.append("")
    if view.limitations:
        lines.append(f"**Limitations / uncertainty:** {view.limitations}")
        lines.append("")
    return lines


def render_hourly_markdown(
    *,
    new_developments: list[StoryView],
    ongoing: list[StoryView],
    as_of: datetime,
    window_start: datetime | None,
    generated_at: datetime | None = None,
) -> str:
    generated = ensure_utc(generated_at or utc_now())
    assert generated is not None
    lines = [
        "# QwenNews Hourly Delta",
        "",
        f"- Generated (UTC): `{_fmt_ts(generated)}`",
        f"- As of (UTC): `{_fmt_ts(as_of)}`",
        f"- Window start (UTC): `{_fmt_ts(window_start)}`",
        "- Mode: **hourly**",
        "",
    ]
    if not new_developments and not ongoing:
        lines.extend(
            [
                "## No significant updates",
                "",
                "No new stories or meaningful updates since the previous successful "
                "hourly report watermark.",
                "",
                "## Limitations",
                "",
                "- Watermark advances only after this report is persisted successfully.",
                "",
            ]
        )
        return "\n".join(lines).rstrip() + "\n"

    if new_developments:
        lines.append("## New developments")
        lines.append("")
        for idx, view in enumerate(new_developments, start=1):
            lines.extend(_render_story_block(idx, view))
    if ongoing:
        lines.append("## Ongoing stories / meaningful updates")
        lines.append("")
        for idx, view in enumerate(ongoing, start=1):
            lines.extend(_render_story_block(idx, view))

    lines.extend(
        [
            "## Limitations",
            "",
            "- Delta selection uses conservative story memory decisions.",
            "- Unchanged headlines and HN score-only changes are omitted.",
            "- Claims are drawn from stored analyses; URLs come from stored articles only.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def render_daily_markdown(
    stories: list[StoryView],
    *,
    as_of: datetime,
    generated_at: datetime | None = None,
) -> str:
    generated = ensure_utc(generated_at or utc_now())
    assert generated is not None
    start = as_of - timedelta(hours=24)
    lines = [
        "# QwenNews Daily Briefing",
        "",
        f"- Generated (UTC): `{_fmt_ts(generated)}`",
        f"- Report window (UTC): `{_fmt_ts(start)}` → `{_fmt_ts(as_of)}`",
        "- Mode: **daily**",
        f"- Stories included: **{len(stories)}**",
        "",
    ]
    if not stories:
        lines.extend(
            [
                "## No stories available",
                "",
                "No significant stories were found in the previous 24 hours.",
                "",
            ]
        )
        return "\n".join(lines).rstrip() + "\n"

    lines.append("## Top stories (24h)")
    lines.append("")
    for idx, view in enumerate(stories, start=1):
        lines.extend(_render_story_block(idx, view))

    lines.extend(
        [
            "## Limitations",
            "",
            "- Daily digests may overlap hourly deltas by design.",
            "- Related sources are grouped under a single story identity.",
            "- Model-generated URLs are never used; citations are stored originals.",
            "",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def generate_report(
    store: ArticleStore,
    *,
    hours: int = 24,
    limit: int = 10,
    output_dir: Path | None = None,
    mode: str | ReportMode = ReportMode.ONDEMAND,
    as_of: datetime | None = None,
    ranking_config: RankingConfig | None = None,
    sync: bool = True,
    advance_watermark: bool = True,
    simulate_persist_failure: bool = False,
) -> tuple[str, Path | None, dict[str, Any]]:
    """
    Build a Markdown report.

    For hourly mode, the watermark advances only after successful persistence.
    `simulate_persist_failure` supports tests of failed persistence / retry.
    """
    cfg = ranking_config or default_ranking_config()
    report_mode = ReportMode(mode) if not isinstance(mode, ReportMode) else mode
    as_of_dt = ensure_utc(as_of or utc_now())
    assert as_of_dt is not None
    meta: dict[str, Any] = {"mode": report_mode.value, "watermark_advanced": False}

    if sync:
        sync_stories(store, limit=500)

    if report_mode == ReportMode.ONDEMAND:
        stories = select_ranked_stories(
            store, hours=hours, limit=limit, ranking_config=cfg, as_of=as_of_dt
        )
        markdown = render_markdown_report(stories, hours=hours, generated_at=as_of_dt)
        path, _report_id = _maybe_persist(
            store,
            markdown,
            output_dir=output_dir,
            hours=hours,
            story_count=len(stories),
            mode=report_mode.value,
            as_of=_fmt_ts(as_of_dt),
            window_start=None,
            simulate_failure=simulate_persist_failure,
        )
        meta["story_count"] = len(stories)
        return markdown, path, meta

    views = build_story_views(store, ranking_config=cfg)

    if report_mode == ReportMode.HOURLY:
        wm_row = store.get_watermark("hourly")
        watermark = _parse_iso(wm_row["watermark_at"]) if wm_row else None
        new_dev, ongoing = select_hourly_delta(
            views, store, as_of=as_of_dt, watermark=watermark, limit=limit
        )
        markdown = render_hourly_markdown(
            new_developments=new_dev,
            ongoing=ongoing,
            as_of=as_of_dt,
            window_start=watermark,
            generated_at=as_of_dt,
        )
        story_count = len(new_dev) + len(ongoing)
        path, report_id = _maybe_persist(
            store,
            markdown,
            output_dir=output_dir,
            hours=1,
            story_count=story_count,
            mode="hourly",
            as_of=_fmt_ts(as_of_dt),
            window_start=_fmt_ts(watermark),
            significant_only=True,
            simulate_failure=simulate_persist_failure,
        )
        if path is not None and advance_watermark and not simulate_persist_failure:
            store.set_watermark("hourly", _fmt_ts(as_of_dt), last_report_id=report_id)
            for view in [*new_dev, *ongoing]:
                store.mark_story_reported(view.id, _fmt_ts(as_of_dt))
            meta["watermark_advanced"] = True
        elif simulate_persist_failure:
            meta["persist_failed"] = True
        meta["new_count"] = len(new_dev)
        meta["ongoing_count"] = len(ongoing)
        return markdown, path, meta

    # daily
    daily = select_daily_stories(views, as_of=as_of_dt, limit=limit)
    markdown = render_daily_markdown(daily, as_of=as_of_dt, generated_at=as_of_dt)
    path, report_id = _maybe_persist(
        store,
        markdown,
        output_dir=output_dir,
        hours=24,
        story_count=len(daily),
        mode="daily",
        as_of=_fmt_ts(as_of_dt),
        window_start=_fmt_ts(as_of_dt - timedelta(hours=24)),
        simulate_failure=simulate_persist_failure,
    )
    if path is not None and advance_watermark and not simulate_persist_failure:
        store.set_watermark("daily", _fmt_ts(as_of_dt), last_report_id=report_id)
        for view in daily:
            store.mark_story_reported(view.id, _fmt_ts(as_of_dt))
        meta["watermark_advanced"] = True
    elif simulate_persist_failure:
        meta["persist_failed"] = True
    meta["story_count"] = len(daily)
    return markdown, path, meta


def _maybe_persist(
    store: ArticleStore,
    markdown: str,
    *,
    output_dir: Path | None,
    hours: int,
    story_count: int,
    mode: str,
    as_of: str | None,
    window_start: str | None,
    significant_only: bool = False,
    simulate_failure: bool = False,
) -> tuple[Path | None, int | None]:
    if output_dir is None:
        return None, None
    if simulate_failure:
        logger.error("Simulated report persistence failure; watermark will not advance")
        report_id = store.save_report(
            path=None,
            hours=hours,
            story_count=story_count,
            markdown=markdown,
            mode=mode,
            as_of=as_of,
            window_start=window_start,
            status="failed",
            significant_only=significant_only,
        )
        return None, report_id
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    path = output_dir / f"briefing_{mode}_{stamp}.md"
    path.write_text(markdown, encoding="utf-8")
    report_id = store.save_report(
        path=str(path),
        hours=hours,
        story_count=story_count,
        markdown=markdown,
        mode=mode,
        as_of=as_of,
        window_start=window_start,
        status="completed",
        significant_only=significant_only,
    )
    logger.info("Wrote %s report to %s (%s stories)", mode, path, story_count)
    return path, report_id
