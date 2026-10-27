import copy
import json

import pytest

from app.config import SAMPLES_DIR
from app.planner.validate import parse_and_validate, validate_lesson, validate_timeline
from app.timing.sentences import split_sentences

SAMPLES = sorted(SAMPLES_DIR.glob("python_loop.*.json"))


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_three_samples_present():
    assert [p.name for p in SAMPLES] == ["python_loop.en.json", "python_loop.hi.json", "python_loop.ta.json"]


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.name)
def test_sample_validates(path):
    assert validate_lesson(load(path)) == []


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.name)
def test_sample_language_matches_filename(path):
    assert load(path)["language"] == path.name.split(".")[1]


def test_translations_keep_structure_and_code():
    en = load(SAMPLES_DIR / "python_loop.en.json")
    for lang in ("hi", "ta"):
        tr = load(SAMPLES_DIR / f"python_loop.{lang}.json")
        assert [s["type"] for s in tr["scenes"]] == [s["type"] for s in en["scenes"]]
        for a, b in zip(en["scenes"], tr["scenes"]):
            for key in ("code", "items", "arrows", "highlight_lines", "layout"):
                assert a.get(key) == b.get(key)


@pytest.mark.parametrize("path", SAMPLES, ids=lambda p: p.name)
def test_sample_has_two_to_three_sentences_per_scene(path):
    for scene in load(path)["scenes"]:
        assert 2 <= len(split_sentences(scene["narration"])) <= 3


def test_no_duration_fields_anywhere():
    schema = json.loads((SAMPLES_DIR.parent / "schema" / "lesson.schema.json").read_text(encoding="utf-8"))

    def property_names(node):
        if isinstance(node, dict):
            yield from node.get("properties", {})
            for v in node.values():
                yield from property_names(v)
        elif isinstance(node, list):
            for v in node:
                yield from property_names(v)

    assert not [n for n in property_names(schema) if "dur" in n or n in ("start", "end", "seconds")]


def _mutated(fn):
    lesson = copy.deepcopy(load(SAMPLES_DIR / "python_loop.en.json"))
    fn(lesson)
    return validate_lesson(lesson)


def test_rejects_extra_property():
    assert _mutated(lambda l: l["scenes"][0].update(duration=5))


def test_rejects_too_few_scenes():
    assert _mutated(lambda l: l.update(scenes=l["scenes"][:2]))


def test_rejects_long_code_line():
    assert _mutated(lambda l: l["scenes"][1].update(code="x" * 51))


def test_rejects_too_many_code_lines():
    assert _mutated(lambda l: l["scenes"][1].update(code="\n".join(["x"] * 13)))


def test_rejects_bad_arrow_index():
    assert _mutated(lambda l: l["scenes"][2]["arrows"].append({"from": 0, "to": 5}))


def test_rejects_highlight_beyond_code():
    assert _mutated(lambda l: l["scenes"][1].update(highlight_lines=[3]))


def test_rejects_unknown_scene_type():
    assert _mutated(lambda l: l["scenes"][0].update(type="video"))


def test_parse_rejects_non_json():
    data, errors = parse_and_validate("import os; os.system('x')")
    assert data is None and errors


def test_timeline_schema():
    lesson = load(SAMPLES_DIR / "python_loop.en.json")
    timeline = {
        "lesson_id": "abc",
        "language": "en",
        "total_seconds": 10.0,
        "audio_url": "/media/lessons/abc/narration.wav",
        "scenes": [
            {
                "index": i,
                "type": s["type"],
                "start": i * 2.5,
                "end": (i + 1) * 2.5,
                "heading": s["heading"],
                "data": s,
                "cues": [{"start": i * 2.5, "end": (i + 1) * 2.5, "text": "hello"}],
                "beats": [{"t": i * 2.5, "action": "reveal", "value": 0}],
            }
            for i, s in enumerate(lesson["scenes"])
        ],
    }
    assert validate_timeline(timeline) == []
    timeline["scenes"][0]["data"]["extra"] = 1
    assert validate_timeline(timeline)


def test_frontend_fake_timeline_matches_schema():
    from app.config import REPO_ROOT

    fake = json.loads((REPO_ROOT / "frontend" / "src" / "dev" / "fakeTimeline.json").read_text(encoding="utf-8"))
    assert validate_timeline(fake) == []
