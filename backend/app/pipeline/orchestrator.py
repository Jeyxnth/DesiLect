"""Runs plan -> timeline (TTS) -> export, timing each stage (G6) and falling back on failure (G2)."""
from __future__ import annotations

import argparse
import logging
import time
from pathlib import Path
from typing import Any, Callable

from ..cache.store import (lesson_cache_key, lesson_dir, read_json, record_timing, record_value, remember_lesson, timed_stage,
                           write_json)
from ..config import drill, get_settings
from ..export.capture import ensure_frontend_built, export_lesson, local_server
from ..planner.fallback import add_static_next_topics, closest_sample, fallback_lesson
from ..planner.ollama_client import OllamaClient, OllamaError, lesson_format_schema
from ..planner.prompts import build_retry_prompt, build_system_prompt, build_user_prompt
from ..planner.validate import (
    LAST_TRY_WORD_TOLERANCE, WORD_BUDGET_TOLERANCE, WORDS_PER_SECOND, clean_quiz, narration_words, parse_and_validate, parse_next_topics,
    parse_quiz, shuffle_quiz,
)
from ..timing.timeline import build_timeline
from ..translate.indictrans import translate_lesson
from ..tts.registry import bundled_engine, voice_for
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
    quiz_questions = get_settings().quiz_questions  # asked in the same call as the lesson (bonus B1)
    system = build_system_prompt(level, target_seconds, quiz_questions)
    user = build_user_prompt(topic, level, target_seconds)
    schema = lesson_format_schema(quiz_questions)
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
    accepted_raw = ""
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
        last = attempt == MAX_ATTEMPTS  # the last try is lenient: cut over-long labels and keep a short plan rather than fall back
        tolerance = LAST_TRY_WORD_TOLERANCE if last else WORD_BUDGET_TOLERANCE
        lesson, errors = parse_and_validate(raw, target_seconds, tolerance, cut_labels=last, accept_short=last)
        log_raw(attempt, seconds, raw + ("\n--- rejected: " + "; ".join(errors) if errors else "\n--- accepted"))
        if lesson is not None:
            accepted_raw = raw
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
    if quiz_questions > 0:
        attach_quiz(lesson, accepted_raw, quiz_questions, lesson_id or topic, meta, raw_path)
    attach_next_topics(lesson, accepted_raw, topic, meta, raw_path)
    lesson["meta"] = {"fallback": False, "source": f"ollama:{client.model}", "topic": topic[:200]}
    # Shorter than asked (accepted on the last try): said honestly in the player, and kept out of the reuse cache
    words, target_words = narration_words(lesson), round(target_seconds * WORDS_PER_SECOND)
    if words < round(target_words * (1 - WORD_BUDGET_TOLERANCE)):
        lesson["meta"]["short_of"] = {"target_seconds": target_seconds, "words": words, "target_words": target_words}
        meta["short_of"] = lesson["meta"]["short_of"]
    return lesson, meta


def attach_next_topics(lesson: dict[str, Any], raw: str, topic: str, meta: dict[str, Any], raw_path: Path | None) -> None:
    """The reply's two follow-up topics (bonus B2). Invalid or missing: the static map of the matching built-in
    sample (shared/next_topics.json), else none. Never a reason to retry or fall back."""
    topics, warnings = parse_next_topics(raw)
    if topics:
        lesson["next_topics"] = topics
    else:
        sample, matches = closest_sample(topic)
        if matches:
            add_static_next_topics(lesson, sample.name)
    meta["next_topics_dropped"] = topics is None
    if raw_path and warnings:
        with raw_path.open("a", encoding="utf-8") as f:
            f.write("".join(f"--- warning: {w}\n" for w in warnings) + "\n")
    for w in warnings:
        log.warning("planner next topics: %s", w)


def attach_quiz(lesson: dict[str, Any], raw: str, quiz_questions: int, seed: str, meta: dict[str, Any],
                raw_path: Path | None) -> None:
    """Add the reply's quiz to an accepted lesson, options shuffled. A bad quiz is dropped with warnings in
    planner_raw.txt and quiz_dropped in timings.json: never a reason to retry or fall back (bonus B1)."""
    if drill("quiz-garbage"):  # failure drill: the model wrote a broken quiz
        quiz, warnings = clean_quiz("garbage", quiz_questions)
    else:
        quiz, warnings = parse_quiz(raw, quiz_questions)
    if quiz:
        lesson["quiz"] = shuffle_quiz(quiz, seed)
    meta.update(quiz_questions=len(quiz or []), quiz_dropped=quiz is None, quiz_warnings=warnings)
    if raw_path:
        with raw_path.open("a", encoding="utf-8") as f:
            f.write(f"=== quiz: kept {len(quiz or [])} question(s)" + "".join(f"\n--- warning: {w}" for w in warnings) + "\n\n")
        record_value(raw_path.parent.name, "quiz_dropped", quiz is None)
    for w in warnings:
        log.warning("planner quiz: %s", w)


def narrate(
    lesson: dict[str, Any],
    topic: str,
    level: str,
    out_dir: Path,
    on_stage: Callable[[str], None],
    speed: float = 1.0,
    voice: str = "female",
) -> dict[str, Any]:
    """Voice and time the lesson at the requested speed; never leaves the job without audio if a sample can stand in (G2).

    If TTS fails (model missing, out of memory, engine error) the closest built-in sample in the same language
    is voiced instead, at normal speed: that is the narration pre-generated in shared/tts_cache, so no engine
    has to load. Returns the lesson that was actually voiced. A sample that fails too is re-raised.
    voice is "female" or "male"; each language's engine maps it to a concrete voice (tts/registry.py voice_for).
    """
    lang = lesson["language"]
    try:
        build_timeline(lesson, lang, out_dir, on_stage=on_stage, speed=speed, voice=voice_for(lang, voice))
        return lesson
    except Exception as exc:  # noqa: BLE001 - any TTS failure falls back to the cached sample
        if lesson.get("meta", {}).get("fallback") and speed == 1.0 and voice == "female":
            raise  # already a sample in the cached voice and speed: there is nothing more cached to fall back to
        log.exception("voice stage failed; using the closest sample's cached narration")
        sample = fallback_lesson(topic, level, lang, reason=f"Voice generation failed ({type(exc).__name__}).")
        # the engine its audio was bundled with, even if TAMIL_TTS picks another one (that one may be what failed)
        build_timeline(sample, lang, out_dir, on_stage=on_stage, engine=bundled_engine(lang))
        return sample


def run_pipeline(
    job_id: str,
    base_url: str | None = None,
    client: OllamaClient | None = None,
    export: bool = True,
    plan_from: str | None = None,
) -> None:
    """Run all stages for a job. Never raises; failures are recorded on the job.

    base_url is where the app (frontend + /media) is served for capture; by default a private local
    server is started for the export. plan_from (a lesson id) re-voices that lesson: its stored English plan
    is reused instead of planning again. A finished lesson that needed no fallback and is not shorter than asked goes
    into the reuse cache, so Generate again on either one plans afresh.
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
    write_json(out_dir / "request.json", req.model_dump())  # re-voicing reads it back
    try:
        _status(job_id, "plan")
        with timed_stage(job_id, "plan"):
            if plan_from:
                lesson = read_json(lesson_dir(plan_from, create=False) / "lesson.en.json")
                plan_meta = {"reused_plan_from": plan_from}
            else:
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
            voiced = narrate(lesson, req.topic, req.level, out_dir, lambda stage: _status(job_id, stage), req.speed, req.voice)
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
    done = JOBS.get(job_id)
    if done is not None and done.mp4_ready and not done.fallback_used and not lesson.get("meta", {}).get("short_of"):
        remember_lesson(request_cache_key(req), job_id)


def request_cache_key(req: ConceptRequest) -> str:
    return lesson_cache_key(req.topic, req.level, req.language, req.target_seconds, req.voice, req.speed)


def run_job(job_id: str, request: ConceptRequest | None = None) -> None:
    """Entry point the API queues (the step-5 name). The request is already stored on the job."""
    run_pipeline(job_id)


def export_job(job_id: str, base_url: str | None = None) -> None:
    """Export the MP4 for a lesson whose timeline is ready (also used by Retry export). Never raises.

    The lesson already plays in the browser, so a failed MP4 is recorded as export_error, not a failed job.
    """
    JOBS.update(job_id, state="running", export_error=None, mp4_ready=False, export_progress=0.0, export_mode=None)
    _status(job_id, "export")
    start = STAGE_PROGRESS["export"]

    def on_progress(fraction: float) -> None:
        JOBS.update(job_id, export_progress=fraction, progress=start + (1.0 - start) * fraction)

    try:
        ensure_frontend_built()
        if base_url:
            export_lesson(job_id, base_url, on_progress=on_progress)
        else:
            with local_server() as url:
                export_lesson(job_id, url, on_progress=on_progress)
        info_path = lesson_dir(job_id) / "export.json"
        mode = read_json(info_path).get("mode") if info_path.is_file() else None
        JOBS.update(job_id, mp4_ready=True, export_progress=1.0, export_mode=mode)
    except Exception as exc:  # noqa: BLE001
        log.exception("export failed")
        JOBS.update(job_id, export_error=str(exc))
        write_json(lesson_dir(job_id) / "export.json", {"mode": None, "error": str(exc)[:500]})  # survives a restart
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
