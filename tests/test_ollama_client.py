"""Ollama adapter tests with mocked HTTP."""

from __future__ import annotations

import pytest

from qwennews.ollama_client import (
    OllamaClient,
    OllamaModelMissingError,
    OllamaTimeoutError,
    OllamaUnavailableError,
)


def test_list_and_ensure_model(httpx_mock) -> None:
    payload = {"models": [{"name": "qwen3:4b", "model": "qwen3:4b"}]}
    httpx_mock.add_response(
        url="http://127.0.0.1:11434/api/tags",
        json=payload,
        is_reusable=True,
    )
    client = OllamaClient(model="qwen3:4b")
    assert client.list_models() == ["qwen3:4b"]
    assert client.ensure_model() == "qwen3:4b"


def test_missing_model(httpx_mock) -> None:
    httpx_mock.add_response(
        url="http://127.0.0.1:11434/api/tags",
        json={"models": [{"name": "other:7b"}]},
    )
    client = OllamaClient(model="qwen3:4b")
    with pytest.raises(OllamaModelMissingError):
        client.ensure_model()


def test_unavailable(httpx_mock) -> None:
    import httpx

    def _raise(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    httpx_mock.add_callback(_raise)
    client = OllamaClient()
    with pytest.raises(OllamaUnavailableError):
        client.list_models()


def test_chat_parses_metrics_without_thinking(httpx_mock) -> None:
    httpx_mock.add_response(
        url="http://127.0.0.1:11434/api/chat",
        json={
            "model": "qwen3:4b",
            "message": {"role": "assistant", "content": '{"ok": true}'},
            "prompt_eval_count": 100,
            "eval_count": 40,
            "prompt_eval_duration": 1_000_000_000,
            "eval_duration": 2_000_000_000,
            "total_duration": 3_500_000_000,
            "done": True,
        },
    )
    client = OllamaClient(think=False)
    result = client.chat(messages=[{"role": "user", "content": "hi"}], format="json")
    assert result.content == '{"ok": true}'
    assert result.thinking is None
    assert result.metrics.thinking_present is False
    assert result.metrics.eval_count == 40
    assert result.metrics.tokens_per_second == 20.0


def test_chat_timeout(httpx_mock) -> None:
    import httpx

    httpx_mock.add_exception(httpx.ReadTimeout("slow"))
    client = OllamaClient(timeout_seconds=1)
    with pytest.raises(OllamaTimeoutError):
        client.chat(messages=[{"role": "user", "content": "x"}])


def test_malformed_chat_response(httpx_mock) -> None:
    from qwennews.ollama_client import OllamaResponseError

    httpx_mock.add_response(
        url="http://127.0.0.1:11434/api/chat",
        json={"message": {"role": "assistant", "content": ""}},
    )
    client = OllamaClient()
    with pytest.raises(OllamaResponseError):
        client.chat(messages=[{"role": "user", "content": "x"}])
