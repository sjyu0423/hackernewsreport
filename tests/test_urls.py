"""URL canonicalization and SSRF rejection tests."""

from __future__ import annotations

import pytest

from qwennews.urls import (
    UnsafeURLError,
    article_id_for_url,
    canonicalize_url,
    is_hn_discussion_url,
    strip_tracking_params,
    validate_public_http_url,
)


def test_strip_tracking_params() -> None:
    url = "https://Example.com/path?utm_source=x&id=1&fbclid=abc#frag"
    cleaned = strip_tracking_params(url)
    assert "utm_source" not in cleaned
    assert "fbclid" not in cleaned
    assert "id=1" in cleaned
    assert "#frag" not in cleaned


def test_canonicalize_url_dedupes() -> None:
    a = canonicalize_url("https://Example.com/Story/?utm_campaign=1")
    b = canonicalize_url("https://example.com/Story")
    assert a == b
    assert article_id_for_url(a) == article_id_for_url(b)


def test_hn_discussion_detection() -> None:
    assert is_hn_discussion_url("https://news.ycombinator.com/item?id=123")
    assert not is_hn_discussion_url("https://example.com/item?id=123")


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/secret",
        "http://localhost/secret",
        "http://192.168.1.10/x",
        "http://10.0.0.5/x",
        "http://[::1]/",
        "file:///etc/passwd",
        "http://169.254.169.254/latest/meta-data/",
    ],
)
def test_reject_unsafe_urls(url: str) -> None:
    with pytest.raises(UnsafeURLError):
        validate_public_http_url(url, resolve_dns=False)


def test_accept_public_url_without_dns() -> None:
    validate_public_http_url("https://example.com/article", resolve_dns=False)
