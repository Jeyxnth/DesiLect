"""On-disk store for lessons, per-sentence audio cache and stage timings (G6)."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from ..config import get_settings

log = logging.getLogger("blu.store")

_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def new_lesson_id() -> str:
    """Return a fresh, filesystem-safe lesson id."""
    return uuid.uuid4().hex[:12]


def lesson_dir(lesson_id: str, create: bool = True) -> Path:
    """Return outputs/lessons/<id>/ (validated so ids cannot escape outputs/)."""
    if not _ID_RE.match(lesson_id):
        raise ValueError(f"invalid lesson id: {lesson_id!r}")
    path = get_settings().outputs_dir / "lessons" / lesson_id
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, data: Any) -> None:
    """Write JSON as UTF-8 (keeps Hindi/Tamil readable)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    """Read a UTF-8 JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def record_timing(lesson_id: str, stage: str, seconds: float) -> None:
    """Merge one stage's wall time into outputs/lessons/<id>/timings.json."""
    path = lesson_dir(lesson_id) / "timings.json"
    timings = read_json(path) if path.is_file() else {}
    timings[stage] = round(seconds, 3)
    write_json(path, timings)


@contextmanager
def timed_stage(lesson_id: str, stage: str) -> Iterator[None]:
    """Log and persist the wall time of a pipeline stage (G6), even on failure."""
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        log.info("stage %s finished in %.2fs (lesson %s)", stage, elapsed, lesson_id)
        record_timing(lesson_id, stage, elapsed)


def cache_key(*parts: str) -> str:
    """Stable content hash used for cache file names."""
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]


def audio_cache_path(language: str, voice: str, text: str) -> Path:
    """Path of the cached WAV for one sentence. TODO(step 2): used by TTS stage."""
    root = get_settings().outputs_dir / "cache" / "audio" / language
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{cache_key(language, voice, text)}.wav"
