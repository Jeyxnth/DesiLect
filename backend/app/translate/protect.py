"""Protect code, numbers and technical terms from translation (G5).

Spans are replaced with numbered placeholders before translation and put back afterwards. What is
protected: `code spans`, calls like range(3), assignments like i = 0, snake_case identifiers, numbers
(the keep_patterns in shared/glossary.json) and every keep_english glossary term.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from typing import Any

from ..config import SHARED_DIR

# IndicTrans2 is trained to copy <ID1>-style tags through unchanged (IndicTransToolkit uses the same form).
PLACEHOLDER = "<ID{}>"
_PLACEHOLDER_RE = re.compile(r"<\s*ID\s*(\d+)\s*>", re.I)


@lru_cache(maxsize=1)
def glossary() -> dict[str, Any]:
    return json.loads((SHARED_DIR / "glossary.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=2)
def _pattern(use_glossary: bool) -> re.Pattern[str]:
    g = glossary()
    parts = list(g["keep_patterns"])
    if use_glossary:
        terms = sorted(g["keep_english"], key=len, reverse=True)  # longest first: "binary search" before "search"
        parts.append(r"(?i:\b(?:" + "|".join(re.escape(t) for t in terms) + r")\b)")
    return re.compile("|".join(f"(?:{p})" for p in parts))


def protect(text: str, use_glossary: bool = True) -> tuple[str, dict[str, str]]:
    """Replace protected spans with placeholders <ID0>, <ID1>, ...

    Returns (masked_text, mapping). use_glossary=False protects only code and numbers (the retry mode).
    """
    mapping: dict[str, str] = {}

    def repl(m: re.Match[str]) -> str:
        key = PLACEHOLDER.format(len(mapping))
        mapping[key] = m.group(0)
        return key

    return _pattern(use_glossary).sub(repl, text), mapping


def missing_placeholders(text: str, mapping: dict[str, str]) -> list[str]:
    """Placeholders from `mapping` that the translation lost."""
    found = {PLACEHOLDER.format(int(n)) for n in _PLACEHOLDER_RE.findall(text)}
    return [k for k in mapping if k not in found]


def restore(text: str, mapping: dict[str, str]) -> str:
    """Put the original spans back after translation (tolerates spacing the model adds inside a tag)."""

    def repl(m: re.Match[str]) -> str:
        return mapping.get(PLACEHOLDER.format(int(m.group(1))), m.group(0))

    return _PLACEHOLDER_RE.sub(repl, text)
