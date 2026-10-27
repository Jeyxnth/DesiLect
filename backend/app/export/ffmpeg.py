"""FFmpeg encoding (H.264 + AAC, 1280x720) and SRT writing."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

FPS = 30


def find_ffmpeg() -> str | None:
    """Path to ffmpeg on this machine, or None."""
    return shutil.which("ffmpeg")


def find_ffprobe() -> str | None:
    return shutil.which("ffprobe")


def write_ffconcat(frames: list[tuple[Path, float]], list_path: Path) -> Path:
    """Write an ffconcat list with exact per-frame durations.

    Per the concat demuxer rules the last file must be listed again (without a duration),
    otherwise its duration is ignored.
    """

    def entry(p: Path) -> str:
        return "file '" + p.resolve().as_posix().replace("'", "'\\''") + "'"

    lines = ["ffconcat version 1.0"]
    for path, duration in frames:
        lines += [entry(path), f"duration {duration:.4f}"]
    lines.append(entry(frames[-1][0]))
    list_path.parent.mkdir(parents=True, exist_ok=True)
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return list_path


def encode_keyframes(
    frames: list[tuple[Path, float]],
    wav: Path,
    srt: Path,
    out_mp4: Path,
    fps: int = FPS,
) -> Path:
    """Encode still frames (each held for its duration) plus lesson.wav into a 1280x720 H.264/AAC MP4.

    Used by both exports: keyframe (one PNG per change) and smooth (JPEGs at 15 fps while animating).

    Captions are already burned into the frames (the caption bar is part of the render page).
    captions.srt is also copied next to the MP4 as a separate download.
    """
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        raise RuntimeError("ffmpeg not found on PATH; run `python scripts/doctor.py`")
    if not frames:
        raise ValueError("no frames to encode")
    out_mp4 = Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    list_path = write_ffconcat(frames, out_mp4.parent / "frames.ffconcat")
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(list_path),
        "-i", str(wav),
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
        # JPEG frames are full-range (yuvj420p); convert to standard limited-range yuv420p for every player
        "-r", str(fps), "-vf", "scale=1280:720:out_range=tv,format=yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", "-shortest",
        str(out_mp4),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}): {proc.stderr.strip()[-800:]}")
    srt_copy = out_mp4.parent / "captions.srt"
    if Path(srt).resolve() != srt_copy.resolve():
        shutil.copyfile(srt, srt_copy)
    return out_mp4


def ffprobe_summary(path: Path) -> dict[str, Any]:
    """Resolution, codecs and duration of a media file via ffprobe."""
    ffprobe = find_ffprobe()
    if ffprobe is None:
        raise RuntimeError("ffprobe not found on PATH")
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {proc.stderr.strip()[-400:]}")
    info = json.loads(proc.stdout)
    streams = info.get("streams", [])
    video = next((s for s in streams if s["codec_type"] == "video"), {})
    audio = next((s for s in streams if s["codec_type"] == "audio"), {})
    return {
        "width": video.get("width"),
        "height": video.get("height"),
        "video_codec": video.get("codec_name"),
        "pix_fmt": video.get("pix_fmt"),
        "audio_codec": audio.get("codec_name"),
        "duration": float(info["format"]["duration"]),
        "size_bytes": int(info["format"]["size"]),
    }


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
