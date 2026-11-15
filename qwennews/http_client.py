"""Shared HTTP client with timeouts, size limits, and safe redirect handling."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any

import httpx

from qwennews.config import Config
from qwennews.urls import UnsafeURLError, validate_public_http_url

logger = logging.getLogger(__name__)

TEXT_CONTENT_TYPES = (
    "text/html",
    "application/xhtml+xml",
    "text/plain",
    "application/xml",
    "text/xml",
    "application/rss+xml",
    "application/atom+xml",
    "application/json",
)


class ResponseTooLargeError(RuntimeError):
    """Raised when a response exceeds the configured size limit."""


class BinaryContentError(RuntimeError):
    """Raised when a response Content-Type is not text-like."""


def build_client(config: Config) -> httpx.Client:
    """Create a shared httpx client. Redirects are handled manually for SSRF checks."""
    timeout = httpx.Timeout(
        connect=config.connect_timeout,
        read=config.read_timeout,
        write=config.read_timeout,
        pool=config.connect_timeout,
    )
    return httpx.Client(
        timeout=timeout,
        headers={"User-Agent": config.user_agent, "Accept": "*/*"},
        follow_redirects=False,
        trust_env=True,
    )


def _content_type_allowed(content_type: str | None, allowed: Iterable[str]) -> bool:
    if not content_type:
        return True  # some endpoints omit CT; allow and inspect later
    mime = content_type.split(";", 1)[0].strip().lower()
    return any(mime == item or mime.startswith(item) for item in allowed)


def safe_get(
    client: httpx.Client,
    url: str,
    *,
    max_bytes: int,
    max_redirects: int = 5,
    allowed_content_types: Iterable[str] | None = None,
    resolve_dns: bool = True,
) -> httpx.Response:
    """
    GET a URL with SSRF validation on every hop, response size capping,
    and optional content-type filtering.
    """
    allowed = tuple(allowed_content_types) if allowed_content_types else TEXT_CONTENT_TYPES
    current = validate_public_http_url(url, resolve_dns=resolve_dns)
    seen: set[str] = set()

    for _ in range(max_redirects + 1):
        if current in seen:
            raise UnsafeURLError(f"Redirect loop detected at {current}")
        seen.add(current)

        response = client.get(current)
        if response.is_redirect:
            location = response.headers.get("Location")
            if not location:
                raise UnsafeURLError("Redirect response missing Location header")
            next_url = str(httpx.URL(current).join(location))
            current = validate_public_http_url(next_url, resolve_dns=resolve_dns)
            response.close()
            continue

        response.raise_for_status()
        content_type = response.headers.get("Content-Type")
        if not _content_type_allowed(content_type, allowed):
            response.close()
            raise BinaryContentError(
                f"Refusing non-text Content-Type {content_type!r} for {current}"
            )

        # Prefer Content-Length when present; still enforce after decode.
        content_length = response.headers.get("Content-Length")
        if content_length and content_length.isdigit():
            if int(content_length) > max_bytes:
                response.close()
                raise ResponseTooLargeError(
                    f"Content-Length {content_length} exceeds limit {max_bytes}"
                )

        # Accessing .content lets httpx handle Content-Encoding once.
        body = response.content
        if len(body) > max_bytes:
            response.close()
            raise ResponseTooLargeError(f"Response exceeded max size of {max_bytes} bytes")
        return response

    raise UnsafeURLError(f"Too many redirects fetching {url}")


def get_json(
    client: httpx.Client,
    url: str,
    *,
    max_bytes: int,
    resolve_dns: bool = True,
) -> Any:
    """Fetch JSON from a public endpoint."""
    response = safe_get(
        client,
        url,
        max_bytes=max_bytes,
        allowed_content_types=("application/json", "text/plain", "text/json"),
        resolve_dns=resolve_dns,
    )
    return response.json()


def get_text(
    client: httpx.Client,
    url: str,
    *,
    max_bytes: int,
    allowed_content_types: Iterable[str] | None = None,
    resolve_dns: bool = True,
) -> tuple[str, str]:
    """
    Fetch text content.

    Returns (final_url, text).
    """
    response = safe_get(
        client,
        url,
        max_bytes=max_bytes,
        allowed_content_types=allowed_content_types,
        resolve_dns=resolve_dns,
    )
    return str(response.url), response.text
