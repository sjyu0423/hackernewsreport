"""Deterministic Markdown briefing generation from validated analyses."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from qwennews.analysis_schema import ArticleAnalysis
from qwennews.models import ensure_utc, utc_now
from qwennews.storage import ArticleStore

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RankedStory:
    article: dict[str, Any]
    analysis: ArticleAnalysis
    rank_score: float


def compute_rank_score(article: dict[str, Any], analysis: ArticleAnalysis) -> float:
    """
    Deterministic blend of model scores and limited HN attention signals.

    rank = 0.45 * relevance + 0.40 * significance + 0.15 * hn_attention
    where hn_attention maps HN score into 1..5 (log-ish clamp). Absent HN => 2.5 neutral.
    Popularity is never treated as truth — only as a mild ranking prior.
    """
    relevance = float(analysis.relevance_score)
    significance = float(analysis.significance_score)
    hn_score = article.get("hn_score")
    if isinstance(hn_score, int) and hn_score >= 0:
        # 0 -> 1.0, 10 -> ~2.0, 50 -> ~3.2, 200 -> ~4.3, 500+ ~5
        from math import log10

        hn_attention = max(1.0, min(5.0, 1.0 + log10(hn_score + 1) * 1.6))
    else:
        hn_attention = 2.5
    return round(0.45 * relevance + 0.40 * significance + 0.15 * hn_attention, 4)


def select_ranked_stories(
    store: ArticleStore,
    *,
    hours: int = 24,
    limit: int = 10,
) -> list[RankedStory]:
    articles = store.recent_articles(hours=hours, limit=max(limit * 5, limit))
    ranked: list[RankedStory] = []
    for article in articles:
        row = store.get_latest_analysis(str(article["id"]))
        if row is None:
            continue
        try:
            analysis = ArticleAnalysis.model_validate_json(row["analysis_json"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping corrupt analysis for %s: %s", article["id"], exc)
            continue
        ranked.append(
            RankedStory(
                article=article,
                analysis=analysis,
                rank_score=compute_rank_score(article, analysis),
            )
        )
    ranked.sort(
        key=lambda item: (
            -item.rank_score,
            -(item.analysis.significance_score),
            -(item.analysis.relevance_score),
            str(item.article.get("published_at") or ""),
            str(item.article["id"]),
        )
    )
    return ranked[:limit]


def _fmt_ts(value: str | datetime | None) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, datetime):
        dt = ensure_utc(value)
        assert dt is not None
        return dt.isoformat().replace("+00:00", "Z")
    return str(value)


def render_markdown_report(
    stories: list[RankedStory],
    *,
    hours: int,
    generated_at: datetime | None = None,
) -> str:
    """Pure Python template — model is never asked to invent stories/citations."""
    generated = ensure_utc(generated_at or utc_now())
    assert generated is not None
    lines: list[str] = []
    lines.append("# QwenNews Briefing")
    lines.append("")
    lines.append(f"- Generated (UTC): `{generated.isoformat().replace('+00:00', 'Z')}`")
    lines.append(f"- Lookback window: last **{hours}** hour(s)")
    lines.append(f"- Stories included: **{len(stories)}**")
    lines.append(
        "- Ranking: deterministic blend "
        "`0.45*relevance + 0.40*significance + 0.15*HN_attention` "
        "(HN attention is optional popularity only, not truth)."
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

    # Category grouping
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
    lines.append("- HN popularity is not evidence of factual correctness.")
    lines.append("- On-demand briefing only (no hourly delta automation in M1).")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def generate_report(
    store: ArticleStore,
    *,
    hours: int = 24,
    limit: int = 10,
    output_dir: Path | None = None,
) -> tuple[str, Path | None]:
    """Build Markdown report and optionally persist under output_dir."""
    stories = select_ranked_stories(store, hours=hours, limit=limit)
    markdown = render_markdown_report(stories, hours=hours)
    path: Path | None = None
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
        path = output_dir / f"briefing_{stamp}.md"
        path.write_text(markdown, encoding="utf-8")
        store.save_report(
            path=str(path),
            hours=hours,
            story_count=len(stories),
            markdown=markdown,
        )
        logger.info("Wrote report to %s (%s stories)", path, len(stories))
    return markdown, path
