"""HTTP client size limits and content-encoding handling."""

from __future__ import annotations

import pytest

from qwennews.config import Config
from qwennews.http_client import ResponseTooLargeError, build_client, get_text, safe_get


def test_safe_get_returns_text_body(httpx_mock, config: Config) -> None:
    payload = '<?xml version="1.0"?><rss version="2.0"><channel></channel></rss>'
    httpx_mock.add_response(
        url="https://example.com/feed.xml",
        text=payload,
        headers={"Content-Type": "application/rss+xml"},
    )
    with build_client(config) as client:
        _url, text = get_text(
            client,
            "https://example.com/feed.xml",
            max_bytes=config.max_response_bytes,
        )
    assert "<rss" in text


def test_safe_get_rejects_oversized_content_length(httpx_mock, config: Config) -> None:
    config.max_response_bytes = 100
    httpx_mock.add_response(
        url="https://example.com/big",
        text="x" * 50,
        headers={
            "Content-Type": "text/html",
            "Content-Length": "999999",
        },
    )
    with build_client(config) as client:
        with pytest.raises(ResponseTooLargeError):
            safe_get(
                client,
                "https://example.com/big",
                max_bytes=config.max_response_bytes,
            )
