"""Text prepared for the voice. Captions keep the original text; only the spoken text changes."""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from ..config import get_settings
from ..translate.protect import glossary

_WORD = r"(?<![A-Za-z0-9_]){}(?![A-Za-z0-9_])"
# Languages whose voice runs an English term into the next word: a comma after the term (and any suffix glued to
# it, as in லூப்-ஐ) makes the voice pause there.
_PAUSE_AFTER_TERMS = {"ta"}
_START, _END = "\x01", "\x02"  # marks a transliterated term while the text is being prepared
_TAMIL_SUFFIX = r"[-஀-௿]*"
_NUMBER = re.compile(r"(?<![A-Za-z0-9_.])(\d+)(?:\.(\d+))?(?![A-Za-z0-9_])")


@lru_cache(maxsize=4)
def _translit(lang: str) -> tuple[re.Pattern[str], dict[str, str]] | None:
    table = {k: v for k, v in glossary().get("tts_translit", {}).get(lang, {}).items() if not k.startswith("_")}
    if not table:
        return None
    lookup = {k.lower(): v for k, v in table.items()}
    keys = sorted(table, key=len, reverse=True)  # longer terms first: "for loop" before "for"
    pattern = re.compile("|".join(_WORD.format(re.escape(k).replace(r"\ ", r"\s+")) for k in keys), re.I)
    return pattern, lookup


def _numbers(lang: str) -> dict[str, Any] | None:
    return glossary().get("tts_numbers", {}).get(lang)


def number_words(digits: str, table: dict[str, Any]) -> str:
    """0-999 as words; longer numbers digit by digit (from shared/glossary.json "tts_numbers")."""
    units, n = table["units"], int(digits)
    if len(digits.lstrip("0") or "0") > 3:
        return " ".join(units[int(d)] for d in digits)
    words: list[str] = []
    hundreds, rest = divmod(n, 100)
    if hundreds:
        if not rest:
            return table["hundreds"][hundreds]
        words.append(table["hundreds_prefix"][hundreds])
    if rest < 20:
        if rest or not hundreds:
            words.append(units[rest])
    else:
        tens, unit = divmod(rest, 10)
        words += [table["tens"][tens]] if not unit else [table["tens_prefix"][tens], units[unit]]
    return " ".join(words)


@lru_cache(maxsize=4)
def _symbols(lang: str) -> tuple[re.Pattern[str], dict[str, str]] | None:
    """Symbols the voice cannot say, from shared/glossary.json "tts_symbols" (longest first: "==" before "=")."""
    table = {k: v for k, v in glossary().get("tts_symbols", {}).get(lang, {}).items() if not k.startswith("_")}
    if not table:
        return None
    return re.compile("|".join(re.escape(k) for k in sorted(table, key=len, reverse=True))), table


def _speak_numbers(text: str, table: dict[str, Any]) -> str:
    def repl(m: re.Match[str]) -> str:
        whole = number_words(m.group(1), table)
        if m.group(2) is None:
            return whole
        return f"{whole} {table['point']} " + " ".join(table["units"][int(d)] for d in m.group(2))

    return _NUMBER.sub(repl, text)


def prepare_tts_text(text: str, lang: str) -> str:
    """The text the voice reads: backticks dropped, call brackets spaced, English terms transliterated.

    Transliteration (hi, ta) is controlled by TTS_TRANSLIT and uses shared/glossary.json "tts_translit". In Tamil
    a comma follows each such term so the voice pauses before the next word, and digits become spoken number words
    ("tts_numbers"), and symbols the voice would drop become words ("tts_symbols"). English is only cleaned up.
    The caption is never changed.
    """
    spoken = text.replace("`", "")
    entry = _translit(lang) if lang != "en" and get_settings().tts_translit else None
    if entry is not None:
        pattern, lookup = entry
        spoken = pattern.sub(lambda m: _START + lookup[" ".join(m.group(0).lower().split())] + _END, spoken)
    spoken = re.sub(r"\s*[()]\s*", " ", spoken)  # range(3) -> "range 3"
    if lang in _PAUSE_AFTER_TERMS:
        # term (+ glued suffix) followed by a word, not by punctuation: add the pause
        spoken = re.sub(_END + "(" + _TAMIL_SUFFIX + r")(?=\s+[^\s,.!?;:])", _END + r"\1,", spoken)
    spoken = spoken.replace(_START, "").replace(_END, "")
    table = _numbers(lang)
    if table is not None:
        spoken = _speak_numbers(spoken, table)
    symbols = _symbols(lang)
    if symbols is not None:
        spoken = symbols[0].sub(lambda m: f" {symbols[1][m.group(0)]} ", spoken)
    return " ".join(spoken.split())
