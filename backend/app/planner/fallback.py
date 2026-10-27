"""Built-in fallback lessons so the demo never breaks (G2)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ..cache.store import read_json
from ..config import LANGUAGES, SAMPLES_DIR, SHARED_DIR
from .validate import cut_at_word

SAMPLE_NAME = "python_loop"  # default sample, used when nothing matches


@dataclass(frozen=True)
class FallbackSample:
    """A built-in lesson, stored as shared/samples/<name>.<lang>.json."""

    name: str
    subject: str  # for logs and the UI notice, e.g. "programming"
    keywords: frozenset[str]  # specific words: the topic really is this sample's topic
    related: frozenset[str] = frozenset()  # broad words: help pick the closest sample, never count as a match


# To add a sample: drop <name>.{en,hi,ta}.json into shared/samples and register it here.
SAMPLES: tuple[FallbackSample, ...] = (
    FallbackSample(
        "python_loop", "programming",
        keywords=frozenset({"loop", "loops", "iteration", "iterate", "iterating", "range", "while"}),
        related=frozenset({"python", "for", "repeat", "code", "coding", "programming", "program", "computer", "javascript", "java"}),
    ),
    FallbackSample(
        "binary_search", "programming",
        keywords=frozenset({"binary", "bisect", "bisection"}),
        related=frozenset({"search", "searching", "sorted", "algorithm", "algorithms", "find", "array", "list", "lists", "middle", "halve"}),
    ),
    FallbackSample(
        "photosynthesis", "science",
        keywords=frozenset({"photosynthesis", "chlorophyll", "glucose", "stomata"}),
        related=frozenset({"plant", "plants", "leaf", "leaves", "sunlight", "oxygen", "biology", "science", "nature", "cell", "cells", "food", "energy"}),
    ),
    FallbackSample(
        "pythagorean_theorem", "maths",
        keywords=frozenset({"pythagoras", "pythagorean", "hypotenuse", "theorem"}),
        related=frozenset({"triangle", "triangles", "right", "angle", "math", "maths", "mathematics", "geometry", "square", "squares", "algebra", "equation", "sides"}),
    ),
)


def _next_topic_map() -> dict[str, Any]:
    path = SHARED_DIR / "next_topics.json"
    return read_json(path) if path.is_file() else {}


def next_topics_for(sample_name: str) -> list[str] | None:
    """The static follow-up topics of a built-in sample (shared/next_topics.json), English; None without an entry."""
    entry = _next_topic_map().get(sample_name)
    return list(entry["topics"]) if isinstance(entry, dict) and len(entry.get("topics", [])) == 2 else None


def next_topic_labels_for(sample_name: str, language: str) -> list[str] | None:
    """The same topics as button text in hi / ta (None for English or without an entry)."""
    entry = _next_topic_map().get(sample_name)
    labels = entry.get("labels", {}).get(language) if isinstance(entry, dict) else None
    return list(labels) if isinstance(labels, list) and len(labels) == 2 else None


def add_static_next_topics(lesson: dict[str, Any], sample_name: str) -> None:
    """Fallback for next_topics (bonus B2): the sample's entry in shared/next_topics.json, if any."""
    topics = next_topics_for(sample_name)
    if topics:
        lesson["next_topics"] = topics
        labels = next_topic_labels_for(sample_name, lesson.get("language", "en"))
        if labels and lesson.get("language") != "en":
            lesson["next_topic_labels"] = labels


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def closest_sample(topic: str) -> tuple[FallbackSample, bool]:
    """The best-matching sample and whether the topic really matches it.

    Specific keywords score 3, related words 1. With no overlap at all the default (first) sample is used.
    "Matches" means a specific keyword was hit; related words alone only help choose.
    """
    words = _words(topic)

    def score(s: FallbackSample) -> int:
        return 3 * len(words & s.keywords) + len(words & s.related)

    best = max(SAMPLES, key=score)  # max keeps the first sample on ties
    return best, bool(words & best.keywords)


def fallback_lesson(topic: str = "", level: str = "beginner", language: str = "en", reason: str = "") -> dict[str, Any]:
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
    add_static_next_topics(lesson, sample.name)
    if reason:
        lesson["meta"]["reason"] = reason[:200]
    return lesson
