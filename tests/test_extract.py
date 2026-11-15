"""Content extraction and unsafe redirect rejection tests."""

from __future__ import annotations

from qwennews.config import Config
from qwennews.extract import ContentExtractor, extract_text_from_html
from qwennews.http_client import build_client
from qwennews.models import ContentExtractionStatus

HTML_ARTICLE = """
<html><head><title>Demo</title></head>
<body>
<nav>ignore</nav>
<article>
  <h1>Demo</h1>
  <p>This is a long enough paragraph for extraction to succeed in tests.</p>
  <p>Second paragraph keeps the extractor happy with enough content overall.</p>
</article>
</body></html>
"""


def test_extract_text_from_html() -> None:
    text = extract_text_from_html(HTML_ARTICLE)
    assert text is not None
    assert "long enough paragraph" in text
    assert "ignore" not in text


def test_extraction_failure_fallback(httpx_mock, config: Config) -> None:
    url = "https://example.com/paywalled"
    httpx_mock.add_response(url=url, status_code=403)
    with build_client(config) as client:
        extractor = ContentExtractor(client, config)
        # Bypass robots for this unit test path by disabling respect.
        config.respect_robots = False
        result = extractor.extract(url)
    assert result.text is None
    assert result.status == ContentExtractionStatus.BLOCKED


def test_extraction_success(httpx_mock, config: Config) -> None:
    url = "https://example.com/ok"
    httpx_mock.add_response(
        url=url,
        text=HTML_ARTICLE,
        headers={"Content-Type": "text/html; charset=utf-8"},
    )
    # robots.txt allow
    httpx_mock.add_response(
        url="https://example.com/robots.txt",
        text="User-agent: *\nAllow: /\n",
        headers={"Content-Type": "text/plain"},
    )
    config.respect_robots = True
    with build_client(config) as client:
        extractor = ContentExtractor(client, config)
        result = extractor.extract(url)
    assert result.status == ContentExtractionStatus.SUCCESS
    assert result.text is not None
    assert "long enough paragraph" in result.text


def test_hn_discussion_skipped(config: Config) -> None:
    with build_client(config) as client:
        extractor = ContentExtractor(client, config)
        result = extractor.extract("https://news.ycombinator.com/item?id=42")
    assert result.status == ContentExtractionStatus.SKIPPED
    assert result.text is None


def test_unsafe_url_rejected(config: Config) -> None:
    with build_client(config) as client:
        extractor = ContentExtractor(client, config)
        result = extractor.extract("http://127.0.0.1/secret")
    assert result.status == ContentExtractionStatus.UNSAFE_URL


def test_redirect_to_private_rejected(httpx_mock, config: Config) -> None:
    public = "https://example.com/redirect"
    httpx_mock.add_response(
        url=public,
        status_code=302,
        headers={"Location": "http://127.0.0.1/internal"},
    )
    httpx_mock.add_response(
        url="https://example.com/robots.txt",
        text="User-agent: *\nAllow: /\n",
    )
    config.respect_robots = True
    with build_client(config) as client:
        extractor = ContentExtractor(client, config)
        result = extractor.extract(public)
    assert result.status == ContentExtractionStatus.UNSAFE_URL
