"""The only place that decides durations (G4): scene length = audio length + short pause."""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Any, Callable

import numpy as np
import soundfile as sf

from ..cache.store import load_cached_audio, read_json, save_cached_audio, tts_cache_path, write_json
from ..config import SAMPLES_DIR, get_settings
from ..export.ffmpeg import write_srt
from ..planner.validate import validate_timeline
from ..tts.audio import POSTPROCESS_VERSION, finalize_sentence
from ..tts.base import SAMPLE_RATE
from ..tts.prep import prepare_tts_text
from ..tts.registry import get_engine, release_all
from .sentences import split_sentences

log = logging.getLogger("blu.timeline")

SENTENCE_GAP_S = 0.15  # silence between sentences inside a scene
SCENE_PAUSE_S = 0.6  # tail pause after the last sentence of a scene


class SentenceSynth:
    """Cached per-sentence synthesis. The model is only loaded on the first cache miss.

    A sentence is spoken from prepare_tts_text(text) (English terms transliterated for hi/ta) while the
    caller keeps the original text for captions. Each result is peak-normalised and trimmed before it is
    cached, so the cached length is the final length the timeline uses.
    """

    def __init__(self, lang: str, voice: str | None, speed: float, use_cache: bool, engine: str | None = None) -> None:
        self.lang, self.speed, self.use_cache = lang, speed, use_cache
        self.engine, default_voice = get_engine(lang, engine)
        requested = voice or default_voice
        resolve = getattr(self.engine, "resolve_voice", None)
        self.voice = resolve(requested) if resolve else requested
        self.synth_seconds = 0.0  # wall time spent in the model
        self.audio_seconds = 0.0  # audio produced by the model (cache misses only)
        self.hits = self.misses = 0
        self.cache_paths: list[Path] = []  # every entry used, in order (scripts/pregen_audio.py bundles them)

    def cache_path(self, text: str) -> Path:
        spoken = prepare_tts_text(text, self.lang)
        return tts_cache_path(self.engine.name, self.voice, self.lang, self.speed, spoken, POSTPROCESS_VERSION)

    def __call__(self, text: str) -> np.ndarray:
        path = self.cache_path(text)
        self.cache_paths.append(path)
        cached = load_cached_audio(path) if self.use_cache else None
        if cached is not None and cached[1] == SAMPLE_RATE:
            self.hits += 1
            return np.asarray(cached[0], dtype=np.float32)
        self.misses += 1
        start = time.perf_counter()
        samples, sr = self.engine.synth(prepare_tts_text(text, self.lang), self.lang, self.voice, self.speed)
        self.synth_seconds += time.perf_counter() - start
        if sr != SAMPLE_RATE:
            raise RuntimeError(f"engine returned {sr} Hz, expected {SAMPLE_RATE}")
        samples = finalize_sentence(np.asarray(samples, dtype=np.float32), sr)
        self.audio_seconds += len(samples) / sr
        save_cached_audio(path, samples, sr)
        return samples


def _beats(scene: dict[str, Any], cues: list[dict[str, Any]], end: float) -> list[dict[str, Any]]:
    """Reveal/highlight beats tied to cue starts."""
    beats: list[dict[str, Any]] = []
    if scene["type"] == "diagram":
        n = len(scene["items"])
        for k in range(min(n, len(cues))):
            beats.append({"t": cues[k]["start"], "action": "reveal", "value": k})
        extra = n - len(cues)
        if extra > 0 and cues:  # more items than sentences: spread the rest evenly to the scene end
            last = cues[-1]["start"]
            for j in range(extra):
                t = last + (end - last) * (j + 1) / (extra + 1)
                beats.append({"t": round(t, 4), "action": "reveal", "value": len(cues) + j})
    elif scene["type"] == "code_walkthrough":
        for k, line in enumerate(scene["highlight_lines"][: len(cues)]):
            beats.append({"t": cues[k]["start"], "action": "highlight", "value": line})
    return beats


def _audio_url(out_dir: Path) -> str:
    try:
        rel = out_dir.resolve().relative_to(get_settings().outputs_dir.resolve())
        return f"/media/{rel.as_posix()}/lesson.wav"
    except ValueError:
        return "lesson.wav"


def build_timeline(
    lesson: dict[str, Any],
    lang: str,
    out_dir: Path,
    *,
    voice: str | None = None,
    speed: float = 1.0,
    use_cache: bool = True,
    on_stage: Callable[[str], None] | None = None,
    engine: str | None = None,
) -> dict[str, Any]:
    """Synthesise narration and write the lesson's audio, timeline and captions.

    engine overrides the configured TTS engine (the sample fallback passes the one its audio was bundled with).

    Writes out_dir/audio/s{scene}_{k}.wav, lesson.wav, timeline.json, captions.srt, timings.json
    and returns the timeline dict (validated against shared/schema/timeline.schema.json).
    on_stage is told "voice" before synthesis and "timing" before the timeline is assembled.
    """
    if on_stage:
        on_stage("voice")
    out_dir = Path(out_dir)
    (out_dir / "audio").mkdir(parents=True, exist_ok=True)
    gap = round(SENTENCE_GAP_S * SAMPLE_RATE)
    pause = round(SCENE_PAUSE_S * SAMPLE_RATE)
    wall = time.perf_counter()
    synth = SentenceSynth(lang, voice, speed, use_cache, engine)

    try:
        # Plan everything in integer samples so lesson.wav length matches total_seconds exactly.
        placed: list[tuple[int, np.ndarray]] = []  # (start sample, audio)
        scenes_out: list[dict[str, Any]] = []
        cursor = 0
        for i, scene in enumerate(lesson["scenes"]):
            scene_start = cursor
            cues: list[dict[str, Any]] = []
            for k, text in enumerate(split_sentences(scene["narration"], lang)):
                audio = synth(text)
                sf.write(out_dir / "audio" / f"s{i}_{k}.wav", audio, SAMPLE_RATE, subtype="PCM_16")
                placed.append((cursor, audio))
                cues.append({"start": cursor / SAMPLE_RATE, "end": (cursor + len(audio)) / SAMPLE_RATE, "text": text})
                cursor += len(audio) + gap
            cursor = (cursor - gap if cues else cursor) + pause  # drop the trailing gap, add the tail pause
            end = cursor / SAMPLE_RATE
            for cue in cues:
                cue["start"], cue["end"] = round(cue["start"], 4), round(cue["end"], 4)
            scenes_out.append(
                {
                    "index": i,
                    "type": scene["type"],
                    "start": round(scene_start / SAMPLE_RATE, 4),
                    "end": round(end, 4),
                    "heading": scene["heading"],
                    "data": scene,
                    "cues": cues,
                    "beats": _beats(scene, cues, end),
                }
            )
    finally:
        release_all()  # unload the model right after the stage (H3)

    if on_stage:
        on_stage("timing")
    wav = np.zeros(cursor, dtype=np.float32)
    for start, audio in placed:
        wav[start : start + len(audio)] = audio
    sf.write(out_dir / "lesson.wav", wav, SAMPLE_RATE, subtype="PCM_16")

    lesson_id = out_dir.name
    timeline = {
        "lesson_id": lesson_id,
        "language": lang,
        "total_seconds": round(cursor / SAMPLE_RATE, 4),
        "audio_url": _audio_url(out_dir),
        "scenes": scenes_out,
    }
    errors = validate_timeline(timeline)
    if errors:
        raise ValueError("timeline does not match schema: " + "; ".join(errors[:5]))
    write_json(out_dir / "timeline.json", timeline)
    write_srt(timeline, out_dir / "captions.srt")

    elapsed = time.perf_counter() - wall
    rtf = synth.synth_seconds / synth.audio_seconds if synth.audio_seconds else None
    timings_path = out_dir / "timings.json"
    timings = read_json(timings_path) if timings_path.is_file() else {}
    timings["timeline"] = {
        "wall_s": round(elapsed, 3),
        "tts_synth_s": round(synth.synth_seconds, 3),
        "tts_audio_s": round(synth.audio_seconds, 3),
        "tts_rtf": round(rtf, 3) if rtf is not None else None,
        "tts_engine": synth.engine.name,
        "tts_voice": synth.voice,
        "cache_hits": synth.hits,
        "cache_misses": synth.misses,
        "total_seconds": timeline["total_seconds"],
    }
    write_json(timings_path, timings)
    log.info("timeline %s: %.1fs audio in %.1fs (hits=%d misses=%d rtf=%s)", lesson_id,
             timeline["total_seconds"], elapsed, synth.hits, synth.misses, rtf)
    return timeline


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build audio + timeline for a bundled sample lesson.")
    ap.add_argument("--sample", default="python_loop")
    ap.add_argument("--lang", default="en", choices=["en", "hi", "ta"])
    ap.add_argument("--out", type=Path, help="output dir (default outputs/lessons/sample-<lang>)")
    ap.add_argument("--voice")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--no-cache", action="store_true", help="ignore the TTS cache (to measure real-time factor)")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    lesson = read_json(SAMPLES_DIR / f"{args.sample}.{args.lang}.json")
    out = args.out or get_settings().outputs_dir / "lessons" / f"sample-{args.lang}"
    try:
        tl = build_timeline(lesson, args.lang, out, voice=args.voice, speed=args.speed, use_cache=not args.no_cache)
    except (NotImplementedError, FileNotFoundError, ImportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    t = read_json(out / "timings.json")["timeline"]
    print(f"wrote {out}  total {tl['total_seconds']:.2f}s  cache hits/misses {t['cache_hits']}/{t['cache_misses']}")
    if t["tts_rtf"] is not None:
        print(f"TTS real-time factor: {t['tts_rtf']:.3f} (synth {t['tts_synth_s']}s for {t['tts_audio_s']}s audio)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
