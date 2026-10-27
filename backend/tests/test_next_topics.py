"""Bonus B2: two follow-up topics from the same planner call; dropped (never retried) when invalid."""
import copy
import json

import pytest

from app.config import SAMPLES_DIR
from app.planner.fallback import fallback_lesson
from app.planner.ollama_client import lesson_format_schema
from app.planner.prompts import build_system_prompt
from app.planner.validate import clean_next_topics, parse_and_validate, validate_lesson

from .test_planner import mock_client, plan, store  # noqa: F401  (store is a fixture)

SAMPLE = json.loads((SAMPLES_DIR / "python_loop.en.json").read_text(encoding="utf-8"))


def reply(next_topics) -> dict:
    lesson = copy.deepcopy(SAMPLE)
    lesson["next_topics"] = next_topics
    return lesson


def test_valid_next_topics_are_kept_and_cleaned():
    assert clean_next_topics(["  Python  while loop ", "Python lists"]) == (["Python while loop", "Python lists"], [])


@pytest.mark.parametrize("bad", [
    "garbage", ["only one"], ["one", "two", "three"], ["ab", "Python lists"], ["x" * 61, "Python lists"],
    ["Python lists", "python LISTS"], ["<b>Loops</b>", "Python lists"], ["लूप", "Python lists"], [1, 2],
])
def test_invalid_next_topics_are_dropped(bad):
    topics, warnings = clean_next_topics(bad)
    assert topics is None and warnings and warnings[0].startswith("next_topics dropped")


def test_next_topics_never_reject_the_lesson():
    for bad in ("garbage", ["x"], None):
        lesson, errors = parse_and_validate(json.dumps(reply(bad)), 50)
        assert errors == [] and lesson is not None and "next_topics" not in lesson


def test_prompt_and_format_ask_for_next_topics():
    prompt = build_system_prompt("beginner", 45)
    assert '"next_topics": exactly 2' in prompt and '"Python while loop"' in prompt  # rule and the example
    fmt = lesson_format_schema()
    assert "next_topics" in fmt["required"] and "next_topic_labels" not in fmt["properties"]


def test_planned_lesson_keeps_the_models_next_topics(store):
    lesson, meta = plan(mock_client(reply(["Recursion in Python", "Python dictionaries"])), store, topic="Loops")
    assert lesson["next_topics"] == ["Recursion in Python", "Python dictionaries"] and meta["next_topics_dropped"] is False
    assert meta["attempts"] == 1 and validate_lesson(lesson) == []


def test_invalid_next_topics_fall_back_to_the_static_map_without_a_retry(store):
    lesson, meta = plan(mock_client(reply("garbage")), store, topic="How does a Python loop work?")
    assert meta["attempts"] == 1 and meta["fallback"] is False and meta["next_topics_dropped"] is True
    assert lesson["next_topics"] == ["Python while loop", "Python lists"]  # shared/next_topics.json
    assert "next_topics dropped" in (store / "t1" / "planner_raw.txt").read_text(encoding="utf-8")


def test_no_map_entry_means_no_suggestions(store):
    lesson, _ = plan(mock_client(reply(None)), store, topic="The French Revolution")
    assert "next_topics" not in lesson


@pytest.mark.parametrize("lang", ["en", "hi", "ta"])
def test_fallback_samples_carry_next_topics_and_labels(lang):
    lesson = fallback_lesson("Photosynthesis", "beginner", lang)
    assert lesson["next_topics"] == ["How plants breathe", "The water cycle"]  # English in every language
    assert ("next_topic_labels" in lesson) == (lang != "en") and validate_lesson(lesson) == []


def test_translated_labels_and_english_requests(monkeypatch):
    from app.translate import indictrans

    monkeypatch.setattr(indictrans, "translate_next_topics", lambda topics, lang, stats: [f"हिं {t}" for t in topics])
    monkeypatch.setattr(indictrans, "_translate_lesson", lambda lesson, lang, stats: {**copy.deepcopy(lesson), "language": lang})
    monkeypatch.setattr(indictrans, "unload", lambda: None)
    lesson = reply(["Recursion", "Python lists"])
    lesson["meta"] = {"fallback": False}
    out = indictrans.translate_lesson(lesson, "hi")
    assert out["next_topics"] == ["Recursion", "Python lists"] and out["next_topic_labels"] == ["हिं Recursion", "हिं Python lists"]


def test_label_translation_failure_keeps_english_buttons(monkeypatch):
    from app.translate import indictrans

    def boom(*a, **k):
        raise RuntimeError("model crashed")

    monkeypatch.setattr(indictrans, "translate_texts", boom)
    assert indictrans.translate_next_topics(["Recursion", "Python lists"], "ta", {}) is None
