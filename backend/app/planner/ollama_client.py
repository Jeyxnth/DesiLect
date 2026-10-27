"""Minimal client for a local Ollama server (localhost only, H1/H2)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from ..config import get_settings


class OllamaError(RuntimeError):
    """Raised when Ollama is unreachable or returns an unusable reply."""


class OllamaClient:
    """Talks to Ollama's HTTP API on this machine. TODO(step 5): harden, stream, tune options."""

    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        s = get_settings()
        self.base_url = (base_url or s.ollama_url).rstrip("/")
        self.model = model or s.ollama_model

    def is_available(self, timeout: float = 0.5) -> bool:
        """True if the Ollama server answers."""
        try:
            with urllib.request.urlopen(f"{self.base_url}/api/tags", timeout=timeout):
                return True
        except (urllib.error.URLError, OSError):
            return False

    def generate_json(self, system: str, prompt: str, timeout: float = 180.0) -> str:
        """Ask the model for JSON and return the raw text. Caller must parse and validate."""
        body: dict[str, Any] = {
            "model": self.model,
            "system": system,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "keep_alive": 0,  # unload right after the stage (H3)
            "options": {"temperature": 0.3},
        }
        req = urllib.request.Request(
            f"{self.base_url}/api/generate",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return str(json.loads(resp.read().decode("utf-8"))["response"])
        except (urllib.error.URLError, OSError, KeyError, ValueError) as exc:
            raise OllamaError(str(exc)) from exc
