"""Story identity, near-duplicate linking, and update classification."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from qwennews.similarity import (
    content_changed_meaningfully,
    fingerprint_text,
    should_merge_candidates,
)
from qwennews.storage import ArticleStore
from qwennews.story_models import LinkDecision, StoryDecision

logger = logging.getLogger(__name__)


def story_id_from_seed(title: str, article_id: str) -> str:
    digest = hashlib.sha256(f"{title.strip().lower()}|{article_id}".encode()).hexdigest()
    return f"story_{digest[:24]}"


def _article_bundle(store: ArticleStore, article_id: str) -> dict[str, Any] | None:
    row = store.get_article(article_id)
    if row is None:
        return None
    # Attach sources
    recent = store.recent_articles(hours=24 * 365 * 5, limit=50_000)
    match = next((r for r in recent if r["id"] == article_id), None)
    if match:
        return match
    row = dict(row)
    row.setdefault("sources", "")
    return row


def classify_against_story(
    article: dict[str, Any],
    *,
    story_id: str,
    prior_articles: list[dict[str, Any]],
    previous_text: str | None,
) -> LinkDecision:
    """Classify an article already linked / candidate-linked to a story."""
    article_id = str(article["id"])
    text = article.get("article_text") or ""

    # Already linked identical content fingerprint among members => UNCHANGED
    fp = fingerprint_text(text)
    for prior in prior_articles:
        if prior["id"] == article_id:
            continue
        if fingerprint_text(prior.get("article_text") or "") == fp and (
            (prior.get("title") or "").strip().lower()
            == (article.get("title") or "").strip().lower()
        ):
            return LinkDecision(
                decision=StoryDecision.UNCHANGED,
                story_id=story_id,
                article_id=article_id,
                evidence={"reason": "identical_fingerprint", "fingerprint": fp},
            )

    # Same article re-seen: compare against previous stored text snapshot if provided
    if previous_text is not None and str(article.get("id")) in {
        str(p["id"]) for p in prior_articles
    }:
        changed, evidence = content_changed_meaningfully(previous_text, text)
        if not changed:
            return LinkDecision(
                decision=StoryDecision.UNCHANGED,
                story_id=story_id,
                article_id=article_id,
                evidence={"reason": "no_meaningful_content_change", **evidence},
            )
        return LinkDecision(
            decision=StoryDecision.MEANINGFUL_UPDATE,
            story_id=story_id,
            article_id=article_id,
            evidence={"reason": "content_delta", **evidence},
        )

    # New article member of story
    # Compare to primary/longest member for meaningful update vs just another source
    best = max(prior_articles, key=lambda a: len(a.get("article_text") or ""), default=None)
    if best is None:
        return LinkDecision(
            decision=StoryDecision.NEW_SOURCE_SAME_STORY,
            story_id=story_id,
            article_id=article_id,
            evidence={"reason": "first_member"},
        )

    changed, evidence = content_changed_meaningfully(best.get("article_text") or "", text)
    # Different source URL with overlapping story but little new info
    same_source = False
    art_sources = set((article.get("sources") or "").split(","))
    best_sources = set((best.get("sources") or "").split(","))
    if art_sources & best_sources and art_sources & best_sources != {""}:
        same_source = True

    if changed and not same_source:
        # Follow-up with genuinely new info from another outlet
        return LinkDecision(
            decision=StoryDecision.MEANINGFUL_UPDATE,
            story_id=story_id,
            article_id=article_id,
            evidence={"reason": "new_source_with_new_info", **evidence},
        )
    if changed and same_source:
        return LinkDecision(
            decision=StoryDecision.MEANINGFUL_UPDATE,
            story_id=story_id,
            article_id=article_id,
            evidence={"reason": "same_source_content_update", **evidence},
        )
    return LinkDecision(
        decision=StoryDecision.NEW_SOURCE_SAME_STORY,
        story_id=story_id,
        article_id=article_id,
        evidence={"reason": "additional_source_same_story", **evidence},
    )


def find_matching_story(
    store: ArticleStore,
    article: dict[str, Any],
) -> tuple[str | None, dict[str, object]]:
    """Search existing stories for a conservative near-duplicate match."""
    stories = store.list_stories(limit=500)
    title = article.get("title") or ""
    text = article.get("article_text") or ""
    best: tuple[float, str, dict[str, object]] | None = None

    for story in stories:
        members = store.list_story_articles(story["id"])
        if not members:
            continue
        # Compare against primary and up to 3 longest members
        candidates = sorted(
            members,
            key=lambda m: len(m.get("article_text") or ""),
            reverse=True,
        )[:3]
        for member in candidates:
            merge, evidence = should_merge_candidates(
                title_a=title,
                title_b=member.get("title") or story.get("title") or "",
                text_a=text,
                text_b=member.get("article_text") or "",
            )
            if not merge:
                continue
            score = float(evidence.get("title_similarity", 0)) + float(
                evidence.get("content_similarity", 0)
            )
            if best is None or score > best[0]:
                best = (score, story["id"], evidence)

    if best is None:
        return None, {"reason": "no_match"}
    return best[1], best[2]


def link_article(
    store: ArticleStore,
    article: dict[str, Any],
    *,
    previous_text: str | None = None,
) -> LinkDecision:
    """
    Link one article into story memory.

    Idempotent: re-linking the same article without content change yields UNCHANGED.
    """
    article_id = str(article["id"])
    existing_story_id = store.get_story_id_for_article(article_id)

    if existing_story_id:
        members = store.list_story_articles(existing_story_id)
        # Detect HN-score-only style unchanged: text fingerprint same as last snapshot
        decision = classify_against_story(
            article,
            story_id=existing_story_id,
            prior_articles=members,
            previous_text=previous_text
            if previous_text is not None
            else article.get("article_text"),
        )
        # If previous_text equals current, force UNCHANGED even if HN metadata changed
        if previous_text is not None and previous_text == (article.get("article_text") or ""):
            decision = LinkDecision(
                decision=StoryDecision.UNCHANGED,
                story_id=existing_story_id,
                article_id=article_id,
                evidence={
                    "reason": "hn_or_metadata_only",
                    "note": "Score/comment changes alone are not meaningful updates",
                },
            )
        store.record_story_event(decision)
        if decision.decision == StoryDecision.MEANINGFUL_UPDATE:
            store.touch_story(
                existing_story_id,
                significant_update=True,
                title=article.get("title"),
            )
        else:
            store.touch_story(existing_story_id, significant_update=False)
        return decision

    seen_at = article.get("discovered_at") or article.get("published_at")

    match_id, evidence = find_matching_story(store, article)
    if match_id:
        members = store.list_story_articles(match_id)
        decision = classify_against_story(
            article,
            story_id=match_id,
            prior_articles=members,
            previous_text=None,
        )
        # Fresh link into existing story should not be UNCHANGED
        if decision.decision == StoryDecision.UNCHANGED:
            decision = LinkDecision(
                decision=StoryDecision.NEW_SOURCE_SAME_STORY,
                story_id=match_id,
                article_id=article_id,
                evidence={**decision.evidence, "match_evidence": evidence},
            )
        else:
            decision.evidence = {**decision.evidence, "match_evidence": evidence}
        store.add_article_to_story(
            match_id,
            article_id,
            link_reason=decision.decision.value,
            linked_at=seen_at if isinstance(seen_at, str) else None,
        )
        store.record_story_event(decision)
        store.touch_story(
            match_id,
            significant_update=decision.decision == StoryDecision.MEANINGFUL_UPDATE,
            title=None,
            seen_at=seen_at if isinstance(seen_at, str) else None,
        )
        return decision

    # Create new story
    sid = story_id_from_seed(article.get("title") or article_id, article_id)
    store.create_story(
        story_id=sid,
        title=article.get("title") or "Untitled",
        primary_article_id=article_id,
        category=None,
        seen_at=seen_at if isinstance(seen_at, str) else None,
    )
    store.add_article_to_story(
        sid,
        article_id,
        link_reason=StoryDecision.NEW_STORY.value,
        linked_at=seen_at if isinstance(seen_at, str) else None,
    )
    decision = LinkDecision(
        decision=StoryDecision.NEW_STORY,
        story_id=sid,
        article_id=article_id,
        evidence={"reason": "no_near_duplicate"},
    )
    store.record_story_event(decision)
    return decision


def sync_stories(store: ArticleStore, *, limit: int = 500) -> list[LinkDecision]:
    """Ensure recent articles are represented in story memory."""
    articles = store.recent_articles(hours=24 * 365, limit=limit)
    decisions: list[LinkDecision] = []
    for article in articles:
        decisions.append(link_article(store, article))
    logger.info("Synced %s articles into story memory", len(decisions))
    return decisions


def hn_score_only_unchanged(
    *,
    old_score: int | None,
    new_score: int | None,
    old_text: str,
    new_text: str,
) -> bool:
    """Helper used by tests: score change without text change is not meaningful."""
    return (old_text or "") == (new_text or "") and old_score != new_score
