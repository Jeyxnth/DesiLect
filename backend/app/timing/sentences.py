"""Sentence splitting for narration (Latin and Devanagari/Tamil punctuation)."""
from __future__ import annotations

import re

# Split after . ! ? or the Devanagari danda, when followed by whitespace.
_SPLIT_RE = re.compile(r"(?<=[.!?।])\s+")


def split_sentences(text: str, language: str = "en") -> list[str]:
    """Split narration into sentences; TTS runs per sentence.

    TODO(step 2): protect abbreviations / code like range(3). from over-splitting.
    """
    return [s.strip() for s in _SPLIT_RE.split(text.strip()) if s.strip()]
