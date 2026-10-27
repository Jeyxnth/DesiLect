"""Render a submission lesson: English plus one Indian language, the same plan, into submissions/ (step 13).

    python scripts/render_submission.py "Explain how caffeine works" --lang hi
    python scripts/render_submission.py "<judges' topic>" --lang hi --seconds 60 --level beginner

Runs the real offline pipeline: the English lesson is planned by Ollama, then the same English plan is re-voiced in
the other language (translated, voiced, timed, exported), exactly as the player's "Same lesson in" does. Copies each
lesson.mp4 and captions.srt to submissions/<topic-slug>_<lang>.mp4 / .srt, checks every MP4 with ffprobe
(1280x720 h264 yuv420p + aac, duration within 0.2 s of the timeline) and writes submissions/<topic-slug>.json.
Refuses to save a lesson that needed a fallback (built-in sample, English narration, or keyframe export) unless
--allow-fallback: a submission must show the real pipeline.
"""
from __future__ import annotations

import argparse
import logging
import re
import shutil
import sys
import time
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.cache.store import lesson_dir, read_json, write_json  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.export.ffmpeg import check_mp4, ffprobe_summary  # noqa: E402
from app.pipeline.jobs import JOBS, ConceptRequest  # noqa: E402
from app.pipeline.orchestrator import run_pipeline  # noqa: E402

SUBMISSIONS = REPO_ROOT / "submissions"


def topic_slug(topic: str, max_length: int = 60) -> str:
    """Same as frontend/src/api/slug.ts topicSlug: the player's download names."""
    ascii_ = "".join(c for c in unicodedata.normalize("NFKD", topic) if not unicodedata.combining(c)).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_).strip("-")[:max_length].rstrip("-")
    return slug or "lesson"


def render(req: ConceptRequest, plan_from: str | None = None) -> tuple[str, list[str]]:
    """Run one lesson; returns (lesson id, reasons it is not submission-ready)."""
    job = JOBS.create(req)
    print(f"{req.language}: lesson {job.id}" + (f" (plan reused from {plan_from})" if plan_from else "") + " ...", flush=True)
    start = time.perf_counter()
    run_pipeline(job.id, plan_from=plan_from)
    done = JOBS.get(job.id)
    assert done is not None
    out = lesson_dir(job.id, create=False)
    meta = read_json(out / "lesson.json").get("meta", {}) if (out / "lesson.json").is_file() else {}
    problems = []
    if done.state != "done" or not done.timeline_ready:
        problems.append(f"pipeline failed: {done.error}")
    if not done.mp4_ready:
        problems.append(f"no MP4: {done.export_error}")
    if meta.get("fallback"):
        problems.append(f"built-in sample used: {meta.get('reason')}")
    if meta.get("translation_fallback"):
        problems.append("translation failed, narration stayed English")
    if done.export_mode == "keyframe":
        problems.append("smooth export failed, keyframe MP4 used")
    print(f"    {time.perf_counter() - start:.0f} s, export {done.export_mode}" + (f", problems: {problems}" if problems else ""))
    return job.id, problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("topic")
    ap.add_argument("--lang", choices=["hi", "ta"], default="hi", help="the Indian language next to English")
    ap.add_argument("--level", choices=["beginner", "intermediate"], default="beginner")
    ap.add_argument("--seconds", type=int, default=60, help="target length of the English lesson (30-90)")
    ap.add_argument("--allow-fallback", action="store_true", help="save even if a stage fell back")
    ap.add_argument("--plan-from", metavar="LESSON_ID",
                    help="voice both languages from this lesson's stored English plan (lesson.en.json) instead of planning again,"
                         " e.g. the best of several plans made with the same planner")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    base = dict(topic=args.topic, level=args.level, target_seconds=args.seconds)
    en_id, problems = render(ConceptRequest(language="en", **base), plan_from=args.plan_from)  # type: ignore[arg-type]
    if problems and not args.allow_fallback:
        print("English lesson is not submission-ready:", "; ".join(problems))
        return 1
    other_id, problems = render(ConceptRequest(language=args.lang, **base), plan_from=en_id)  # type: ignore[arg-type]
    if problems and not args.allow_fallback:
        print(f"{args.lang} lesson is not submission-ready:", "; ".join(problems))
        return 1

    slug = topic_slug(args.topic)
    SUBMISSIONS.mkdir(exist_ok=True)
    manifest = {"topic": args.topic, "level": args.level, "target_seconds": args.seconds,
                "planner": get_settings().ollama_model, "plan_from": args.plan_from, "lessons": {}}
    failed = False
    for lang, lesson_id in (("en", en_id), (args.lang, other_id)):
        out = lesson_dir(lesson_id, create=False)
        mp4, srt = SUBMISSIONS / f"{slug}_{lang}.mp4", SUBMISSIONS / f"{slug}_{lang}.srt"
        shutil.copyfile(out / "lesson.mp4", mp4)
        shutil.copyfile(out / "captions.srt", srt)
        total = read_json(out / "timeline.json")["total_seconds"]
        problems = check_mp4(mp4, total)
        info = ffprobe_summary(mp4)
        failed |= bool(problems)
        manifest["lessons"][lang] = {
            "lesson_id": lesson_id, "mp4": mp4.name, "srt": srt.name, "title": read_json(out / "lesson.json")["title"],
            "timeline_seconds": total, "ffprobe": info, "check": problems or "ok",
            "export": read_json(out / "export.json"), "timings": read_json(out / "timings.json"),
        }
        print(f"{mp4.relative_to(REPO_ROOT)}: {total:.1f} s, " + ("ffprobe OK" if not problems else "CHECK FAILED: " + "; ".join(problems)))
    write_json(SUBMISSIONS / f"{slug}.json", manifest)
    print(f"wrote {(SUBMISSIONS / f'{slug}.json').relative_to(REPO_ROOT)}; now watch both MP4s in full")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
