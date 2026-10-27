"""Text prepared for the voice. Captions keep the original text; only the spoken text changes."""
from __future__ import annotations

import re
from functools import lru_cache

from ..config import get_settings
from ..translate.protect import glossary

_WORD = r"(?<![A-Za-z0-9_]){}(?![A-Za-z0-9_])"


@lru_cache(maxsize=4)
def _translit(lang: str) -> tuple[re.Pattern[str], dict[str, str]] | None:
    table = {k: v for k, v in glossary().get("tts_translit", {}).get(lang, {}).items() if not k.startswith("_")}
    if not table:
        return None
    lookup = {k.lower(): v for k, v in table.items()}
    keys = sorted(table, key=len, reverse=True)  # longer terms first: "for loop" before "for"
    pattern = re.compile("|".join(_WORD.format(re.escape(k).replace(r"\ ", r"\s+")) for k in keys), re.I)
    return pattern, lookup


def prepare_tts_text(text: str, lang: str) -> str:
    """The text the voice reads: backticks dropped, call brackets spaced, English terms transliterated.

    Transliteration (hi, ta) is controlled by TTS_TRANSLIT and uses shared/glossary.json "tts_translit".
    English is only cleaned up. The caption is never changed.
    """
    spoken = text.replace("`", "")
    entry = _translit(lang) if lang != "en" and get_settings().tts_translit else None
    if entry is not None:
        pattern, lookup = entry
        spoken = pattern.sub(lambda m: lookup[" ".join(m.group(0).lower().split())], spoken)
    spoken = re.sub(r"\s*[()]\s*", " ", spoken)  # range(3) -> "range 3"
    return " ".join(spoken.split())
