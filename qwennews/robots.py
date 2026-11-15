"""robots.txt helpers with a small in-memory cache."""

from __future__ import annotations

import logging
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from qwennews.http_client import safe_get
from qwennews.urls import UnsafeURLError, validate_public_http_url

logger = logging.getLogger(__name__)


class RobotsChecker:
    """Fetch and cache robots.txt decisions per origin."""

    def __init__(self, client: httpx.Client, *, max_bytes: int, user_agent: str) -> None:
        self._client = client
        self._max_bytes = max_bytes
        self._user_agent = user_agent
        self._parsers: dict[str, RobotFileParser | None] = {}

    def _origin(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"

    def _load(self, origin: str) -> RobotFileParser | None:
        if origin in self._parsers:
            return self._parsers[origin]

        robots_url = f"{origin}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            validate_public_http_url(robots_url, resolve_dns=True)
            response = safe_get(
                self._client,
                robots_url,
                max_bytes=min(self._max_bytes, 256_000),
                allowed_content_types=("text/plain", "text/html", "text/*"),
            )
            parser.parse(response.text.splitlines())
            self._parsers[origin] = parser
            return parser
        except (UnsafeURLError, httpx.HTTPError, OSError, ValueError) as exc:
            # Fail open for robots fetch errors (network/404) but log clearly.
            # Many sites 404 robots.txt; treat as unrestricted.
            logger.info("robots.txt unavailable for %s (%s); allowing fetch", origin, exc)
            self._parsers[origin] = None
            return None

    def allowed(self, url: str) -> bool:
        """Return True if User-Agent may fetch the URL per robots.txt."""
        origin = self._origin(url)
        parser = self._load(origin)
        if parser is None:
            return True
        return bool(parser.can_fetch(self._user_agent, url))
