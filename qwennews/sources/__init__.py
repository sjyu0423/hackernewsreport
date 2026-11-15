"""News source adapters."""

from qwennews.sources.base import SourceAdapter, get_adapter, list_adapters
from qwennews.sources.hackernews import HackerNewsSource
from qwennews.sources.rss import RssSource

__all__ = [
    "SourceAdapter",
    "HackerNewsSource",
    "RssSource",
    "get_adapter",
    "list_adapters",
]
