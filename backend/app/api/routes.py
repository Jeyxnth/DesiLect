"""HTTP API under /api."""
from __future__ import annotations

import platform
import shutil
from importlib import metadata
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException

from .. import __version__
from ..cache.store import lesson_dir, read_json
from ..config import LANGUAGES, SAMPLES_DIR, get_settings
from ..export.ffmpeg import find_ffmpeg
from ..pipeline.jobs import JOBS, ConceptRequest
from ..pipeline.orchestrator import run_pipeline
from ..planner.ollama_client import OllamaClient

router = APIRouter(prefix="/api")

# Directory (under models/) that must exist and be non-empty for a model to count as present.
MODEL_DIRS = {
    "kokoro": "kokoro",
    "indictrans2": "indictrans2-en-indic-dist-200M",
    "indic_parler_tts": "indic-parler-tts",
}


def _version(pkg: str) -> str | None:
    try:
        return metadata.version(pkg)
    except metadata.PackageNotFoundError:
        return None


def _model_present(dirname: str) -> bool:
    path = get_settings().models_dir / dirname
    return path.is_dir() and any(path.iterdir())


@router.get("/health")
def health() -> dict[str, Any]:
    """Versions and which models are on disk."""
    ollama = OllamaClient()
    return {
        "status": "ok",
        "versions": {
            "app": __version__,
            "python": platform.python_version(),
            "fastapi": _version("fastapi"),
            "pydantic": _version("pydantic"),
        },
        "models": {name: _model_present(d) for name, d in MODEL_DIRS.items()},
        "ollama": {"model": ollama.model, "running": ollama.is_available()},
        "ffmpeg": find_ffmpeg() is not None,
        "playwright": shutil.which("playwright") is not None,
    }


@router.get("/samples")
def list_samples() -> list[str]:
    """Names of bundled sample lessons, e.g. python_loop.en."""
    return sorted(p.name.removesuffix(".json") for p in SAMPLES_DIR.glob("*.json"))


@router.get("/samples/{name}")
def get_sample(name: str) -> dict[str, Any]:
    """A bundled sample lesson (G2 fallback source)."""
    if name not in list_samples():
        raise HTTPException(404, "unknown sample")
    return read_json(SAMPLES_DIR / f"{name}.json")


@router.post("/lessons", status_code=202)
def create_lesson(req: ConceptRequest, background: BackgroundTasks) -> dict[str, Any]:
    """Start the pipeline for a concept. Poll /api/jobs/{id}."""
    if req.language not in LANGUAGES:
        raise HTTPException(422, "unsupported language")
    job = JOBS.create(req)
    background.add_task(run_pipeline, job.id)
    return job.public()


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(404, "unknown job")
    return job.public()


def _lesson_file(lesson_id: str, name: str) -> Any:
    try:
        path = lesson_dir(lesson_id, create=False) / name
    except ValueError:
        raise HTTPException(404, "unknown lesson") from None
    if not path.is_file():
        raise HTTPException(404, f"{name} not available yet")
    return read_json(path)


@router.get("/lessons/{lesson_id}")
def get_lesson(lesson_id: str) -> Any:
    return _lesson_file(lesson_id, "lesson.json")


@router.get("/lessons/{lesson_id}/timeline")
def get_timeline(lesson_id: str) -> Any:
    return _lesson_file(lesson_id, "timeline.json")


@router.get("/lessons/{lesson_id}/timings")
def get_timings(lesson_id: str) -> Any:
    return _lesson_file(lesson_id, "timings.json")
