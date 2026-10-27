"""In-memory job tracking for pipeline runs."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

from ..cache.store import new_lesson_id
from ..config import MAX_TARGET_SECONDS, MIN_TARGET_SECONDS

JobState = Literal["queued", "running", "done", "failed"]


class ConceptRequest(BaseModel):
    """Stage 1: concept input."""

    topic: str = Field(min_length=3, max_length=200)
    level: Literal["beginner", "intermediate"] = "beginner"
    language: Literal["en", "hi", "ta"] = "en"
    target_seconds: int = Field(default=45, ge=MIN_TARGET_SECONDS, le=MAX_TARGET_SECONDS)


@dataclass
class Job:
    """One pipeline run. The job id doubles as the lesson id."""

    id: str
    request: ConceptRequest
    state: JobState = "queued"
    stage: str = "queued"
    progress: float = 0.0  # 0..1
    fallback_used: bool = False
    error: str | None = None
    created_at: float = field(default_factory=time.time)

    def public(self) -> dict:
        return {
            "id": self.id,
            "lesson_id": self.id,
            "state": self.state,
            "stage": self.stage,
            "status": {"stage": self.stage, "progress": round(self.progress, 3), "fallback_used": self.fallback_used},
            "error": self.error,
            "request": self.request.model_dump(),
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

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **changes: object) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in changes.items():
                setattr(job, key, value)


JOBS = JobStore()
