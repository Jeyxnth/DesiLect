"""Re-export the submission MP4s after a visual change (theme, fonts), without planning, translating or voicing again.

    python scripts/reexport_submissions.py

For every submissions/<slug>.json, each listed lesson is exported again from its own timeline and audio (same plan,
same narration, same timing), checked with ffprobe (1280x720 h264 yuv420p + aac, duration within 0.2 s of the
timeline), and copied over submissions/<slug>_<lang>.mp4 and .srt; the json gets the new ffprobe and export records.
Refuses to save a keyframe-fallback export: a submission must show the smooth export.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.cache.store import lesson_dir, read_json, write_json  # noqa: E402
from app.export.capture import ensure_frontend_built, export_lesson, local_server  # noqa: E402
from app.export.ffmpeg import check_mp4, ffprobe_summary  # noqa: E402

SUBMISSIONS = REPO_ROOT / "submissions"


def main() -> int:
    ensure_frontend_built()
    problems: list[str] = []
    with local_server() as url:
        for record_path in sorted(SUBMISSIONS.glob("*.json")):
            record = read_json(record_path)
            for lang, entry in record["lessons"].items():
                lid = entry["lesson_id"]
                out = lesson_dir(lid, create=False)
                total = float(read_json(out / "timeline.json")["total_seconds"])
                mp4 = export_lesson(lid, url)
                export = read_json(out / "export.json")
                found = check_mp4(mp4, total)
                if export.get("mode") != "smooth":
                    found.append(f"export fell back to {export.get('mode')}")
                if found:
                    problems.append(f"{record_path.stem} {lang}: " + "; ".join(found))
                    continue
                shutil.copy(mp4, SUBMISSIONS / entry["mp4"])
                shutil.copy(out / "captions.srt", SUBMISSIONS / entry["srt"])
                entry["ffprobe"], entry["export"], entry["check"] = ffprobe_summary(mp4), export, "ok"
                print(f"{entry['mp4']}: {entry['ffprobe']['duration']:.2f}s (timeline {total:.2f}s), "
                      f"{entry['ffprobe']['size_bytes'] / 1e6:.2f} MB, {export['mode']}")
            write_json(record_path, record)
    for p in problems:
        print("PROBLEM", p)
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
