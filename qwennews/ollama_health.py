"""Ollama availability checks (detect only — never start servers)."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Any

import httpx

from qwennews.config import Config, load_config


@dataclass(slots=True)
class OllamaHealth:
    reachable: bool
    model_present: bool
    base_url: str
    model: str
    installed_models: list[str]
    ollama_binary: str | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "reachable": self.reachable,
            "model_present": self.model_present,
            "base_url": self.base_url,
            "model": self.model,
            "installed_models": self.installed_models,
            "ollama_binary": self.ollama_binary,
            "error": self.error,
            "ok": self.reachable and self.model_present,
        }


def check_ollama(config: Config | None = None, *, timeout: float = 3.0) -> OllamaHealth:
    """
    Probe the configured Ollama endpoint.

    Never launches ``ollama serve`` or modifies login items / launch services.
    """
    cfg = config or load_config()
    binary = shutil.which("ollama")
    try:
        with httpx.Client(base_url=cfg.ollama_base_url.rstrip("/"), timeout=timeout) as client:
            response = client.get("/api/tags")
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:  # noqa: BLE001
        return OllamaHealth(
            reachable=False,
            model_present=False,
            base_url=cfg.ollama_base_url,
            model=cfg.ollama_model,
            installed_models=[],
            ollama_binary=binary,
            error=str(exc),
        )

    names: list[str] = []
    for item in payload.get("models") or []:
        if isinstance(item, dict):
            name = item.get("name") or item.get("model")
            if name:
                names.append(str(name))
    present = cfg.ollama_model in names
    return OllamaHealth(
        reachable=True,
        model_present=present,
        base_url=cfg.ollama_base_url,
        model=cfg.ollama_model,
        installed_models=names,
        ollama_binary=binary,
        error=None if present else f"model {cfg.ollama_model!r} not installed",
    )
