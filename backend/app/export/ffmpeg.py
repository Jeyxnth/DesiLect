"""FFmpeg encoding (H.264 + AAC, 1280x720) and SRT writing."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def find_ffmpeg() -> str | None:
    """Path to ffmpeg on this machine, or None."""
    return shutil.which("ffmpeg")


def encode_mp4(frames_dir: Path, audio_path: Path, out_path: Path, fps: int = 30) -> Path:
    """Encode frames + narration into a 1280x720 H.264/AAC MP4.

    Captions are already burned into the frames by the render page.
    TODO(step 4): build the ffmpeg command (yuv420p, +faststart).
    """
    raise NotImplementedError("TODO(step 4): ffmpeg encode")


def _srt_time(seconds: float) -> str:
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(timeline: dict[str, Any], out_path: Path) -> Path:
    """Write the .srt from timeline cues (text is in the lesson's own script)."""
    lines: list[str] = []
    n = 0
    for scene in timeline["scenes"]:
        for cue in scene["cues"]:
            n += 1
            lines += [str(n), f"{_srt_time(cue['start'])} --> {_srt_time(cue['end'])}", cue["text"], ""]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
