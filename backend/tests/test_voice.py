"""Step 9: spoken text, audio clean-up, engine registry and caption/voice sync in en, hi and ta."""
import json
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from app.cache import store
from app.config import SAMPLES_DIR
from app.timing import timeline as tl
from app.timing.sentences import split_sentences
from app.tts import audio, registry
from app.tts.base import SAMPLE_RATE
from app.tts.parler_engine import ParlerEngine, pace_phrase
from app.tts.prep import prepare_tts_text

SAMPLE_NAMES = ["python_loop", "binary_search", "photosynthesis", "pythagorean_theorem"]
LANGS = ["en", "hi", "ta"]


def tone(seconds, amp=0.3, sr=SAMPLE_RATE):
    t = np.arange(round(seconds * sr)) / sr
    return (amp * np.sin(2 * np.pi * 220 * t)).astype(np.float32)


# --- audio clean-up ----------------------------------------------------------

def test_normalise_peak_is_minus_one_dbfs():
    out = audio.normalise_peak(tone(0.5, amp=0.2))
    assert np.abs(out).max() == pytest.approx(10 ** (-1 / 20), rel=1e-3)
    assert np.abs(audio.normalise_peak(tone(0.5, amp=1.4))).max() == pytest.approx(10 ** (-1 / 20), rel=1e-3)


def test_normalise_leaves_silence_alone():
    assert not audio.normalise_peak(np.zeros(100, dtype=np.float32)).any()


def test_trim_silence_keeps_speech_and_pad():
    sr = SAMPLE_RATE
    x = np.concatenate([np.zeros(sr), tone(0.5), np.zeros(sr // 2)])
    out = audio.trim_silence(x, sr)
    expected = round((0.5 + 2 * audio.KEEP_PAD_S) * sr)
    assert abs(len(out) - expected) <= 2 * round(audio.FRAME_S * sr)
    assert np.abs(out).max() == pytest.approx(0.3, rel=1e-3)  # nothing of the tone was cut


def test_trim_silence_does_not_empty_silent_input():
    x = np.zeros(1000, dtype=np.float32)
    assert len(audio.trim_silence(x)) == 1000


def test_finalize_sentence_fades_edges():
    out = audio.finalize_sentence(np.concatenate([np.zeros(5000), tone(0.4), np.zeros(5000)]))
    assert out[0] == 0.0 and out[-1] == 0.0
    assert np.abs(out).max() <= 10 ** (-1 / 20) + 1e-6


def test_resample_fft_keeps_pitch_and_length():
    sr_in = 44_100
    t = np.arange(sr_in) / sr_in  # 1 s of 1 kHz
    out = audio.resample_fft(np.sin(2 * np.pi * 1000 * t).astype(np.float32), sr_in, SAMPLE_RATE)
    assert len(out) == SAMPLE_RATE
    spectrum = np.abs(np.fft.rfft(out))
    assert np.argmax(spectrum) * SAMPLE_RATE / len(out) == pytest.approx(1000, abs=2)
    assert np.abs(out).max() == pytest.approx(1.0, abs=0.02)


# --- spoken text ---------------------------------------------------------------

def test_transliteration_is_for_tts_only():
    text = "Python में loop कैसे काम करता है।"
    spoken = prepare_tts_text(text, "hi")
    assert spoken == "पाइथन में लूप कैसे काम करता है।"
    assert text.startswith("Python")  # the caption is the untouched original


def test_transliteration_longest_term_wins_and_handles_calls():
    assert prepare_tts_text("यह for loop है", "hi") == "यह फॉर लूप है"
    assert prepare_tts_text("range(3) हमें 0 देता है", "hi") == "रेंज 3 हमें 0 देता है"
    assert prepare_tts_text("variable i", "hi") == "वेरिएबल आई"
    assert prepare_tts_text("Loop", "hi") == "लूप"  # case-insensitive
    assert prepare_tts_text("loopback", "hi") == "loopback"  # whole words only


def test_tamil_transliteration_and_english_untouched():
    assert prepare_tts_text("இது loop ஆகும்", "ta") == "இது லூப் ஆகும்"
    assert prepare_tts_text("A loop repeats `print(i)`.", "en") == "A loop repeats print i ."


def test_transliteration_switch(monkeypatch):
    monkeypatch.setattr("app.tts.prep.get_settings", lambda: SimpleNamespace(tts_translit=False))
    assert prepare_tts_text("Python loop", "hi") == "Python loop"


def test_every_sample_term_has_a_spoken_form():
    """No Latin word is left in the spoken hi/ta narration of any bundled sample."""
    import re

    for lang in ("hi", "ta"):
        for name in SAMPLE_NAMES:
            lesson = json.loads((SAMPLES_DIR / f"{name}.{lang}.json").read_text(encoding="utf-8"))
            for scene in lesson["scenes"]:
                left = re.findall(r"[A-Za-z]+", prepare_tts_text(scene["narration"], lang))
                assert left == [], f"{name}.{lang}: {left}"


# --- engines ---------------------------------------------------------------------

def test_registry_engines_and_one_loaded_at_a_time():
    assert registry.LANG_ENGINES == {"en": ("kokoro", "hf_alpha"), "hi": ("kokoro", "hf_alpha"), "ta": ("parler", "jaya")}
    kokoro, _ = registry.get_engine("hi")
    parler, _ = registry.get_engine("ta")
    assert (kokoro.name, parler.name) == ("kokoro", "parler")
    assert list(registry._active) == ["parler"]  # the Kokoro engine was unloaded and dropped
    registry.release_all()
    assert registry._active == {}


def test_list_voices():
    assert [v["id"] for v in registry.list_voices("hi")] == ["hf_alpha", "hm_omega"]
    assert [v["id"] for v in registry.list_voices("ta")] == ["jaya"]
    assert registry.list_voices("ta")[0]["engine"] == "parler"
    with pytest.raises(ValueError):
        registry.list_voices("xx")


def test_plan_b_name_is_refused_until_built(monkeypatch):
    monkeypatch.setattr(registry, "get_settings", lambda: SimpleNamespace(tamil_tts="indic-tts"))
    with pytest.raises(NotImplementedError, match="Plan B"):
        registry.get_engine("ta")


def test_parler_description_is_fixed_per_voice_and_speed():
    engine = ParlerEngine()
    assert engine.description("jaya") == engine.description("jaya", 1.0)
    assert "Jaya" in engine.description("unknown-voice")  # falls back to the default voice
    assert engine.description("jaya", 0.8) != engine.description("jaya", 1.0)
    assert pace_phrase(1.0) == "at a moderate pace"


def test_parler_reports_missing_model(tmp_path, monkeypatch):
    monkeypatch.setattr("app.tts.parler_engine.get_settings", lambda: SimpleNamespace(models_dir=tmp_path))
    with pytest.raises(FileNotFoundError, match="download_models"):
        ParlerEngine().synth("வணக்கம்", "ta", "jaya")


# --- sync: cue starts = sentence starts, scene end = audio end + pause -------------

class VoiceFake:
    """Engine whose sentence length depends on the spoken text, with silence around the 'speech'."""

    name = "fake"
    languages = ("en", "hi", "ta")
    spoken: list[str] = []

    def load(self): ...
    def unload(self): ...

    def synth(self, text, lang, voice, speed=1.0):
        VoiceFake.spoken.append(text)
        speech = tone(0.3 + 0.02 * len(text))
        pad = np.zeros(round(0.4 * SAMPLE_RATE), dtype=np.float32)  # leading/trailing silence to trim
        return np.concatenate([pad, speech, pad]), SAMPLE_RATE


@pytest.fixture
def env(tmp_path, monkeypatch):
    settings = SimpleNamespace(outputs_dir=tmp_path / "outputs")
    monkeypatch.setattr("app.cache.store.get_settings", lambda: settings)
    monkeypatch.setattr(tl, "get_settings", lambda: settings)
    monkeypatch.setattr(store, "BUNDLED_TTS_DIR", tmp_path / "no-bundle")
    monkeypatch.setattr(tl, "get_engine", lambda lang: (VoiceFake(), "v"))
    VoiceFake.spoken = []
    return settings


def sample(name, lang):
    return json.loads((SAMPLES_DIR / f"{name}.{lang}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", SAMPLE_NAMES)
@pytest.mark.parametrize("lang", LANGS)
def test_cues_and_scene_ends_match_the_audio(env, tmp_path, name, lang):
    out = tmp_path / "lessons" / f"{name}-{lang}"
    lesson = sample(name, lang)
    timeline = tl.build_timeline(lesson, lang, out)
    wav, sr = sf.read(out / "lesson.wav", dtype="float32")
    cursor = 0.0
    for i, (scene, planned) in enumerate(zip(timeline["scenes"], lesson["scenes"])):
        sentences = split_sentences(planned["narration"], lang)
        assert [c["text"] for c in scene["cues"]] == sentences  # captions are the original sentences
        assert scene["start"] == pytest.approx(cursor, abs=1e-3)
        for k, cue in enumerate(scene["cues"]):
            clip, _ = sf.read(out / "audio" / f"s{i}_{k}.wav", dtype="float32")
            assert cue["start"] == pytest.approx(cursor, abs=1e-3)  # cue start = sentence start
            assert cue["end"] - cue["start"] == pytest.approx(len(clip) / sr, abs=1e-3)
            a = round(cue["start"] * sr)
            assert np.allclose(wav[a : a + len(clip)], clip, atol=1e-4)  # the sentence really sits there
            cursor = cue["end"] + (tl.SENTENCE_GAP_S if k < len(scene["cues"]) - 1 else 0.0)
        cursor = scene["cues"][-1]["end"] + tl.SCENE_PAUSE_S
        assert scene["end"] == pytest.approx(cursor, abs=1e-3)  # audio end + pause
    assert timeline["total_seconds"] == pytest.approx(len(wav) / sr, abs=2e-3)


def test_voice_gets_spoken_text_but_captions_keep_the_original(env, tmp_path):
    timeline = tl.build_timeline(sample("python_loop", "hi"), "hi", tmp_path / "lessons" / "h")
    captions = " ".join(c["text"] for s in timeline["scenes"] for c in s["cues"])
    assert "Python" in captions and "loop" in captions.lower()
    assert any("लूप" in s for s in VoiceFake.spoken)
    assert not any("loop" in s.lower() for s in VoiceFake.spoken)


def test_sentences_are_trimmed_and_normalised_before_timing(env, tmp_path):
    out = tmp_path / "lessons" / "n"
    timeline = tl.build_timeline(sample("python_loop", "en"), "en", out)
    cue = timeline["scenes"][0]["cues"][0]
    clip, _ = sf.read(out / "audio" / "s0_0.wav", dtype="float32")
    assert len(clip) / SAMPLE_RATE < 0.3 + 0.02 * len(cue["text"]) + 0.2  # the 0.8 s of padding is gone
    assert np.abs(clip).max() == pytest.approx(10 ** (-1 / 20), abs=1e-3)


# --- committed fallback audio (G2: no TTS needed at demo time) ----------------------

def bundled_langs():
    return {p.stem for p in (store.BUNDLED_TTS_DIR / "manifest").glob("*.json")} if (store.BUNDLED_TTS_DIR / "manifest").is_dir() else set()


@pytest.mark.parametrize("lang", LANGS)
def test_fallback_samples_play_from_the_bundled_cache(lang, tmp_path, monkeypatch):
    """Every sentence of every sample is in shared/tts_cache, so no engine is loaded."""
    if lang not in bundled_langs():
        pytest.skip(f"no bundled {lang} audio yet; run scripts/pregen_audio.py --lang {lang}")

    class NoTTS(VoiceFake):
        def synth(self, *a, **k):
            raise AssertionError("TTS was called for a bundled sample")

    settings = SimpleNamespace(outputs_dir=tmp_path / "outputs")
    monkeypatch.setattr("app.cache.store.get_settings", lambda: settings)
    monkeypatch.setattr(tl, "get_settings", lambda: settings)
    real_engine, voice = registry.get_engine(lang)
    NoTTS.name, NoTTS.languages = real_engine.name, (lang,)
    registry.release_all()
    monkeypatch.setattr(tl, "get_engine", lambda _lang: (NoTTS(), voice))
    for name in SAMPLE_NAMES:
        timeline = tl.build_timeline(sample(name, lang), lang, tmp_path / "lessons" / f"{name}-{lang}")
        assert timeline["total_seconds"] > 20
