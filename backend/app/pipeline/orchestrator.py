"""Runs the five stages in order, timing each one (G6) and falling back on failure (G2)."""
from __future__ import annotations

import logging
from typing import Any

from ..cache.store import lesson_dir, timed_stage, write_json
from ..planner.fallback import fallback_lesson
from ..planner.validate import validate_lesson
from .jobs import JOBS, ConceptRequest

log = logging.getLogger("blu.pipeline")


def plan_lesson(req: ConceptRequest) -> dict[str, Any]:
    """Stage 2. TODO(step 5): Ollama + validate + one retry, then fall back."""
    return fallback_lesson(req.topic, req.level, req.language)


def run_pipeline(job_id: str) -> None:
    """Run all stages for a job. Never raises; failures are recorded on the job.

    TODO(step 8): translate, TODO(step 2/9): narrate + timeline, TODO(step 4): export.
    """
    job = JOBS.get(job_id)
    if job is None:
        return
    JOBS.update(job_id, state="running")
    try:
        JOBS.update(job_id, stage="plan")
        with timed_stage(job_id, "plan"):
            lesson = plan_lesson(job.request)
            errors = validate_lesson(lesson)
            if errors:  # planner output is never trusted (H4)
                log.warning("planner output invalid (%s); using fallback", errors[:3])
                lesson = fallback_lesson(job.request.topic, job.request.level, job.request.language)
            write_json(lesson_dir(job_id) / "lesson.json", lesson)
        JOBS.update(job_id, state="done", stage="planned")
    except Exception as exc:  # noqa: BLE001 - report on the job instead of crashing the worker
        log.exception("pipeline failed")
        JOBS.update(job_id, state="failed", error=str(exc))
