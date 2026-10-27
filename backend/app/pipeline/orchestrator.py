"""Runs plan -> timeline (TTS) -> export, timing each stage (G6) and falling back on failure (G2)."""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Any

from ..cache.store import lesson_dir, record_timing, timed_stage, write_json
from ..config import get_settings
from ..export.capture import ensure_frontend_built, export_lesson, local_server
from ..planner.fallback import fallback_lesson
from ..planner.ollama_client import OllamaClient, OllamaError, lesson_format_schema
from ..planner.prompts import build_retry_prompt, build_system_prompt, build_user_prompt
from ..planner.validate import parse_and_validate
from ..timing.timeline import build_timeline
from ..translate.indictrans import translate_lesson
from .jobs import JOBS, ConceptRequest

log = logging.getLogger("blu.pipeline")

# (stage, progress when the stage starts); progress is 1.0 when everything is done
STAGES = (("plan", 0.0), ("translate", 0.3), ("narrate", 0.35), ("export", 0.6))
MAX_ATTEMPTS = 2


def plan_lesson(
    topic: str,
    level: str,
    target_seconds: int,
    lesson_id: str | None = None,
    client: OllamaClient | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Stage 2: ask the local model for an English lesson; never raise.

    Attempt 1; if invalid, attempt 2 with the validator errors appended; if still invalid, or Ollama is
    down, timed out or missing the model, use the built-in fallback lesson. Raw replies go to
    outputs/lessons/<id>/planner_raw.txt and each attempt's wall time to timings.json.
    Returns (lesson, meta) where meta describes how the plan was made.
    """
    client = client or OllamaClient()
    system = build_system_prompt(level, target_seconds)
    user = build_user_prompt(topic, level, target_seconds)
    schema = lesson_format_schema()
    raw_path = lesson_dir(lesson_id) / "planner_raw.txt" if lesson_id else None
    if raw_path:
        raw_path.write_text("", encoding="utf-8")

    def log_raw(n: int, seconds: float, body: str) -> None:
        if raw_path:
            with raw_path.open("a", encoding="utf-8") as f:
                f.write(f"=== attempt {n} ({seconds:.1f}s) ===\n{body}\n\n")

    attempt_seconds: list[float] = []
    errors: list[str] = []
    reason: str | None = None
    lesson: dict[str, Any] | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        prompt = user if attempt == 1 else user + build_retry_prompt(errors)
        start = time.perf_counter()
        try:
            raw = client.chat_json(system, prompt, schema)
        except OllamaError as exc:  # not running, model missing, timeout, HTTP error: retrying will not help
            seconds = time.perf_counter() - start
            attempt_seconds.append(round(seconds, 2))
            reason = f"{type(exc).__name__}: {exc}"
            log_raw(attempt, seconds, f"[no reply] {reason}")
            log.warning("planner attempt %d failed: %s", attempt, reason)
            break
        seconds = time.perf_counter() - start
        attempt_seconds.append(round(seconds, 2))
        lesson, errors = parse_and_validate(raw, target_seconds)
        log_raw(attempt, seconds, raw + ("\n--- rejected: " + "; ".join(errors) if errors else "\n--- accepted"))
        if lesson is not None:
            break
        reason = "invalid plan: " + "; ".join(errors[:3])
        log.warning("planner attempt %d rejected: %s", attempt, reason)

    for n, seconds in enumerate(attempt_seconds, 1):
        if lesson_id:
            record_timing(lesson_id, f"plan_attempt_{n}", seconds)

    meta: dict[str, Any] = {
        "fallback": lesson is None,
        "reason": None if lesson is not None else reason,
        "model": client.model,
        "attempts": len(attempt_seconds),
        "attempt_seconds": attempt_seconds,
        "planner_seconds": round(sum(attempt_seconds), 2),
    }
    if lesson is None:
        return fallback_lesson(topic, level, "en"), meta
    lesson["level"], lesson["language"] = level, "en"  # the plan is always English; level is the request's
    lesson["meta"] = {"fallback": False, "source": f"ollama:{client.model}", "topic": topic[:200]}
    return lesson, meta


def run_pipeline(
    job_id: str,
    base_url: str | None = None,
    client: OllamaClient | None = None,
    export: bool = True,
) -> None:
    """Run all stages for a job. Never raises; failures are recorded on the job.

    base_url is where the app (frontend + /media) is served for capture; by default a private local
    server is started for the export. TODO(step 8): real translation; TODO(step 9): Tamil TTS.
    """
    job = JOBS.get(job_id)
    if job is None:
        return
    req = job.request
    out_dir = lesson_dir(job_id)

    def status(stage: str, progress: float) -> None:
        JOBS.update(job_id, stage=stage, progress=progress)
        write_json(out_dir / "status.json", {"stage": stage, "progress": progress, "fallback_used": JOBS.get(job_id).fallback_used})  # type: ignore[union-attr]

    JOBS.update(job_id, state="running")
    try:
        status("plan", 0.0)
        with timed_stage(job_id, "plan"):
            lesson, plan_meta = plan_lesson(req.topic, req.level, req.target_seconds, job_id, client)
        JOBS.update(job_id, fallback_used=plan_meta["fallback"])
        write_json(out_dir / "plan_meta.json", plan_meta)

        if req.language != "en":
            status("translate", 0.3)
            with timed_stage(job_id, "translate"):
                lesson = translate_lesson(lesson, req.language)  # falls back to the pre-translated sample (G2)
            JOBS.update(job_id, fallback_used=True)
        write_json(out_dir / "lesson.json", lesson)

        status("narrate", 0.35)
        with timed_stage(job_id, "narrate"):
            build_timeline(lesson, req.language, out_dir)

        if export:
            status("export", 0.6)
            ensure_frontend_built()
            if base_url:
                export_lesson(job_id, base_url)
            else:
                with local_server() as url:
                    export_lesson(job_id, url)
        status("done", 1.0)
        JOBS.update(job_id, state="done")
    except Exception as exc:  # noqa: BLE001 - report on the job instead of crashing the worker
        log.exception("pipeline failed")
        JOBS.update(job_id, state="failed", error=str(exc))


def main(argv: list[str] | None = None) -> int:
    """CLI: python -m app.pipeline.orchestrator "Photosynthesis" --level beginner --seconds 45"""
    ap = argparse.ArgumentParser(description="Plan, narrate and export a lesson for a concept.")
    ap.add_argument("topic")
    ap.add_argument("--level", choices=["beginner", "intermediate"], default="beginner")
    ap.add_argument("--language", choices=["en", "hi", "ta"], default="en")
    ap.add_argument("--seconds", type=int, default=45)
    ap.add_argument("--no-export", action="store_true", help="stop after the timeline (skip the MP4)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    job = JOBS.create(ConceptRequest(topic=args.topic, level=args.level, language=args.language, target_seconds=args.seconds))
    start = time.perf_counter()
    run_pipeline(job.id, export=not args.no_export)
    job = JOBS.get(job.id)
    assert job is not None
    out = get_settings().outputs_dir / "lessons" / job.id
    meta = Path(out / "plan_meta.json")
    print(f"\nlesson {job.id}: {job.state}  fallback_used={job.fallback_used}  total {time.perf_counter() - start:.1f}s")
    if meta.is_file():
        print(meta.read_text(encoding="utf-8"))
    if job.error:
        print("error:", job.error)
    print(out / "lesson.mp4" if (out / "lesson.mp4").is_file() else out)
    return 0 if job.state == "done" else 1


if __name__ == "__main__":
    raise SystemExit(main())
