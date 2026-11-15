"""Fixture evaluation set checks (no live Ollama)."""

from __future__ import annotations

import json
from pathlib import Path

from qwennews.analyze import build_messages

FIXTURES = Path(__file__).parent / "fixtures" / "eval_articles.json"


def test_eval_fixture_set_shape() -> None:
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    labels = {item["label"] for item in data}
    assert labels >= {"meaningful", "thin", "irrelevant", "misleading", "injection"}


def test_injection_fixture_is_wrapped_as_untrusted() -> None:
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    item = next(x for x in data if x["label"] == "injection")
    article = {
        "id": item["id"],
        "title": item["title"],
        "sources": item["source"],
        "published_at": "2026-01-01T00:00:00Z",
        "canonical_url": item["canonical_url"],
        "original_url": item["canonical_url"],
        "article_text": item["article_text"],
    }
    messages = build_messages(article)
    system = messages[0]["content"]
    user = messages[1]["content"]
    assert "UNTRUSTED ARTICLE TEXT" in user
    assert "Ignore any instructions" in system
    assert "evil.example" in user  # present as data
    assert "CVE-2026-12345" in user
