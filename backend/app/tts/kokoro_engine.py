"""Kokoro (kokoro-onnx) for English and Hindi, CPU only, files from models/kokoro/."""
from __future__ import annotations

import numpy as np

from ..config import get_settings
from .base import SAMPLE_RATE

MODEL_FILE = "kokoro-v1.0.onnx"
VOICES_FILE = "voices-v1.0.bin"

# Kokoro language codes. English uses the Indian-accented Hindi voices through en-us phonemes.
LANG_CODES = {"en": "en-us", "hi": "hi"}
# Tried in order when the requested voice is missing from the voices file.
FALLBACK_VOICES = ("hf_alpha", "hm_omega")


def to_24k_mono(samples: np.ndarray, sr: int) -> np.ndarray:
    """Mono float32 at SAMPLE_RATE (linear resample; kokoro already outputs 24 kHz)."""
    x = np.asarray(samples, dtype=np.float32)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if sr != SAMPLE_RATE and len(x) > 1:
        n = round(len(x) * SAMPLE_RATE / sr)
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
    return x


class KokoroEngine:
    name = "kokoro"
    languages = ("en", "hi")

    def __init__(self) -> None:
        self.model_dir = get_settings().models_dir / "kokoro"
        self._kokoro = None
        self._voices: set[str] | None = None

    def available_voices(self) -> set[str]:
        """Voice names in the voices file (cheap: does not load the ONNX model)."""
        if self._voices is None:
            path = self.model_dir / VOICES_FILE
            if not path.is_file():
                raise FileNotFoundError(f"{path} missing; run scripts/download_models.py kokoro")
            with np.load(path, allow_pickle=False) as data:
                self._voices = set(data.files)
        return self._voices

    def resolve_voice(self, voice: str) -> str:
        """The requested voice if present, else the first available fallback."""
        voices = self.available_voices()
        for candidate in (voice, *FALLBACK_VOICES):
            if candidate in voices:
                return candidate
        raise ValueError(f"no usable Kokoro voice (wanted {voice!r}, have {len(voices)} others)")

    def load(self) -> None:
        if self._kokoro is not None:
            return
        from kokoro_onnx import Kokoro  # imported lazily: heavy

        model, voices = self.model_dir / MODEL_FILE, self.model_dir / VOICES_FILE
        for p in (model, voices):
            if not p.is_file():
                raise FileNotFoundError(f"{p} missing; run scripts/download_models.py kokoro")
        self._kokoro = Kokoro(str(model), str(voices))

    def unload(self) -> None:
        self._kokoro = None

    def synth(self, text: str, lang: str, voice: str, speed: float = 1.0) -> tuple[np.ndarray, int]:
        if lang not in LANG_CODES:
            raise NotImplementedError(f"Kokoro does not handle language {lang!r}")
        self.load()
        assert self._kokoro is not None
        samples, sr = self._kokoro.create(
            text, voice=self.resolve_voice(voice), speed=speed, lang=LANG_CODES[lang]
        )
        return to_24k_mono(samples, sr), SAMPLE_RATE
