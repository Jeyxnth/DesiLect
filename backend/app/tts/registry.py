"""Maps language -> (engine, default voice) and keeps at most one engine loaded (H3)."""
from __future__ import annotations

from ..config import get_settings
from .base import TTSEngine
from .kokoro_engine import KokoroEngine
from .parler_engine import ParlerEngine

# lang -> (engine name, default voice)
LANG_ENGINES: dict[str, tuple[str, str]] = {
    "en": ("kokoro", "hf_alpha"),  # Indian-accented English: a Hindi voice speaking en-us phonemes
    "hi": ("kokoro", "hf_alpha"),
    "ta": ("parler", "jaya"),
}
_ENGINE_CLASSES: dict[str, type] = {"kokoro": KokoroEngine, "parler": ParlerEngine}

# Voices a learner can pick (step 11): lang -> [(voice id, label, gender)]
VOICES: dict[str, list[tuple[str, str, str]]] = {
    "en": [("hf_alpha", "Alpha", "female"), ("hm_omega", "Omega", "male")],
    "hi": [("hf_alpha", "Alpha", "female"), ("hm_omega", "Omega", "male")],
    "ta": [("jaya", "Jaya", "female"), ("kavitha", "Kavitha", "female")],  # Indic Parler-TTS has no male Tamil speaker
}

_active: dict[str, TTSEngine] = {}


def list_voices(lang: str) -> list[dict[str, str]]:
    if lang not in VOICES:
        raise ValueError(f"unsupported language: {lang}")
    engine = LANG_ENGINES[lang][0]
    return [{"id": v, "label": label, "gender": gender, "engine": engine} for v, label, gender in VOICES[lang]]


def _engine_for(lang: str) -> tuple[str, str]:
    if lang not in LANG_ENGINES:
        raise ValueError(f"unsupported language: {lang}")
    name, voice = LANG_ENGINES[lang]
    if lang == "ta" and get_settings().tamil_tts != "parler":
        raise NotImplementedError(
            f"TAMIL_TTS={get_settings().tamil_tts!r}: no Plan B Tamil engine is built (see README, Tamil voice)"
        )
    return name, voice


def get_engine(lang: str) -> tuple[TTSEngine, str]:
    """Return (engine, default voice) for a language, dropping any other engine first."""
    name, voice = _engine_for(lang)
    for other in [n for n in _active if n != name]:
        _active.pop(other).unload()
    if name not in _active:
        _active[name] = _ENGINE_CLASSES[name]()
    return _active[name], voice


def release_all() -> None:
    """Unload whatever engine is active (call after the TTS stage)."""
    while _active:
        _active.popitem()[1].unload()
