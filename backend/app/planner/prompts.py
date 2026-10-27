"""Prompt templates for the local planner LLM. The model must return JSON only (H4)."""
from __future__ import annotations

import json

from ..config import SAMPLES_DIR

WORDS_PER_SECOND = 2.3  # spoken narration pace the word budget is based on


def word_budget(target_seconds: int) -> int:
    """Target total narration words for a lesson of target_seconds."""
    return round(target_seconds * WORDS_PER_SECOND)


def _example() -> str:
    """The Python-loop sample, as compact JSON (one complete few-shot example)."""
    sample = json.loads((SAMPLES_DIR / "python_loop.en.json").read_text(encoding="utf-8"))
    return json.dumps(sample, ensure_ascii=False, indent=1)


def scene_plan(target_seconds: int) -> tuple[int, int]:
    """(number of scenes to aim for, words of narration per scene) for a target length."""
    words = word_budget(target_seconds)
    scenes = max(3, min(6, round(words / 28)))
    return scenes, round(words / scenes)


def build_system_prompt(level: str, target_seconds: int) -> str:
    """System prompt: teacher persona, output rules, scene types, word budget and one example."""
    words = word_budget(target_seconds)
    scenes, per_scene = scene_plan(target_seconds)
    return f"""You are a patient, friendly teacher who explains one concept as a short visual lesson.
Reply with ONE JSON object and nothing else: no markdown, no code fences, no HTML, no comments, no text before or after it.
The JSON must match the format of the example below exactly.

Rules:
- 3 to 6 scenes. The first scene must be a title_card. Build understanding step by step and end with a short recap title_card.
- Scene types:
  title_card: heading (max 60 characters), optional subheading (max 80), narration.
  diagram: heading, layout ("row" for a sequence, "cycle" for something that repeats, "stack" for layers or comparisons), items (2 to 6 labels, max 24 characters each), optional arrows (from and to are item numbers starting at 0, optional label max 16 characters), narration.
  code_walkthrough: heading, code (at most 12 lines of at most 50 characters), highlight_lines (1-based line numbers of the code, in the order they are explained), optional language_hint, narration.
- Use code_walkthrough only for programming topics (and then include one with a short, real, working example). Use diagram for processes, cycles and comparisons. Never write code anywhere except the code field.
- Diagram items must all be different: each one a short, concrete step, stage or part of the concept (not the same label repeated). The narration of a diagram walks through its items in order, one sentence per item when possible.
- Write every word, including diagram items and headings, in English using plain Latin letters. Never use Chinese, Hindi or any other script.
- Every scene must teach something specific about the topic. Do not repeat sentences between scenes.
- Narration is spoken aloud: simple English for a {level} learner, 2 to 3 short sentences per scene, no lists, no symbols that are hard to read aloud.
- Aim for {scenes} scenes, each with 2 to 3 full sentences, about {per_scene} words of narration per scene. Total narration across all scenes: about {words} words (too short or too long is rejected).
- "language" must be "en" and "level" must be "{level}". Do not add any other fields (no durations, no meta).

Example (topic "How a Python loop works", beginner, 45 seconds):
{_example()}"""


def build_user_prompt(topic: str, level: str, target_seconds: int) -> str:
    """User message for a concept request."""
    return (
        f"Topic: {topic}\nLevel: {level}\n"
        f"Target length: about {target_seconds} seconds, about {word_budget(target_seconds)} words of narration in total.\n"
        "Return the lesson JSON now."
    )


def build_retry_prompt(errors: list[str]) -> str:
    """Text appended to the user message for the single retry."""
    listed = "\n".join(f"- {e}" for e in errors[:8])
    return (
        "\n\nYour previous answer was rejected for these reasons:\n" + listed +
        "\nFix every problem and return the complete corrected lesson JSON again."
    )
