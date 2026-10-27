"""Pre-generate the narration of the bundled fallback samples into shared/tts_cache/ (commit the result).

The timeline looks there after outputs/cache/tts, so a sample lesson plays with no TTS engine at demo time (G2).
Entries are keyed exactly like the runtime cache (engine, voice, lang, speed, spoken text, audio version) and
stored as 16-bit FLAC. Re-run after changing a sample, the glossary's tts_translit table or the audio processing.

    python scripts/pregen_audio.py                 # every sample, en hi ta
    python scripts/pregen_audio.py --lang hi       # one language
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.cache.store import BUNDLED_TTS_DIR, bundled_tts_path, load_cached_audio, read_json, save_bundled_audio  # noqa: E402
from app.config import SAMPLES_DIR  # noqa: E402
from app.timing.sentences import split_sentences  # noqa: E402
from app.timing.timeline import SentenceSynth  # noqa: E402
from app.tts.prep import prepare_tts_text  # noqa: E402
from app.tts.registry import release_all  # noqa: E402

SAMPLES = ("python_loop", "binary_search", "photosynthesis", "pythagorean_theorem")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--lang", nargs="+", default=["en", "hi", "ta"], choices=["en", "hi", "ta"])
    ap.add_argument("--sample", nargs="+", default=list(SAMPLES))
    ap.add_argument("--rebuild", action="store_true", help="synthesise again even if the bundle already has the entry")
    args = ap.parse_args()

    manifest_dir = BUNDLED_TTS_DIR / "manifest"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    for lang in args.lang:
        entries: dict[str, dict[str, str]] = {}
        synth = SentenceSynth(lang, None, 1.0, use_cache=not args.rebuild)
        started = time.perf_counter()
        try:
            for name in args.sample:
                lesson = read_json(SAMPLES_DIR / f"{name}.{lang}.json")
                for scene in lesson["scenes"]:
                    for text in split_sentences(scene["narration"], lang):
                        samples = synth(text)
                        path = synth.cache_path(text)
                        if args.rebuild or not bundled_tts_path(path).is_file():
                            save_bundled_audio(path, samples, 24_000)
                        entries[path.stem] = {
                            "sample": name,
                            "engine": synth.engine.name,
                            "voice": synth.voice,
                            "caption": text,
                            "spoken": prepare_tts_text(text, lang),
                        }
        except (FileNotFoundError, ImportError, NotImplementedError) as exc:
            print(f"{lang}: skipped, {exc}", file=sys.stderr)
            continue
        finally:
            release_all()
        out = manifest_dir / f"{lang}.json"
        out.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
        seconds = sum(len(load_cached_audio(synth.cache_path(e["caption"]))[0]) for e in entries.values()) / 24_000
        print(f"{lang}: {len(entries)} sentences, {seconds:.0f}s of audio, "
              f"synth rtf {synth.synth_seconds / max(synth.audio_seconds, 1e-9):.2f}, wall {time.perf_counter() - started:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
