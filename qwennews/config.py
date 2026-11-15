"""Configuration loaded from environment variables / optional .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Known source identifiers. Availability is documented in docs/milestones/m0.md.
ALL_SOURCES: tuple[str, ...] = (
    "hackernews",
    "openai",
    "deepmind",
    "huggingface",
    "techcrunch",
)

# Verified endpoints (probed during M0). Do not invent substitutes.
SOURCE_ENDPOINTS: dict[str, dict[str, str]] = {
    "hackernews": {
        "type": "hackernews",
        "topstories": "https://hacker-news.firebaseio.com/v0/topstories.json",
        "newstories": "https://hacker-news.firebaseio.com/v0/newstories.json",
        "item": "https://hacker-news.firebaseio.com/v0/item/{id}.json",
    },
    "openai": {
        "type": "rss",
        "feed": "https://openai.com/news/rss.xml",
        "label": "OpenAI News",
    },
    "deepmind": {
        "type": "rss",
        "feed": "https://deepmind.google/blog/rss.xml",
        "label": "Google DeepMind Blog",
    },
    "huggingface": {
        "type": "rss",
        "feed": "https://huggingface.co/blog/feed.xml",
        "label": "Hugging Face Blog",
    },
    "techcrunch": {
        "type": "rss",
        "feed": "https://techcrunch.com/category/artificial-intelligence/feed/",
        "label": "TechCrunch AI",
    },
}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


@dataclass(slots=True)
class Config:
    """Runtime configuration for ingestion and local analysis."""

    db_path: Path = field(default_factory=lambda: Path("data/qwennews.db"))
    user_agent: str = "QwenNews/0.1 (+https://localhost; local news aggregator; research use)"
    connect_timeout: float = 5.0
    read_timeout: float = 20.0
    max_response_bytes: int = 2_097_152
    hn_limit: int = 30
    rss_limit: int = 20
    max_concurrency: int = 4
    enabled_sources: tuple[str, ...] = ALL_SOURCES
    extract_content: bool = True
    respect_robots: bool = True
    # Local Ollama / Qwen analysis (M1)
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:4b"
    ollama_timeout: float = 180.0
    ollama_num_predict: int = 900
    ollama_think: bool = False
    ollama_temperature: float = 0.1
    report_dir: Path = field(default_factory=lambda: Path("data/reports"))
    # M2 ranking: optional "category:score,category:score" overrides
    category_priority_overrides: dict[str, float] = field(default_factory=dict)

    @property
    def timeout(self) -> float:
        """Combined timeout used by httpx Timeout convenience constructors."""
        return self.connect_timeout + self.read_timeout

    def is_source_enabled(self, source: str) -> bool:
        return source in self.enabled_sources

    def source_limit(self, source: str) -> int:
        if source == "hackernews":
            return self.hn_limit
        return self.rss_limit


def load_config(env_file: str | Path | None = ".env") -> Config:
    """Load configuration from the environment, optionally reading a .env file."""
    if env_file:
        path = Path(env_file)
        if path.is_file():
            load_dotenv(path)

    enabled_raw = os.getenv("QWENNEWS_ENABLED_SOURCES", ",".join(ALL_SOURCES))
    enabled = tuple(part.strip().lower() for part in enabled_raw.split(",") if part.strip())
    unknown = [s for s in enabled if s not in ALL_SOURCES]
    if unknown:
        raise ValueError(f"Unknown source(s) in QWENNEWS_ENABLED_SOURCES: {unknown}")

    return Config(
        db_path=Path(os.getenv("QWENNEWS_DB_PATH", "data/qwennews.db")),
        user_agent=os.getenv(
            "QWENNEWS_USER_AGENT",
            "QwenNews/0.1 (+https://localhost; local news aggregator; research use)",
        ),
        connect_timeout=_env_float("QWENNEWS_CONNECT_TIMEOUT", 5.0),
        read_timeout=_env_float("QWENNEWS_READ_TIMEOUT", 20.0),
        max_response_bytes=_env_int("QWENNEWS_MAX_RESPONSE_BYTES", 2_097_152),
        hn_limit=_env_int("QWENNEWS_HN_LIMIT", 30),
        rss_limit=_env_int("QWENNEWS_RSS_LIMIT", 20),
        max_concurrency=_env_int("QWENNEWS_MAX_CONCURRENCY", 4),
        enabled_sources=enabled or ALL_SOURCES,
        extract_content=_env_bool("QWENNEWS_EXTRACT_CONTENT", True),
        respect_robots=_env_bool("QWENNEWS_RESPECT_ROBOTS", True),
        ollama_base_url=os.getenv("QWENNEWS_OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        ollama_model=os.getenv("QWENNEWS_OLLAMA_MODEL", "qwen3:4b"),
        ollama_timeout=_env_float("QWENNEWS_OLLAMA_TIMEOUT", 180.0),
        ollama_num_predict=_env_int("QWENNEWS_OLLAMA_NUM_PREDICT", 900),
        ollama_think=_env_bool("QWENNEWS_OLLAMA_THINK", False),
        ollama_temperature=_env_float("QWENNEWS_OLLAMA_TEMPERATURE", 0.1),
        report_dir=Path(os.getenv("QWENNEWS_REPORT_DIR", "data/reports")),
        category_priority_overrides=_parse_category_priorities(
            os.getenv("QWENNEWS_CATEGORY_PRIORITIES", "")
        ),
    )


def _parse_category_priorities(raw: str) -> dict[str, float]:
    """Parse `weather:1.0,models:5.0` style overrides."""
    out: dict[str, float] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        name, score = part.split(":", 1)
        try:
            out[name.strip().lower()] = float(score.strip())
        except ValueError:
            continue
    return out


def default_ranking_config_from_env():
    """Build RankingConfig using env overrides when present."""
    from qwennews.ranking import default_ranking_config

    cfg = load_config()
    return default_ranking_config(cfg.category_priority_overrides)
