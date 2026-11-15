"""Source adapter protocol and registry."""

from __future__ import annotations

from typing import Protocol

import httpx

from qwennews.config import SOURCE_ENDPOINTS, Config
from qwennews.models import SourceFetchResult


class SourceAdapter(Protocol):
    name: str

    def fetch(self, client: httpx.Client, config: Config) -> SourceFetchResult:
        """Fetch and normalize articles. Must not raise for remote failures."""
        ...


def list_adapters() -> list[str]:
    return sorted(SOURCE_ENDPOINTS.keys())


def get_adapter(name: str) -> SourceAdapter:
    from qwennews.sources.hackernews import HackerNewsSource
    from qwennews.sources.rss import RssSource

    if name not in SOURCE_ENDPOINTS:
        raise KeyError(f"Unknown source: {name}")

    meta = SOURCE_ENDPOINTS[name]
    if meta["type"] == "hackernews":
        return HackerNewsSource()
    if meta["type"] == "rss":
        return RssSource(
            name=name,
            feed_url=meta["feed"],
            label=meta.get("label", name),
        )
    raise ValueError(f"Unsupported source type for {name}: {meta['type']}")
