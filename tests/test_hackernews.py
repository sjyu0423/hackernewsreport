"""Hacker News API parsing tests with mocked HTTP."""

from __future__ import annotations

import json

import httpx

from qwennews.config import Config
from qwennews.sources.hackernews import HackerNewsSource


def test_hn_parsing_and_normalization(httpx_mock, config: Config) -> None:
    httpx_mock.add_response(
        url="https://hacker-news.firebaseio.com/v0/topstories.json",
        json=[101, 102],
    )
    httpx_mock.add_response(
        url="https://hacker-news.firebaseio.com/v0/newstories.json",
        json=[102, 103],
    )
    httpx_mock.add_response(
        url="https://hacker-news.firebaseio.com/v0/item/101.json",
        json={
            "id": 101,
            "type": "story",
            "title": "Example Story",
            "url": "https://example.com/a?utm_source=hn",
            "by": "alice",
            "score": 42,
            "descendants": 7,
            "time": 1_700_000_000,
        },
    )
    httpx_mock.add_response(
        url="https://hacker-news.firebaseio.com/v0/item/102.json",
        json={
            "id": 102,
            "type": "story",
            "title": "Ask HN: Tools?",
            "by": "bob",
            "score": 10,
            "descendants": 3,
            "time": 1_700_000_100,
        },
    )
    httpx_mock.add_response(
        url="https://hacker-news.firebaseio.com/v0/item/103.json",
        json={
            "id": 103,
            "type": "comment",
            "text": "not a story",
            "by": "carol",
            "time": 1_700_000_200,
        },
    )

    config.hn_limit = 10
    source = HackerNewsSource()
    with httpx.Client() as client:
        result = source.fetch(client, config)

    assert result.ok
    assert result.items_fetched == 2
    by_title = {a.title: a for a in result.articles}

    story = by_title["Example Story"]
    assert story.canonical_url == "https://example.com/a"
    assert story.hn_score == 42
    assert story.hn_comment_count == 7
    assert story.hn_discussion_url == "https://news.ycombinator.com/item?id=101"
    assert story.author == "alice"
    assert "utm_source" not in story.canonical_url

    ask = by_title["Ask HN: Tools?"]
    assert ask.original_url.startswith("https://news.ycombinator.com/item?id=102")
    assert ask.hn_discussion_url == ask.original_url


def test_hn_list_failure_isolated(httpx_mock, config: Config) -> None:
    httpx_mock.add_response(
        url="https://hacker-news.firebaseio.com/v0/topstories.json",
        status_code=500,
    )
    source = HackerNewsSource()
    with httpx.Client() as client:
        result = source.fetch(client, config)
    assert not result.ok
    assert result.error
    assert result.articles == []


def test_hn_rejects_non_array_payload(httpx_mock, config: Config) -> None:
    httpx_mock.add_response(
        url="https://hacker-news.firebaseio.com/v0/topstories.json",
        text=json.dumps({"nope": True}),
        headers={"Content-Type": "application/json"},
    )
    httpx_mock.add_response(
        url="https://hacker-news.firebaseio.com/v0/newstories.json",
        json=[1],
    )
    source = HackerNewsSource()
    with httpx.Client() as client:
        result = source.fetch(client, config)
    assert result.error
    assert "expected JSON arrays" in result.error
