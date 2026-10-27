"""Sentence splitting for narration (Latin, Devanagari danda, Tamil)."""
from __future__ import annotations

import re

# A sentence ends at . ? ! or the Devanagari danda (optionally followed by closing quotes/brackets)
# and is followed by whitespace. Because whitespace is required, tokens such as range(3),
# 3.5 or os.path never split. A terminator glued to the next word is not a boundary.
_BOUNDARY = re.compile(r"(?<=[.?!।॥])([\"'”’)\]]*)\s+")

# Lowercase-word abbreviations whose trailing dot is not a sentence end.
_ABBREV = re.compile(r"(?:\b(?:e\.g|i\.e|etc|vs)\.)$", re.I)


def split_sentences(text: str, language: str = "en") -> list[str]:
    """Split narration into sentences; TTS runs per sentence."""
    text = " ".join(text.split())
    if not text:
        return []
    sentences: list[str] = []
    start = 0
    for m in _BOUNDARY.finditer(text):
        piece = text[start : m.start() + len(m.group(1))]
        if _ABBREV.search(piece):
            continue
        sentences.append(piece.strip())
        start = m.end()
    tail = text[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences
