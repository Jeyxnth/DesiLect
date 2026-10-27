"""HTTP API under /api."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import platform
from importlib import metadata
from pathlib import Path
from typing import Any, AsyncIterator, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from fastapi.responses import FileResponse, StreamingResponse

from .. import __version__
from ..cache.store import find_cached_lesson, lesson_dir, read_json
from ..config import LANGUAGES, SAMPLES_DIR, get_settings
from ..export.ffmpeg import find_ffmpeg
from ..export.summary import is_stale, render_summary_pdf, summary_pdf_path
from ..pipeline.jobs import JOBS, QUEUE, ConceptRequest, Job
from ..pipeline.orchestrator import export_job, request_cache_key, run_job, run_pipeline
from ..planner.ollama_client import OllamaClient, OllamaError

router = APIRouter(prefix="/api")

SSE_INTERVAL_S = 0.5

# Directory (under models/) that must exist and be non-empty for a model to count as present.
MODEL_DIRS = {
    "kokoro": "kokoro",
    "indictrans2": "indictrans2",
    "indic_parler_tts": "indic-parler-tts",
    "indic_tts_ta": "indic-tts-ta",
}


def _version(pkg: str) -> str | None:
    try:
        return metadata.version(pkg)
    except metadata.PackageNotFoundError:
        return None


def _model_present(dirname: str) -> bool:
    path = get_settings().models_dir / dirname
    return path.is_dir() and any(path.iterdir())


@router.get("/ping")
def ping() -> dict[str, bool]:
    """Instant readiness probe (does not touch Ollama or the disk)."""
    return {"ok": True}


@router.get("/health")
def health() -> dict[str, Any]:
    """Versions and which models are on disk. Probes Ollama once, briefly."""
    ollama = OllamaClient()
    try:
        pulled = ollama.list_models(timeout=0.5)
    except OllamaError:
        pulled = None
    wanted = ollama.model if ":" in ollama.model else f"{ollama.model}:latest"
    return {
        "status": "ok",
        "versions": {
            "app": __version__,
            "python": platform.python_version(),
            "fastapi": _version("fastapi"),
            "pydantic": _version("pydantic"),
        },
        "models": {name: _model_present(d) for name, d in MODEL_DIRS.items()},
        "ollama": {"model": ollama.model, "running": pulled is not None, "model_present": pulled is not None and wanted in pulled},
        "ffmpeg": find_ffmpeg() is not None,
        # importable, not on PATH: the venv's Scripts folder is usually not on PATH (clean-clone check, step 13)
        "playwright": importlib.util.find_spec("playwright") is not None,
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


def _start(req: ConceptRequest, plan_from: str | None = None) -> dict[str, Any]:
    """A finished lesson for exactly this request (reuse cache), else a new queued job."""
    cached = find_cached_lesson(request_cache_key(req))
    if cached is not None:
        return {**_status(cached), "cached": True}
    job = JOBS.create(req)
    QUEUE.submit(job.id, lambda: run_pipeline(job.id, plan_from=plan_from) if plan_from else run_job(job.id, req))
    return {**job.public(QUEUE.ahead(job.id)), "cached": False}


@router.post("/lessons", status_code=202)
def create_lesson(req: ConceptRequest) -> dict[str, Any]:
    """Queue the pipeline for a concept (one job runs at a time). Follow it with /lessons/{id}/events.

    A repeat of a request whose lesson finished (same topic, level, language, length, voice and speed) returns
    that lesson at once with "cached": true.
    """
    if req.language not in LANGUAGES:
        raise HTTPException(422, "unsupported language")
    return _start(req)


def _dir(lesson_id: str) -> Path:
    try:
        return lesson_dir(lesson_id, create=False)
    except ValueError:
        raise HTTPException(404, "unknown lesson") from None


def _status(lesson_id: str) -> dict[str, Any]:
    """The job's status, or one reconstructed from disk for a lesson this server did not make."""
    job = JOBS.get(lesson_id)
    if job is not None:
        return job.public(QUEUE.ahead(lesson_id))
    out = _dir(lesson_id)
    if not (out / "timeline.json").is_file():
        raise HTTPException(404, "unknown lesson")
    meta = read_json(out / "lesson.json").get("meta", {}) if (out / "lesson.json").is_file() else {}
    timings = read_json(out / "timings.json") if (out / "timings.json").is_file() else {}
    export = read_json(out / "export.json") if (out / "export.json").is_file() else {}
    mp4_ready = (out / "lesson.mp4").is_file()
    try:  # the typed topic names the downloads
        request = ConceptRequest(**read_json(out / "request.json")) if (out / "request.json").is_file() else None
    except ValueError:
        request = None
    # No MP4 on disk: say why, so the player offers Retry export instead of a button that never enables
    export_error = None if mp4_ready else export.get("error") or "The MP4 export did not finish (the app was restarted)"
    return Job(
        id=lesson_id,
        request=request,
        state="done",
        stage="done",
        progress=1.0,
        fallback_used=bool(meta.get("fallback")),
        fallback_reason=meta.get("reason"),
        timeline_ready=True,
        mp4_ready=mp4_ready,
        export_mode=export.get("mode") if mp4_ready else None,
        export_error=export_error,
        timings={k: round(v, 1) for k, v in timings.items() if isinstance(v, (int, float)) and not isinstance(v, bool)},
    ).public()


def _finished(status: dict[str, Any]) -> bool:
    return status["state"] in ("done", "failed")


@router.get("/lessons/{lesson_id}")
def get_lesson_status(lesson_id: str) -> dict[str, Any]:
    """Job status: stage, progress, fallback_used, timings, timeline_ready, mp4_ready."""
    return _status(lesson_id)


@router.get("/lessons/{lesson_id}/events")
async def lesson_events(lesson_id: str) -> StreamingResponse:
    """Server-Sent Events: the status whenever it changes, until the job is done or failed."""
    _status(lesson_id)  # 404 before the stream starts

    async def stream() -> AsyncIterator[str]:
        last = ""
        while True:
            status = _status(lesson_id)
            data = json.dumps(status)
            if data != last:
                yield f"data: {data}\n\n"
                last = data
            if _finished(status):
                return
            await asyncio.sleep(SSE_INTERVAL_S)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.post("/lessons/{lesson_id}/export", status_code=202)
def retry_export(lesson_id: str) -> dict[str, Any]:
    """Queue the MP4 export again for a lesson whose timeline exists (Retry export)."""
    if not (_dir(lesson_id) / "timeline.json").is_file():
        raise HTTPException(404, "this lesson has no timeline yet")
    if QUEUE.busy(lesson_id):
        raise HTTPException(409, "this lesson is already queued or running")
    JOBS.adopt(lesson_id, state="done", stage="done", progress=1.0, timeline_ready=True)
    JOBS.update(lesson_id, state="queued", export_error=None, mp4_ready=False)
    QUEUE.submit(lesson_id, lambda: export_job(lesson_id))
    return _status(lesson_id)


def _lesson_file(lesson_id: str, name: str) -> Any:
    path = _dir(lesson_id) / name
    if not path.is_file():
        raise HTTPException(404, f"{name} not available yet")
    return read_json(path)


@router.get("/lessons/{lesson_id}/lesson")
def get_lesson(lesson_id: str) -> Any:
    """The lesson plan (lesson.json), including meta.fallback/source/reason."""
    return _lesson_file(lesson_id, "lesson.json")


@router.get("/lessons/{lesson_id}/timeline")
def get_timeline(lesson_id: str) -> Any:
    return _lesson_file(lesson_id, "timeline.json")


@router.get("/lessons/{lesson_id}/timings")
def get_timings(lesson_id: str) -> Any:
    return _lesson_file(lesson_id, "timings.json")


@router.get("/lessons/{lesson_id}/summary.pdf")
def get_summary_pdf(lesson_id: str, request: Request) -> FileResponse:
    """One-page A4 summary of the lesson (bonus B3), printed by the capture browser from /summary/<id>.
    Cached as summary.<lang>.pdf and made again only when lesson.json is newer. No model is called."""
    out = _dir(lesson_id)
    lesson_json = out / "lesson.json"
    if not lesson_json.is_file():
        raise HTTPException(404, "lesson.json not available yet")
    language = read_json(lesson_json).get("language", "en")
    pdf = summary_pdf_path(out, language)
    if is_stale(pdf, lesson_json, get_settings().frontend_dist / "index.html"):  # a new app build re-makes old PDFs
        try:
            render_summary_pdf(lesson_id, str(request.base_url), pdf)
        except Exception as exc:  # noqa: BLE001 - the page and browser print still work
            raise HTTPException(503, f"summary PDF could not be made ({exc}); use Print / Save as PDF on the summary page") from exc
    return FileResponse(pdf, media_type="application/pdf", filename=f"{lesson_id}_{language}_summary.pdf")


class RevoiceRequest(BaseModel):
    language: Literal["en", "hi", "ta"]


def _source_request(lesson_id: str) -> ConceptRequest:
    """The request a lesson was made from: in memory, else request.json, else rebuilt from its English plan."""
    job = JOBS.get(lesson_id)
    if job is not None and job.request is not None:
        return job.request
    out = _dir(lesson_id)
    if (out / "request.json").is_file():
        return ConceptRequest(**read_json(out / "request.json"))
    plan = read_json(out / "lesson.en.json")
    topic = plan.get("meta", {}).get("topic") or plan.get("title") or "lesson"
    return ConceptRequest(topic=topic[:120], level=plan.get("level", "beginner"))


@router.post("/lessons/{lesson_id}/revoice", status_code=202)
def revoice_lesson(lesson_id: str, body: RevoiceRequest) -> dict[str, Any]:
    """The same lesson in another language: reuses the stored English plan (no re-planning), then translates,
    voices, times and exports it as a new lesson. Returns that lesson's status (instantly if it is cached).
    """
    if not (_dir(lesson_id) / "lesson.en.json").is_file():
        raise HTTPException(409, "this lesson has no stored English plan to re-voice (bundled samples cannot be re-voiced)")
    req = _source_request(lesson_id).model_copy(update={"language": body.language})
    return _start(req, plan_from=lesson_id)
