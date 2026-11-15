"""Pydantic response models for the dashboard API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ReportSummary(BaseModel):
    id: int
    mode: str | None = None
    created_at: str | None = None
    as_of: str | None = None
    window_start: str | None = None
    story_count: int = 0
    significant_only: bool = False
    status: str | None = None
    markdown_preview: str | None = None
    kind: str | None = None  # new | update | empty | unknown


class ReportDetail(ReportSummary):
    markdown: str = ""
    hours: int | None = None


class StoryArticle(BaseModel):
    id: str
    title: str
    canonical_url: str | None = None
    sources: str | None = None
    discovered_at: str | None = None
    published_at: str | None = None
    link_reason: str | None = None
    summary: str | None = None
    why_it_matters: str | None = None
    category: str | None = None
    relevance_score: int | None = None
    significance_score: int | None = None


class StoryCard(BaseModel):
    id: str
    title: str
    category: str | None = None
    first_seen_at: str | None = None
    last_seen_at: str | None = None
    significant_update_at: str | None = None
    article_count: int = 0
    primary: StoryArticle | None = None
    articles: list[StoryArticle] = Field(default_factory=list)


class TodayResponse(BaseModel):
    source: str  # daily | fallback
    fallback_reason: str | None = None
    report: ReportDetail | None = None
    stories: list[StoryCard] = Field(default_factory=list)


class HourlyListResponse(BaseModel):
    items: list[ReportSummary]


class HistoryResponse(BaseModel):
    items: list[ReportSummary]
    categories: list[str] = Field(default_factory=list)


class StatusResponse(BaseModel):
    db: dict[str, Any]
    watermarks: dict[str, Any]
    backlog: dict[str, int]
    recent_runs: list[dict[str, Any]]
    last_hourly_report: ReportSummary | None = None
    last_daily_report: ReportSummary | None = None
    ollama: dict[str, Any] | None = None
    ollama_live: bool = False
    note: str = (
        "Watermarks, backlog, and recent runs are last-known values from SQLite. "
        "Ollama fields are from a bounded live probe when enabled."
    )


class HealthResponse(BaseModel):
    ok: bool
    service: str = "qwennews-dashboard-api"
    readonly: bool = True
