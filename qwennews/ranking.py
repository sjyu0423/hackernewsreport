"""Deterministic ranking with category priorities and diversity (M2)."""

from __future__ import annotations

from dataclasses import dataclass
from math import log10
from typing import Any

from qwennews.analysis_schema import ArticleAnalysis

# Configurable category priorities (1.0–5.0). Higher = more preferred for AI briefing.
DEFAULT_CATEGORY_PRIORITIES: dict[str, float] = {
    "models": 5.0,
    "ai models": 5.0,
    "model release": 5.0,
    "research": 4.7,
    "tooling": 4.5,
    "developer infrastructure": 4.5,
    "infrastructure": 4.4,
    "robotics": 4.0,
    "security": 3.8,
    "payments": 3.2,
    "business": 3.0,
    "policy": 2.8,
    "weather": 1.2,
    "sports": 1.0,
    "entertainment": 1.1,
    "uncertain": 2.0,
}

# Categories treated as low AI-briefing value even if HN-popular.
LOW_PRIORITY_CATEGORIES = frozenset(
    {
        "weather",
        "sports",
        "entertainment",
        "lifestyle",
        "food",
        "travel",
    }
)

AI_SIGNAL_TERMS = frozenset(
    {
        "model",
        "models",
        "llm",
        "gpt",
        "gemini",
        "claude",
        "openai",
        "deepmind",
        "huggingface",
        "pytorch",
        "inference",
        "agent",
        "agents",
        "training",
        "benchmark",
        "gguf",
        "ollama",
        "transformer",
        "diffusion",
        "robotics",
        "ml",
        "ai",
    }
)


@dataclass(slots=True)
class RankingConfig:
    category_priorities: dict[str, float]
    max_per_source: int = 3
    max_per_category: int = 4
    hn_weight: float = 0.05
    category_weight: float = 0.25
    significance_weight: float = 0.35
    relevance_weight: float = 0.25
    ai_signal_weight: float = 0.10


def default_ranking_config(
    overrides: dict[str, float] | None = None,
) -> RankingConfig:
    priorities = dict(DEFAULT_CATEGORY_PRIORITIES)
    if overrides:
        for key, value in overrides.items():
            priorities[key.strip().lower()] = float(value)
    return RankingConfig(category_priorities=priorities)


def category_priority(category: str | None, config: RankingConfig) -> float:
    if not category:
        return 2.5
    key = category.strip().lower()
    if key in config.category_priorities:
        return config.category_priorities[key]
    # Fuzzy contains
    for name, score in config.category_priorities.items():
        if name in key or key in name:
            return score
    return 2.8


def hn_attention_capped(hn_score: int | None, *, cap: float = 3.5) -> float:
    """
    Map HN score to a capped secondary signal in [1, cap].

    Intentionally weaker/capped vs M1 so popularity cannot dominate AI priority.
    """
    if not isinstance(hn_score, int) or hn_score < 0:
        return 2.0
    raw = 1.0 + log10(hn_score + 1) * 1.2
    return max(1.0, min(cap, raw))


def ai_signal_score(article: dict[str, Any], analysis: ArticleAnalysis | None) -> float:
    """1–5 score estimating AI/tech-development centrality from title/category/claims."""
    blob_parts = [
        str(article.get("title") or ""),
        str(analysis.category if analysis else ""),
        " ".join(analysis.key_claims if analysis else []),
        str(analysis.summary if analysis else "")[:400],
    ]
    blob = " ".join(blob_parts).lower()
    hits = sum(1 for term in AI_SIGNAL_TERMS if term in blob)
    if hits >= 5:
        return 5.0
    if hits >= 3:
        return 4.2
    if hits >= 1:
        return 3.2
    # Explicit low-priority categories
    cat = (analysis.category if analysis else "") or ""
    if cat.strip().lower() in LOW_PRIORITY_CATEGORIES:
        return 1.2
    return 2.0


def compute_rank_score_m2(
    article: dict[str, Any],
    analysis: ArticleAnalysis,
    *,
    config: RankingConfig | None = None,
) -> float:
    """
    Documented M2 ranking function:

    rank = 0.35*significance + 0.25*relevance + 0.25*category_priority
         + 0.10*ai_signal + 0.05*hn_attention_capped

    Relevance and significance remain separate inputs (not collapsed).
    HN popularity is a capped secondary signal only.
    """
    cfg = config or default_ranking_config()
    significance = float(analysis.significance_score)
    relevance = float(analysis.relevance_score)
    cat = category_priority(analysis.category, cfg)
    ai = ai_signal_score(article, analysis)
    hn = hn_attention_capped(
        article.get("hn_score") if isinstance(article.get("hn_score"), int) else None
    )

    # Extra penalty: high HN + low AI category must not outrank model releases.
    if analysis.category and analysis.category.strip().lower() in LOW_PRIORITY_CATEGORIES:
        cat = min(cat, 1.5)
        relevance = min(relevance, 2.5)

    score = (
        cfg.significance_weight * significance
        + cfg.relevance_weight * relevance
        + cfg.category_weight * cat
        + cfg.ai_signal_weight * ai
        + cfg.hn_weight * hn
    )
    return round(score, 4)


def apply_diversity(
    ranked: list[tuple[float, dict[str, Any], ArticleAnalysis]],
    *,
    limit: int,
    config: RankingConfig | None = None,
) -> list[tuple[float, dict[str, Any], ArticleAnalysis]]:
    """Limit domination by a single source or category while preserving score order."""
    cfg = config or default_ranking_config()
    selected: list[tuple[float, dict[str, Any], ArticleAnalysis]] = []
    source_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}

    for score, article, analysis in ranked:
        sources = str(article.get("sources") or "unknown").split(",")
        primary_source = sources[0].strip() or "unknown"
        cat = (analysis.category or "unknown").strip().lower()
        if source_counts.get(primary_source, 0) >= cfg.max_per_source:
            continue
        if category_counts.get(cat, 0) >= cfg.max_per_category:
            continue
        selected.append((score, article, analysis))
        source_counts[primary_source] = source_counts.get(primary_source, 0) + 1
        category_counts[cat] = category_counts.get(cat, 0) + 1
        if len(selected) >= limit:
            break
    return selected
