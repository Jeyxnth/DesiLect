"""The only place that decides durations (G4): scene length = audio length + short pause."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SENTENCE_GAP_S = 0.15  # silence between sentences inside a scene
SCENE_PAUSE_S = 0.6  # short pause after the last sentence of a scene


@dataclass(frozen=True)
class SentenceAudio:
    """Measured audio for one narrated sentence."""

    scene_index: int
    text: str
    duration_s: float
    path: str


def scene_duration(sentence_durations: list[float]) -> float:
    """Scene length from measured audio. Never hard-coded."""
    if not sentence_durations:
        return SCENE_PAUSE_S
    return sum(sentence_durations) + SENTENCE_GAP_S * (len(sentence_durations) - 1) + SCENE_PAUSE_S


def build_timeline(
    lesson: dict[str, Any],
    lesson_id: str,
    audio: list[SentenceAudio],
    audio_url: str,
) -> dict[str, Any]:
    """Build a dict matching shared/schema/timeline.schema.json.

    TODO(step 2): absolute scene start/end, cues per sentence, beats for
    reveal/highlight spread across each scene's sentences.
    """
    raise NotImplementedError("TODO(step 2): build timeline from audio durations")
