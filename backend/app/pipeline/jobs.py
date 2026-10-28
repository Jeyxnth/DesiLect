"""In-memory job tracking for pipeline runs, and the single worker that runs them."""
from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field

from ..cache.store import new_lesson_id
from ..config import MAX_SPEED, MAX_TARGET_SECONDS, MIN_SPEED, MIN_TARGET_SECONDS

log = logging.getLogger("blu.jobs")

JobState = Literal["queued", "running", "done", "failed"]
IDLE_STAGES = ("queued", "done")  # stages that are not timed


class ConceptRequest(BaseModel):
    """Stage 1: concept input."""

    topic: str = Field(min_length=3, max_length=120)
    level: Literal["beginner", "intermediate"] = "beginner"
    language: Literal["en", "hi", "ta"] = "en"
    target_seconds: int = Field(default=45, ge=MIN_TARGET_SECONDS, le=MAX_TARGET_SECONDS)
    speed: float = Field(default=1.0, ge=MIN_SPEED, le=MAX_SPEED)  # narration speed; the UI offers 0.9 / 1.0 / 1.1
    voice: Literal["female", "male"] = "female"  # mapped per language to a concrete voice (tts/registry.py voice_for)


@dataclass
class Job:
    """One pipeline run. The job id doubles as the lesson id."""

    id: str
    request: ConceptRequest | None  # None for a lesson adopted from disk (e.g. to retry its export)
    state: JobState = "queued"
    stage: str = "queued"  # queued | plan | translate | voice | timing | export | done
    progress: float = 0.0  # 0..1
    fallback_used: bool = False
    fallback_reason: str | None = None  # shown in the UI notice
    timeline_ready: bool = False  # narration done: the lesson can play
    mp4_ready: bool = False
    error: str | None = None
    failed_stage: str | None = None  # the stage that raised, when state is "failed"
    export_error: str | None = None  # MP4 failed; the lesson still plays
    export_progress: float | None = None  # 0..1 while the MP4 is captured (smooth mode), None before export starts
    export_mode: str | None = None  # "smooth" or "keyframe": how the MP4 was actually made
    stop_export: bool = False  # set by Generate again on the lesson it replaces: its export stops at the next frame
    timings: dict[str, float] = field(default_factory=dict)  # finished stages, seconds
    stage_started: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)

    def public(self, ahead: int | None = None) -> dict[str, Any]:
        timings = dict(self.timings)
        if self.state == "running" and self.stage not in IDLE_STAGES:  # the running stage, live
            timings[self.stage] = round(time.time() - self.stage_started, 1)
        return {
            "id": self.id,
            "job_id": self.id,
            "lesson_id": self.id,
            "state": self.state,
            "stage": self.stage,
            "status": {
                "stage": self.stage,
                "progress": round(self.progress, 3),
                "fallback_used": self.fallback_used,
                "fallback_reason": self.fallback_reason,
                "timeline_ready": self.timeline_ready,
                "mp4_ready": self.mp4_ready,
                "timings": timings,
                "failed_stage": self.failed_stage,
                "export_progress": None if self.export_progress is None else round(self.export_progress, 3),
                "export_mode": self.export_mode,
                "queue_ahead": ahead,  # jobs before this one in the queue (0 = next), None when not queued
            },
            "error": self.error,
            "export_error": self.export_error,
            "request": self.request.model_dump() if self.request else None,
        }


class JobStore:
    """Thread-safe job registry."""

    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, request: ConceptRequest) -> Job:
        job = Job(id=new_lesson_id(), request=request)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def adopt(self, lesson_id: str, **fields: Any) -> Job:
        """Register a lesson that exists on disk but not in memory (server restarted, or a sample)."""
        with self._lock:
            job = self._jobs.get(lesson_id)
            if job is None:
                job = self._jobs[lesson_id] = Job(id=lesson_id, request=None, **fields)
            return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **changes: object) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in changes.items():
                setattr(job, key, value)

    def set_stage(self, job_id: str, stage: str, progress: float) -> None:
        """Move to a new stage, recording how long the previous one took."""
        now = time.time()
        with self._lock:
            job = self._jobs[job_id]
            if job.stage not in IDLE_STAGES:
                job.timings[job.stage] = round(now - job.stage_started, 1)
            job.stage, job.progress, job.stage_started = stage, progress, now


class WorkQueue:
    """Runs jobs one at a time on a background thread, in order (H3: one model in memory at a time)."""

    def __init__(self) -> None:
        self._queue: queue.Queue[tuple[str, Callable[[], None]]] = queue.Queue()
        self._pending: list[str] = []  # running job first, then the waiting ones
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def submit(self, job_id: str, fn: Callable[[], None]) -> None:
        with self._lock:
            self._pending.append(job_id)
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._work, name="blu-jobs", daemon=True)
                self._thread.start()
        self._queue.put((job_id, fn))

    def ahead(self, job_id: str) -> int | None:
        """How many jobs run before this one (0 = running or next), or None if it is not queued."""
        with self._lock:
            return self._pending.index(job_id) if job_id in self._pending else None

    def busy(self, job_id: str) -> bool:
        return self.ahead(job_id) is not None

    def _work(self) -> None:
        while True:
            job_id, fn = self._queue.get()
            try:
                fn()
            except Exception:  # noqa: BLE001 - one bad job must not stop the worker
                log.exception("job %s crashed", job_id)
            finally:
                with self._lock:
                    self._pending.remove(job_id)


JOBS = JobStore()
QUEUE = WorkQueue()
