import json
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from app.config import SAMPLES_DIR
from app.export.ffmpeg import write_srt
from app.planner.validate import validate_timeline
from app.timing import timeline as tl
from app.timing.sentences import split_sentences
from app.tts.base import SAMPLE_RATE


class FakeEngine:
    """Deterministic stand-in for Kokoro: duration depends only on text length."""

    name = "fake"
    languages = ("en", "hi")
    calls = 0

    def load(self): ...
    def unload(self): ...

    def synth(self, text, lang, voice, speed=1.0):
        FakeEngine.calls += 1
        n = int(SAMPLE_RATE * (0.2 + 0.03 * len(text)) / speed)
        t = np.arange(n) / SAMPLE_RATE
        return (0.1 * np.sin(2 * np.pi * 220 * t)).astype(np.float32), SAMPLE_RATE


@pytest.fixture
def env(tmp_path, monkeypatch):
    settings = SimpleNamespace(outputs_dir=tmp_path / "outputs")
    monkeypatch.setattr("app.cache.store.get_settings", lambda: settings)
    monkeypatch.setattr(tl, "get_settings", lambda: settings)
    monkeypatch.setattr(tl, "get_engine", lambda lang, engine=None: (FakeEngine(), "v"))
    FakeEngine.calls = 0
    return settings


def sample(lang="en"):
    return json.loads((SAMPLES_DIR / f"python_loop.{lang}.json").read_text(encoding="utf-8"))


# --- sentences -------------------------------------------------------------

def test_split_keeps_code_like_tokens():
    s = split_sentences("The range(3) call gives 0, 1 and 2. Pi is 3.5 here! Does os.path work? Yes.")
    assert s == ["The range(3) call gives 0, 1 and 2.", "Pi is 3.5 here!", "Does os.path work?", "Yes."]


def test_split_devanagari_danda():
    assert split_sentences("यह एक वाक्य है। range(3) दूसरा है। तीसरा?") == [
        "यह एक वाक्य है।", "range(3) दूसरा है।", "तीसरा?"]


def test_split_sentence_end_after_code():
    assert split_sentences("Call range(3). Then print(i).") == ["Call range(3).", "Then print(i)."]


@pytest.mark.parametrize("lang", ["en", "hi", "ta"])
def test_sample_sentence_counts(lang):
    assert all(2 <= len(split_sentences(s["narration"])) <= 3 for s in sample(lang)["scenes"])


# --- SRT -------------------------------------------------------------------

def test_srt_format(tmp_path):
    timeline = {"scenes": [{"cues": [
        {"start": 0.0, "end": 1.5, "text": "Hello"},
        {"start": 3661.0075, "end": 3662.0, "text": "नमस्ते"}]}]}
    out = write_srt(timeline, tmp_path / "c.srt")
    assert out.read_text(encoding="utf-8") == (
        "1\n00:00:00,000 --> 00:00:01,500\nHello\n\n"
        "2\n01:01:01,008 --> 01:01:02,000\nनमस्ते\n")


# --- timeline --------------------------------------------------------------

def test_timeline_invariants(env, tmp_path):
    out = tmp_path / "lessons" / "t1"
    timeline = tl.build_timeline(sample(), "en", out)
    assert validate_timeline(timeline) == []
    assert validate_timeline(json.loads((out / "timeline.json").read_text(encoding="utf-8"))) == []

    prev_end = 0.0
    for scene in timeline["scenes"]:
        cues = scene["cues"]
        assert scene["start"] == pytest.approx(prev_end, abs=1e-3)  # scenes are contiguous
        assert cues[0]["start"] == pytest.approx(scene["start"], abs=1e-3)
        for a, b in zip(cues, cues[1:]):  # monotonic, 0.15 s gaps
            assert a["start"] < a["end"] <= b["start"]
            assert b["start"] - a["end"] == pytest.approx(tl.SENTENCE_GAP_S, abs=1e-3)
        assert scene["end"] == pytest.approx(cues[-1]["end"] + tl.SCENE_PAUSE_S, abs=1e-3)
        prev_end = scene["end"]
    assert timeline["total_seconds"] == pytest.approx(prev_end, abs=1e-3)


def test_total_matches_wav(env, tmp_path):
    out = tmp_path / "lessons" / "t2"
    timeline = tl.build_timeline(sample(), "en", out)
    wav, sr = sf.read(out / "lesson.wav")
    assert sr == SAMPLE_RATE and wav.ndim == 1
    assert abs(timeline["total_seconds"] - len(wav) / sr) < 0.05
    assert (out / "audio" / "s0_0.wav").is_file()
    assert (out / "captions.srt").is_file()
    assert timeline["audio_url"].endswith("/lessons/t2/lesson.wav") or timeline["audio_url"] == "lesson.wav"


def test_cue_audio_is_placed_at_cue_start(env, tmp_path):
    out = tmp_path / "lessons" / "t3"
    timeline = tl.build_timeline(sample(), "en", out)
    wav, sr = sf.read(out / "lesson.wav")
    cue = timeline["scenes"][1]["cues"][1]
    mid = int((cue["start"] + cue["end"]) / 2 * sr)
    assert np.abs(wav[mid - 200 : mid + 200]).max() > 0.01
    gap_mid = int((cue["end"] + tl.SENTENCE_GAP_S / 2) * sr)
    assert np.abs(wav[gap_mid - 100 : gap_mid + 100]).max() < 1e-3


def test_beats(env, tmp_path):
    timeline = tl.build_timeline(sample(), "en", tmp_path / "lessons" / "t4")
    title, code, diagram, recap = timeline["scenes"]
    assert title["beats"] == [] and recap["beats"] == []
    assert [(b["action"], b["value"], b["t"]) for b in code["beats"]] == [
        ("highlight", 1, code["cues"][0]["start"]), ("highlight", 2, code["cues"][1]["start"])]
    assert [(b["action"], b["value"], b["t"]) for b in diagram["beats"]] == [
        ("reveal", k, diagram["cues"][k]["start"]) for k in range(3)]


def test_extra_diagram_items_spread_over_scene():
    scene = {"type": "diagram", "items": list("abcde")}
    cues = [{"start": 0.0, "end": 1.0, "text": "x"}, {"start": 1.2, "end": 2.0, "text": "y"}]
    beats = tl._beats(scene, cues, end=4.2)
    assert [b["value"] for b in beats] == [0, 1, 2, 3, 4]
    assert [b["t"] for b in beats[:2]] == [0.0, 1.2]
    assert [b["t"] for b in beats[2:]] == pytest.approx([1.95, 2.7, 3.45])  # evenly spaced after the last cue
    assert all(1.2 < b["t"] < 4.2 for b in beats[2:])


def test_cache_makes_second_run_instant(env, tmp_path):
    tl.build_timeline(sample(), "en", tmp_path / "lessons" / "a")
    first_calls = FakeEngine.calls
    assert first_calls > 0
    t2 = tl.build_timeline(sample(), "en", tmp_path / "lessons" / "b")
    assert FakeEngine.calls == first_calls  # no synthesis at all
    stats = json.loads((tmp_path / "lessons" / "b" / "timings.json").read_text(encoding="utf-8"))["timeline"]
    assert stats["cache_misses"] == 0 and stats["cache_hits"] == first_calls
    assert t2["total_seconds"] > 0


def test_no_cache_flag_resynthesises(env, tmp_path):
    tl.build_timeline(sample(), "en", tmp_path / "lessons" / "a")
    n = FakeEngine.calls
    tl.build_timeline(sample(), "en", tmp_path / "lessons" / "b", use_cache=False)
    assert FakeEngine.calls == 2 * n


def test_tamil_engine_object_is_light(monkeypatch):
    from app.tts import registry
    monkeypatch.setattr(registry, "get_settings", lambda: SimpleNamespace(tamil_tts="indic-tts"))
    engine, voice = registry.get_engine("ta")
    assert (engine.name, voice) == ("indic-tts", "female")  # object only; the model loads on the first cache miss
    registry.release_all()
