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


def _words(lesson: dict[str, Any]) -> int:
    scenes = lesson.get("scenes", [])
    return sum(len(str(s.get("narration", "")).split()) for s in scenes if isinstance(s, dict)) if isinstance(scenes, list) else 0


def _semantic_errors(lesson: dict[str, Any], target_words: int | None = None) -> list[str]:
    """Checks JSON Schema cannot express."""
    errors: list[str] = []
    scenes = [s for s in lesson.get("scenes", []) if isinstance(s, dict)] if isinstance(lesson.get("scenes"), list) else []
    if scenes and scenes[0].get("type") != "title_card":
        errors.append("scenes/0: the first scene must be a title_card")
    for i, scene in enumerate(scenes):
        if scene.get("type") == "diagram":
            n = len(scene["items"]) if isinstance(scene.get("items"), list) else 0
            for j, arrow in enumerate(scene["arrows"] if isinstance(scene.get("arrows"), list) else []):
                if not isinstance(arrow, dict):
                    continue
                for end in ("from", "to"):
                    if isinstance(arrow.get(end), int) and arrow[end] >= n:
                        errors.append(f"scenes/{i}/arrows/{j}/{end}: index out of range for {n} items")
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
        words = _words(lesson)
        lo, hi = round(target_words * (1 - WORD_BUDGET_TOLERANCE)), round(target_words * (1 + WORD_BUDGET_TOLERANCE))
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


def sanitize(lesson: Any) -> Any:
    """Return a cleaned copy: trimmed, spaces collapsed, over-long headings cut at a word boundary,
    code trimmed per line (indentation kept). The model's own `meta` is dropped (the backend sets it)."""
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
        if isinstance(scene.get("items"), list):
            scene["items"] = [_clean(x) if isinstance(x, str) else x for x in scene["items"]]
        for arrow in scene.get("arrows", []) if isinstance(scene.get("arrows"), list) else []:
            if isinstance(arrow, dict) and isinstance(arrow.get("label"), str):
                arrow["label"] = _clean(arrow["label"])
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


def validate_lesson(data: Any, target_words: int | None = None) -> list[str]:
    """Return a list of human-readable errors (empty means valid)."""
    errors = _schema_errors("lesson.schema.json", data)
    if not isinstance(data, dict):
        return errors
    if isinstance(data.get("scenes"), list):
        n = len(data["scenes"])
        if not 3 <= n <= 6:  # friendlier than the schema's message
            errors = [e for e in errors if not e.startswith("scenes:")]
            errors.append(f"scenes: found {n} scenes; a lesson needs 3 to 6")
    semantic = _semantic_errors(data, target_words)
    if any("/code:" in e for e in semantic):  # the semantic message is clearer than the code pattern's
        errors = [e for e in errors if not (e.split(":")[0].endswith("/code") and "wrong shape" in e)]
    return sorted(set(errors + semantic))


def parse_and_validate(raw: str, target_seconds: int | None = None) -> tuple[dict[str, Any] | None, list[str]]:
    """Parse model output, sanitise, screen, validate. Returns (lesson | None, errors).

    target_seconds enables the word-budget check (about 2.3 words per second, +/-25 percent).
    """
    try:
        data = json.loads(extract_json_text(raw))
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return None, ["the top level must be a JSON object"]
    lesson = sanitize(data)
    errors = unsafe_strings(lesson) or foreign_script_strings(lesson)
    if errors:
        return None, errors
    target_words = round(target_seconds * 2.3) if target_seconds else None
    errors = validate_lesson(lesson, target_words)
    return (None, errors) if errors else (lesson, [])


def validate_timeline(data: Any) -> list[str]:
    """Validate a timeline, including each scene's embedded 'data' object."""
    errors = _schema_errors("timeline.schema.json", data)
    if errors or not isinstance(data, dict):
        return errors
    scene_validator = Draft202012Validator(
        {"$ref": "#/$defs/scene", "$defs": _schema("lesson.schema.json")["$defs"]}
    )
    for i, scene in enumerate(data["scenes"]):
        for e in scene_validator.iter_errors(scene["data"]):
            errors.append(f"scenes/{i}/data: {_format_error(e)}")
        if scene["end"] < scene["start"]:
            errors.append(f"scenes/{i}: end before start")
    return errors
