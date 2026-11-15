"""Story memory domain models for M2."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class StoryDecision(StrEnum):
    NEW_STORY = "NEW_STORY"
    NEW_SOURCE_SAME_STORY = "NEW_SOURCE_SAME_STORY"
    MEANINGFUL_UPDATE = "MEANINGFUL_UPDATE"
    UNCHANGED = "UNCHANGED"


class ReportMode(StrEnum):
    ONDEMAND = "ondemand"
    HOURLY = "hourly"
    DAILY = "daily"


@dataclass(slots=True)
class LinkDecision:
    decision: StoryDecision
    story_id: str | None
    article_id: str
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class StoryView:
    """Story with attached articles for reporting."""

    id: str
    title: str
    category: str | None
    first_seen_at: str | None
    last_seen_at: str | None
    last_reported_at: str | None
    significant_update_at: str | None
    primary_article_id: str | None
    articles: list[dict[str, Any]] = field(default_factory=list)
    latest_decision: StoryDecision | None = None
    rank_score: float = 0.0
    relevance_score: int | None = None
    significance_score: int | None = None
    evidence_sufficiency: str | None = None
    summary: str | None = None
    why_it_matters: str | None = None
    limitations: str | None = None
    key_claims: list[str] = field(default_factory=list)
    # M3: mode-specific last reported timestamps
    last_reported_hourly_at: str | None = None
    last_reported_daily_at: str | None = None


@dataclass(slots=True)
class ReportWindow:
    mode: ReportMode
    as_of: datetime
    window_start: datetime | None
    watermark_before: datetime | None
