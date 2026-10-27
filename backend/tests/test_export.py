import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.cache.store import read_json
from app.config import REPO_ROOT
from app.export.capture import capture_times, fresh_frames
from app.export.ffmpeg import ffprobe_summary, write_ffconcat


def test_capture_times_settle_inside_own_interval():
    # fade needs 1.2 s but the second interval is only 0.15 s long: capture just before the next keyframe
    assert capture_times([0.0, 0.875, 1.025, 5.0], 10.0, 1.2) == [0.865, 1.015, 2.225, 5.0 + 1.2]
    # last interval ends at total
    assert capture_times([8.0], 8.5, 1.2) == [8.49]
    assert capture_times([0.0], 3.0, 0.0) == [0.0]


def test_fresh_frames_photograph_animations_and_repeat_still_stretches():
    plan = fresh_frames([0.0, 2.0], total=4.0, settle=0.5, fps=10)
    assert len(plan) == 40  # one frame per 1/10 s
    fresh = [i for i, f in enumerate(plan) if f]
    # 0.0-0.5 animating (new photo every frame), still until 2.0 (repeated), 2.0-2.5 animating, then repeated
    assert fresh == [0, 1, 2, 3, 4, 5, 20, 21, 22, 23, 24, 25]


def test_fresh_frames_catch_a_keyframe_between_grid_points():
    plan = fresh_frames([0.0, 1.03], total=2.0, settle=0.0, fps=10)
    assert [i for i, f in enumerate(plan) if f] == [0, 11]  # 1.03 changes the picture: frame 11 (1.1 s) shows it


@pytest.fixture
def lesson(tmp_path, monkeypatch):
    """A lesson folder with a timeline, export stubs that record what ran, and no real browser or ffmpeg."""
    from contextlib import nullcontext

    from app.export import capture

    out = tmp_path / "lessons" / "x1"
    out.mkdir(parents=True)
    (out / "timeline.json").write_text('{"total_seconds": 10.0, "language": "ta"}', encoding="utf-8")
    monkeypatch.setattr(capture, "lesson_dir", lambda lid, create=True: out)
    monkeypatch.setattr(capture, "timed_stage", lambda *a: nullcontext())
    monkeypatch.setattr(capture, "check_mp4", lambda path, total: [])
    monkeypatch.setattr(capture, "capture_keyframes", lambda *a, **k: [(out / "k.png", 1.0)])
    ran = []
    monkeypatch.setattr(capture, "encode_keyframes", lambda frames, *a, **k: ran.append(("keyframe", k.get("lang"))))
    return capture, out, ran


def test_smooth_export_is_the_default_and_records_its_mode(lesson, monkeypatch):
    capture, out, ran = lesson
    budgets = []

    def smooth(lesson_id, out_dir, base_url, fps, budget, on_progress):
        budgets.append(budget)
        return out_dir / "lesson.mp4", 42

    monkeypatch.setattr(capture, "capture_smooth", smooth)
    capture.export_lesson("x1", "http://x")
    assert ran == [] and budgets == [60.0]  # 3x a 10 s lesson is below the 60 s minimum budget
    assert read_json(out / "export.json") == {"mode": "smooth", "fps": 15, "photos": 42, "budget_s": 60.0}
    assert capture.smooth_budget(100.0) == 300.0


@pytest.mark.parametrize("failure", ["crash", "budget", "check"])
def test_smooth_export_falls_back_to_keyframes(lesson, monkeypatch, failure):
    capture, out, ran = lesson

    def smooth(*a, **k):
        if failure == "crash":
            raise RuntimeError("chromium crashed")
        if failure == "budget":
            raise capture.ExportBudgetExceeded("smooth capture passed its 60s budget at 40%")
        return out / "lesson.mp4", 10

    checks = iter([["duration 3.00s, timeline says 10.00s"], []])  # smooth MP4 bad, keyframe MP4 good
    monkeypatch.setattr(capture, "capture_smooth", smooth)
    if failure == "check":
        monkeypatch.setattr(capture, "check_mp4", lambda path, total: next(checks))
    capture.export_lesson("x1", "http://x")
    assert ran == [("keyframe", "ta")]  # soft subtitle track tagged with the lesson language
    info = read_json(out / "export.json")
    expected = {"crash": "chromium crashed", "budget": "budget", "check": "duration 3.00s"}[failure]
    assert info["mode"] == "keyframe" and expected in info["smooth_failed"]


def test_export_fails_loudly_when_the_final_mp4_is_wrong(lesson, monkeypatch):
    capture, out, ran = lesson
    (out / "lesson.mp4").write_bytes(b"not really a video")
    monkeypatch.setattr(capture, "check_mp4", lambda path, total: ["resolution 640x360, expected 1280x720"])
    with pytest.raises(capture.ExportCheckFailed, match="640x360"):
        capture.export_lesson("x1", "http://x", mode="keyframe")
    assert not (out / "lesson.mp4").exists() and (out / "lesson.rejected.mp4").is_file()  # nothing to download


def test_check_mp4_lists_every_problem(monkeypatch):
    from app.export import ffmpeg

    good = {"width": 1280, "height": 720, "video_codec": "h264", "pix_fmt": "yuv420p", "audio_codec": "aac", "duration": 50.1}
    monkeypatch.setattr(ffmpeg, "ffprobe_summary", lambda p: good)
    assert ffmpeg.check_mp4(Path("x.mp4"), 50.0) == []
    bad = dict(good, width=1920, height=1080, pix_fmt="yuvj420p", audio_codec="mp3", duration=48.0)
    monkeypatch.setattr(ffmpeg, "ffprobe_summary", lambda p: bad)
    problems = ffmpeg.check_mp4(Path("x.mp4"), 50.0)
    assert len(problems) == 4 and any("1920x1080" in p for p in problems) and any("48.00s" in p for p in problems)


def test_srt_is_utf8_without_bom(tmp_path):
    from app.export.ffmpeg import write_srt

    out = write_srt({"scenes": [{"cues": [{"start": 0.0, "end": 1.0, "text": "வணக்கம்!"}]}]}, tmp_path / "c.srt")
    raw = out.read_bytes()
    assert not raw.startswith(bytes([0xEF, 0xBB, 0xBF])) and "வணக்கம்".encode("utf-8") in raw


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
    assert info["subtitle_codec"] == "mov_text" and info["subtitle_language"] == "eng"  # soft caption track
    assert read_json(out / "export.json")["mode"] == "smooth"
