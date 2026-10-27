"""Render the bundled sample lesson to an MP4 (make sample).

timing + TTS (cached) -> build frontend if stale -> local server -> capture keyframes -> encode -> ffprobe.
Writes outputs/lessons/sample-<lang>/lesson.mp4 next to timeline.json, lesson.wav and captions.srt.
"""
from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.cache.store import read_json  # noqa: E402
from app.config import SAMPLES_DIR, get_settings  # noqa: E402
from app.export.capture import export_lesson, local_server  # noqa: E402
from app.export.ffmpeg import ffprobe_summary  # noqa: E402
from app.timing.timeline import build_timeline  # noqa: E402

FRONTEND = REPO_ROOT / "frontend"
TOLERANCE_S = 0.2


def _newest(paths: list[Path]) -> float:
    latest = 0.0
    for base in paths:
        files = [base] if base.is_file() else [p for p in base.rglob("*") if p.is_file()] if base.is_dir() else []
        latest = max([latest, *(f.stat().st_mtime for f in files)])
    return latest


def ensure_frontend_built(force: bool = False) -> None:
    """Run `npm run build` when frontend/dist is missing or older than the sources."""
    index = FRONTEND / "dist" / "index.html"
    sources = [FRONTEND / "src", FRONTEND / "public", FRONTEND / "index.html", FRONTEND / "package.json"]
    if not force and index.is_file() and index.stat().st_mtime >= _newest(sources):
        print("frontend: dist is up to date")
        return
    npm = shutil.which("npm")
    if npm is None:
        raise SystemExit("npm not found; install Node 20 (python scripts/doctor.py)")
    if not (FRONTEND / "node_modules").is_dir():
        subprocess.run([npm, "install"], cwd=FRONTEND, check=True)
    print("frontend: building ...")
    subprocess.run([npm, "run", "build"], cwd=FRONTEND, check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--language", "--lang", dest="lang", choices=["en", "hi", "ta"], default="en")
    ap.add_argument("--sample", default="python_loop")
    ap.add_argument("--rebuild", action="store_true", help="force a frontend rebuild")
    args = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)

    start = time.perf_counter()
    lesson_id = f"sample-{args.lang}"
    out_dir = get_settings().outputs_dir / "lessons" / lesson_id

    print(f"timing: {args.sample}.{args.lang} -> {out_dir}")
    lesson = read_json(SAMPLES_DIR / f"{args.sample}.{args.lang}.json")
    timeline = build_timeline(lesson, args.lang, out_dir)  # TTS is cached per sentence
    ensure_frontend_built(args.rebuild)

    with local_server() as url:
        mp4 = export_lesson(lesson_id, url)

    info = ffprobe_summary(mp4)
    drift = abs(info["duration"] - timeline["total_seconds"])
    print(f"\n{mp4}")
    print(f"  {info['width']}x{info['height']}  video={info['video_codec']} ({info['pix_fmt']})  audio={info['audio_codec']}")
    print(f"  duration {info['duration']:.2f}s vs timeline {timeline['total_seconds']:.2f}s (drift {drift * 1000:.0f} ms)")
    print(f"  size {info['size_bytes'] / 1e6:.2f} MB   captions: {mp4.parent / 'captions.srt'}")
    print(f"  total wall time {time.perf_counter() - start:.1f}s")

    problems = []
    if (info["width"], info["height"]) != (1280, 720):
        problems.append("resolution is not 1280x720")
    if info["video_codec"] != "h264":
        problems.append("video codec is not h264")
    if info["audio_codec"] != "aac":
        problems.append("audio codec is not aac")
    if drift > TOLERANCE_S:
        problems.append(f"duration differs from timeline by {drift:.2f}s (> {TOLERANCE_S}s)")
    for p in problems:
        print("FAIL:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
