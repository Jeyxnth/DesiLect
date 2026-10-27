"""Indic Parler-TTS for Tamil."""
from __future__ import annotations

from pathlib import Path

from ..config import get_settings
from .base import AudioResult, TTSEngine


class ParlerEngine(TTSEngine):
    """TODO(step 9): Tamil synthesis on CPU."""

    name = "parler"
    languages = ("ta",)

    def __init__(self) -> None:
        self.model_dir = get_settings().models_dir / "indic-parler-tts"
        self._model = None

    def load(self) -> None:
        raise NotImplementedError("TODO(step 9): load Indic Parler-TTS from models/")

    def synthesize(self, text: str, language: str, out_path: Path, voice: str | None = None) -> AudioResult:
        raise NotImplementedError("TODO(step 9): Parler synthesis")

    def unload(self) -> None:
        self._model = None
