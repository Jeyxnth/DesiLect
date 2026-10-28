"""Prompt templates for the local planner LLM. The model must return JSON only (H4)."""
from __future__ import annotations

import json
import math
import re

from ..config import SAMPLES_DIR
from .fallback import next_topics_for

WORDS_PER_SECOND = 2.3  # spoken narration pace the word budget is based on
WORDS_PER_SENTENCE = 12  # what llama3.2 writes per sentence (measured: 10-13, docs/length): it follows a sentence count, not a word count
EXAMPLE_SECONDS = 45  # the few-shot example below is the 45 s Python-loop sample (118 words, 4 scenes)


def word_budget(target_seconds: int) -> int:
    """Target total narration words for a lesson of target_seconds."""
    return round(target_seconds * WORDS_PER_SECOND)


def _example(quiz_questions: int = 3) -> str:
    """The Python-loop sample, as compact JSON (one complete few-shot example), with its quiz cut to quiz_questions."""
    sample = json.loads((SAMPLES_DIR / "python_loop.en.json").read_text(encoding="utf-8"))
    if quiz_questions > 0 and sample.get("quiz"):
        sample["quiz"] = sample["quiz"][:quiz_questions]
    else:
        sample.pop("quiz", None)
    sample["next_topics"] = next_topics_for("python_loop")  # bonus B2: the example shows the shape
    return json.dumps(sample, ensure_ascii=False, indent=1)


NEXT_TOPICS_RULE = (
    '- Add "next_topics": exactly 2 short topics (3 to 60 characters each, in English) the learner should study next: '
    "each one step harder or one step sideways from this topic. They are not spoken."
)


def quiz_rule(quiz_questions: int) -> str:
    """The prompt line asking for the end-of-lesson quiz (bonus B1); empty when the quiz is off."""
    if quiz_questions <= 0:
        return ""
    return (
        f'\n- After "scenes", add "quiz": exactly {quiz_questions} multiple-choice questions that check what THIS lesson\'s scenes taught. '
        'Each has "question" (max 160 characters), "options" (exactly 4 short answers, max 80 characters each, all different, '
        'exactly one correct), "answer_index" (0 to 3, the position of the correct option) and "explanation" (one sentence, '
        'max 200 characters, saying why that answer is right). No trick questions, no "all of the above" or "none of the above". '
        "The quiz is not spoken and does not count toward the narration words."
    )


def scene_plan(target_seconds: int) -> tuple[int, int]:
    """(number of scenes to aim for, words of narration per scene) for a target length."""
    words = word_budget(target_seconds)
    scenes = max(3, min(6, round(words / 28)))
    return scenes, round(words / scenes)


def sentences_per_scene(target_seconds: int) -> int:
    """Spoken sentences each scene needs for the target length. The model meets a plain sentence count far better than a
    word total; given a range ("2 to 3") it writes the upper end and overshoots, so this is one number, rounded to nearest."""
    _, per_scene = scene_plan(target_seconds)
    return max(2, round(per_scene / WORDS_PER_SENTENCE))


# What each level adds. Without this, "intermediate" plans were no longer than beginner ones (often shorter):
# 90 s intermediate lessons came out at a median of 58% of the words asked for.
LEVEL_BRIEF = {
    "beginner": (
        "Beginner learner: use everyday words and one idea per sentence. Explain the main idea with a familiar comparison "
        "from daily life. When a technical word is needed, explain it in the same sentence."
    ),
    "intermediate": (
        "Intermediate learner: assume the basics are known, so do not spend sentences on a basic introduction. Use the correct "
        "technical terms, explain how and why it works step by step, give one concrete example with real values, and mention "
        "one common mistake or limitation."
    ),
}


def length_rule(target_seconds: int) -> str:
    """The length rule, in sentences per scene, and how this lesson's length compares with the example's."""
    words = word_budget(target_seconds)
    scenes, per_scene = scene_plan(target_seconds)
    n = sentences_per_scene(target_seconds)
    rule = (f"- Length: {target_seconds} seconds of speech. Write {scenes} scenes, and give EVERY scene, including both title_cards, "
            f"{n} full sentences of narration (about {per_scene} words; keep each sentence short, about {WORDS_PER_SENTENCE} words). Total narration: about {words} words; much shorter or "
            "longer is rejected.")
    if target_seconds > EXAMPLE_SECONDS + 5:
        rule += (f" The example below is a short {EXAMPLE_SECONDS}-second lesson: your lesson is longer, so each of your narrations "
                 f"must be longer than the example's, {n} sentences each.")
    elif target_seconds < EXAMPLE_SECONDS - 5:
        rule += f" The example below is a {EXAMPLE_SECONDS}-second lesson: yours is shorter, so keep each narration to {n} sentences."
    return rule


def build_system_prompt(level: str, target_seconds: int, quiz_questions: int = 3) -> str:
    """System prompt: teacher persona, output rules, scene types, word budget, the quiz and one example."""
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
- Narration is spoken aloud: clear English, no lists, no symbols that are hard to read aloud.
- {LEVEL_BRIEF.get(level, LEVEL_BRIEF['beginner'])}
{length_rule(target_seconds)}
- "language" must be "en" and "level" must be "{level}". Do not add any other fields (no durations, no meta).{quiz_rule(quiz_questions)}
{NEXT_TOPICS_RULE}

Example (topic "How a Python loop works", beginner, 45 seconds):
{_example(quiz_questions)}"""


def build_user_prompt(topic: str, level: str, target_seconds: int) -> str:
    """User message for a concept request."""
    return (
        f"Topic: {topic}\nLevel: {level}\n"
        f"Target length: about {target_seconds} seconds: {scene_plan(target_seconds)[0]} scenes with "
        f"{sentences_per_scene(target_seconds)} sentences of narration each, about {word_budget(target_seconds)} words in total.\n"
        "Return the lesson JSON now."
    )


_WORD_ERROR = re.compile(r"narration has (\d+) words in total; it must be between \d+ and \d+ \(about (\d+)\)")


def length_fix(errors: list[str]) -> str:
    """A concrete instruction for a narration of the wrong length: how many sentences to add or remove (or "")."""
    for e in errors:
        m = _WORD_ERROR.search(e)
        if m:
            got, want = int(m.group(1)), int(m.group(2))
            n = max(1, math.ceil(abs(want - got) / WORDS_PER_SENTENCE))
            if got < want:
                return (f"\nYour narration had {got} words but needs about {want}. Add about {n} more sentences in total, "
                        "spread over the scenes (one or two more in each scene's narration). Keep every scene; do not add new ones.")
            return f"\nYour narration had {got} words but needs about {want}. Remove about {n} sentences, spread over the scenes."
    return ""


def build_retry_prompt(errors: list[str]) -> str:
    """Text appended to the user message for the single retry."""
    listed = "\n".join(f"- {e}" for e in errors[:8])
    return (
        "\n\nYour previous answer was rejected for these reasons:\n" + listed + length_fix(errors) +
        "\nFix every problem and return the complete corrected lesson JSON again."
    )
