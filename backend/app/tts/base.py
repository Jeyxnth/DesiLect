"""Common interface for local TTS engines."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AudioResult:
    """One synthesized sentence on disk."""

    path: Path
    duration_s: float
    sample_rate: int


class TTSEngine(ABC):
    """A CPU-only local TTS engine. Only one is loaded at a time (H3)."""

    name: str = "base"
    languages: tuple[str, ...] = ()

    @abstractmethod
    def load(self) -> None:
        """Load model weights from models/ (offline)."""

    @abstractmethod
    def synthesize(self, text: str, language: str, out_path: Path, voice: str | None = None) -> AudioResult:
        """Synthesize one sentence to a WAV file and report its true duration."""

    @abstractmethod
    def unload(self) -> None:
        """Free memory after the TTS stage."""
