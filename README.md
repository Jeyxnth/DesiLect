# DesiLect (Blu Visual Teacher)

## Setup

```
make setup
.venv/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU-only build
.venv/Scripts/python -m pip install -r backend/requirements-models.txt
.venv/Scripts/python -m pip install git+https://github.com/huggingface/parler-tts.git   # Tamil TTS (step 9)
.venv/Scripts/python -m pip install transformers==4.46.3   # parler-tts downgrades it; put the tested pin back
.venv/Scripts/hf auth login            # once: IndicTrans2 and Indic Parler-TTS are gated (accept their terms on huggingface.co first)
.venv/Scripts/python scripts/download_models.py kokoro ollama indictrans2 indic-parler-tts   # one-time, needs network (H2 exception)
python scripts/doctor.py --smoke                         # preflight: checks every dependency, prints the fix for each gap
```

Translation (step 8): `python -m app.translate.indictrans --sample photosynthesis --lang hi ta` (from `backend/`)
translates an English lesson offline. Code, numbers and `shared/glossary.json` terms stay in English.
A full lesson takes about 8-13 s per language on this laptop. `transformers` is pinned to 4.46.3: IndicTrans2's model code
crashes in newer versions. The model is loaded with `local_files_only`, so after the one-time download no account or network is needed;
another laptop can simply copy the `models/` folder.

On a fresh or test laptop run `python scripts/doctor.py` first. It needs only Python, reports what is missing
(Python 3.11, Node 20, FFmpeg, browser, models, Ollama, fonts) and exits non-zero if anything required for the
current step is absent. Do not start testing until it reports 0 failed.

## Run offline

```
make sample    # narrates the sample lesson and writes outputs/lessons/sample-en/lesson.mp4 (+ captions.srt)
make dev       # backend :8000, frontend :5173; play at /lesson/sample-en
```

Other bundled samples render to their own folder, e.g.
`python scripts/render_sample.py --sample photosynthesis --lang hi` writes `outputs/lessons/sample-photosynthesis-hi/`.

Built-in samples (the G2 fallback when the planner fails), each in en/hi/ta: `python_loop` (code + row diagram),
`binary_search` (stack diagram + code), `photosynthesis` (row + cycle diagrams), `pythagorean_theorem` (maths).
The closest one to the requested topic is used, and the UI says so.

Player keys: Space play/pause, ← → previous/next scene, R replay.

The planner takes about 35 s per plan on a CPU-only laptop (about 65 s when the first plan is rejected and retried);
with a GPU Ollama is about 4x faster. Set `OLLAMA_NUM_GPU=0` in `.env` to measure the CPU-only time on a GPU laptop.

## Models and licences

| Model / library | Used for | Licence |
|---|---|---|
| Kokoro-82M via kokoro-onnx (voices `hf_alpha`, `hm_omega`) | English (Indian accent) and Hindi TTS | Apache-2.0 (kokoro-onnx: MIT) |
| Llama 3.2 3B Instruct via Ollama (`llama3.2:3b`) | lesson planner. **Built with Llama.** | Llama 3.2 Community License |
| eSpeak NG (via espeakng-loader) | phonemes | GPL-3.0-or-later |
| ONNX Runtime, NumPy, soundfile | CPU inference, audio | MIT / BSD-3-Clause |
| IndicTrans2 en-indic dist-200M + IndicTransToolkit (PyTorch CPU) | English -> Hindi / Tamil translation | MIT |
| Indic Parler-TTS (`ai4bharat/indic-parler-tts`) + parler-tts | Tamil TTS (voice `jaya`) | Apache-2.0 |
| Noto Sans, Noto Sans Mono (bundled in `frontend/public/fonts`) | UI, captions, code | SIL Open Font License 1.1 |

Full list: `LICENSES.md`.

> Translation review status: the Hindi samples are machine translations that **need a native speaker check**.
> Made by the IndicTrans2 pipeline (step 8): `shared/samples/photosynthesis.hi.json`, `shared/samples/binary_search.hi.json`;
> earlier machine-assisted drafts: `shared/samples/python_loop.hi.json`, `shared/samples/pythagorean_theorem.hi.json`.
> The four Tamil samples were rewritten in step 9 in **spoken classroom Tamil** (e.g. செய்யுது, பார்ப்போம், இன்னைக்கு), because the
> formal written Tamil sounded wrong when narrated; they are awaiting the team's native-speaker review.
> Live translations still come from IndicTrans2, which writes formal Tamil, so a new Tamil lesson will sound bookish.
> Things to look at: word order around English terms kept by the glossary (e.g. "oxygen", "sorted list"), and diagram labels.

## Voices (step 9)

| Language | Engine | Voice | Notes |
|---|---|---|---|
| en | Kokoro (kokoro-onnx) | `hf_alpha` (female), `hm_omega` (male) | Indian-accented English: these Hindi voices speak en-us phonemes |
| hi | Kokoro | `hf_alpha` (female), `hm_omega` (male) | Hindi phonemes; Latin words switch to English phonemes |
| ta | Indic Parler-TTS | `jaya` (female). The model's only other Tamil speaker, Kavitha, was dropped after a listening check (drags words; 0.66 s for a greeting Jaya says in 1.81 s); it has no male Tamil speaker | `backend/app/tts/parler_engine.py`: CPU, float32, `local_files_only`, threads = physical cores, seed 0, one fixed speaker description per voice and speed. Parler sometimes stops mid-sentence, so audio under 40 ms per character is generated again with seed 1, then 2 |
| ta (Plan B, `TAMIL_TTS=indic-tts`) | AI4Bharat Indic-TTS (FastPitch + HiFi-GAN, via coqui-tts) | `female`, `male` | `backend/app/tts/indic_tts_engine.py`: about 10x faster than Parler, same text always gives the same audio, cannot stop mid-sentence; real speed control (duration scale 1 / speed). Its alphabet is Tamil letters only, so the transliteration and number words below are required |

The registry (`backend/app/tts/registry.py`) keeps one engine loaded and `release_all()` unloads it after the voice stage. `list_voices(lang)`
and the `voice` / `speed` arguments of `build_timeline` are what step 11 uses. Parler has no speed control, so speed changes its description
("slowly", "a little fast"), which is a coarse effect; Kokoro and Indic-TTS take a real speed value.

**Spoken text vs captions.** Narration is spoken from `prepare_tts_text` (`backend/app/tts/prep.py`): in hi and ta, English terms are replaced by their
Devanagari / Tamil spelling from `shared/glossary.json` -> `tts_translit` (e.g. loop -> लूप), backticks are dropped and `range(3)` is read "range 3".
The caption always keeps the original text. Set `TTS_TRANSLIT=0` to speak the Latin words instead. Without the table Kokoro does not spell letters out
(espeak switches to English phonemes), but the English words are then said in an English accent inside a Hindi sentence; compare the two with the
A/B clips from step 9 and keep whichever sounds better to a Hindi speaker.

**Per sentence audio.** Each sentence is synthesised alone, peak-normalised to -1 dBFS, trimmed of leading/trailing silence (30 ms kept, 4 ms fades) and
cached in `outputs/cache/tts/` before it is timed, so cue starts are sentence starts and a scene ends at its last sentence's end plus the 0.6 s pause
(`backend/tests/test_voice.py` checks this for every sample in en, hi and ta).

**If voicing fails** (model missing, out of memory, engine error), the pipeline voices the closest built-in sample in the
same language instead, from the bundled audio below, and the UI shows the fallback notice (`narrate` in `backend/app/pipeline/orchestrator.py`).

**Fallback audio.** `python scripts/pregen_audio.py` writes the narration of the four bundled samples into `shared/tts_cache/` (16-bit FLAC, committed;
manifest in `shared/tts_cache/manifest/<lang>.json`). Lookup order is `outputs/cache/tts`, then `shared/tts_cache`, then the engine, so a sample lesson
needs no TTS at demo time. Re-run it after editing a sample, the transliteration table or `backend/app/tts/audio.py` (bump `POSTPROCESS_VERSION`).

### Speed on this laptop (14 cores, 20 threads; not the weakest laptop)

| Stage | Real-time factor (synthesis time / audio time) | Whole sample (4 scenes) |
|---|---|---|
| English, Kokoro | 0.25 | about 30 s for 154 s of audio over all four samples |
| Hindi, Kokoro | 0.27 | about 54 s for 200 s of audio over all four samples |
| Tamil, Indic Parler-TTS (14 threads, float32) | **5.36** | 262 s to voice the 52.5 s `python_loop` sample (12 sentences, about 22 s each); a 60 s lesson takes about 5.5 min. A second run over the other three samples (34 sentences, 22 min wall) measured **8.6**, so budget 5-9x |
| Tamil, Indic-TTS Plan B (14 threads) | **0.48** | 26 s to voice the 58 s `python_loop` sample (female; male 0.48 too); model loads in about 3 s |

### Tamil voice: Plan B decision

Rule: if Indic Parler-TTS is slower than 3x real time on the weakest laptop, add a second engine behind the same `TTSEngine` interface
(AI4Bharat Indic-TTS FastPitch + HiFi-GAN) and select it with `TAMIL_TTS` in `.env`.

**Measured (step 9):** Parler runs at **5.4x to 8.6x real time** on this 14-core development laptop, which is *not* the weakest one, so the rule
triggered. **Plan B is built**: Indic-TTS runs at **0.48x real time** on the same laptop, about 10x faster (26 s instead of 262 s for the Python-loop
lesson). Repeat with `TAMIL_TTS=indic-tts python -m app.timing.timeline --lang ta --no-cache` (from `backend/`).

- `TAMIL_TTS=parler` (default for now): Jaya, pre-generated audio for the four samples is bundled. Live Tamil takes 5-9 min per minute of lesson.
- `TAMIL_TTS=indic-tts`: female or male voice, live Tamil in well under real time. Run `python scripts/pregen_audio.py --lang ta` with it set to bundle
  its sample audio too (the cache is keyed by engine, so both sets can live side by side).
- Which one is the default is a listening decision for the team (sound quality vs speed); not yet made.

Install notes: coqui-tts is installed **without dependencies** (see `backend/requirements-models.txt`), because its normal install would upgrade
transformers and huggingface_hub and break IndicTrans2 and Parler. The released config points its speaker list at the authors' training folder, so the
engine writes a corrected copy at load time.

## Tested laptops

## Architecture

### HTTP API (`backend/app/api/routes.py`)

| Method and path | What it does |
|---|---|
| `POST /api/lessons` `{topic, level, language, target_seconds}` | queues a lesson (one runs at a time), returns `{job_id, ...status}` |
| `GET /api/lessons/{id}` | status: `stage` (plan, translate, voice, timing, export, done), `progress`, `fallback_used`, `timings`, `timeline_ready`, `mp4_ready` |
| `GET /api/lessons/{id}/events` | the same status as Server-Sent Events, until the job is done or failed |
| `POST /api/lessons/{id}/export` | retry the MP4 export (the lesson keeps playing if export fails) |
| `GET /api/lessons/{id}/lesson` | the lesson plan, with `meta.fallback`, `meta.source`, `meta.reason` |

Results (`timeline.json`, `lesson.wav`, `lesson.mp4`, `captions.srt`) are served under `/media/lessons/{id}/`.
