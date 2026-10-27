"""Protect code, numbers and technical terms from translation (G5)."""
from __future__ import annotations

import json
import re
from functools import lru_cache

from ..config import SHARED_DIR


@lru_cache(maxsize=1)
def _glossary() -> dict:
    return json.loads((SHARED_DIR / "glossary.json").read_text(encoding="utf-8"))


def _pattern() -> re.Pattern[str]:
    g = _glossary()
    terms = sorted(g["keep_english"], key=len, reverse=True)
    parts = list(g["keep_patterns"]) + [r"\b(?:" + "|".join(map(re.escape, terms)) + r")\b"]
    return re.compile("|".join(f"(?:{p})" for p in parts))


def protect(text: str) -> tuple[str, dict[str, str]]:
    """Replace protected spans with placeholders like __K0__.

    Returns (masked_text, mapping). TODO(step 8): verify placeholders survive IndicTrans2.
    """
    mapping: dict[str, str] = {}

    def repl(m: re.Match[str]) -> str:
        key = f"__K{len(mapping)}__"
        mapping[key] = m.group(0)
        return key

    return _pattern().sub(repl, text), mapping


def restore(text: str, mapping: dict[str, str]) -> str:
    """Put the original spans back after translation."""
    for key, original in mapping.items():
        text = text.replace(key, original)
    return text
