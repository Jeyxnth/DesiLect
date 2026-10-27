"""Client for the local Ollama server (127.0.0.1 only, H1/H2)."""
from __future__ import annotations

import copy
import json
import os
from typing import Any

import httpx

from ..config import SCHEMA_DIR, drill, get_settings

TIMEOUT_S = 120.0
OPTIONS = {"temperature": 0.2, "num_ctx": 4096}


class OllamaError(RuntimeError):
    """Ollama gave no usable answer."""


class OllamaNotRunning(OllamaError):
    """Nothing is listening on the Ollama port."""


class OllamaModelMissing(OllamaError):
    """Ollama is running but the model has not been pulled."""


class OllamaTimeout(OllamaError):
    """The model did not answer within the timeout."""


def lesson_format_schema(quiz_questions: int = 3) -> dict[str, Any]:
    """lesson.schema.json as the structured-output `format`, minus `meta` (the backend sets that, not the model).

    With quiz_questions > 0 the quiz becomes required with exactly that many questions, so the model always writes
    one; with 0 it is left out of the format entirely. The stored lesson schema keeps the quiz optional.
    """
    schema = json.loads((SCHEMA_DIR / "lesson.schema.json").read_text(encoding="utf-8"))
    schema = copy.deepcopy(schema)
    schema["properties"].pop("meta", None)
    schema["$defs"].pop("meta", None)
    if quiz_questions > 0:
        schema["required"] = [*schema["required"], "quiz"]
        schema["$defs"]["quiz"].update(minItems=quiz_questions, maxItems=quiz_questions)
    else:
        schema["properties"].pop("quiz", None)
    return schema


class OllamaClient:
    """Thin httpx wrapper around /api/chat. `http_client` can be injected (tests use a mock transport)."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        s = get_settings()
        self.base_url = (base_url or s.ollama_url).rstrip("/")
        self.model = model or s.ollama_model
        self._http = http_client or httpx.Client(timeout=httpx.Timeout(TIMEOUT_S, connect=3.0))

    @staticmethod
    def _options() -> dict[str, Any]:
        """Sampling options; OLLAMA_NUM_GPU=0 forces CPU-only inference (to measure a CPU-only laptop, H3)."""
        options: dict[str, Any] = dict(OPTIONS)
        if os.environ.get("OLLAMA_NUM_GPU", "").strip() != "":
            options["num_gpu"] = int(os.environ["OLLAMA_NUM_GPU"])
        return options

    def list_models(self, timeout: float = 1.5) -> list[str]:
        """Names of pulled models. Raises OllamaNotRunning if the server is down."""
        try:
            r = self._http.get(f"{self.base_url}/api/tags", timeout=timeout)
            r.raise_for_status()
            return [m["name"] for m in r.json().get("models", [])]
        except httpx.TimeoutException as exc:
            raise OllamaTimeout(str(exc)) from exc
        except (httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            raise OllamaNotRunning(f"Ollama is not running at {self.base_url}") from exc
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise OllamaError(str(exc)) from exc

    def is_available(self, timeout: float = 0.5) -> bool:
        """True if the Ollama server answers."""
        try:
            self.list_models(timeout)
            return True
        except OllamaError:
            return False

    def has_model(self, timeout: float = 1.5) -> bool:
        """True if the configured model is pulled."""
        try:
            names = self.list_models(timeout)
        except OllamaError:
            return False
        wanted = self.model if ":" in self.model else f"{self.model}:latest"
        return wanted in names

    def chat_json(self, system: str, user: str, schema: dict[str, Any] | None = None) -> str:
        """Ask for JSON matching `schema` and return the raw message text. The caller must parse and validate it."""
        if drill("planner-garbage"):  # failure drill: the planner answers with junk instead of a lesson
            return "Sure! Here is your lesson about it: {scenes: [title_card, oops"
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "format": schema if schema is not None else "json",
            "options": self._options(),
            "keep_alive": 0,  # free the model's RAM as soon as planning ends (H3)
        }
        try:
            r = self._http.post(f"{self.base_url}/api/chat", json=body, timeout=httpx.Timeout(TIMEOUT_S, connect=3.0))
        except httpx.TimeoutException as exc:
            raise OllamaTimeout(f"no answer from {self.model} within {TIMEOUT_S:.0f}s") from exc
        except (httpx.ConnectError, httpx.RemoteProtocolError) as exc:
            raise OllamaNotRunning(f"Ollama is not running at {self.base_url}") from exc
        except httpx.HTTPError as exc:
            raise OllamaError(str(exc)) from exc
        if r.status_code == 404:
            raise OllamaModelMissing(f"model {self.model!r} is not pulled; run: python scripts/download_models.py ollama")
        if r.status_code >= 400:
            raise OllamaError(f"HTTP {r.status_code}: {r.text[:300]}")
        try:
            return str(r.json()["message"]["content"])
        except (ValueError, KeyError, TypeError) as exc:
            raise OllamaError(f"unexpected Ollama reply: {r.text[:200]}") from exc
