"""Built-in fallback lessons so the demo never breaks (G2)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..cache.store import read_json
from ..config import LANGUAGES, SAMPLES_DIR
from .validate import cut_at_word

SAMPLE_NAME = "python_loop"  # default sample (kept for callers that want it by name)


@dataclass(frozen=True)
class FallbackSample:
    """A built-in lesson, stored as shared/samples/<name>.<lang>.json."""

    name: str
    keywords: frozenset[str]  # lower-case words that make a topic "match" this sample


# To add a sample: drop <name>.{en,hi,ta}.json into shared/samples and register it here.
SAMPLES: tuple[FallbackSample, ...] = (
    FallbackSample("python_loop", frozenset({"python", "loop", "loops", "for", "while", "range", "iteration", "iterate", "repeat"})),
)


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def closest_sample(topic: str) -> tuple[FallbackSample, bool]:
    """The best-matching sample and whether the topic really matches it (shares a keyword)."""
    words = _words(topic)
    best = max(SAMPLES, key=lambda s: len(words & s.keywords))
    return best, bool(words & best.keywords)


def fallback_lesson(topic: str = "", level: str = "beginner", language: str = "en") -> dict[str, Any]:
    """Return the closest built-in lesson (pre-translated for hi/ta), flagged meta.fallback = true.

    The title becomes the requested topic only when the topic matches the sample; otherwise the
    sample keeps its own title so the video never claims to teach something it does not.
    """
    sample, matches = closest_sample(topic)
    lang = language if language in LANGUAGES else "en"
    lesson = read_json(SAMPLES_DIR / f"{sample.name}.{lang}.json")
    lesson["level"] = level if level in ("beginner", "intermediate") else "beginner"
    clean_topic = " ".join(topic.split())
    if matches and clean_topic and lang == "en":  # translated titles stay in their own language
        lesson["title"] = cut_at_word(clean_topic, 80)
    lesson["meta"] = {"fallback": True, "source": f"sample:{sample.name}", "topic": clean_topic[:200]}
    return lesson
