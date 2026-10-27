import json
import re

import pytest

from app.config import SAMPLES_DIR
from app.planner.validate import validate_lesson
from app.timing.sentences import split_sentences
from app.translate import indictrans
from app.translate.protect import missing_placeholders, protect, restore

DEVANAGARI = re.compile("[ऀ-ॿ]")
TAMIL = re.compile("[஀-௿]")


def sample(name):
    return json.loads((SAMPLES_DIR / f"{name}.en.json").read_text(encoding="utf-8"))


# --- protection (no model needed) ---

@pytest.mark.parametrize("text, kept", [
    ("The range(3) call gives 0, 1 and 2 to the loop.", ["range(3)", "0", "1", "2", "loop"]),
    ("First i = 0, then i += 1 each time.", ["i = 0", "i += 1"]),
    ("Call binary_search with a sorted list.", ["binary_search", "sorted", "list"]),
    ("Plants turn carbon dioxide into glucose.", ["carbon dioxide", "glucose"]),
    ("Use `print(i)` inside the for loop.", ["`print(i)`", "for loop"]),
])
def test_placeholders_round_trip(text, kept):
    masked, mapping = protect(text)
    for span in kept:
        assert span in mapping.values()
        assert span not in masked or span in ("0", "1", "2")  # digits may appear inside <IDn> tags
    assert restore(masked, mapping) == text
    assert missing_placeholders(masked, mapping) == []


def test_restore_tolerates_spaces_inside_tags_and_reports_lost_ones():
    masked, mapping = protect("Use range(3) in the loop.")
    assert restore(masked.replace("<ID0>", "< ID0 >"), mapping).startswith("Use range(3)")
    assert missing_placeholders(masked.replace("<ID1>", ""), mapping) == ["<ID1>"]


def test_retry_protection_keeps_code_but_not_glossary_words():
    _, mapping = protect("The loop calls range(3).", use_glossary=False)
    assert list(mapping.values()) == ["range(3)"]


def test_plain_english_words_are_not_protected():
    _, mapping = protect("For example, if it is high, we go back.")
    assert mapping == {}


@pytest.mark.parametrize("item, code", [("i = 0", True), ("print(i)", True), ("16", True), ("16 sorted numbers", False), ("Water", False)])
def test_code_items_are_detected(item, code):
    assert indictrans.is_code_item(item) is code


# --- lesson translation logic with a fake model ---

@pytest.fixture
def fake_model(monkeypatch, tmp_path):
    """A stand-in for IndicTrans2: 'translates' to Devanagari but keeps every <IDn> tag."""
    monkeypatch.setattr(indictrans, "load", lambda: None)
    monkeypatch.setattr(indictrans, "unload", lambda: None)
    monkeypatch.setattr(indictrans, "translate_cache_path", lambda m, l, t: tmp_path / f"{abs(hash((m, l, t)))}.json")
    calls = []

    def fake(texts, tgt):
        calls.append(list(texts))
        return [" ".join(w if w.startswith("<ID") else "शब्द" for w in t.replace(".", " .").split()) for t in texts]

    monkeypatch.setattr(indictrans, "_generate", fake)
    return calls


def test_translate_lesson_keeps_code_numbers_and_sentence_counts(fake_model):
    en = sample("python_loop")
    hi = indictrans.translate_lesson(en, "hi")
    assert hi["language"] == "hi" and validate_lesson(hi) == []
    assert len(fake_model) == 1  # every string of the lesson in one batched call
    for a, b in zip(en["scenes"], hi["scenes"]):
        assert len(split_sentences(b["narration"], "hi")) == len(split_sentences(a["narration"], "en"))
        assert a.get("code") == b.get("code") and a.get("highlight_lines") == b.get("highlight_lines")
        for x, y in zip(a.get("items", []), b.get("items", [])):
            if indictrans.is_code_item(x):
                assert x == y  # code items are never translated
    assert "range(3)" in hi["scenes"][1]["narration"]


def test_lost_placeholder_retries_then_keeps_english(monkeypatch, fake_model):
    monkeypatch.setattr(indictrans, "_generate", lambda texts, tgt: ["शब्द।" for _ in texts])  # drops every tag
    text = "The range(3) call gives three numbers."
    stats = {}
    assert indictrans.translate_texts([text, "Hello there."], "hi", stats) == [text, "शब्द।"]
    assert stats == {"english": 1, "translated": 1}


def test_missing_model_keeps_english_for_a_generated_plan(monkeypatch, tmp_path):
    monkeypatch.setattr(indictrans, "model_dir", lambda: tmp_path / "none")
    monkeypatch.setattr(indictrans, "translate_cache_path", lambda m, l, t: tmp_path / "empty-cache.json")
    plan = sample("binary_search")
    plan["meta"] = {"fallback": False, "source": "ollama:llama3.2:3b", "topic": "binary search"}
    out = indictrans.translate_lesson(plan, "hi")
    assert out["language"] == "en" and out["meta"]["translation_fallback"] is True
    assert out["scenes"] == plan["scenes"]


def test_missing_model_uses_the_pretranslated_sample_for_a_fallback_lesson(monkeypatch, tmp_path):
    monkeypatch.setattr(indictrans, "model_dir", lambda: tmp_path / "none")
    monkeypatch.setattr(indictrans, "translate_cache_path", lambda m, l, t: tmp_path / "empty-cache.json")
    plan = sample("photosynthesis")
    plan["meta"] = {"fallback": True, "source": "sample:photosynthesis", "topic": "Photosynthesis", "reason": "down"}
    out = indictrans.translate_lesson(plan, "ta")
    assert out["language"] == "ta" and out["meta"]["source"] == "sample:photosynthesis"


# --- the real model (skipped when models/indictrans2 is not downloaded) ---

needs_model = pytest.mark.skipif(not indictrans.is_available(), reason="IndicTrans2 not downloaded")


@needs_model
@pytest.mark.parametrize("lang, script", [("hi", DEVANAGARI), ("ta", TAMIL)])
def test_real_translation_keeps_terms_and_uses_the_script(lang, script):
    en = sample("python_loop")
    out = indictrans.translate_lesson(en, lang)
    assert out["language"] == lang and not out.get("meta", {}).get("translation_fallback")
    assert validate_lesson(out) == []
    for a, b in zip(en["scenes"], out["scenes"]):
        assert script.search(b["narration"])
        assert len(split_sentences(b["narration"], lang)) == len(split_sentences(a["narration"], "en"))
    assert "range(3)" in out["scenes"][1]["narration"]


def test_visible_length_counts_letters_not_code_points():
    assert indictrans.visible_len("Plants make oxygen") == 18
    assert indictrans.visible_len("தாவரங்கள்") < len("தாவரங்கள்")  # vowel signs join their consonant


def test_diagram_labels_lose_the_full_stop(monkeypatch, fake_model):
    lesson = sample("photosynthesis")
    monkeypatch.setattr(indictrans, "_generate", lambda texts, tgt: [t + "।" if "<ID" not in t else "शब्द " + t + "।" for t in texts])
    out = indictrans.translate_lesson(lesson, "hi")
    items = [i for s in out["scenes"] for i in s.get("items", [])]
    assert items and not any(i.endswith(("।", ".")) for i in items)


def test_fallback_lesson_uses_its_pretranslated_sample_without_the_model(monkeypatch):
    monkeypatch.setattr(indictrans, "_translate_lesson", lambda *a: pytest.fail("the model should not run"))
    from app.planner.fallback import fallback_lesson

    lesson = fallback_lesson("explain a car gearbox", "beginner", "en", reason="The planner's lesson failed validation twice.")
    out = indictrans.translate_lesson(lesson, "ta")
    assert out["language"] == "ta" and out["meta"]["fallback"] is True
    assert out["meta"]["reason"] == "The planner's lesson failed validation twice."
