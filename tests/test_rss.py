"""RSS/Atom parsing and failed-source handling tests."""

from __future__ import annotations

import httpx

from qwennews.config import Config
from qwennews.sources.rss import RssSource, parse_feed_bytes

SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example AI Feed</title>
    <link>https://example.com/</link>
    <item>
      <title>First Post</title>
      <link>https://example.com/posts/1?utm_medium=rss</link>
      <guid>https://example.com/posts/1</guid>
      <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
      <author>Ada</author>
    </item>
    <item>
      <title>Second Post</title>
      <link>https://example.com/posts/2/</link>
      <pubDate>Tue, 02 Jan 2024 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""

SAMPLE_ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Example</title>
  <entry>
    <title>Atom Entry</title>
    <link href="https://example.com/atom/1"/>
    <id>urn:example:1</id>
    <updated>2024-03-01T10:00:00Z</updated>
    <author><name>Grace</name></author>
  </entry>
</feed>
"""

HF_STYLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>HF-style</title>
    <item>
      <title>No Link Tag</title>
      <guid isPermaLink="true">https://huggingface.co/blog/example</guid>
      <pubDate>Wed, 03 Jan 2024 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def test_parse_rss_normalization() -> None:
    articles = parse_feed_bytes(SAMPLE_RSS, source="openai", limit=10)
    assert len(articles) == 2
    first = articles[0]
    assert first.title == "First Post"
    assert first.canonical_url == "https://example.com/posts/1"
    assert first.author == "Ada"
    assert first.published_at is not None
    assert first.source == "openai"


def test_parse_atom() -> None:
    articles = parse_feed_bytes(SAMPLE_ATOM, source="deepmind", limit=5)
    assert len(articles) == 1
    assert articles[0].title == "Atom Entry"
    assert articles[0].canonical_url == "https://example.com/atom/1"
    assert articles[0].author == "Grace"


def test_parse_guid_permalink_without_link() -> None:
    articles = parse_feed_bytes(HF_STYLE_RSS, source="huggingface", limit=5)
    assert len(articles) == 1
    assert articles[0].canonical_url == "https://huggingface.co/blog/example"


def test_rss_fetch_success(httpx_mock, config: Config) -> None:
    feed_url = "https://openai.com/news/rss.xml"
    httpx_mock.add_response(
        url=feed_url,
        text=SAMPLE_RSS,
        headers={"Content-Type": "application/rss+xml"},
    )
    source = RssSource(name="openai", feed_url=feed_url, label="OpenAI News")
    with httpx.Client() as client:
        result = source.fetch(client, config)
    assert result.ok
    assert result.items_fetched == 2


def test_rss_fetch_failure_isolated(httpx_mock, config: Config) -> None:
    feed_url = "https://deepmind.google/blog/rss.xml"
    httpx_mock.add_response(url=feed_url, status_code=503)
    source = RssSource(name="deepmind", feed_url=feed_url)
    with httpx.Client() as client:
        result = source.fetch(client, config)
    assert not result.ok
    assert "503" in (result.error or "")
    assert result.articles == []
