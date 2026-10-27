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
    assert prepare_tts_text("இது loop ஆகும்", "ta") == "இது லூப், ஆகும்"
    assert prepare_tts_text("A loop repeats `print(i)`.", "en") == "A loop repeats print i ."


def test_tamil_pauses_after_english_terms_not_before_punctuation():
    assert prepare_tts_text("Python-ல loop எப்படி", "ta") == "பைதான்-ல, லூப், எப்படி"
    assert prepare_tts_text("இது ஒரு for loop.", "ta") == "இது ஒரு ஃபார் லூப்."  # already a pause
    assert prepare_tts_text("code-ஐ, பல", "ta") == "கோட்-ஐ, பல"
    assert prepare_tts_text("Python में loop", "hi") == "पाइथन में लूप"  # Hindi is unchanged


@pytest.mark.parametrize("digits, words", [
    ("0", "பூஜ்ஜியம்"), ("3", "மூணு"), ("16", "பதினாறு"), ("20", "இருபது"), ("25", "இருபத்தி அஞ்சு"),
    ("100", "நூறு"), ("105", "நூத்தி அஞ்சு"), ("250", "இருநூத்தி அம்பது"), ("2026", "ரெண்டு பூஜ்ஜியம் ரெண்டு ஆறு"),
])
def test_tamil_number_words(digits, words):
    from app.tts.prep import _numbers, number_words

    assert number_words(digits, _numbers("ta")) == words


def test_tamil_numbers_in_sentences():
    assert prepare_tts_text("range(3) நமக்கு 0, 1, 2-ன்னு", "ta") == "ரேஞ்ச், மூணு நமக்கு பூஜ்ஜியம், ஒண்ணு, ரெண்டு-ன்னு"
    assert prepare_tts_text("9 கூட்டல் 16, 25 ஆகுது", "ta") == "ஒம்போது கூட்டல் பதினாறு, இருபத்தி அஞ்சு ஆகுது"
    assert prepare_tts_text("3.5 ஆகும்", "ta") == "மூணு புள்ளி அஞ்சு ஆகும்"
    assert prepare_tts_text("CO2 உள்ளே", "ta") == "சி ஓ டூ, உள்ளே"  # CO2 is a term, not a number
    assert prepare_tts_text("range(3) हमें 0 देता है", "hi") == "रेंज 3 हमें 0 देता है"  # Hindi digits untouched


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

def test_indic_tts_female_is_the_default_tamil_voice():
    from app.config import Settings

    assert Settings.__dataclass_fields__["tamil_tts"].default == "indic-tts"
    assert registry.LANG_ENGINES == {
        "en": ("kokoro", "hf_alpha"), "hi": ("kokoro", "hf_alpha"), "ta": ("indic-tts", "female")}
    assert registry.TAMIL_ENGINES["indic-tts"] == ("indic-tts", "female")


def test_registry_keeps_one_engine_loaded(monkeypatch):
    monkeypatch.setattr(registry, "get_settings", lambda: SimpleNamespace(tamil_tts="indic-tts"))
    kokoro, _ = registry.get_engine("hi")
    tamil, _ = registry.get_engine("ta")
    assert (kokoro.name, tamil.name) == ("kokoro", "indic-tts")
    assert list(registry._active) == ["indic-tts"]  # the Kokoro engine was unloaded and dropped
    registry.release_all()
    assert registry._active == {}


def test_list_voices(monkeypatch):
    assert [v["id"] for v in registry.list_voices("hi")] == ["hf_alpha", "hm_omega"]
    with pytest.raises(ValueError):
        registry.list_voices("xx")
    monkeypatch.setattr(registry, "get_settings", lambda: SimpleNamespace(tamil_tts="parler"))
    assert [v["id"] for v in registry.list_voices("ta")] == ["jaya"]  # Parler stays selectable
    assert registry.get_engine("ta")[0].name == "parler"
    registry.release_all()


def test_unknown_tamil_engine_is_refused(monkeypatch):
    monkeypatch.setattr(registry, "get_settings", lambda: SimpleNamespace(tamil_tts="espeak"))
    with pytest.raises(NotImplementedError, match="TAMIL_TTS='espeak'"):
        registry.get_engine("ta")


def test_plan_b_engine_is_selected_by_config(monkeypatch):
    monkeypatch.setattr(registry, "get_settings", lambda: SimpleNamespace(tamil_tts="indic-tts"))
    engine, voice = registry.get_engine("ta")
    assert (engine.name, voice) == ("indic-tts", "female")
    assert [v["id"] for v in registry.list_voices("ta")] == ["female", "male"]
    assert registry.list_voices("ta")[0]["engine"] == "indic-tts"
    registry.release_all()


def test_indic_tts_voices_and_missing_model(tmp_path, monkeypatch):
    from app.tts.indic_tts_engine import IndicTTSEngine

    monkeypatch.setattr("app.tts.indic_tts_engine.get_settings", lambda: SimpleNamespace(models_dir=tmp_path))
    engine = IndicTTSEngine()
    assert engine.resolve_voice("male") == "male" and engine.resolve_voice("jaya") == "female"
    with pytest.raises(FileNotFoundError, match="indic-tts-ta"):
        engine.synth("வணக்கம்", "ta", "female")


def test_parler_description_is_fixed_per_voice_and_speed():
    engine = ParlerEngine()
    assert engine.description("jaya") == engine.description("jaya", 1.0)
    assert "Jaya" in engine.description("unknown-voice")  # falls back to the default voice
    assert engine.description("jaya", 0.8) != engine.description("jaya", 1.0)
    assert pace_phrase(1.0) == "at a moderate pace"


def test_parler_regenerates_a_cut_short_sentence():
    from app.tts.parler_engine import MAX_ATTEMPTS, SEED, longest_complete

    text = "செங்கோண முக்கோணத்துல ஒரு மூலை நேர் கோணமா இருக்கும்"  # 46 characters
    lengths = {SEED: 0.5, SEED + 1: 3.4}  # seed 0 stops early, seed 1 is complete
    seeds = []

    def generate(seed):
        seeds.append(seed)
        return tone(lengths.get(seed, 0.4))

    assert len(longest_complete(generate, text, SAMPLE_RATE)) == len(tone(3.4))
    assert seeds == [SEED, SEED + 1]

    seeds.clear()
    assert len(longest_complete(lambda s: (seeds.append(s), tone(0.2 + 0.1 * s))[1], text, SAMPLE_RATE)) == len(
        tone(0.2 + 0.1 * (SEED + MAX_ATTEMPTS - 1)))  # never complete: the longest attempt wins
    assert len(seeds) == MAX_ATTEMPTS

    seeds.clear()
    longest_complete(lambda s: (seeds.append(s), tone(3.0))[1], text, SAMPLE_RATE)
    assert seeds == [SEED]  # a normal sentence is generated once


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


def test_voice_for_maps_gender_per_engine(monkeypatch):
    monkeypatch.setattr(registry, "get_settings", lambda: SimpleNamespace(tamil_tts="indic-tts"))
    assert registry.voice_for("en", "female") == "hf_alpha" and registry.voice_for("hi", "male") == "hm_omega"
    assert registry.voice_for("ta", "male") == "male"
    monkeypatch.setattr(registry, "get_settings", lambda: SimpleNamespace(tamil_tts="parler"))
    assert registry.voice_for("ta", "male") == "jaya"  # Parler has no male Tamil voice: its default


def test_timed_stage_records_peak_memory(tmp_path, monkeypatch):
    from app.cache.store import read_json, timed_stage

    monkeypatch.setattr("app.cache.store.get_settings", lambda: SimpleNamespace(outputs_dir=tmp_path))
    with timed_stage("rss-test", "narrate"):
        block = bytearray(50 * 2**20)  # 50 MB while the stage runs
        import time
        time.sleep(0.3)
        del block
    timings = read_json(tmp_path / "lessons" / "rss-test" / "timings.json")
    assert timings["narrate"] > 0.2 and timings["rss_mb"]["narrate"] > 50


def test_bench_table_rows():
    import importlib.util
    from app.config import REPO_ROOT

    spec = importlib.util.spec_from_file_location("bench", REPO_ROOT / "scripts" / "bench.py")
    bench = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bench)
    rows = bench.table({"plan": 9.0, "narrate": 29.4, "export_smooth": 50.0,
                        "rss_mb": {"plan": 300, "plan_ollama": 2900, "narrate": 1800, "export_smooth": 900}})
    assert rows[0] == ("plan", "9.0", "300") and rows[1] == ("plan (ollama)", "", "2900")
    assert ("voice + timing", "29.4", "1800") in rows and rows[-1] == ("total", "88.4", "2900")


def test_lesson_cache_key_normalises_topic_and_covers_voice_and_speed():
    from app.cache.store import lesson_cache_key

    k = lesson_cache_key("How does a Python loop work?", "beginner", "ta", 45, "female", 1.0)
    assert k == lesson_cache_key("  how does a PYTHON loop work ", "beginner", "ta", 45, "female", 1.0)
    assert k != lesson_cache_key("How does a Python loop work?", "beginner", "ta", 45, "male", 1.0)
    assert k != lesson_cache_key("How does a Python loop work?", "beginner", "ta", 45, "female", 1.1)
    assert k != lesson_cache_key("How does a Python loop work?", "beginner", "hi", 45, "female", 1.0)
