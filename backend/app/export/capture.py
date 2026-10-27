"""Playwright capture of the render page into PNG frames (CPU, headless) and the MP4 export driver."""
from __future__ import annotations

import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Literal

from ..cache.store import lesson_dir, read_json, timed_stage
from ..config import REPO_ROOT
from .ffmpeg import encode_keyframes

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


def _launch(p):  # type: ignore[no-untyped-def]
    """Bundled Chromium if installed, else the system Chrome or Edge (no runtime download, H2)."""
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


def capture_frames(lesson_id: str, out_dir: Path, fps: int = 15, base_url: str = "http://localhost:8000") -> list[Path]:
    """Dense frame sequence for smooth export. TODO(step 10)."""
    raise NotImplementedError("TODO(step 10): smooth 15 fps capture")


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


def export_lesson(lesson_id: str, base_url: str, mode: CaptureMode = "keyframe") -> Path:
    """Capture the render page and encode outputs/lessons/<id>/lesson.mp4 (keyframe mode).

    Needs timeline.json, lesson.wav and captions.srt in the lesson dir, and the app served at base_url.
    Step 6 calls this from the API; step 10 adds mode="smooth".
    """
    if mode != "keyframe":
        raise NotImplementedError("TODO(step 10): smooth export")
    out_dir = lesson_dir(lesson_id, create=False)
    with timed_stage(lesson_id, "export_capture"):
        frames = capture_keyframes(lesson_id, out_dir, base_url)
    with timed_stage(lesson_id, "export_encode"):
        return encode_keyframes(frames, out_dir / "lesson.wav", out_dir / "captions.srt", out_dir / "lesson.mp4")
