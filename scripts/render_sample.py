"""Render the bundled sample lesson end to end (make sample). TODO(step 4): full MP4 export."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.cache.store import lesson_dir, write_json  # noqa: E402
from app.planner.fallback import fallback_lesson  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--language", choices=["en", "hi", "ta"], default="en")
    args = ap.parse_args()

    lesson = fallback_lesson(language=args.language)
    out = lesson_dir(f"sample-{args.language}")
    write_json(out / "lesson.json", lesson)
    print(f"wrote {out / 'lesson.json'}")
    # TODO(step 2): TTS + timeline. TODO(step 4): Playwright capture + FFmpeg -> lesson.mp4 + .srt
    print("audio, timeline and MP4 export are not implemented yet")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
