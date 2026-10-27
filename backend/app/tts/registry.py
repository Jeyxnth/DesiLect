"""Chooses the TTS engine per language and keeps at most one loaded (H3)."""
from __future__ import annotations

from .base import TTSEngine
from .kokoro_engine import KokoroEngine
from .parler_engine import ParlerEngine

ENGINE_FOR_LANGUAGE: dict[str, type[TTSEngine]] = {
    "en": KokoroEngine,
    "hi": KokoroEngine,
    "ta": ParlerEngine,
}

_active: TTSEngine | None = None


def get_engine(language: str) -> TTSEngine:
    """Return the engine for a language, unloading any other engine first."""
    global _active
    cls = ENGINE_FOR_LANGUAGE.get(language)
    if cls is None:
        raise ValueError(f"unsupported language: {language}")
    if _active is not None and not isinstance(_active, cls):
        _active.unload()
        _active = None
    if _active is None:
        _active = cls()
    return _active


def release_all() -> None:
    """Unload whatever engine is active (call after the TTS stage)."""
    global _active
    if _active is not None:
        _active.unload()
        _active = None
