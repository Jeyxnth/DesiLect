import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.cache.store import read_json
from app.config import REPO_ROOT
from app.export.capture import capture_times
from app.export.ffmpeg import ffprobe_summary, write_ffconcat


def test_capture_times_settle_inside_own_interval():
    # fade needs 1.2 s but the second interval is only 0.15 s long: capture just before the next keyframe
    assert capture_times([0.0, 0.875, 1.025, 5.0], 10.0, 1.2) == [0.865, 1.015, 2.225, 5.0 + 1.2]
    # last interval ends at total
    assert capture_times([8.0], 8.5, 1.2) == [8.49]
    assert capture_times([0.0], 3.0, 0.0) == [0.0]


def test_ffconcat_has_exact_durations_and_repeats_last_file(tmp_path):
    frames = [(tmp_path / "a.png", 0.875), (tmp_path / "it's.png", 2.5)]
    text = write_ffconcat(frames, tmp_path / "list.ffconcat").read_text(encoding="utf-8").splitlines()
    assert text[0] == "ffconcat version 1.0"
    assert text[2] == "duration 0.8750" and text[4] == "duration 2.5000"
    assert text[3].endswith("it'\\''s.png'")  # quote escaped for the concat demuxer
    assert text[-1] == text[3] and len(text) == 6  # last file listed again without a duration


def _missing_prereq():
    k = REPO_ROOT / "models" / "kokoro"
    if not (k / "kokoro-v1.0.onnx").is_file() or not (k / "voices-v1.0.bin").is_file():
        return "Kokoro models not downloaded"
    for tool in ("ffmpeg", "ffprobe", "npm"):
        if shutil.which(tool) is None:
            return f"{tool} not installed"
    try:
        import playwright  # noqa: F401
    except ImportError:
        return "playwright not installed"
    return None


@pytest.mark.skipif(_missing_prereq() is not None, reason=str(_missing_prereq()))
def test_export_smoke_full_sample_under_60s():
    """Gate 1: timing + capture + encode of the sample lesson, end to end, in under a minute."""
    start = time.perf_counter()
    proc = subprocess.run([sys.executable, str(REPO_ROOT / "scripts" / "render_sample.py")],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
    elapsed = time.perf_counter() - start
    assert proc.returncode == 0, proc.stdout[-1500:] + proc.stderr[-1500:]
    assert elapsed < 60, f"export took {elapsed:.0f}s"

    out = REPO_ROOT / "outputs" / "lessons" / "sample-en"
    info = ffprobe_summary(out / "lesson.mp4")
    total = read_json(out / "timeline.json")["total_seconds"]
    assert (info["width"], info["height"]) == (1280, 720)
    assert info["video_codec"] == "h264" and info["audio_codec"] == "aac" and info["pix_fmt"] == "yuv420p"
    assert abs(info["duration"] - total) <= 0.2
    assert (out / "captions.srt").is_file()
