"""Runs plan -> timeline (TTS) -> export, timing each stage (G6) and falling back on failure (G2)."""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Any, Callable

from ..cache.store import lesson_dir, record_timing, timed_stage, write_json
from ..config import get_settings
from ..export.capture import ensure_frontend_built, export_lesson, local_server
from ..planner.fallback import fallback_lesson
from ..planner.ollama_client import OllamaClient, OllamaError, lesson_format_schema
from ..planner.prompts import build_retry_prompt, build_system_prompt, build_user_prompt
from ..planner.validate import LAST_TRY_WORD_TOLERANCE, WORD_BUDGET_TOLERANCE, parse_and_validate
from ..timing.timeline import build_timeline
from ..translate.indictrans import translate_lesson
from .jobs import JOBS, ConceptRequest

log = logging.getLogger("blu.pipeline")

# Progress when each stage starts; the UI labels them Planning, Translating, Voicing, Timing, Exporting.
STAGE_PROGRESS = {"plan": 0.0, "translate": 0.3, "voice": 0.35, "timing": 0.55, "export": 0.6, "done": 1.0}
MAX_ATTEMPTS = 2

# Planner failure -> the sentence the user sees in the fallback notice
FRIENDLY_REASONS = {
    "OllamaNotRunning": "The local planner (Ollama) is not running.",
    "OllamaModelMissing": "The planner model is not installed.",
    "OllamaTimeout": "The planner took too long to answer.",
}


def friendly_reason(reason: str | None) -> str:
    """Turn plan_lesson's technical reason into a short sentence for the UI."""
    if not reason:
        return "The planner did not return a lesson."
    if reason.startswith("invalid plan"):
        return "The planner's lesson failed validation twice."
    return FRIENDLY_REASONS.get(reason.split(":", 1)[0], "The local planner returned an error.")


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
        tolerance = LAST_TRY_WORD_TOLERANCE if attempt == MAX_ATTEMPTS else WORD_BUDGET_TOLERANCE
        lesson, errors = parse_and_validate(raw, target_seconds, tolerance)
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
        return fallback_lesson(topic, level, "en", reason=friendly_reason(reason)), meta
    lesson["level"], lesson["language"] = level, "en"  # the plan is always English; level is the request's
    lesson["meta"] = {"fallback": False, "source": f"ollama:{client.model}", "topic": topic[:200]}
    return lesson, meta


def narrate(
    lesson: dict[str, Any],
    topic: str,
    level: str,
    out_dir: Path,
    on_stage: Callable[[str], None],
    speed: float = 1.0,
) -> dict[str, Any]:
    """Voice and time the lesson at the requested speed; never leaves the job without audio if a sample can stand in (G2).

    If TTS fails (model missing, out of memory, engine error) the closest built-in sample in the same language
    is voiced instead, at normal speed: that is the narration pre-generated in shared/tts_cache, so no engine
    has to load. Returns the lesson that was actually voiced. A sample that fails too is re-raised.
    """
    lang = lesson["language"]
    try:
        build_timeline(lesson, lang, out_dir, on_stage=on_stage, speed=speed)
        return lesson
    except Exception as exc:  # noqa: BLE001 - any TTS failure falls back to the cached sample
        if lesson.get("meta", {}).get("fallback") and speed == 1.0:
            raise  # already a sample at the cached speed: there is nothing more cached to fall back to
        log.exception("voice stage failed; using the closest sample's cached narration")
        sample = fallback_lesson(topic, level, lang, reason=f"Voice generation failed ({type(exc).__name__}).")
        build_timeline(sample, lang, out_dir, on_stage=on_stage)
        return sample


def run_pipeline(
    job_id: str,
    base_url: str | None = None,
    client: OllamaClient | None = None,
    export: bool = True,
) -> None:
    """Run all stages for a job. Never raises; failures are recorded on the job.

    base_url is where the app (frontend + /media) is served for capture; by default a private local
    server is started for the export.
    """
    job = JOBS.get(job_id)
    if job is None or job.request is None:
        return
    req = job.request
    out_dir = lesson_dir(job_id)

    def note_fallback(lesson: dict[str, Any]) -> None:
        meta = lesson.get("meta", {})
        if meta.get("fallback"):
            JOBS.update(job_id, fallback_used=True, fallback_reason=meta.get("reason"))

    JOBS.update(job_id, state="running")
    try:
        _status(job_id, "plan")
        with timed_stage(job_id, "plan"):
            lesson, plan_meta = plan_lesson(req.topic, req.level, req.target_seconds, job_id, client)
        note_fallback(lesson)
        write_json(out_dir / "plan_meta.json", plan_meta)
        write_json(out_dir / "lesson.en.json", lesson)  # the English plan; re-voicing reuses it (step 11)

        if req.language != "en":
            _status(job_id, "translate")
            with timed_stage(job_id, "translate"):
                # unloads the model before TTS (H3); on failure: pre-translated sample or English (G2)
                lesson = translate_lesson(lesson, req.language)
            note_fallback(lesson)
            write_json(out_dir / f"lesson.{req.language}.json", lesson)
        write_json(out_dir / "lesson.json", lesson)

        with timed_stage(job_id, "narrate"):
            # the lesson's own language: a failed translation stays English and is voiced in English
            voiced = narrate(lesson, req.topic, req.level, out_dir, lambda stage: _status(job_id, stage), req.speed)
        if voiced is not lesson:  # TTS failed: the closest sample was voiced from cached audio
            lesson = voiced
            note_fallback(lesson)
            write_json(out_dir / "lesson.json", lesson)
        JOBS.update(job_id, timeline_ready=True)  # the player can open the lesson now
    except Exception as exc:  # noqa: BLE001 - report on the job instead of crashing the worker
        log.exception("pipeline failed")
        JOBS.update(job_id, failed_stage=JOBS.get(job_id).stage)  # type: ignore[union-attr]
        _status(job_id, "done")
        JOBS.update(job_id, state="failed", error=str(exc))
        return

    if export:
        export_job(job_id, base_url)
    else:
        _status(job_id, "done")
        JOBS.update(job_id, state="done")


def run_job(job_id: str, request: ConceptRequest | None = None) -> None:
    """Entry point the API queues (the step-5 name). The request is already stored on the job."""
    run_pipeline(job_id)


def export_job(job_id: str, base_url: str | None = None) -> None:
    """Export the MP4 for a lesson whose timeline is ready (also used by Retry export). Never raises.

    The lesson already plays in the browser, so a failed MP4 is recorded as export_error, not a failed job.
    """
    JOBS.update(job_id, state="running", export_error=None, mp4_ready=False)
    _status(job_id, "export")
    try:
        ensure_frontend_built()
        if base_url:
            export_lesson(job_id, base_url)
        else:
            with local_server() as url:
                export_lesson(job_id, url)
        JOBS.update(job_id, mp4_ready=True)
    except Exception as exc:  # noqa: BLE001
        log.exception("export failed")
        JOBS.update(job_id, export_error=str(exc))
    _status(job_id, "done")
    JOBS.update(job_id, state="done")


def _status(job_id: str, stage: str) -> None:
    """Move the job to a stage and mirror its status to outputs/lessons/<id>/status.json."""
    JOBS.set_stage(job_id, stage, STAGE_PROGRESS[stage])
    write_json(lesson_dir(job_id) / "status.json", JOBS.get(job_id).public()["status"])  # type: ignore[union-attr]


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
