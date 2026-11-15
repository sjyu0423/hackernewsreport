"""Pydantic schemas for Qwen article analysis (M1)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class EvidenceSufficiency(StrEnum):
    SUFFICIENT = "sufficient"
    PARTIAL = "partial"
    INSUFFICIENT = "insufficient"


class ArticleAnalysis(BaseModel):
    """Structured, source-grounded analysis of a single stored article."""

    article_id: str = Field(min_length=8, max_length=64)
    category: str = Field(
        min_length=2,
        max_length=64,
        description="Short topical category, e.g. models, tooling, research, business",
    )
    summary: str = Field(min_length=20, max_length=1200)
    why_it_matters: str = Field(min_length=10, max_length=800)
    relevance_score: int = Field(ge=1, le=5)
    significance_score: int = Field(ge=1, le=5)
    evidence_sufficiency: EvidenceSufficiency
    key_claims: list[str] = Field(default_factory=list, max_length=8)
    limitations: str = Field(min_length=5, max_length=800)

    @field_validator("category")
    @classmethod
    def _normalize_category(cls, value: str) -> str:
        cleaned = " ".join(value.strip().split())
        if not cleaned:
            raise ValueError("category must not be empty")
        return cleaned[:64]

    @field_validator("summary", "why_it_matters", "limitations")
    @classmethod
    def _collapse_ws(cls, value: str) -> str:
        return " ".join(value.strip().split())

    @field_validator("key_claims")
    @classmethod
    def _clean_claims(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in value:
            text = " ".join(str(item).strip().split())
            if text:
                cleaned.append(text[:400])
        return cleaned[:8]


class AnalysisCacheKey(BaseModel):
    """Identity for cached analysis results."""

    article_id: str
    content_hash: str
    model_id: str
    config_version: str


ANALYSIS_JSON_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "article_id": {"type": "string"},
        "category": {"type": "string"},
        "summary": {"type": "string"},
        "why_it_matters": {"type": "string"},
        "relevance_score": {"type": "integer", "minimum": 1, "maximum": 5},
        "significance_score": {"type": "integer", "minimum": 1, "maximum": 5},
        "evidence_sufficiency": {
            "type": "string",
            "enum": ["sufficient", "partial", "insufficient"],
        },
        "key_claims": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 8,
        },
        "limitations": {"type": "string"},
    },
    "required": [
        "article_id",
        "category",
        "summary",
        "why_it_matters",
        "relevance_score",
        "significance_score",
        "evidence_sufficiency",
        "key_claims",
        "limitations",
    ],
}


# Config version bumped when prompt/schema/ranking inputs change in a cache-breaking way.
ANALYSIS_CONFIG_VERSION = "m1.v1"

ScoreBlendMode = Literal["default"]
