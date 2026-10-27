"""Prompt templates for the local planner LLM. The model must return JSON only (H4)."""
from __future__ import annotations

import json

from ..config import SCHEMA_DIR


def build_system_prompt() -> str:
    """System prompt describing the scene types and the JSON-only rule.

    TODO(step 5): tune wording, add few-shot example from shared/samples.
    """
    schema = (SCHEMA_DIR / "lesson.schema.json").read_text(encoding="utf-8")
    return (
        "You write short visual lessons as JSON. Reply with one JSON object and nothing else. "
        "It must match this JSON Schema exactly:\n" + schema
    )


def build_user_prompt(topic: str, level: str, target_seconds: int) -> str:
    """User prompt for a concept request. TODO(step 5): derive scene count from target_seconds."""
    return f"Topic: {topic}\nLevel: {level}\nTarget length: about {target_seconds} seconds of narration.\nLanguage: English."


def build_retry_prompt(previous: str, errors: list[str]) -> str:
    """Prompt for the single retry, listing validation errors. TODO(step 5)."""
    return (
        "Your previous JSON was invalid.\nErrors:\n- " + "\n- ".join(errors)
        + "\nPrevious output:\n" + json.dumps(previous)[:4000]
        + "\nReturn corrected JSON only."
    )
