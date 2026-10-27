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


def tts_cache_path(engine: str, voice: str, lang: str, speed: float, text: str) -> Path:
    """Cache file for one sentence: outputs/cache/tts/<sha1(engine, voice, lang, speed, text)>.wav."""
    key = hashlib.sha1("\x1f".join([engine, voice, lang, f"{speed:.3f}", text]).encode("utf-8")).hexdigest()
    root = get_settings().outputs_dir / "cache" / "tts"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{key}.wav"


def translate_cache_path(model: str, lang: str, text: str) -> Path:
    """Cache file for one translated string: outputs/cache/translate/<sha1(model, lang, text)>.json."""
    key = hashlib.sha1("\x1f".join([model, lang, text]).encode("utf-8")).hexdigest()
    root = get_settings().outputs_dir / "cache" / "translate"
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{key}.json"


def load_cached_text(path: Path) -> str | None:
    try:
        return str(read_json(path)["text"]) if path.is_file() else None
    except (ValueError, KeyError, OSError):  # a corrupt cache entry is just a miss
        return None


def save_cached_text(path: Path, source: str, text: str) -> None:
    tmp = path.with_suffix(".tmp")
    write_json(tmp, {"source": source, "text": text})
    tmp.replace(path)


def load_cached_audio(path: Path) -> tuple[Any, int] | None:
    """Return (float32 samples, sample_rate) if the cache file exists and reads cleanly."""
    if not path.is_file():
        return None
    import soundfile as sf

    try:
        data, sr = sf.read(path, dtype="float32")
    except Exception:  # noqa: BLE001 - a corrupt cache entry is just a miss
        return None
    return data, int(sr)


def save_cached_audio(path: Path, samples: Any, sample_rate: int) -> None:
    """Write lossless float WAV atomically so an interrupted run never leaves a bad entry."""
    import soundfile as sf

    tmp = path.with_suffix(".tmp.wav")
    sf.write(tmp, samples, sample_rate, subtype="FLOAT")
    tmp.replace(path)
