"""Stage times and peak memory of a lesson (make bench): reads outputs/lessons/<id>/timings.json.

    python scripts/bench.py                 # the most recently finished lesson
    python scripts/bench.py 7ff7c16f8930    # a given lesson
    python scripts/bench.py --all           # one row per lesson, total time

Peak RSS is sampled every 0.1 s during each stage: the app process plus its children (ffmpeg, the capture browser).
The planner's model runs inside the Ollama server, a separate process; its peak is shown as "plan (ollama)".
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.cache.store import read_json  # noqa: E402
from app.config import get_settings  # noqa: E402

# timings.json key -> label, in pipeline order
STAGES = [
    ("plan", "plan"),
    ("translate", "translate"),
    ("narrate", "voice + timing"),
    ("export_smooth", "export (smooth)"),
    ("export_capture", "export capture (keyframe)"),
    ("export_encode", "export encode (keyframe)"),
]


def _lessons() -> list[Path]:
    root = get_settings().outputs_dir / "lessons"
    found = [p for p in root.glob("*/timings.json")] if root.is_dir() else []
    return sorted(found, key=lambda p: p.stat().st_mtime)


def table(timings: dict) -> list[tuple[str, str, str]]:
    rss = timings.get("rss_mb", {})
    rows = []
    for key, label in STAGES:
        if isinstance(timings.get(key), (int, float)):
            rows.append((label, f"{timings[key]:.1f}", f"{rss[key]:.0f}" if key in rss else "-"))
        if key == "plan" and "plan_ollama" in rss:
            rows.append(("plan (ollama)", "", f"{rss['plan_ollama']:.0f}"))
    total = sum(timings[k] for k, _ in STAGES if isinstance(timings.get(k), (int, float)))
    rows.append(("total", f"{total:.1f}", f"{max(rss.values()):.0f}" if rss else "-"))
    return rows


def print_table(lesson: str, timings: dict) -> None:
    tl = timings.get("timeline", {})
    head = f"lesson {lesson}"
    if tl:
        head += f": {tl.get('total_seconds', 0):.1f} s of audio, {tl.get('tts_engine', '?')} rtf {tl.get('tts_rtf')}"
    print(head)
    print(f"  {'stage':<28}{'seconds':>9}{'peak RSS MB':>14}")
    for label, secs, mb in table(timings):
        print(f"  {label:<28}{secs:>9}{mb:>14}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lesson_id", nargs="?", help="lesson to report (default: the latest)")
    ap.add_argument("--all", action="store_true", help="one line per lesson")
    args = ap.parse_args()

    lessons = _lessons()
    if args.all:
        for path in lessons:
            rows = table(read_json(path))
            print(f"{path.parent.name:<32} total {rows[-1][1]:>7} s   peak {rows[-1][2]:>6} MB")
        return 0
    path = (get_settings().outputs_dir / "lessons" / args.lesson_id / "timings.json") if args.lesson_id else (lessons[-1] if lessons else None)
    if path is None or not path.is_file():
        print("no timings yet; generate a lesson or run `make sample` first")
        return 1
    print_table(path.parent.name, read_json(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
