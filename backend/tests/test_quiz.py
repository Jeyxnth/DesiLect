"""Bonus B1: the end-of-lesson quiz. Made in the same planner call; a bad quiz never fails or delays the lesson."""
import copy
import json
from types import SimpleNamespace

import numpy as np
import pytest

from app.config import SAMPLES_DIR
from app.planner.ollama_client import lesson_format_schema
from app.planner.prompts import build_system_prompt
from app.planner.validate import clean_quiz, parse_and_validate, parse_quiz, shuffle_quiz, validate_lesson, validate_timeline

from .test_planner import TARGET, mock_client, plan, store  # noqa: F401  (store is a fixture)

SAMPLE = json.loads((SAMPLES_DIR / "python_loop.en.json").read_text(encoding="utf-8"))


def quiz() -> list[dict]:
    return copy.deepcopy(SAMPLE["quiz"])


def reply(q) -> dict:
    lesson = copy.deepcopy(SAMPLE)
    lesson["quiz"] = q
    return lesson


# --- validation ---------------------------------------------------------------------------------

def test_valid_quiz_is_kept():
    kept, warnings = clean_quiz(quiz())
    assert kept == quiz() and warnings == []


def test_one_broken_question_is_dropped():
    q = quiz()
    q[1]["options"][2] = q[1]["options"][0].upper()  # options must be unique, case-insensitive
    kept, warnings = clean_quiz(q)
    assert [x["question"] for x in kept] == [quiz()[0]["question"], quiz()[2]["question"]]
    assert len(warnings) == 1 and "quiz/1 dropped" in warnings[0] and "options repeat" in warnings[0]


def test_two_broken_questions_drop_the_quiz():
    q = quiz()
    q[0]["answer_index"] = 4
    q[2]["options"] = q[2]["options"][:3]
    kept, warnings = clean_quiz(q)
    assert kept is None
    assert any("answer_index" in w for w in warnings) and any("exactly 4" in w for w in warnings)
    assert warnings[-1].startswith("quiz dropped: 1 usable question")


@pytest.mark.parametrize("bad", ["<b>loop</b>", "<script>alert(1)</script>", "javascript:alert(1)", "<img src=x onerror=alert(1)>"])
def test_html_in_an_option_is_rejected(bad):
    q = quiz()
    q[0]["options"][3] = bad
    kept, warnings = clean_quiz(q)
    assert len(kept) == 2 and "HTML or script markup" in warnings[0]


@pytest.mark.parametrize("field,value,limit", [("question", "x" * 161, "1-160"), ("explanation", "y" * 201, "1-200")])
def test_length_limits(field, value, limit):
    q = quiz()
    q[0][field] = value
    _, warnings = clean_quiz(q)
    assert limit in warnings[0]
    q[0]["options"][0] = "z" * 81
    assert any("1-80" in w for w in clean_quiz(q)[1])


def test_all_of_the_above_and_other_scripts_are_rejected():
    q = quiz()
    q[0]["options"][3] = "All of the above"
    q[1]["question"] = "loop क्या है?"
    kept, warnings = clean_quiz(q)
    assert kept is None and "all/none of the above" in warnings[0] and "non-English" in warnings[1]


@pytest.mark.parametrize("garbage", ["garbage", 42, {"question": "x"}, [], ["a", "b", "c"]])
def test_garbage_quiz_is_dropped_without_error(garbage):
    kept, warnings = clean_quiz(garbage)
    assert kept is None and warnings


def test_quiz_never_affects_lesson_validation_or_the_word_budget():
    words = sum(len(s["narration"].split()) for s in SAMPLE["scenes"])
    target = round(words / 2.3)
    long_quiz = quiz()
    long_quiz[0]["explanation"] = " ".join(["word"] * 60)  # 60 extra words: would break the budget if counted
    for q in (long_quiz, "garbage", None):
        lesson, errors = parse_and_validate(json.dumps(reply(q)), target)
        assert errors == [] and lesson is not None and "quiz" not in lesson


def test_shuffle_keeps_the_right_answer_and_is_seeded():
    q = quiz()
    a, b = shuffle_quiz(q, "lesson-1"), shuffle_quiz(q, "lesson-1")
    assert a == b  # same lesson id, same order
    for before, after in zip(q, a):
        assert sorted(after["options"]) == sorted(before["options"])
        assert after["options"][after["answer_index"]] == before["options"][before["answer_index"]]
    first = [{**x, "answer_index": 0, "options": [x["options"][x["answer_index"]]] + [o for k, o in enumerate(x["options"]) if k != x["answer_index"]]} for x in q]
    positions = {shuffle_quiz(first, f"id-{n}")[0]["answer_index"] for n in range(40)}
    assert len(positions) > 1  # an answer the model always put first does not stay first


# --- planner ------------------------------------------------------------------------------------

def test_prompt_and_format_ask_for_the_quiz():
    assert 'exactly 3 multiple-choice questions' in build_system_prompt("beginner", 45, 3)
    assert '"quiz"' in build_system_prompt("beginner", 45, 3)  # the few-shot example carries one
    assert "multiple-choice" not in build_system_prompt("beginner", 45, 0) and '"quiz"' not in build_system_prompt("beginner", 45, 0)
    fmt = lesson_format_schema(2)
    assert "quiz" in fmt["required"] and fmt["$defs"]["quiz"]["minItems"] == fmt["$defs"]["quiz"]["maxItems"] == 2
    assert "quiz" not in lesson_format_schema(0)["properties"]


def test_planned_lesson_gets_the_shuffled_quiz(store):
    lesson, meta = plan(mock_client(reply(quiz())), store)
    assert meta["quiz_dropped"] is False and meta["quiz_questions"] == 3 and meta["attempts"] == 1
    assert validate_lesson(lesson) == [] and len(lesson["quiz"]) == 3
    assert lesson["quiz"] == shuffle_quiz(quiz(), "t1")
    timings = json.loads((store / "t1" / "timings.json").read_text(encoding="utf-8"))
    assert timings["quiz_dropped"] is False
    assert "=== quiz: kept 3" in (store / "t1" / "planner_raw.txt").read_text(encoding="utf-8")


def test_garbage_quiz_still_gives_the_lesson_with_no_retry(store):
    lesson, meta = plan(mock_client(reply("garbage")), store)
    assert meta["fallback"] is False and meta["attempts"] == 1  # never a reason to retry or fall back
    assert "quiz" not in lesson and validate_lesson(lesson) == []
    assert meta["quiz_dropped"] is True and meta["quiz_warnings"]
    assert json.loads((store / "t1" / "timings.json").read_text(encoding="utf-8"))["quiz_dropped"] is True
    assert "--- warning: quiz is a str" in (store / "t1" / "planner_raw.txt").read_text(encoding="utf-8")


def test_quiz_garbage_drill_drops_only_the_quiz(store, monkeypatch):
    monkeypatch.setenv("BLU_DRILL", "quiz-garbage")
    lesson, meta = plan(mock_client(reply(quiz())), store)
    assert meta["fallback"] is False and "quiz" not in lesson and meta["quiz_dropped"] is True


def test_quiz_off(store, monkeypatch):
    monkeypatch.setattr("app.pipeline.orchestrator.get_settings", lambda: SimpleNamespace(quiz_questions=0))
    lesson, meta = plan(mock_client(reply(quiz())), store)
    assert "quiz" not in lesson and "quiz_dropped" not in meta


def test_parse_quiz_on_non_json():
    assert parse_quiz("not json")[0] is None


# --- translation --------------------------------------------------------------------------------

def test_quiz_translation_keeps_a_question_in_english_when_options_collide(monkeypatch):
    from app.translate import indictrans

    def fake(texts, lang, stats=None):
        # every option of question 0 becomes the same word; everything else gets a Hindi prefix
        out = []
        for t in texts:
            out.append("विकल्प" if t in quiz()[0]["options"] else f"हिं {t}")
        return out

    monkeypatch.setattr(indictrans, "translate_texts", fake)
    tr = indictrans.translate_quiz(quiz(), "hi", {})
    assert tr[0] == quiz()[0]  # collided: kept whole, in English
    assert tr[1]["question"].startswith("हिं ") and tr[1]["answer_index"] == quiz()[1]["answer_index"]
    assert tr[2]["options"][0].startswith("हिं ")


def test_quiz_translation_failure_keeps_english(monkeypatch):
    from app.translate import indictrans

    def boom(*a, **k):
        raise RuntimeError("model crashed")

    monkeypatch.setattr(indictrans, "translate_texts", boom)
    assert indictrans.translate_quiz(quiz(), "ta", {}) == quiz()


def test_code_options_are_not_translated(monkeypatch):
    from app.translate import indictrans

    seen = []
    monkeypatch.setattr(indictrans, "translate_texts", lambda texts, lang, stats=None: seen.extend(texts) or [f"த {t}" for t in texts])
    q = quiz()
    q[0]["options"] = ["range(3)", "i = 0", "print(i)", "Loops repeat code"]
    indictrans.translate_quiz(q, "ta", {})
    assert "range(3)" not in seen and "i = 0" not in seen and "Loops repeat code" in seen
    assert quiz()[0]["question"] in seen  # a question with code in it is still translated (protect.py keeps range(3))


# --- timeline -----------------------------------------------------------------------------------

def test_timeline_carries_the_quiz_and_timing_is_unchanged(tmp_path, monkeypatch):
    from app.cache import store as cache_store
    from app.timing import timeline as tl
    from app.tts.base import SAMPLE_RATE

    class Engine:
        name = "fake"

        def unload(self): ...

        def synth(self, text, lang, voice, speed=1.0):
            return np.full(round((0.3 + 0.02 * len(text)) * SAMPLE_RATE), 0.3, dtype=np.float32), SAMPLE_RATE

    settings = SimpleNamespace(outputs_dir=tmp_path / "outputs")
    monkeypatch.setattr("app.cache.store.get_settings", lambda: settings)
    monkeypatch.setattr(tl, "get_settings", lambda: settings)
    monkeypatch.setattr(cache_store, "BUNDLED_TTS_DIR", tmp_path / "no-bundle")
    monkeypatch.setattr(tl, "get_engine", lambda lang, engine=None: (Engine(), "v"))
    with_quiz = tl.build_timeline(copy.deepcopy(SAMPLE), "en", tmp_path / "a")
    without = copy.deepcopy(SAMPLE)
    without.pop("quiz")
    plain = tl.build_timeline(without, "en", tmp_path / "b")
    assert with_quiz["quiz"] == SAMPLE["quiz"] and "quiz" not in plain
    strip = lambda t: {k: v for k, v in t.items() if k not in ("quiz", "lesson_id", "audio_url")}  # noqa: E731
    assert strip(with_quiz) == strip(plain)  # same scenes, cues, beats and total
    assert (tmp_path / "a" / "lesson.wav").read_bytes() == (tmp_path / "b" / "lesson.wav").read_bytes()


def test_timeline_quiz_is_checked_against_the_lesson_schema():
    scene = {"index": 0, "type": "title_card", "start": 0, "end": 1, "heading": "h",
             "data": {"type": "title_card", "heading": "h", "narration": "n"}, "cues": [], "beats": []}
    timeline = {"lesson_id": "x", "language": "en", "total_seconds": 1.0, "audio_url": "a.wav", "scenes": [scene]}
    assert validate_timeline(timeline) == []
    assert validate_timeline({**timeline, "quiz": SAMPLE["quiz"]}) == []
    assert any(e.startswith("quiz:") for e in validate_timeline({**timeline, "quiz": [{"question": "q"}]}))


@pytest.mark.parametrize("lang", ["en", "hi", "ta"])
def test_fallback_sample_quiz_is_valid_in_every_language(lang):
    sample = json.loads((SAMPLES_DIR / f"python_loop.{lang}.json").read_text(encoding="utf-8"))
    kept, warnings = clean_quiz(sample["quiz"], 3, lang)
    assert kept == sample["quiz"] and warnings == [] and validate_lesson(sample) == []
    assert [q["answer_index"] for q in sample["quiz"]] == [1, 0, 2]  # the right answer is not always first
