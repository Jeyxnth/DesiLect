"""Indic Parler-TTS for Tamil."""
from __future__ import annotations

import numpy as np

from ..config import get_settings


class ParlerEngine:
    """TODO(step 9): Tamil synthesis on CPU."""

    name = "parler"
    languages = ("ta",)

    def __init__(self) -> None:
        self.model_dir = get_settings().models_dir / "indic-parler-tts"
        self._model = None

    def load(self) -> None:
        raise NotImplementedError("TODO(step 9): load Indic Parler-TTS from models/")

    def unload(self) -> None:
        self._model = None

    def synth(self, text: str, lang: str, voice: str, speed: float = 1.0) -> tuple[np.ndarray, int]:
        raise NotImplementedError("TODO(step 9): Parler synthesis")
