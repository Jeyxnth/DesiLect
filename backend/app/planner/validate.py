"""Validation of lesson and timeline JSON against shared/schema (G1, H4)."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from jsonschema import Draft202012Validator

from ..config import SCHEMA_DIR


@lru_cache(maxsize=None)
def _schema(name: str) -> dict[str, Any]:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def _validator(name: str) -> Draft202012Validator:
    return Draft202012Validator(_schema(name))


def _format_error(err: Any) -> str:
    path = "/".join(str(p) for p in err.absolute_path) or "(root)"
    return f"{path}: {err.message}"


def _schema_errors(name: str, data: Any) -> list[str]:
    return sorted(_format_error(e) for e in _validator(name).iter_errors(data))


def _semantic_errors(lesson: dict[str, Any]) -> list[str]:
    """Checks JSON Schema cannot express: arrow/highlight indices must exist."""
    errors: list[str] = []
    for i, scene in enumerate(lesson.get("scenes", [])):
        if scene.get("type") == "diagram":
            n = len(scene.get("items", []))
            for j, arrow in enumerate(scene.get("arrows", [])):
                for end in ("from", "to"):
                    if arrow.get(end, 0) >= n:
                        errors.append(f"scenes/{i}/arrows/{j}/{end}: index out of range for {n} items")
        elif scene.get("type") == "code_walkthrough":
            n_lines = len(str(scene.get("code", "")).split("\n"))
            for line in scene.get("highlight_lines", []):
                if line > n_lines:
                    errors.append(f"scenes/{i}/highlight_lines: line {line} but code has {n_lines} lines")
    return errors


def validate_lesson(data: Any) -> list[str]:
    """Return a list of human-readable errors (empty means valid)."""
    errors = _schema_errors("lesson.schema.json", data)
    if not errors and isinstance(data, dict):
        errors = _semantic_errors(data)
    return errors


def parse_and_validate(raw: str) -> tuple[dict[str, Any] | None, list[str]]:
    """Parse model output as JSON (never executed, H4) and validate it."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {exc}"]
    errors = validate_lesson(data)
    return (None, errors) if errors else (data, [])


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
