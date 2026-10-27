"""FFmpeg encoding (H.264 + AAC, 1280x720) and SRT writing."""
from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
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


# ISO 639-2 codes for the soft subtitle track's language tag
SUBTITLE_LANG = {"en": "eng", "hi": "hin", "ta": "tam"}
DURATION_TOLERANCE_S = 0.2


def _output_args(srt_input: int, lang: str, out_mp4: Path, duration: float, fps: int = FPS) -> list[str]:
    """Shared encoder settings: 1280x720 H.264 yuv420p at fps, AAC 128k, captions.srt as a soft mov_text track.

    Captions are also burned into the picture; the soft track lets a player switch them on/off or restyle them.
    Length is set with -t (the lesson length), not -shortest: the subtitle stream ends at the last caption, and
    -shortest with a subtitle input makes ffmpeg stop reading piped frames without exiting (a hang).
    """
    return [
        "-map", "0:v:0", "-map", "1:a:0", "-map", f"{srt_input}:s:0",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
        # JPEG frames are full-range (yuvj420p); convert to standard limited-range yuv420p for every player
        "-r", str(fps), "-vf", "scale=1280:720:out_range=tv,format=yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-c:s", "mov_text", "-metadata:s:s:0", f"language={SUBTITLE_LANG.get(lang, 'und')}",
        "-movflags", "+faststart", "-t", f"{duration:.3f}",
        str(out_mp4),
    ]


def _copy_srt_next_to(srt: Path, out_mp4: Path) -> None:
    srt_copy = out_mp4.parent / "captions.srt"
    if Path(srt).resolve() != srt_copy.resolve():
        shutil.copyfile(srt, srt_copy)


def open_pipe_encoder(wav: Path, srt: Path, out_mp4: Path, lang: str, fps_in: int, duration: float) -> subprocess.Popen[bytes]:
    """Start ffmpeg reading JPEG/PNG frames from stdin (image2pipe) at fps_in, muxed with lesson.wav and captions.srt.

    Write one image per 1/fps_in seconds to proc.stdin, close it, then finish_pipe_encoder(). Output is resampled to
    30 fps and cut to `duration`. ffmpeg's messages go to a temp file, not a pipe, so it can never block on them.
    """
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        raise RuntimeError("ffmpeg not found on PATH; run `python scripts/doctor.py`")
    out_mp4 = Path(out_mp4)
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "image2pipe", "-framerate", str(fps_in), "-i", "-",
        "-i", str(wav), "-i", str(srt),
        *_output_args(2, lang, out_mp4, duration),
    ]
    log_file = tempfile.TemporaryFile()
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log_file)
    proc.log_file = log_file  # type: ignore[attr-defined]
    return proc


def finish_pipe_encoder(proc: subprocess.Popen[bytes], srt: Path, out_mp4: Path) -> Path:
    """Close ffmpeg's input, wait for it and raise with its messages if it failed."""
    assert proc.stdin is not None
    proc.stdin.close()
    rc = proc.wait()
    log_file = proc.log_file  # type: ignore[attr-defined]
    log_file.seek(0)
    err = log_file.read().decode("utf-8", errors="replace")
    log_file.close()
    if rc != 0:
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}): {err.strip()[-800:]}")
    _copy_srt_next_to(srt, out_mp4)
    return out_mp4


def check_mp4(path: Path, expected_seconds: float) -> list[str]:
    """Problems with an exported MP4 (empty list = good): 1280x720, h264, yuv420p, aac, duration within 0.2 s."""
    try:
        info = ffprobe_summary(path)
    except (RuntimeError, OSError, KeyError, ValueError) as exc:
        return [f"ffprobe could not read the MP4: {exc}"]
    problems = []
    if (info["width"], info["height"]) != (1280, 720):
        problems.append(f"resolution {info['width']}x{info['height']}, expected 1280x720")
    if info["video_codec"] != "h264":
        problems.append(f"video codec {info['video_codec']}, expected h264")
    if info["pix_fmt"] != "yuv420p":
        problems.append(f"pixel format {info['pix_fmt']}, expected yuv420p")
    if info["audio_codec"] != "aac":
        problems.append(f"audio codec {info['audio_codec']}, expected aac")
    if abs(info["duration"] - expected_seconds) > DURATION_TOLERANCE_S:
        problems.append(f"duration {info['duration']:.2f}s, timeline says {expected_seconds:.2f}s")
    return problems


def encode_keyframes(
    frames: list[tuple[Path, float]],
    wav: Path,
    srt: Path,
    out_mp4: Path,
    fps: int = FPS,
    lang: str = "en",
) -> Path:
    """Encode still frames (each held for its duration) plus lesson.wav into a 1280x720 H.264/AAC MP4.

    Used by both exports: keyframe (one PNG per change) and smooth (JPEGs at 15 fps while animating).

    Captions are burned into the frames (the caption bar is part of the render page) and also added as a soft
    mov_text track; captions.srt is copied next to the MP4 as a separate download.
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
        "-i", str(wav), "-i", str(srt),
        *_output_args(2, lang, out_mp4, sum(d for _, d in frames), fps),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}): {proc.stderr.strip()[-800:]}")
    _copy_srt_next_to(srt, out_mp4)
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
    subs = next((s for s in streams if s["codec_type"] == "subtitle"), {})
    return {
        "subtitle_codec": subs.get("codec_name"),
        "subtitle_language": subs.get("tags", {}).get("language"),
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
    """Write the .srt from timeline cues (text is in the lesson's own script; UTF-8 without a BOM)."""
    lines: list[str] = []
    n = 0
    for scene in timeline["scenes"]:
        for cue in scene["cues"]:
            n += 1
            lines += [str(n), f"{_srt_time(cue['start'])} --> {_srt_time(cue['end'])}", cue["text"], ""]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
