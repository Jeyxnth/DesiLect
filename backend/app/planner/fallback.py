"""Built-in fallback lesson so the demo never breaks (G2)."""
from __future__ import annotations

from typing import Any

from ..cache.store import read_json
from ..config import LANGUAGES, SAMPLES_DIR

SAMPLE_NAME = "python_loop"


def fallback_lesson(topic: str = "", level: str = "beginner", language: str = "en") -> dict[str, Any]:
    """Return the pre-written (and pre-translated) sample lesson.

    topic and level are accepted for signature stability; the sample is fixed.
    """
    lang = language if language in LANGUAGES else "en"
    lesson = read_json(SAMPLES_DIR / f"{SAMPLE_NAME}.{lang}.json")
    lesson["level"] = level if level in ("beginner", "intermediate") else "beginner"
    return lesson
