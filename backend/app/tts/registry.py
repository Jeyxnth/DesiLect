"""Maps language -> (engine, default voice) and keeps at most one engine loaded (H3)."""
from __future__ import annotations

from ..config import get_settings
from .base import TTSEngine
from .indic_tts_engine import IndicTTSEngine
from .kokoro_engine import KokoroEngine
from .parler_engine import ParlerEngine

# lang -> (engine name, default voice). Tamil's engine is chosen by TAMIL_TTS (see TAMIL_ENGINES).
LANG_ENGINES: dict[str, tuple[str, str]] = {
    "en": ("kokoro", "hf_alpha"),  # Indian-accented English: a Hindi voice speaking en-us phonemes
    "hi": ("kokoro", "hf_alpha"),
    "ta": ("indic-tts", "female"),
}
# TAMIL_TTS value -> (engine name, default voice)
TAMIL_ENGINES: dict[str, tuple[str, str]] = {
    "indic-tts": ("indic-tts", "female"),  # default: FastPitch + HiFi-GAN, about 10x faster than Parler on CPU
    "parler": ("parler", "jaya"),  # opt-in: 5-9x real time, so live Tamil lessons take minutes to voice
}
_ENGINE_CLASSES: dict[str, type] = {"kokoro": KokoroEngine, "parler": ParlerEngine, "indic-tts": IndicTTSEngine}

# Voices a learner can pick (step 11): engine -> [(voice id, label, gender)]
ENGINE_VOICES: dict[str, list[tuple[str, str, str]]] = {
    "kokoro": [("hf_alpha", "Alpha", "female"), ("hm_omega", "Omega", "male")],
    # Indic Parler-TTS's other Tamil speaker, Kavitha, drags words and cut a short sentence; it has no male one
    "parler": [("jaya", "Jaya", "female")],
    "indic-tts": [("female", "Female", "female"), ("male", "Male", "male")],
}

_active: dict[str, TTSEngine] = {}


def _engine_for(lang: str) -> tuple[str, str]:
    if lang not in LANG_ENGINES:
        raise ValueError(f"unsupported language: {lang}")
    if lang == "ta":
        choice = get_settings().tamil_tts
        if choice not in TAMIL_ENGINES:
            raise NotImplementedError(f"TAMIL_TTS={choice!r}: choose one of {', '.join(TAMIL_ENGINES)}")
        return TAMIL_ENGINES[choice]
    return LANG_ENGINES[lang]


def voice_for(lang: str, gender: str) -> str:
    """The language's engine voice for "female" or "male"; its default voice when the engine has no such voice."""
    engine, default = _engine_for(lang)
    return next((v for v, _, g in ENGINE_VOICES[engine] if g == gender), default)


def list_voices(lang: str) -> list[dict[str, str]]:
    engine = _engine_for(lang)[0]
    return [{"id": v, "label": label, "gender": gender, "engine": engine} for v, label, gender in ENGINE_VOICES[engine]]


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
