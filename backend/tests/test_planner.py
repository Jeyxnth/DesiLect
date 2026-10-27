import copy
import json
from types import SimpleNamespace

import httpx
import pytest

from app.config import SAMPLES_DIR
from app.pipeline import orchestrator as orch
from app.planner.fallback import closest_sample, fallback_lesson
from app.planner.ollama_client import (
    OllamaClient, OllamaModelMissing, OllamaNotRunning, OllamaTimeout, lesson_format_schema)
from app.planner.validate import cut_at_word, parse_and_validate, validate_lesson

SAMPLE = json.loads((SAMPLES_DIR / "python_loop.en.json").read_text(encoding="utf-8"))  # 118 words
TARGET = 45  # budget 103 words, allowed 77..129


def good() -> dict:
    return copy.deepcopy(SAMPLE)


def mock_client(*replies, record=None):
    """OllamaClient on a mock transport. Each reply is a dict/str (message content), an Exception, or an int status."""
    queue = list(replies)

    def handler(request: httpx.Request) -> httpx.Response:
        if record is not None:
            record.append(json.loads(request.content))
        item = queue.pop(0) if len(queue) > 1 else queue[0]
        if isinstance(item, Exception):
            raise item
        if isinstance(item, int):
            return httpx.Response(item, text="model not found")
        text = item if isinstance(item, str) else json.dumps(item)
        return httpx.Response(200, json={"message": {"role": "assistant", "content": text}})

    return OllamaClient("http://127.0.0.1:11434", "llama3.2:3b", httpx.Client(transport=httpx.MockTransport(handler)))


@pytest.fixture
def store(tmp_path, monkeypatch):
    settings = SimpleNamespace(outputs_dir=tmp_path / "outputs")
    monkeypatch.setattr("app.cache.store.get_settings", lambda: settings)
    return tmp_path / "outputs" / "lessons"


def plan(client, store, lesson_id="t1", topic="How a Python loop works"):
    return orch.plan_lesson(topic, "beginner", TARGET, lesson_id, client)


# --- plan_lesson with a mocked Ollama ----------------------------------------------------------

def test_valid_response_first_try(store):
    lesson, meta = plan(mock_client(good()), store)
    assert meta["fallback"] is False and meta["attempts"] == 1 and meta["reason"] is None
    assert lesson["meta"] == {"fallback": False, "source": "ollama:llama3.2:3b", "topic": "How a Python loop works"}
    assert validate_lesson(lesson) == []
    raw = (store / "t1" / "planner_raw.txt").read_text(encoding="utf-8")
    assert "=== attempt 1" in raw and "accepted" in raw
    assert "plan_attempt_1" in json.loads((store / "t1" / "timings.json").read_text(encoding="utf-8"))


def test_request_body_follows_the_contract(store):
    sent: list = []
    plan(mock_client(good(), record=sent), store)
    body = sent[0]
    assert body["model"] == "llama3.2:3b" and body["stream"] is False and body["keep_alive"] == 0
    assert body["options"] == {"temperature": 0.2, "num_ctx": 4096}
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert "meta" not in body["format"]["properties"] and "meta" not in body["format"]["$defs"]
    assert body["format"]["properties"]["scenes"]["minItems"] == 3
    assert "103 words" in body["messages"][1]["content"] and "Python loop" in body["messages"][0]["content"]


def test_invalid_json_twice_falls_back(store):
    lesson, meta = plan(mock_client("this is not json"), store)
    assert meta["fallback"] is True and meta["attempts"] == 2 and "invalid JSON" in meta["reason"]
    assert lesson["meta"]["fallback"] is True and validate_lesson(lesson) == []
    assert (store / "t1" / "planner_raw.txt").read_text(encoding="utf-8").count("=== attempt") == 2


def test_schema_violation_is_fixed_on_retry(store):
    bad = good()
    bad["scenes"] = bad["scenes"][:2]  # only 2 scenes
    sent: list = []
    lesson, meta = plan(mock_client(bad, good(), record=sent), store)
    assert meta["fallback"] is False and meta["attempts"] == 2
    assert "rejected for these reasons" in sent[1]["messages"][1]["content"]
    assert "found 2 scenes" in sent[1]["messages"][1]["content"]
    assert lesson["meta"]["fallback"] is False


@pytest.mark.parametrize("failure, name", [
    (httpx.ReadTimeout("slow"), "OllamaTimeout"),
    (httpx.ConnectError("refused"), "OllamaNotRunning"),
    (404, "OllamaModelMissing"),
])
def test_ollama_problems_fall_back_without_retry(store, failure, name):
    lesson, meta = plan(mock_client(failure), store)
    assert meta["fallback"] is True and meta["attempts"] == 1 and name in meta["reason"]
    assert lesson["meta"]["fallback"] is True


def test_client_error_types():
    with pytest.raises(OllamaTimeout):
        mock_client(httpx.ConnectTimeout("t")).chat_json("s", "u")
    with pytest.raises(OllamaNotRunning):
        mock_client(httpx.ConnectError("x")).chat_json("s", "u")
    with pytest.raises(OllamaModelMissing, match="download_models"):
        mock_client(404).chat_json("s", "u")


@pytest.mark.parametrize("field, payload", [
    ("narration", "Great. <script>alert(1)</script> Now loops."),
    ("heading", '<img src=x onerror=alert(1)>'),
    ("narration", "Click javascript:alert(1) to continue."),
    ("subheading", "<b>bold</b> idea"),
])
def test_html_injection_is_rejected_and_replaced_by_fallback(store, field, payload):
    evil = good()
    evil["scenes"][0][field] = payload
    lesson, meta = plan(mock_client(evil), store)
    assert meta["fallback"] is True and meta["attempts"] == 2
    assert "markup" in meta["reason"]
    assert payload not in json.dumps(lesson)


# --- validator ---------------------------------------------------------------------------------

def test_strips_code_fences_and_prose():
    raw = "Sure! Here it is:\n```json\n" + json.dumps(good()) + "\n```"
    lesson, errors = parse_and_validate(raw, TARGET)
    assert errors == [] and lesson is not None


def test_sanitise_trims_collapses_and_cuts_headings():
    d = good()
    d["scenes"][0]["heading"] = "  A   very long heading " + "word " * 20
    d["scenes"][0]["narration"] = "  Hello    there.  " + d["scenes"][0]["narration"]
    d["scenes"][1]["code"] = "for i in range(3):   \n\tprint(i)  \n\n"
    lesson, errors = parse_and_validate(json.dumps(d), TARGET)
    assert errors == []
    s0 = lesson["scenes"][0]
    assert len(s0["heading"]) <= 60 and s0["heading"].startswith("A very long heading word") and not s0["heading"].endswith(" ")
    assert s0["narration"].startswith("Hello there. Welcome!")
    assert lesson["scenes"][1]["code"] == "for i in range(3):\n    print(i)"


def test_cut_at_word():
    assert cut_at_word("short", 10) == "short"
    assert cut_at_word("alpha beta gamma delta", 12) == "alpha beta"
    assert cut_at_word("abcdefghijklmnop", 8) == "abcdefgh"  # no space to cut at


def test_model_supplied_meta_is_dropped():
    d = good()
    d["meta"] = {"fallback": False, "source": "trust me"}
    lesson, errors = parse_and_validate(json.dumps(d), TARGET)
    assert errors == [] and "meta" not in lesson


@pytest.mark.parametrize("mutate, expect", [
    (lambda d: d["scenes"].__setitem__(0, d["scenes"][3] | {"type": "title_card"}) or d["scenes"].insert(0, d["scenes"].pop(1)), "first scene"),
    (lambda d: d["scenes"][2]["arrows"].append({"from": 0, "to": 5}), "out of range"),
    (lambda d: d["scenes"][1].update(highlight_lines=[1, 4]), "code has 2 lines"),
    (lambda d: d["scenes"][1].update(code="\n".join(["x = 1"] * 13)), "at most 12"),
    (lambda d: d["scenes"][1].update(code="y = '" + "a" * 60 + "'"), "at most 50"),
    (lambda d: [x.update(narration="Too short.") for x in d["scenes"]], "words in total"),
    (lambda d: d["scenes"][0].update(narration="word " * 400), "words in total"),
    (lambda d: d["scenes"][2].update(layout="spiral"), "layout"),
    (lambda d: d.update(scenes=d["scenes"] * 2), "found 8 scenes"),
])
def test_semantic_and_schema_rejections(mutate, expect):
    d = good()
    mutate(d)
    lesson, errors = parse_and_validate(json.dumps(d), TARGET)
    assert lesson is None and any(expect in e for e in errors), errors


def test_word_budget_edges():
    d = good()  # 118 words; for 45 s the window is 77..129
    assert parse_and_validate(json.dumps(d), 45)[0] is not None
    assert parse_and_validate(json.dumps(d), 90)[0] is None  # 207 words wanted
    assert parse_and_validate(json.dumps(d), 30)[0] is None  # 69 wanted, 118 is too many
    assert parse_and_validate(json.dumps(d), None)[0] is not None  # no budget check


def test_generic_types_in_code_are_not_html():
    d = good()
    d["scenes"][1]["code"] = "vector<int> v;\nif (a < b && c > d) {}"
    d["scenes"][1]["highlight_lines"] = [1]
    assert parse_and_validate(json.dumps(d), TARGET)[0] is not None
    d["scenes"][1]["code"] = "x = '<script>alert(1)</script>'"
    assert parse_and_validate(json.dumps(d), TARGET)[0] is None


def test_oneof_errors_name_the_real_problem():
    d = good()
    d["scenes"][2]["items"] = ["only one"]
    lesson, errors = parse_and_validate(json.dumps(d), TARGET)
    assert lesson is None
    assert any("scenes/2/items" in e for e in errors) and not any("not valid under any" in e for e in errors)


def test_format_schema_drops_meta_only():
    s = lesson_format_schema()
    assert "meta" not in s["properties"] and "meta" not in s["$defs"]
    assert set(s["properties"]) == {"title", "level", "language", "scenes", "quiz"}  # quiz: bonus B1


# --- fallback ----------------------------------------------------------------------------------

def test_fallback_title_follows_topic_only_when_it_matches():
    matching = fallback_lesson("How do for loops work in Python?", "intermediate")
    assert matching["title"] == "How do for loops work in Python?" and matching["level"] == "intermediate"
    assert matching["meta"] == {"fallback": True, "source": "sample:python_loop", "topic": "How do for loops work in Python?"}
    other = fallback_lesson("Newton's third law")
    assert other["title"] == "How a Python loop works" and other["meta"]["fallback"] is True
    assert closest_sample("Newton's third law")[1] is False and closest_sample("python loop")[1] is True


def test_fallback_hi_keeps_translated_title():
    hi = fallback_lesson("python loop", language="hi")
    assert hi["language"] == "hi" and hi["title"].startswith("Python loop")


@pytest.mark.parametrize("text", ["The 叶 is green.", "Привет friends.", "यह हिंदी है।", "Emoji 🌱 time."])
def test_non_english_scripts_are_rejected(text):
    d = good()
    d["scenes"][0]["narration"] = text + " " + d["scenes"][0]["narration"]
    lesson, errors = parse_and_validate(json.dumps(d), TARGET)
    assert lesson is None and any("non-English" in e for e in errors)


def test_english_typography_is_allowed():
    d = good()
    d["scenes"][0]["narration"] = "Plants’ leaves — at 25°C → make sugar (π × r²). " + d["scenes"][0]["narration"]
    assert parse_and_validate(json.dumps(d), TARGET)[0] is not None


@pytest.mark.parametrize("topic, sample, matches", [
    ("How does photosynthesis work?", "photosynthesis", True),
    ("What does chlorophyll do", "photosynthesis", True),
    ("Pythagoras theorem for beginners", "pythagorean_theorem", True),
    ("Explain the hypotenuse", "pythagorean_theorem", True),
    ("How do for loops work in Python?", "python_loop", True),
    ("How does binary search work?", "binary_search", True),
    ("Searching a sorted array", "binary_search", False),  # related words only
    ("How do plants get energy from sunlight", "photosynthesis", False),  # related words only: closest, not a match
    ("Triangles and angles in geometry", "pythagorean_theorem", False),
    ("Newton's third law", "python_loop", False),  # nothing overlaps: the default sample
])
def test_closest_sample_selection(topic, sample, matches):
    chosen, is_match = closest_sample(topic)
    assert (chosen.name, is_match) == (sample, matches)


def test_fallback_retitles_only_on_a_real_match():
    assert fallback_lesson("How does photosynthesis work?")["title"] == "How does photosynthesis work?"
    related = fallback_lesson("How do plants get energy from sunlight")
    assert related["title"] == "How photosynthesis works" and related["meta"]["source"] == "sample:photosynthesis"
    assert fallback_lesson("Pythagoras theorem")["meta"]["source"] == "sample:pythagorean_theorem"


@pytest.mark.parametrize("lang", ["en", "hi", "ta"])
@pytest.mark.parametrize("topic", ["photosynthesis", "pythagorean theorem", "python loop", "anything else"])
def test_every_fallback_is_valid_in_every_language(topic, lang):
    lesson = fallback_lesson(topic, "intermediate", lang)
    assert validate_lesson(lesson) == [] and lesson["language"] == lang and lesson["level"] == "intermediate"


def test_english_diagram_text_keeps_the_short_limits():
    lesson = json.loads((SAMPLES_DIR / "photosynthesis.en.json").read_text(encoding="utf-8"))
    diagram = next(s for s in lesson["scenes"] if s["type"] == "diagram")
    diagram["items"][0] = "A very long diagram label here"  # 30 > 24
    assert any("items/0: is too long (at most 24" in e for e in validate_lesson(lesson))
    lesson["language"] = "hi"  # translated text may be longer
    assert not validate_lesson(lesson)


def test_sanitize_shortens_long_english_diagram_text():
    from app.planner.validate import sanitize

    lesson = json.loads((SAMPLES_DIR / "photosynthesis.en.json").read_text(encoding="utf-8"))
    diagram = next(s for s in lesson["scenes"] if s["type"] == "diagram")
    diagram["items"][0] = "Engine turns the clutch plate"
    out = sanitize(lesson)
    item = next(s for s in out["scenes"] if s["type"] == "diagram")["items"][0]
    assert item == "Engine turns the clutch" and not validate_lesson(out)


def test_last_planner_attempt_accepts_a_lesson_that_is_somewhat_short():
    lesson = json.loads((SAMPLES_DIR / "python_loop.en.json").read_text(encoding="utf-8"))
    raw = json.dumps(lesson)
    words = sum(len(s["narration"].split()) for s in lesson["scenes"])
    seconds = round(words / 2.3 * 1.4)  # the lesson is about 30% shorter than asked for
    assert parse_and_validate(raw, seconds)[0] is None
    assert parse_and_validate(raw, seconds, tolerance=0.5)[0] is not None


def caffeine_like_plan() -> dict:
    """The shape llama3.2 gave for "Explain how caffeine works" (step 13): sentences as diagram items."""
    lesson = json.loads((SAMPLES_DIR / "photosynthesis.en.json").read_text(encoding="utf-8"))
    diagram = next(s for s in lesson["scenes"] if s["type"] == "diagram")
    diagram["items"] = ["Adenosine is a chemical that makes us feel tired", "Caffeine blocks adenosine",
                        "Caffeine blocks adenosine again"]
    diagram["arrows"] = [{"from": 0, "to": 1}, {"from": 1, "to": 2}]
    return lesson


def test_long_diagram_items_are_rejected_so_the_retry_asks_for_labels():
    """Step 13 bug: items were cut to 24 characters before validation, giving "Caffeine blocks" twice on screen."""
    lesson, errors = parse_and_validate(json.dumps(caffeine_like_plan()), None, cut_labels=False)
    assert lesson is None
    assert any("items/0: is too long" in e and "not a sentence" in e for e in errors)


def test_last_attempt_cuts_items_and_drops_the_duplicates_it_makes():
    lesson, errors = parse_and_validate(json.dumps(caffeine_like_plan()), None, cut_labels=True)
    assert errors == []
    diagram = next(s for s in lesson["scenes"] if s["type"] == "diagram")
    assert diagram["items"] == ["Adenosine is a chemical", "Caffeine blocks"]  # the repeat is gone
    assert diagram["arrows"] == [{"from": 0, "to": 1}]  # the arrow to the dropped item went with it


def test_repeated_items_are_a_validation_error():
    lesson = json.loads((SAMPLES_DIR / "photosynthesis.en.json").read_text(encoding="utf-8"))
    diagram = next(s for s in lesson["scenes"] if s["type"] == "diagram")
    diagram["items"][1] = diagram["items"][0].upper()
    assert any("repeats an earlier item" in e for e in validate_lesson(lesson))
