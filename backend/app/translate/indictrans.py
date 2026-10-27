"""English -> Hindi/Tamil translation with IndicTrans2, CPU only, loaded then unloaded (H3)."""
from __future__ import annotations

from typing import Any

from ..planner.fallback import fallback_lesson

TARGET_CODES = {"hi": "hin_Deva", "ta": "tam_Taml"}
SOURCE_CODE = "eng_Latn"


def translate_texts(texts: list[str], target_lang: str) -> list[str]:
    """Translate English strings to target_lang with protected terms kept (G5).

    TODO(step 8): load model from models/, protect()/restore(), batch, unload.
    """
    raise NotImplementedError("TODO(step 8): IndicTrans2 translation")


def translate_lesson(lesson: dict[str, Any], target_lang: str) -> dict[str, Any]:
    """Translate narration, heading, subheading and title; keep code and items in English.

    Falls back to the pre-translated sample on any failure (G2).
    TODO(step 8): real translation via translate_texts.
    """
    if target_lang == "en":
        return lesson
    try:
        raise NotImplementedError("TODO(step 8)")
    except Exception:
        meta = lesson.get("meta", {})
        reason = "Translation to this language is not available yet."
        if meta.get("fallback") and meta.get("reason"):  # the planner already failed: that is the real cause
            reason = meta["reason"]
        return fallback_lesson(meta.get("topic", ""), lesson.get("level", "beginner"), target_lang, reason=reason)


def unload() -> None:
    """Release the model from memory. TODO(step 8)."""
