"""Validation and sanitising of lesson and timeline JSON (G1, H4).

Planner output is untrusted text: it is parsed as JSON, cleaned, screened for markup, validated
against shared/schema and checked semantically. Nothing the model wrote is ever executed or rendered as HTML.
"""
from __future__ import annotations

import copy
import json
import re
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator

from ..config import SCHEMA_DIR

WORD_BUDGET_TOLERANCE = 0.25
LAST_TRY_WORD_TOLERANCE = 0.5  # the last planner attempt: the timeline fits any length, so only reject a big miss
WORDS_PER_SECOND = 2.3
MIN_LESSON_WORDS = round(30 * WORDS_PER_SECOND)  # 30 s, the shortest lesson the app makes: a short last try is kept above this
EN_ITEM_MAX, EN_LABEL_MAX = 24, 16  # English diagram text; the schema allows 48 / 32 for Indic scripts
SCENE_TYPES = ("title_card", "diagram", "code_walkthrough")  # order of the oneOf branches in the schema


@lru_cache(maxsize=None)
def _schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(_schema(name))


def _short(text: str, n: int = 200) -> str:
    return text if len(text) <= n else text[: n - 3] + "..."


_SIZE_RULES = {"maxLength": "is too long (at most {v} characters)", "minLength": "is too short (at least {v} characters)",
               "maxItems": "has too many items (at most {v})", "minItems": "has too few items (at least {v})",
               "pattern": "has the wrong shape (see the size limits)"}


def _describe(err: Any) -> str:
    """Short message that never echoes the whole offending value back to the model."""
    rule = _SIZE_RULES.get(err.validator)
    return rule.format(v=err.validator_value) if rule else _short(err.message)


def _format_error(err: Any) -> str:
    path = "/".join(str(p) for p in err.absolute_path) or "(root)"
    return f"{path}: {_describe(err)}"


def _schema_errors(name: str, data: Any) -> list[str]:
    """Schema errors, with oneOf failures narrowed to the branch matching the scene's own type."""
    out: list[str] = []
    for err in _validator(name).iter_errors(data):
        if err.validator == "oneOf" and isinstance(err.instance, dict):
            kind = err.instance.get("type")
            if kind in SCENE_TYPES:
                branch = SCENE_TYPES.index(kind)
                base = "/".join(str(p) for p in err.absolute_path)
                for sub in err.context:
                    if sub.schema_path and sub.schema_path[0] == branch:
                        rel = "/".join(str(p) for p in sub.absolute_path)
                        out.append(f"{rel or base}: {_describe(sub)}")
                continue
            out.append(f"{'/'.join(str(p) for p in err.absolute_path)}: type must be one of {', '.join(SCENE_TYPES)}")
            continue
        out.append(_format_error(err))
    return sorted(set(out))


def narration_words(lesson: dict[str, Any]) -> int:
    scenes = lesson.get("scenes", [])
    return sum(len(str(s.get("narration", "")).split()) for s in scenes if isinstance(s, dict)) if isinstance(scenes, list) else 0


def _semantic_errors(
    lesson: dict[str, Any], target_words: int | None = None, tolerance: float = WORD_BUDGET_TOLERANCE, accept_short: bool = False
) -> list[str]:
    """Checks JSON Schema cannot express. accept_short: too little narration is only an error below MIN_LESSON_WORDS."""
    errors: list[str] = []
    scenes = [s for s in lesson.get("scenes", []) if isinstance(s, dict)] if isinstance(lesson.get("scenes"), list) else []
    if scenes and scenes[0].get("type") != "title_card":
        errors.append("scenes/0: the first scene must be a title_card")
    for i, scene in enumerate(scenes):
        if scene.get("type") == "diagram":
            n = len(scene["items"]) if isinstance(scene.get("items"), list) else 0
            if lesson.get("language") == "en":  # the schema leaves room for Indic scripts; English stays short
                for j, item in enumerate(scene["items"] if n else []):
                    if isinstance(item, str) and len(item) > EN_ITEM_MAX:
                        errors.append(f"scenes/{i}/items/{j}: is too long (at most {EN_ITEM_MAX} characters; "
                                      "use a 1-4 word label, not a sentence)")
            seen: set[str] = set()
            for j, item in enumerate(scene["items"] if n else []):
                key = " ".join(str(item).lower().split())
                if key in seen:
                    errors.append(f"scenes/{i}/items/{j}: repeats an earlier item; every item must be different")
                seen.add(key)
            for j, arrow in enumerate(scene["arrows"] if isinstance(scene.get("arrows"), list) else []):
                if not isinstance(arrow, dict):
                    continue
                for end in ("from", "to"):
                    if isinstance(arrow.get(end), int) and arrow[end] >= n:
                        errors.append(f"scenes/{i}/arrows/{j}/{end}: index out of range for {n} items")
                label = arrow.get("label")
                if lesson.get("language") == "en" and isinstance(label, str) and len(label) > EN_LABEL_MAX:
                    errors.append(f"scenes/{i}/arrows/{j}/label: is too long (at most {EN_LABEL_MAX} characters)")
        elif scene.get("type") == "code_walkthrough":
            code = scene["code"] if isinstance(scene.get("code"), str) else ""
            lines = code.split("\n")
            if len(lines) > 12:
                errors.append(f"scenes/{i}/code: {len(lines)} lines, at most 12 allowed")
            for k, line in enumerate(lines, 1):
                if len(line) > 50:
                    errors.append(f"scenes/{i}/code: line {k} has {len(line)} characters, at most 50 allowed")
            for line_no in scene["highlight_lines"] if isinstance(scene.get("highlight_lines"), list) else []:
                if isinstance(line_no, int) and line_no > len(lines):
                    errors.append(f"scenes/{i}/highlight_lines: line {line_no} but code has {len(lines)} lines")
    if target_words:
        words = narration_words(lesson)
        lo, hi = round(target_words * (1 - tolerance)), round(target_words * (1 + tolerance))
        if accept_short:
            lo = min(lo, MIN_LESSON_WORDS)
        if not lo <= words <= hi:
            errors.append(f"narration has {words} words in total; it must be between {lo} and {hi} (about {target_words})")
    return errors


# --- safety screen (H4) ---------------------------------------------------------------------

_BAD = re.compile(r"<\s*script|javascript\s*:|onerror\s*=", re.I)
_ANY_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?:\s[^<>]*)?/?>|<!|<\?")
# Inside code, only real HTML tag names count, so generics such as vector<int> stay legal.
_HTML_TAG_NAMES = (
    "html|head|body|div|span|a|p|br|img|svg|script|style|link|meta|iframe|object|embed|form|input|button|"
    "table|tr|td|ul|ol|li|h[1-6]|b|i|u|em|strong|video|audio|canvas|textarea|select|option|noscript"
)
_HTML_TAG = re.compile(rf"</?(?:{_HTML_TAG_NAMES})(?:\s[^<>]*)?/?>", re.I)


def unsafe_strings(lesson: Any) -> list[str]:
    """Errors for any string containing script, javascript:, onerror= or HTML tags."""
    errors: list[str] = []

    def check(path: str, text: str, is_code: bool) -> None:
        tag = _HTML_TAG if is_code else _ANY_TAG
        if _BAD.search(text) or tag.search(text):
            errors.append(f"{path}: contains HTML or script markup, which is not allowed")

    def walk(node: Any, path: str) -> None:
        if isinstance(node, str):
            check(path, node, path.endswith("/code"))
        elif isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}/{k}" if path else str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}/{i}")

    walk(lesson, "")
    return errors


# The planner always plans in English (step 8 translates). Latin text, punctuation, arrows, maths and Greek
# are fine; other scripts (CJK, Cyrillic, Devanagari, Tamil, Arabic, emoji ...) are not.
_FOREIGN = re.compile("[Ѐ-ԯ֐-῿⺀-￿𐀀-􏿿]")


def foreign_script_strings(lesson: Any) -> list[str]:
    """Errors for strings that contain non-English scripts."""
    errors: list[str] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, str):
            if _FOREIGN.search(node):
                errors.append(f"{path}: contains non-English characters; write everything in English")
        elif isinstance(node, dict):
            for k, v in node.items():
                walk(v, f"{path}/{k}" if path else str(k))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}/{i}")

    walk(lesson, "")
    return errors


# --- sanitising -----------------------------------------------------------------------------

def cut_at_word(text: str, limit: int) -> str:
    """Shorten text to at most `limit` characters, cutting at a word boundary."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if text[limit] != " ":
        space = cut.rfind(" ")
        if space >= limit // 2:
            cut = cut[:space]
    return cut.rstrip(" ,;:-.!?")


def _clean(text: str) -> str:
    return " ".join(text.split())


def _drop_repeated_items(scene: dict[str, Any]) -> None:
    """Remove items that repeat an earlier one (as cutting can make them) and the arrows that touched them."""
    items = scene.get("items")
    if not isinstance(items, list):
        return
    keep, index, seen = [], {}, set()
    for j, item in enumerate(items):
        key = " ".join(str(item).lower().split())
        if key not in seen:
            seen.add(key)
            index[j] = len(keep)
            keep.append(item)
    if len(keep) == len(items) or len(keep) < 2:  # nothing repeated, or too few left: let validation report it
        return
    scene["items"] = keep
    if isinstance(scene.get("arrows"), list):
        arrows = []
        for arrow in scene["arrows"]:
            if isinstance(arrow, dict) and arrow.get("from") in index and arrow.get("to") in index:
                arrows.append({**arrow, "from": index[arrow["from"]], "to": index[arrow["to"]]})
        scene["arrows"] = arrows


def sanitize(lesson: Any, cut_labels: bool = True) -> Any:
    """Return a cleaned copy: trimmed, spaces collapsed, over-long headings cut at a word boundary,
    code trimmed per line (indentation kept). The model's own `meta` is dropped (the backend sets it).

    cut_labels=False leaves over-long diagram items and arrow labels as written, so validation rejects them and the
    retry asks the model for short labels (cutting sentences gave fragments such as "Caffeine blocks" twice).
    With cut_labels=True (the last attempt) they are cut, and items the cut made identical are dropped."""
    if not isinstance(lesson, dict):
        return lesson
    out = copy.deepcopy(lesson)
    out.pop("meta", None)
    if isinstance(out.get("title"), str):
        out["title"] = cut_at_word(_clean(out["title"]), 80)
    for scene in out.get("scenes", []) if isinstance(out.get("scenes"), list) else []:
        if not isinstance(scene, dict):
            continue
        limits = {"heading": 60, "subheading": 80}
        for key, text in list(scene.items()):
            if key == "code" and isinstance(text, str):
                lines = [ln.rstrip().replace("\t", "    ") for ln in text.strip("\n").split("\n")]
                scene[key] = "\n".join(lines).rstrip()
            elif isinstance(text, str):
                scene[key] = cut_at_word(_clean(text), limits[key]) if key in limits else _clean(text)
        item_max, label_max = (EN_ITEM_MAX, EN_LABEL_MAX) if cut_labels else (10_000, 10_000)
        if isinstance(scene.get("items"), list):
            scene["items"] = [cut_at_word(_clean(x), item_max) if isinstance(x, str) else x for x in scene["items"]]
            if cut_labels:
                _drop_repeated_items(scene)
        for arrow in scene.get("arrows", []) if isinstance(scene.get("arrows"), list) else []:
            if isinstance(arrow, dict) and isinstance(arrow.get("label"), str):
                arrow["label"] = cut_at_word(_clean(arrow["label"]), label_max)
    return out


# --- public API -----------------------------------------------------------------------------

_FENCE = re.compile(r"^```[A-Za-z]*[ \t]*\n?(.*?)\n?```\s*$", re.S)


def extract_json_text(raw: str) -> str:
    """Strip Markdown code fences (and any prose around the outermost braces)."""
    text = raw.strip()
    m = _FENCE.match(text)
    if m:
        text = m.group(1).strip()
    if not text.startswith("{"):
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            text = text[start : end + 1]
    return text


def validate_lesson(
    data: Any, target_words: int | None = None, tolerance: float = WORD_BUDGET_TOLERANCE, accept_short: bool = False
) -> list[str]:
    """Return a list of human-readable errors (empty means valid)."""
    errors = _schema_errors("lesson.schema.json", data)
    if not isinstance(data, dict):
        return errors
    if isinstance(data.get("scenes"), list):
        n = len(data["scenes"])
        if not 3 <= n <= 6:  # friendlier than the schema's message
            errors = [e for e in errors if not e.startswith("scenes:")]
            errors.append(f"scenes: found {n} scenes; a lesson needs 3 to 6")
    semantic = _semantic_errors(data, target_words, tolerance, accept_short)
    if any("/code:" in e for e in semantic):  # the semantic message is clearer than the code pattern's
        errors = [e for e in errors if not (e.split(":")[0].endswith("/code") and "wrong shape" in e)]
    return sorted(set(errors + semantic))


def parse_and_validate(
    raw: str, target_seconds: int | None = None, tolerance: float = WORD_BUDGET_TOLERANCE, cut_labels: bool = True,
    accept_short: bool = False,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Parse model output, sanitise, screen, validate. Returns (lesson | None, errors).

    target_seconds enables the word-budget check (about 2.3 words per second, +/- tolerance).
    cut_labels=False (a planner attempt that can still be retried) rejects over-long diagram labels instead of cutting them.
    accept_short=True (the last attempt) keeps a plan with too little narration, down to MIN_LESSON_WORDS: audio sets the
    timing (G4), so it is a shorter lesson on the asked topic instead of an unrelated sample.
    """
    try:
        data = json.loads(extract_json_text(raw))
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return None, ["the top level must be a JSON object"]
    data.pop("quiz", None)  # judged on its own by parse_quiz: a bad quiz never rejects the lesson
    data.pop("next_topics", None)  # likewise parse_next_topics (bonus B2)
    lesson = sanitize(data, cut_labels)
    errors = unsafe_strings(lesson) or foreign_script_strings(lesson)
    if errors:
        return None, errors
    target_words = round(target_seconds * WORDS_PER_SECOND) if target_seconds else None
    errors = validate_lesson(lesson, target_words, tolerance, accept_short)
    return (None, errors) if errors else (lesson, [])


# --- quiz (bonus B1): validated apart from the lesson; bad questions are dropped, never retried --------------

QUIZ_LIMITS_EN = {"question": 160, "option": 80, "explanation": 200}
QUIZ_LIMITS_INDIC = {"question": 320, "option": 160, "explanation": 400}  # translated text; the schema maxima
MIN_QUIZ_QUESTIONS = 2
_ALL_OF_THE_ABOVE = re.compile(r"\b(all|none|both) of the above\b", re.I)


def question_problems(q: Any, limits: dict[str, int], english: bool) -> list[str]:
    """Why one quiz question is unusable (empty list = keep it)."""
    if not isinstance(q, dict):
        return ["is not an object"]
    problems = []
    question, options, answer, explanation = q.get("question"), q.get("options"), q.get("answer_index"), q.get("explanation")
    if not isinstance(question, str) or not 1 <= len(question) <= limits["question"]:
        problems.append(f"question must be 1-{limits['question']} characters")
    if not isinstance(options, list) or len(options) != 4 or not all(isinstance(o, str) for o in options):
        problems.append("needs exactly 4 text options")
    else:
        if any(not 1 <= len(o) <= limits["option"] for o in options):
            problems.append(f"each option must be 1-{limits['option']} characters")
        if len({" ".join(o.casefold().split()) for o in options}) != 4:
            problems.append("options repeat")
        if any(_ALL_OF_THE_ABOVE.search(o) for o in options):
            problems.append('uses "all/none of the above"')
    if not isinstance(answer, int) or isinstance(answer, bool) or not 0 <= answer <= 3:
        problems.append("answer_index must be 0-3")
    if not isinstance(explanation, str) or not 1 <= len(explanation) <= limits["explanation"]:
        problems.append(f"explanation must be 1-{limits['explanation']} characters")
    problems += [e.split(": ", 1)[-1] for e in unsafe_strings(q)]
    if english:
        problems += [e.split(": ", 1)[-1] for e in foreign_script_strings(q)]
    return problems


def _clean_question(q: Any) -> Any:
    """Known keys only, text trimmed with spaces collapsed (anything malformed is left for the checks to reject)."""
    if not isinstance(q, dict):
        return q
    out = {k: q[k] for k in ("question", "options", "answer_index", "explanation") if k in q}
    for key in ("question", "explanation"):
        if isinstance(out.get(key), str):
            out[key] = _clean(out[key])
    if isinstance(out.get("options"), list):
        out["options"] = [_clean(o) if isinstance(o, str) else o for o in out["options"]]
    return out


def clean_quiz(raw: Any, max_questions: int = 3, language: str = "en") -> tuple[list[dict[str, Any]] | None, list[str]]:
    """(quiz or None, warnings). Each invalid question is dropped; fewer than 2 good ones drops the whole quiz.

    Text is trimmed and spaces collapsed first. English is held to 160 / 80 / 200 characters (question / option /
    explanation), translated text to the schema's roomier limits. Same markup screen as every other string (H4).
    """
    if raw is None:
        return None, ["no quiz in the plan"]
    if not isinstance(raw, list):
        return None, [f"quiz is a {type(raw).__name__}, not a list; dropped"]
    limits = QUIZ_LIMITS_EN if language == "en" else QUIZ_LIMITS_INDIC
    kept: list[dict[str, Any]] = []
    warnings: list[str] = []
    for i, q in enumerate(raw):
        q = _clean_question(q)
        problems = question_problems(q, limits, english=language == "en")
        if problems:
            warnings.append(f"quiz/{i} dropped: " + "; ".join(problems))
        elif len(kept) < max_questions:
            kept.append(q)
    if len(kept) < MIN_QUIZ_QUESTIONS:
        warnings.append(f"quiz dropped: {len(kept)} usable question(s), at least {MIN_QUIZ_QUESTIONS} needed")
        return None, warnings
    return kept, warnings


def shuffle_quiz(quiz: list[dict[str, Any]], seed: str) -> list[dict[str, Any]]:
    """Shuffle each question's options (seeded by the lesson id, so a lesson always shows the same order) and move
    answer_index with its option: a 3B model tends to put the right answer first."""
    import random

    out = []
    for i, q in enumerate(quiz):
        order = list(range(4))
        random.Random(f"{seed}:quiz:{i}").shuffle(order)
        out.append({**q, "options": [q["options"][k] for k in order], "answer_index": order.index(q["answer_index"])})
    return out


def parse_quiz(raw: str, max_questions: int = 3) -> tuple[list[dict[str, Any]] | None, list[str]]:
    """The quiz part of a planner reply (the lesson part is judged by parse_and_validate)."""
    try:
        data = json.loads(extract_json_text(raw))
    except json.JSONDecodeError:
        return None, ["quiz dropped: the reply is not JSON"]
    return clean_quiz(data.get("quiz") if isinstance(data, dict) else None, max_questions)


# --- next topics (bonus B2): two follow-up topics, dropped (never retried) when invalid ------------------------

NEXT_TOPIC_MIN, NEXT_TOPIC_MAX = 3, 60


def clean_next_topics(raw: Any) -> tuple[list[str] | None, list[str]]:
    """(two English topics or None, warnings): exactly 2 distinct strings of 3-60 characters, no markup, English only."""
    if raw is None:
        return None, ["no next_topics in the plan"]
    if not isinstance(raw, list) or len(raw) != 2 or not all(isinstance(t, str) for t in raw):
        return None, ["next_topics dropped: needs exactly 2 strings"]
    topics = [_clean(t) for t in raw]
    problems = []
    if any(not NEXT_TOPIC_MIN <= len(t) <= NEXT_TOPIC_MAX for t in topics):
        problems.append(f"each must be {NEXT_TOPIC_MIN}-{NEXT_TOPIC_MAX} characters")
    if topics[0].casefold() == topics[1].casefold():
        problems.append("the two are the same")
    problems += [e.split(": ", 1)[-1] for e in unsafe_strings(topics) + foreign_script_strings(topics)]
    if problems:
        return None, ["next_topics dropped: " + "; ".join(problems)]
    return topics, []


def parse_next_topics(raw: str) -> tuple[list[str] | None, list[str]]:
    """The next_topics part of a planner reply."""
    try:
        data = json.loads(extract_json_text(raw))
    except json.JSONDecodeError:
        return None, ["next_topics dropped: the reply is not JSON"]
    return clean_next_topics(data.get("next_topics") if isinstance(data, dict) else None)


def validate_timeline(data: Any) -> list[str]:
    """Validate a timeline, including each scene's embedded 'data' object and the optional quiz."""
    errors = _schema_errors("timeline.schema.json", data)
    if errors or not isinstance(data, dict):
        return errors
    if "quiz" in data:
        quiz_validator = Draft202012Validator({"$ref": "#/$defs/quiz", "$defs": _schema("lesson.schema.json")["$defs"]})
        errors += [f"quiz: {_format_error(e)}" for e in quiz_validator.iter_errors(data["quiz"])]
    scene_validator = Draft202012Validator(
        {"$ref": "#/$defs/scene", "$defs": _schema("lesson.schema.json")["$defs"]}
    )
    for i, scene in enumerate(data["scenes"]):
        for e in scene_validator.iter_errors(scene["data"]):
            errors.append(f"scenes/{i}/data: {_format_error(e)}")
        if scene["end"] < scene["start"]:
            errors.append(f"scenes/{i}: end before start")
    return errors
