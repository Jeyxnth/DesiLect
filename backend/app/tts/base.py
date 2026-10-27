"""Common interface for local TTS engines. Stable: later steps add engines, not methods."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

SAMPLE_RATE = 24_000  # every engine returns 24 kHz mono float32


@runtime_checkable
class TTSEngine(Protocol):
    """A CPU-only local TTS engine. Only one is loaded at a time (H3)."""

    name: str
    languages: tuple[str, ...]

    def load(self) -> None:
        """Load model weights from models/ (offline)."""

    def unload(self) -> None:
        """Free memory after the TTS stage."""

    def synth(self, text: str, lang: str, voice: str, speed: float = 1.0) -> tuple[np.ndarray, int]:
        """Synthesize one sentence. Returns (float32 mono samples, sample_rate)."""
