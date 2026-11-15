"""Local Ollama /api/chat adapter (no cloud fallback)."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class OllamaError(Exception):
    """Base error for Ollama adapter failures."""


class OllamaUnavailableError(OllamaError):
    """Server unreachable."""


class OllamaModelMissingError(OllamaError):
    """Requested model is not installed locally."""


class OllamaTimeoutError(OllamaError):
    """Request timed out."""


class OllamaResponseError(OllamaError):
    """Malformed or unsuccessful response payload."""


@dataclass(slots=True)
class ChatMetrics:
    model: str
    latency_seconds: float
    wall_time_seconds: float
    prompt_eval_count: int | None = None
    eval_count: int | None = None
    prompt_eval_duration_ns: int | None = None
    eval_duration_ns: int | None = None
    total_duration_ns: int | None = None
    thinking_present: bool = False
    tokens_per_second: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "latency_seconds": self.latency_seconds,
            "wall_time_seconds": self.wall_time_seconds,
            "prompt_eval_count": self.prompt_eval_count,
            "eval_count": self.eval_count,
            "prompt_eval_duration_ns": self.prompt_eval_duration_ns,
            "eval_duration_ns": self.eval_duration_ns,
            "total_duration_ns": self.total_duration_ns,
            "thinking_present": self.thinking_present,
            "tokens_per_second": self.tokens_per_second,
        }


@dataclass(slots=True)
class ChatResult:
    content: str
    raw: dict[str, Any]
    metrics: ChatMetrics
    thinking: str | None = None


@dataclass(slots=True)
class OllamaClient:
    """Thin wrapper around Ollama native HTTP APIs."""

    base_url: str = "http://127.0.0.1:11434"
    model: str = "qwen3:4b"
    timeout_seconds: float = 180.0
    num_predict: int = 900
    think: bool = False
    temperature: float = 0.1
    _lock_note: str = field(default="concurrency=1", repr=False)

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout_seconds),
            trust_env=False,
        )

    def list_models(self) -> list[str]:
        try:
            with self._client() as client:
                response = client.get("/api/tags")
                response.raise_for_status()
                payload = response.json()
        except httpx.ConnectError as exc:
            raise OllamaUnavailableError(f"Ollama unavailable at {self.base_url}: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise OllamaTimeoutError(f"Timed out listing models: {exc}") from exc
        except httpx.HTTPError as exc:
            raise OllamaUnavailableError(f"Failed to list models: {exc}") from exc

        models = payload.get("models") or []
        names: list[str] = []
        for item in models:
            if isinstance(item, dict):
                name = item.get("name") or item.get("model")
                if name:
                    names.append(str(name))
        return names

    def ensure_model(self) -> str:
        names = self.list_models()
        if self.model not in names:
            # Also accept exact match against model field variants already collected.
            raise OllamaModelMissingError(
                f"Model {self.model!r} not installed. Available: {names or '(none)'}"
            )
        return self.model

    def chat(
        self,
        *,
        messages: list[dict[str, str]],
        format: dict[str, Any] | str | None = "json",
        think: bool | None = None,
    ) -> ChatResult:
        """
        Call POST /api/chat sequentially (caller should keep concurrency=1).

        `think` defaults to the client setting. Observed with qwen3:4b: when
        think=false, the message typically contains only role/content (no thinking).
        """
        use_think = self.think if think is None else think
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": use_think,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.num_predict,
            },
        }
        if format is not None:
            body["format"] = format

        started = time.perf_counter()
        try:
            with self._client() as client:
                response = client.post("/api/chat", json=body)
        except httpx.ConnectError as exc:
            raise OllamaUnavailableError(f"Ollama unavailable at {self.base_url}: {exc}") from exc
        except httpx.TimeoutException as exc:
            raise OllamaTimeoutError(
                f"Ollama chat timed out after {self.timeout_seconds}s: {exc}"
            ) from exc
        except httpx.HTTPError as exc:
            raise OllamaResponseError(f"Ollama HTTP error: {exc}") from exc

        latency = time.perf_counter() - started

        if response.status_code == 404:
            # Common when model is missing
            detail = response.text[:300]
            raise OllamaModelMissingError(
                f"Model {self.model!r} rejected by Ollama (404): {detail}"
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise OllamaResponseError(
                f"Ollama chat failed ({response.status_code}): {response.text[:400]}"
            ) from exc

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise OllamaResponseError("Ollama returned non-JSON response") from exc

        if not isinstance(payload, dict):
            raise OllamaResponseError("Ollama JSON root must be an object")

        message = payload.get("message")
        if not isinstance(message, dict):
            raise OllamaResponseError("Ollama response missing message object")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise OllamaResponseError("Ollama message content missing or empty")

        thinking_raw = message.get("thinking")
        thinking = (
            thinking_raw.strip() if isinstance(thinking_raw, str) and thinking_raw.strip() else None
        )

        eval_count = _as_int(payload.get("eval_count"))
        eval_duration_ns = _as_int(payload.get("eval_duration"))
        tokens_per_second = None
        if eval_count and eval_duration_ns and eval_duration_ns > 0:
            tokens_per_second = round(eval_count / (eval_duration_ns / 1e9), 3)

        metrics = ChatMetrics(
            model=str(payload.get("model") or self.model),
            latency_seconds=round(latency, 3),
            wall_time_seconds=round(latency, 3),
            prompt_eval_count=_as_int(payload.get("prompt_eval_count")),
            eval_count=eval_count,
            prompt_eval_duration_ns=_as_int(payload.get("prompt_eval_duration")),
            eval_duration_ns=eval_duration_ns,
            total_duration_ns=_as_int(payload.get("total_duration")),
            thinking_present=thinking is not None,
            tokens_per_second=tokens_per_second,
        )
        logger.info(
            "Ollama chat model=%s latency=%.3fs eval_count=%s tok/s=%s thinking=%s",
            metrics.model,
            metrics.latency_seconds,
            metrics.eval_count,
            metrics.tokens_per_second,
            metrics.thinking_present,
        )
        return ChatResult(content=content, raw=payload, metrics=metrics, thinking=thinking)


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def discover_default_model(base_url: str = "http://127.0.0.1:11434") -> str | None:
    """Return a preferred local Qwen3 4B model id if installed, else first model."""
    client = OllamaClient(base_url=base_url)
    try:
        names = client.list_models()
    except OllamaError:
        return None
    for preferred in ("qwen3:4b", "qwen3:4b-instruct", "qwen3:4b-q4_K_M"):
        if preferred in names:
            return preferred
    for name in names:
        lowered = name.lower()
        if "qwen3" in lowered and "4b" in lowered:
            return name
    return names[0] if names else None
