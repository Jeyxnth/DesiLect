"""Playwright capture of the render page into PNG frames (CPU, headless)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

CaptureMode = Literal["smooth", "keyframe"]  # keyframe is the G2 fallback


def capture_frames(
    lesson_id: str,
    timeline: dict[str, Any],
    out_dir: Path,
    fps: int = 30,
    mode: CaptureMode = "smooth",
    base_url: str = "http://localhost:8000",
) -> list[Path]:
    """Open /render?lesson=<id>, set time t per frame via window.__setTime(t), screenshot 1280x720.

    TODO(step 4): keyframe mode; TODO(step 10): smooth mode.
    """
    raise NotImplementedError("TODO(step 4): Playwright frame capture")
