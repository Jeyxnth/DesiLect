"""On-disk store for lessons, per-sentence audio cache and stage timings (G6)."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from ..config import SHARED_DIR, get_settings

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


def record_value(lesson_id: str, key: str, value: Any) -> None:
    """Merge a non-timing fact into timings.json, e.g. quiz_dropped: true (bonus B1)."""
    path = lesson_dir(lesson_id) / "timings.json"
    timings = read_json(path) if path.is_file() else {}
    timings[key] = value
    write_json(path, timings)


def record_rss(lesson_id: str, stage: str, megabytes: float) -> None:
    """Merge one stage's peak memory (MB) into timings.json under "rss_mb"."""
    path = lesson_dir(lesson_id) / "timings.json"
    timings = read_json(path) if path.is_file() else {}
    timings.setdefault("rss_mb", {})[stage] = round(megabytes, 1)
    write_json(path, timings)


def ollama_rss(ps: Any) -> int:
    """Resident bytes of the Ollama server and its children, each counted once.

    The model itself runs in a child process (llama-server.exe in current Ollama), so matching the name
    "ollama" alone missed it: step 12 measured 2.4 GB there while "plan (ollama)" showed 120 MB.
    """
    procs: dict[int, Any] = {}
    for p in ps.process_iter(["name"]):
        if (p.info["name"] or "").lower().startswith("ollama"):
            procs[p.pid] = p
            try:
                procs.update((c.pid, c) for c in p.children(recursive=True))
            except ps.Error:
                pass
    total = 0
    for p in procs.values():
        try:
            total += p.memory_info().rss
        except ps.Error:  # exited mid-sample
            pass
    return total


class _PeakRSS:
    """Samples resident memory every 0.1 s on a thread: this process plus its children (ffmpeg, the browser).

    With include_ollama it also tracks the Ollama server (a separate process), reported as "<stage>_ollama".
    Without psutil it records nothing.
    """

    def __init__(self, include_ollama: bool = False) -> None:
        self.app = self.ollama = 0
        self._include_ollama = include_ollama
        self._stop = threading.Event()
        try:
            import psutil

            self._psutil, self._me = psutil, psutil.Process()
        except ImportError:
            self._psutil = None
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _sample(self) -> None:
        ps = self._psutil
        try:
            procs = [self._me, *self._me.children(recursive=True)]
            self.app = max(self.app, sum(p.memory_info().rss for p in procs if p.is_running()))
            if self._include_ollama:
                self.ollama = max(self.ollama, ollama_rss(ps))
        except (ps.Error, OSError):  # a child exited mid-sample
            pass

    def _run(self) -> None:
        while not self._stop.wait(0.1):
            self._sample()

    def stop(self) -> None:
        if self._psutil is None:
            return
        self._stop.set()
        self._thread.join(timeout=1)
        self._sample()


@contextmanager
def timed_stage(lesson_id: str, stage: str) -> Iterator[None]:
    """Log and persist the wall time and peak memory of a pipeline stage (G6), even on failure."""
    start = time.perf_counter()
    peak = _PeakRSS(include_ollama=stage == "plan")
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        peak.stop()
        log.info("stage %s finished in %.2fs, peak %.0f MB (lesson %s)", stage, elapsed, peak.app / 2**20, lesson_id)
        record_timing(lesson_id, stage, elapsed)
        if peak.app:
            record_rss(lesson_id, stage, peak.app / 2**20)
        if peak.ollama:
            record_rss(lesson_id, f"{stage}_ollama", peak.ollama / 2**20)


# --- reuse cache: finished lessons by request ---------------------------------------------------

def normalise_topic(topic: str) -> str:
    """Case, spacing and trailing punctuation do not make a different lesson."""
    return " ".join(topic.casefold().split()).strip(" ?!.")


def lesson_cache_key(topic: str, level: str, lang: str, target_seconds: int, voice: str, speed: float) -> str:
    from ..config import PIPELINE_VERSION

    parts = [normalise_topic(topic), level, lang, str(int(target_seconds)), voice, f"{speed:.2f}", PIPELINE_VERSION]
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()


def _lesson_index(key: str) -> Path:
    return get_settings().outputs_dir / "cache" / "lessons" / f"{key}.json"


def find_cached_lesson(key: str) -> str | None:
    """Id of a finished lesson (timeline and MP4 on disk) made for this request, else None."""
    path = _lesson_index(key)
    if not path.is_file():
        return None
    try:
        lesson_id = str(read_json(path)["lesson_id"])
        out = lesson_dir(lesson_id, create=False)
    except (ValueError, KeyError, OSError):
        return None
    return lesson_id if (out / "timeline.json").is_file() and (out / "lesson.mp4").is_file() else None


def remember_lesson(key: str, lesson_id: str) -> None:
    write_json(_lesson_index(key), {"lesson_id": lesson_id})


def cache_key(*parts: str) -> str:
    """Stable content hash used for cache file names."""
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]


def tts_cache_path(engine: str, voice: str, lang: str, speed: float, text: str, variant: str = "") -> Path:
    """Cache file for one sentence: outputs/cache/tts/<sha1(engine, voice, lang, speed, text[, variant])>.wav.

    text is the spoken text. variant versions the audio processing so old entries become misses.
    """
    parts = [engine, voice, lang, f"{speed:.3f}", text] + ([variant] if variant else [])
    key = hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()
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


BUNDLED_TTS_DIR = SHARED_DIR / "tts_cache"  # committed audio for the fallback samples (G2), read-only


def bundled_tts_path(cache_path: Path) -> Path:
    """The committed copy (FLAC) of a cache entry, same key as outputs/cache/tts/<key>.wav."""
    return BUNDLED_TTS_DIR / f"{cache_path.stem}.flac"


def load_cached_audio(path: Path) -> tuple[Any, int] | None:
    """Return (float32 samples, sample_rate) from outputs/cache/tts, else from the committed bundle."""
    import soundfile as sf

    for candidate in (path, bundled_tts_path(path)):
        if not candidate.is_file():
            continue
        try:
            data, sr = sf.read(candidate, dtype="float32")
        except Exception:  # noqa: BLE001 - a corrupt cache entry is just a miss
            continue
        return data, int(sr)
    return None


def save_bundled_audio(cache_path: Path, samples: Any, sample_rate: int) -> Path:
    """Write a cache entry into the committed bundle (lossless 16-bit FLAC). Used by scripts/pregen_audio.py."""
    import soundfile as sf

    dest = bundled_tts_path(cache_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sf.write(dest, samples, sample_rate, subtype="PCM_16", format="FLAC")
    return dest


def save_cached_audio(path: Path, samples: Any, sample_rate: int) -> None:
    """Write lossless float WAV atomically so an interrupted run never leaves a bad entry."""
    import soundfile as sf

    tmp = path.with_suffix(".tmp.wav")
    sf.write(tmp, samples, sample_rate, subtype="FLOAT")
    tmp.replace(path)
