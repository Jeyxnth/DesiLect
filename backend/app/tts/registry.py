"""Maps language -> (engine, default voice) and keeps at most one engine loaded (H3)."""
from __future__ import annotations

from .base import TTSEngine
from .kokoro_engine import KokoroEngine

# lang -> (engine name, default voice). Step 9 adds ta (Parler) and more voices here.
LANG_ENGINES: dict[str, tuple[str, str]] = {
    "en": ("kokoro", "hf_alpha"),
    "hi": ("kokoro", "hf_alpha"),
}
_ENGINE_CLASSES: dict[str, type] = {"kokoro": KokoroEngine}

_active: dict[str, TTSEngine] = {}


def get_engine(lang: str) -> tuple[TTSEngine, str]:
    """Return (engine, default voice) for a language, dropping any other engine first."""
    if lang == "ta":
        raise NotImplementedError("TODO(step 9): Tamil TTS (Indic Parler-TTS)")
    if lang not in LANG_ENGINES:
        raise ValueError(f"unsupported language: {lang}")
    name, voice = LANG_ENGINES[lang]
    for other in [n for n in _active if n != name]:
        _active.pop(other).unload()
    if name not in _active:
        _active[name] = _ENGINE_CLASSES[name]()
    return _active[name], voice


def release_all() -> None:
    """Unload whatever engine is active (call after the TTS stage)."""
    while _active:
        _active.popitem()[1].unload()
