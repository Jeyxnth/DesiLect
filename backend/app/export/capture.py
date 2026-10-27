"""Playwright capture of the render page (CPU, headless) and the MP4 export driver: smooth (frames piped to ffmpeg)
with a keyframe fallback, each result checked with ffprobe."""
from __future__ import annotations

import bisect
import logging
import math
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator, Literal

from ..cache.store import lesson_dir, read_json, timed_stage, write_json
from ..config import REPO_ROOT, drill
from .ffmpeg import check_mp4, encode_keyframes, finish_pipe_encoder, open_pipe_encoder

log = logging.getLogger("blu.export")

CaptureMode = Literal["smooth", "keyframe"]  # keyframe is the G2 fallback
VIEWPORT = {"width": 1280, "height": 720}


def capture_times(keyframes: list[float], total: float, settle: float) -> list[float]:
    """Time at which to photograph each keyframe's interval.

    Scenes fade in after a keyframe, so the picture at the keyframe itself is half-drawn.
    Each interval is photographed once the animation has settled (keyframe + settle), but never
    at or after the next keyframe, so the frame still belongs to its own interval.
    """
    ends = keyframes[1:] + [total]
    return [round(max(k, min(k + settle, e - 0.01)), 3) for k, e in zip(keyframes, ends)]


SMOOTH_FPS = 15
SMOOTH_BUDGET_FACTOR = 3.0  # smooth capture may take at most this many times the lesson length, then keyframe mode
SMOOTH_MIN_BUDGET_S = 60.0  # ...but never less than this (short lessons, slow first page load)


class ExportBudgetExceeded(RuntimeError):
    """Smooth capture ran past its time budget (the keyframe export takes over)."""


class ExportCheckFailed(RuntimeError):
    """The encoded MP4 failed the ffprobe check (resolution, codecs, pixel format or duration)."""


def fresh_frames(keyframes: list[float], total: float, settle: float, fps: int = SMOOTH_FPS) -> list[bool]:
    """For each frame on the 1/fps grid: True = photograph the page, False = repeat the previous photo.

    While an animation runs (from a keyframe until it settles) every frame is a new photo; after that the
    picture cannot change until the next keyframe, so the last photo is repeated. Frame count = ceil(total * fps).
    """
    n = max(1, math.ceil(total * fps - 1e-9))
    plan: list[bool] = []
    last_shot_key = -2
    for i in range(n):
        t = i / fps
        k_idx = bisect.bisect_right(keyframes, t + 1e-9) - 1
        k = keyframes[k_idx] if k_idx >= 0 else 0.0
        fresh = i == 0 or t - k < settle + 1e-9 or k_idx != last_shot_key
        if fresh:
            last_shot_key = k_idx
        plan.append(fresh)
    return plan


def _launch(p):  # type: ignore[no-untyped-def]
    """Bundled Chromium if installed, else the system Chrome or Edge (no runtime download, H2)."""
    if drill("export-fail"):  # failure drill: no browser can be started, so both export modes fail
        raise RuntimeError("no Chromium/Chrome/Edge available for capture (BLU_DRILL=export-fail)")
    errors = []
    for kwargs in ({}, {"channel": "chrome"}, {"channel": "msedge"}):
        try:
            return p.chromium.launch(headless=True, **kwargs)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc).splitlines()[0])
    raise RuntimeError("no Chromium/Chrome/Edge available for capture: " + "; ".join(errors))


def capture_keyframes(
    lesson_id: str,
    out_dir: Path,
    base_url: str = "http://localhost:8000",
) -> list[tuple[Path, float]]:
    """Photograph the render page at every keyframe.

    Opens /render/<lesson_id> in a 1280x720 headless browser, waits for window.__ready, reads
    window.__keyframes(), and for each calls window.__seek(t) and saves frames/k_0001.png.
    Returns [(png, seconds the picture stays on screen)]; durations sum to total_seconds.
    """
    from playwright.sync_api import sync_playwright

    out_dir = Path(out_dir)
    frames_dir = out_dir / "frames"
    if frames_dir.is_dir():
        for old in frames_dir.glob("k_*.png"):
            old.unlink()
    frames_dir.mkdir(parents=True, exist_ok=True)
    total = float(read_json(out_dir / "timeline.json")["total_seconds"])

    with sync_playwright() as p:
        browser = _launch(p)
        try:
            page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
            page.goto(f"{base_url}/render/{lesson_id}", wait_until="load")
            page.wait_for_function("window.__ready === true", timeout=30_000)
            keyframes: list[float] = page.evaluate("window.__keyframes()")
            settle = float(page.evaluate("window.__settle ?? 0"))
            frames: list[tuple[Path, float]] = []
            for i, (k, t) in enumerate(zip(keyframes, capture_times(keyframes, total, settle)), start=1):
                page.evaluate("(t) => window.__seek(t)", t)
                png = frames_dir / f"k_{i:04d}.png"
                page.screenshot(path=str(png))
                nxt = keyframes[i] if i < len(keyframes) else total
                frames.append((png, round(nxt - k, 4)))
        finally:
            browser.close()
    return frames


def capture_smooth(
    lesson_id: str,
    out_dir: Path,
    base_url: str = "http://localhost:8000",
    fps: int = SMOOTH_FPS,
    budget_s: float | None = None,
    on_progress: Callable[[float], None] | None = None,
) -> tuple[Path, int]:
    """Smooth export: seek the render page every 1/fps s and pipe JPEG frames into ffmpeg (no frame files on disk).

    One page is reused; unchanged frames re-send the previous image (see fresh_frames). Raises ExportBudgetExceeded
    when capture runs past budget_s. on_progress gets the captured fraction (0..1). Returns (mp4, new photos taken).
    """
    from playwright.sync_api import sync_playwright

    out_dir = Path(out_dir)
    timeline = read_json(out_dir / "timeline.json")
    total = float(timeline["total_seconds"])
    wav, srt, mp4 = out_dir / "lesson.wav", out_dir / "captions.srt", out_dir / "lesson.mp4"
    started = time.perf_counter()
    shots = 0
    with sync_playwright() as p:
        browser = _launch(p)
        proc = open_pipe_encoder(wav, srt, mp4, timeline.get("language", "en"), fps, total)
        assert proc.stdin is not None
        # The budget is enforced by a watchdog too: a blocked frame write cannot reach the check in the loop.
        watchdog = threading.Timer(budget_s, proc.kill) if budget_s is not None else None
        if watchdog:
            watchdog.daemon = True
            watchdog.start()
        try:
            page = browser.new_page(viewport=VIEWPORT, device_scale_factor=1)
            page.goto(f"{base_url}/render/{lesson_id}", wait_until="load")
            page.wait_for_function("window.__ready === true", timeout=30_000)
            keyframes: list[float] = page.evaluate("window.__keyframes()")
            settle = float(page.evaluate("window.__settle ?? 0"))
            plan = fresh_frames(keyframes, total, settle, fps)
            image = b""
            for i, fresh in enumerate(plan):
                if fresh:
                    page.evaluate("(t) => window.__seek(t)", i / fps)
                    image = page.screenshot(type="jpeg", quality=90)
                    shots += 1
                try:
                    proc.stdin.write(image)
                except OSError as exc:  # ffmpeg exited: killed by the watchdog, or it failed
                    if watchdog and not watchdog.is_alive():
                        raise ExportBudgetExceeded(f"smooth capture passed its {budget_s:.0f}s budget at {i / len(plan):.0%}") from exc
                    raise
                if i % fps == 0:  # once per lesson second
                    if budget_s is not None and time.perf_counter() - started > budget_s:
                        raise ExportBudgetExceeded(f"smooth capture passed its {budget_s:.0f}s budget at {i / len(plan):.0%}")
                    if on_progress:
                        on_progress(i / len(plan))
        except BaseException:
            proc.kill()
            proc.wait()
            raise
        finally:
            if watchdog:
                watchdog.cancel()
            browser.close()
    finish_pipe_encoder(proc, srt, mp4)
    if on_progress:
        on_progress(1.0)
    return mp4, shots


FRONTEND = REPO_ROOT / "frontend"


def _newest(paths: list[Path]) -> float:
    latest = 0.0
    for base in paths:
        files = [base] if base.is_file() else [p for p in base.rglob("*") if p.is_file()] if base.is_dir() else []
        latest = max([latest, *(f.stat().st_mtime for f in files)])
    return latest


def ensure_frontend_built(force: bool = False) -> bool:
    """Run `npm run build` when frontend/dist is missing or older than the sources. Returns True if it built."""
    index = FRONTEND / "dist" / "index.html"
    sources = [FRONTEND / "src", FRONTEND / "public", FRONTEND / "index.html", FRONTEND / "package.json"]
    if not force and index.is_file() and index.stat().st_mtime >= _newest(sources):
        return False
    npm = shutil.which("npm")
    if npm is None:
        if index.is_file():
            return False  # stale but usable
        raise RuntimeError("frontend is not built and npm is not installed; run `python scripts/doctor.py`")
    if not (FRONTEND / "node_modules").is_dir():
        subprocess.run([npm, "install"], cwd=FRONTEND, check=True)
    subprocess.run([npm, "run", "build"], cwd=FRONTEND, check=True, capture_output=True)
    return True


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@contextmanager
def local_server(timeout: float = 30.0) -> Iterator[str]:
    """Serve the app (API, /media and the built frontend) on a free localhost port; yields its URL."""
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port),
         "--log-level", "warning"],
        cwd=REPO_ROOT / "backend",
    )
    url = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + timeout
        while True:
            try:
                with urllib.request.urlopen(f"{url}/api/ping", timeout=2):
                    break
            except (urllib.error.URLError, OSError):
                if proc.poll() is not None or time.time() > deadline:
                    raise RuntimeError("local server did not start") from None
                time.sleep(0.2)
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def smooth_budget(total_seconds: float) -> float:
    return max(SMOOTH_MIN_BUDGET_S, SMOOTH_BUDGET_FACTOR * total_seconds)


def export_lesson(
    lesson_id: str,
    base_url: str,
    mode: CaptureMode = "smooth",
    on_progress: Callable[[float], None] | None = None,
) -> Path:
    """Capture the render page and encode outputs/lessons/<id>/lesson.mp4, then check it with ffprobe.

    mode="smooth" pipes 15 fps frames to ffmpeg within a time budget (3x the lesson length); if it fails, runs over
    budget or its MP4 fails the check, the keyframe export (one frame per change) runs instead (G2). Writes
    export.json with the mode actually used. Raises ExportCheckFailed when the final MP4 is not 1280x720
    h264/yuv420p + aac with the timeline's duration (the bad file is renamed lesson.rejected.mp4).
    Needs timeline.json, lesson.wav and captions.srt in the lesson dir, and the app served at base_url.
    """
    out_dir = lesson_dir(lesson_id, create=False)
    timeline = read_json(out_dir / "timeline.json")
    total = float(timeline["total_seconds"])
    wav, srt, mp4 = out_dir / "lesson.wav", out_dir / "captions.srt", out_dir / "lesson.mp4"
    smooth_failed: str | None = None
    if mode == "smooth":
        budget = smooth_budget(total)
        try:
            with timed_stage(lesson_id, "export_smooth"):
                _, shots = capture_smooth(lesson_id, out_dir, base_url, SMOOTH_FPS, budget, on_progress)
            problems = check_mp4(mp4, total)
            if problems:
                raise ExportCheckFailed("; ".join(problems))
            write_json(out_dir / "export.json", {"mode": "smooth", "fps": SMOOTH_FPS, "photos": shots, "budget_s": round(budget, 1)})
            return mp4
        except Exception as exc:  # noqa: BLE001 - the keyframe export is the fallback
            smooth_failed = f"{type(exc).__name__}: {exc}"[:300]
            log.warning("smooth export failed (%s); falling back to keyframe export", smooth_failed)
    with timed_stage(lesson_id, "export_capture"):
        frames = capture_keyframes(lesson_id, out_dir, base_url)
    with timed_stage(lesson_id, "export_encode"):
        encode_keyframes(frames, wav, srt, mp4, lang=timeline.get("language", "en"))
    problems = check_mp4(mp4, total)
    if problems:
        mp4.replace(out_dir / "lesson.rejected.mp4")
        log.error("MP4 check failed for %s: %s", lesson_id, "; ".join(problems))
        raise ExportCheckFailed("MP4 check failed: " + "; ".join(problems))
    write_json(out_dir / "export.json", {"mode": "keyframe", "frames": len(frames), "smooth_failed": smooth_failed})
    if on_progress:
        on_progress(1.0)
    return mp4
