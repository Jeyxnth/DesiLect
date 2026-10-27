"""Kokoro TTS for English (Indian accent voice) and Hindi."""
from __future__ import annotations

from pathlib import Path

from ..config import get_settings
from .base import AudioResult, TTSEngine


class KokoroEngine(TTSEngine):
    """TODO(step 2): English; TODO(step 9): Hindi."""

    name = "kokoro"
    languages = ("en", "hi")

    def __init__(self) -> None:
        self.model_dir = get_settings().models_dir / "kokoro"
        self._pipeline = None

    def load(self) -> None:
        raise NotImplementedError("TODO(step 2): load Kokoro from models/kokoro")

    def synthesize(self, text: str, language: str, out_path: Path, voice: str | None = None) -> AudioResult:
        raise NotImplementedError("TODO(step 2): Kokoro synthesis")

    def unload(self) -> None:
        self._pipeline = None
