# DesiLect (Blu Visual Teacher)

Type any concept, such as "How does binary search work?", and get a 30 to 90 second narrated visual lesson in English, Hindi or
Tamil: animated diagrams, highlighted code and captions in the learner's own script, playing in the browser right away and saved as a
720p MP4. Everything runs on an ordinary CPU-only laptop with no internet and no cloud AI. A small local LLM plans the lesson as
JSON, IndicTrans2 translates it, Kokoro and AI4Bharat Indic-TTS voice it, and the audio decides the timing of every scene. If any
stage fails, a working fallback takes over and the screen says so, so the lesson still plays.

**Built with Llama** (the planner is Meta Llama 3.2; see [Models, voices, fonts and tools](#models-voices-fonts-and-tools)).

## Submission videos

Both lessons were made by this app, offline. Planner: llama3.2:3b, beginner level, 60 s target. The Hindi version re-voices the same
English plan (translated, voiced, timed and exported again), exactly as the player's "Same lesson in" does.

| # | Topic | Language | Video | Captions | Length |
|---|---|---|---|---|---|
| 1 (our topic) | How does binary search work? | English | [`how-does-binary-search-work_en.mp4`](submissions/how-does-binary-search-work_en.mp4) | [`.srt`](submissions/how-does-binary-search-work_en.srt) | 41.7 s |
| | | Hindi | [`how-does-binary-search-work_hi.mp4`](submissions/how-does-binary-search-work_hi.mp4) | [`.srt`](submissions/how-does-binary-search-work_hi.srt) | 57.6 s |
| 2 (judges' topic) | Explain how caffeine works | English | [`explain-how-caffeine-works_en.mp4`](submissions/explain-how-caffeine-works_en.mp4) | [`.srt`](submissions/explain-how-caffeine-works_en.srt) | 41.0 s |
| | | Hindi | [`explain-how-caffeine-works_hi.mp4`](submissions/explain-how-caffeine-works_hi.mp4) | [`.srt`](submissions/explain-how-caffeine-works_hi.srt) | 61.0 s |

- **Checks.** Each MP4 is 1280x720 H.264 (yuv420p, 30 fps) with AAC audio and a soft subtitle track (eng / hin). Its length matches
  the timeline, its narration peaks at -1 dB, and it has no gap longer than 1.5 s. The captions are also burned in.
  `submissions/<topic>.json` records the lesson ids, the ffprobe output and the stage timings.
- **How they were picked.** Binary search is the first plan the planner gave (after its built-in retry). For caffeine, the first render
  had cut-off duplicate diagram labels. That was a validator bug, fixed in step 13. The planner then wrote five plans with the same
  settings, and the most accurate one was rendered (`--plan-from`). Of the other four, two had wrong labels such as "Adenosine blocks", and
  three ended by telling students to try a cup of coffee.
- **Re-render:** `.venv/Scripts/python scripts/render_submission.py "<topic>" --lang hi` (add `--plan-from <lesson id>` to voice a stored
  plan). It refuses to save a lesson that needed any fallback.
- The Hindi is IndicTrans2 output and has not had a native speaker's check yet. Two known rough spots: "दिमाग को जागो" (should be
  जगाएँ) in caffeine, and an awkward recap sentence in binary search.

## Architecture

```
  concept, level, language, length, voice, speed            (React input page -> POST /api/lessons)
        |
        v
 1 PLAN       Ollama llama3.2:3b on 127.0.0.1 -> lesson JSON (3-6 scenes: title_card, diagram, code_walkthrough)
        |     validated against shared/schema; 2 attempts      fallback: closest built-in sample lesson
        v
 2 TRANSLATE  IndicTrans2 en->hi/ta (PyTorch CPU), glossary keeps code and terms in English, then unloaded
        |                                                       fallback: pre-translated sample, or English narration
        v
 3 VOICE      Kokoro (en, hi) / Indic-TTS (ta), one sentence at a time, normalised + trimmed + cached
        |                                                       fallback: the sample's bundled audio (shared/tts_cache)
        v
 4 TIME       backend/app/timing/timeline.py: scene length = its audio + pauses -> timeline.json, lesson.wav, captions.srt
        |
        v
 5 RENDER     player: SVG + CSS scenes as a pure function of (timeline, t), clocked by the audio element
              export: headless Chromium seeks the render page -> JPEG frames piped to FFmpeg -> H.264/AAC MP4, ffprobe-checked
                                                                fallback: keyframe export; if both fail the lesson still plays
```

One stage runs at a time and each model is unloaded after its stage (8 GB laptops). Every stage writes its wall time and peak
memory to `outputs/lessons/<id>/timings.json`. `shared/` (JSON schemas, samples, glossary, bundled audio) is the contract between the
FastAPI backend (`backend/app`) and the React + Vite frontend (`frontend/src`). The model only ever writes JSON data: nothing it
writes is executed or rendered as HTML, and code is shown as text.

## Setup (online, once)

Needs about 7 GB of disk for models (IndicTrans2 2.1 GB, Indic-TTS 1.6 GB, Kokoro 0.3 GB, llama3.2:3b 2 GB; Indic Parler-TTS
3.6 GB more if you want the opt-in Tamil voice) plus about 3 GB for Python packages. Windows commands shown; on Linux/macOS use
`.venv/bin/python`. If the other laptop already has everything, copying `models/` across is enough for step 4 (or put
`MODELS_DIR=<path to that folder>` in `.env`).

**Checked from a clean clone (step 13).** On the dev laptop, a fresh clone in a new folder ran every command below in 16 minutes,
using the existing models through `MODELS_DIR`. It ended with doctor at 0 failed, the offline check OK, 260 tests passing (including
a full sample MP4 export), and the app serving on :8000. That check found and fixed three problems: doctor ignored `MODELS_DIR`,
`/api/health` reported Playwright missing, and Playwright was missing from `backend/requirements.txt`. The 8 GB laptop has not been
set up from the README yet.

**Install first:** Python 3.11 or newer (tested on 3.13.3), Node.js 20 or newer (tested on 22.20.0), Git, FFmpeg with libx264
(`winget install Gyan.FFmpeg`, then reopen the terminal), and Ollama (ollama.com). `make` is optional: Windows has none by default,
so the commands below are spelled out (the `Makefile` targets are the same commands). Run them in Git Bash from the repo root.

```
git clone https://github.com/Jeyxnth/DesiLect.git
cd DesiLect

# 1. Python and Node dependencies (make setup does the first four lines)
py -3.13 -m venv .venv                                       # or py -3.11; plain `python` may be an older version
.venv/Scripts/python -m pip install --upgrade pip
.venv/Scripts/python -m pip install -r backend/requirements.txt
(cd frontend && npm install)
.venv/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU-only build
.venv/Scripts/python -m pip install -r backend/requirements-models.txt
.venv/Scripts/python -m pip install git+https://github.com/huggingface/parler-tts.git   # also brings libraries Indic-TTS uses
.venv/Scripts/python -m pip install transformers==4.46.3    # parler-tts downgrades it; put the tested pin back
.venv/Scripts/python -m pip install --no-deps coqui-tts==0.28.0 coqui-tts-trainer==0.4.0 coqpit-config==0.2.5 torchcodec==0.17.0 monotonic-alignment-search==0.2.1 anyascii==0.3.3 pysbd==0.3.4 inflect num2words typeguard more-itertools jaraco.functools docopt

# 2. Capture browser for the MP4 export
.venv/Scripts/python -m playwright install chromium         # (an installed Chrome or Edge also works)

# 3. Planner model (Ollama must be running)
ollama pull llama3.2:3b

# 4. Models: IndicTrans2 is gated, so accept its terms on huggingface.co first, then log in once
.venv/Scripts/hf auth login
.venv/Scripts/python scripts/download_models.py kokoro indictrans2 indic-tts-ta    # add indic-parler-tts for the opt-in voice

# 5. Build the frontend and check everything
(cd frontend && npm run build)
.venv/Scripts/python scripts/doctor.py --smoke              # must end with 0 failed
```

Why the odd install order: IndicTrans2 needs `transformers==4.46.3`, parler-tts pins 4.46.1, and a normal coqui-tts install would
upgrade to 5.x, so coqui-tts goes in without dependencies. Afterwards `pip check` reports "parler-tts 0.2.2 has requirement
transformers==4.46.1"; that is expected and harmless. `.env` is optional (`cp .env.example .env`); no keys or accounts are needed at runtime.

## Run offline

Turn Wi-Fi off, start Ollama, then:

```
.venv/Scripts/python scripts/check_offline.py                                    # make offline-check
.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --port 8000      # make dev-backend
```

The offline check confirms every model, font, tool and browser is on disk, finds no external URLs, and confirms nothing reaches the
internet. `make dev` also starts the Vite dev server on :5173, which is only needed for frontend work.

Open **http://localhost:8000**, type a concept, pick level, language, voice and speed, and press Generate. The stages tick off;
the player opens and starts as soon as the narration is ready (about 1 to 3 minutes), and **Download MP4** enables when the export
finishes. "Same lesson in" re-voices the lesson in another language without planning again. Keys: Space play/pause, Left/Right
previous/next scene, R replay. When the lesson ends, a short quiz checks what it taught (keys 1-4 to answer, Enter for the next
question). `.venv/Scripts/python scripts/render_sample.py` (`make sample`) renders a bundled sample with no planner at all.

## How fallback works

The demo never breaks: each stage has a fallback, and the screen always says when one was used.

| Stage fails | What plays instead | What the screen says |
|---|---|---|
| Planner: Ollama stopped, model missing, timeout, or two invalid plans | the closest of four built-in lessons (Python loop, binary search, photosynthesis, Pythagoras), in the chosen language | "Fallback lesson used: a built-in sample", the reason, which sample, and a **Generate again** button (the same request, planned afresh) |
| Planner: the last plan's narration is short for the length asked (but at least 30 s) | that plan, as a shorter lesson on the topic asked (audio sets the timing) | "Shorter than you asked: about N s instead of M s" with **Generate again** |
| Translation: model missing or bad output | a built-in sample uses its checked translation; a new lesson stays in English | "Translation unavailable" |
| Voice: model missing, out of memory, engine error | the closest sample, voiced from its bundled audio (no model has to load) | "Fallback lesson used", reason "Voice generation failed" |
| Smooth MP4 export: browser error, over its time budget, or a bad file | the keyframe export (one frame per change) | the MP4 still downloads |
| Both exports | nothing to download, but the lesson plays in the browser | "MP4 export failed" with a **Retry export** button |
| Quiz: a bad question, or a broken quiz | that question is dropped; with fewer than 2 good questions, no quiz (never a retry or a fallback) | nothing: the lesson ends as it would without a quiz |

The planner's JSON is checked against `shared/schema/lesson.schema.json` plus content rules (scene count, word budget for the
length, short distinct diagram labels, code at most 12 x 50, no markup, English only). A rejected first plan is retried once with
the errors listed. On that last try, narration that is too short is kept rather than replaced by a sample, as long as it is at least 30 s
(69 words): with a 3B model on a CPU, short narration was the most common reason a real lesson fell back. A fallback or short lesson never
goes into the reuse cache, so Generate again really plans again. Failure drills for all of this: `.venv/Scripts/python scripts/drill.py` (`make drill`; see step 12 below).

## How audio sets timing

Only `backend/app/timing/timeline.py` decides durations, and it decides them from the voice. Each narration sentence is synthesised
on its own, peak-normalised, and trimmed of silence. A caption cue then starts exactly where its sentence starts, and a scene lasts
as long as its sentences plus a 0.15 s gap between them and a 0.6 s pause at the end. Diagram items appear and code lines highlight
at the sentence that talks about them. `lesson.wav` is built from the same samples, so the timeline total equals the audio length
exactly. In the browser the audio element is the clock, so picture and voice cannot drift. The MP4 export seeks the same render page
frame by frame, so the video has the same timing. A Hindi lesson is longer than its English plan because the Hindi narration takes
longer to say, and the scenes simply stretch to fit it.

## Tested laptops

Budget: a 60 s lesson ready, MP4 included, in about 5 minutes on the weakest laptop. Otherwise, lower the planner to `qwen2.5:1.5b`,
the export to keyframe, and the TTS threads. Full stage tables are in `docs/bench.md` (`python scripts/bench.py --run` appends one per
machine), and the offline matrix is in `docs/offline-test.md`.

| Laptop | CPU | RAM | OS | Planner | 60 s lesson: en / hi / ta | Peak RAM | Verdict |
|---|---|---|---|---|---|---|---|
| Dev laptop | Intel Core i7-13650HX, 14 cores / 20 threads | 24 GB | Windows 11 | llama3.2:3b on CPU (`OLLAMA_NUM_GPU=0`), 45 s per plan | 112 s / 144 s / 173 s | 2.66 GB (planner, inside Ollama); app 2.1 GB at export | within budget, nothing lowered |
| Second laptop (8 GB) | TODO | 8 GB | TODO | | **not measured yet**: run `python scripts/bench.py --run` and, with Wi-Fi off, `python scripts/drill.py --wifi-off` | | |

Stage seconds on the dev laptop (en / hi / ta): plan 45 / 45 / 46, translate - / 19 / 11, voice + timing 12 / 18 / 37, smooth MP4
export 54 / 60 / 76. The offline matrix (3 topics x 3 languages x 2 levels) and six failure drills all passed on the dev laptop
behind an in-process network block (`docs/offline-test.md`). The run with Wi-Fi physically off, and the check on a real phone, are
still to do.

## Known limitations

- **Translations are machine-made.** Live Hindi and Tamil come from IndicTrans2. Its Tamil is formal and bookish, and it can
  mistranslate. For example, in the first caffeine render "doesn't work as well" became "doesn't work" in Hindi. The bundled
  Tamil samples were rewritten by hand in spoken classroom Tamil. The Hindi samples still await a native speaker's check.
- **A 3B planner writes simple lessons.** Facts are not verified. Plans can run short of the target length (for example, a 44 s
  English lesson when 60 s was asked for), and a plan sometimes needs its retry. Hindi and Tamil lessons run 10-40% longer
  than the English plan.
- **Quiz questions come from the same 3B model.** They are checked for shape and markup, not for truth: one hash-table question
  in testing had a wrong "right" answer. The quiz also makes each planner call about 20 s longer on a CPU (see B1 below).
- **Speed.** A lesson takes about 2 to 3 minutes on the dev laptop with the planner on its CPU (measured before the quiz; add about
  20 s per planner call for it). With a GPU, Ollama plans in about 10 to 25 s. The opt-in Parler Tamil voice is 5 to 9 times
  slower than real time.
- **One lesson at a time.** Requests queue behind each other. Repeating an identical request returns the earlier lesson instantly.
- **Not yet done:** the benchmark on the 8 GB laptop, the Wi-Fi-off matrix run, and a check on a real phone (an emulated phone at 4x
  and 6x CPU slowdown plays smoothly).
- **Versions.** The rules target Python 3.11 and Node 20. The dev laptop runs Python 3.13.3 and Node 22.20.0, and everything was
  tested there.
- **Scope.** Three languages (en, hi, ta); a fourth was left out at feature freeze. Hindi is voiced by Kokoro, so English terms in it
  are read through a transliteration table. Voice and diagram choices are limited to the three scene types.

## Team

TODO: names and roles of both team members (fill in before submitting).

## Models, voices, fonts and tools

Every item, with its exact licence name and where it was checked, is in [`LICENSES.md`](LICENSES.md), which also lists all the
Python and frontend libraries.

| Item | Version | Used for | Licence | Source |
|---|---|---|---|---|
| Llama 3.2 3B Instruct (`llama3.2:3b`), **Built with Llama** | Llama 3.2 (Q4_K_M) | lesson planner | Llama 3.2 Community License Agreement + Acceptable Use Policy | Meta, via the Ollama library |
| Ollama | 0.40.2 | local model server | MIT | ollama.com |
| IndicTrans2 en-indic dist-200M | HF snapshot | en -> hi, ta translation | MIT License | `ai4bharat/indictrans2-en-indic-dist-200M` |
| IndicTransToolkit `IndicProcessor` (vendored port) | 1.1.1 | translation pre/post-processing | MIT | PyPI `IndicTransToolkit` |
| Kokoro-82M (ONNX), voices `hf_alpha`, `hm_omega` | v1.0 | English and Hindi voice | Apache-2.0 | `hexgrad/Kokoro-82M`; files from the kokoro-onnx release |
| kokoro-onnx | 0.6.1 | runs Kokoro on CPU | MIT License | PyPI |
| eSpeak NG (in espeakng-loader 0.2.4) | bundled | phonemes for Kokoro | GPL-3.0-or-later (loader: MIT) | PyPI `espeakng-loader` |
| AI4Bharat Indic-TTS Tamil (FastPitch + HiFi-GAN), voices `female`, `male` | v1 checkpoints | Tamil voice (default) | MIT License | github.com/AI4Bharat/Indic-TTS release |
| coqui-tts | 0.28.0 | runs Indic-TTS | MPL-2.0 | PyPI |
| Indic Parler-TTS, voice `jaya` (opt-in) | HF snapshot | Tamil voice, `TAMIL_TTS=parler` | apache-2.0 | `ai4bharat/indic-parler-tts` |
| parler-tts | 0.2.2 | runs Indic Parler-TTS | Apache License 2.0 | github.com/huggingface/parler-tts |
| Noto Sans, Noto Sans Mono, Noto Sans Devanagari, Noto Sans Tamil | hinted TTF (Indic as WOFF2) | all on-screen text and captions | SIL Open Font License, Version 1.1 | notofonts (bundled in `frontend/public/fonts`) |
| FFmpeg + libx264 | 8.1 (gyan.dev full build) | MP4 encode and ffprobe checks | GPL-3.0-or-later (this build) / GPL-2.0-or-later; run as a separate program | gyan.dev via winget |
| Playwright + Chromium | 1.64.1 | headless capture for the MP4 | Apache-2.0 / BSD-3-Clause | PyPI; `playwright install chromium` |
| PyTorch (CPU), Transformers, ONNX Runtime | 2.14.1, 4.46.3, 1.31.1 | model runtimes | BSD-3-Clause, Apache-2.0, MIT | PyPI / download.pytorch.org |
| FastAPI, Uvicorn, Pydantic, jsonschema, httpx, NumPy, soundfile, psutil | see LICENSES.md | backend | MIT / BSD-3-Clause | PyPI |
| React, React DOM, Vite, TypeScript | 18.3.1, 18.3.1, 5.4.21, 5.9.3 | frontend | MIT, MIT, MIT, Apache-2.0 | npm |

## Engineering notes (by build step)

### Translation (step 8)

`python -m app.translate.indictrans --sample photosynthesis --lang hi ta` (from `backend/`) translates an English lesson offline.
Code, numbers and `shared/glossary.json` terms stay in English. A full lesson takes about 8-13 s per language on the dev laptop.
`transformers` is pinned to 4.46.3 because IndicTrans2's model code crashes in newer versions. The model loads with
`local_files_only`, so no account or network is needed after the one-time download.

> Translation review status: the Hindi samples are machine translations that **need a native speaker check**
> (`shared/samples/photosynthesis.hi.json`, `binary_search.hi.json` from IndicTrans2; `python_loop.hi.json`, `pythagorean_theorem.hi.json`
> machine-assisted drafts). The four Tamil samples were rewritten in step 9 in **spoken classroom Tamil**, because formal written Tamil
> sounded wrong when narrated. Live translations still come from IndicTrans2, which writes formal Tamil.

### Voices (step 9)

| Language | Engine | Voice | Notes |
|---|---|---|---|
| en | Kokoro (kokoro-onnx) | `hf_alpha` (female), `hm_omega` (male) | Indian-accented English: these Hindi voices speak en-us phonemes |
| hi | Kokoro | `hf_alpha` (female), `hm_omega` (male) | Hindi phonemes; Latin words switch to English phonemes |
| ta (opt-in, `TAMIL_TTS=parler`) | Indic Parler-TTS | `jaya` (female). The model's only other Tamil speaker, Kavitha, was dropped after a listening check (drags words; 0.66 s for a greeting Jaya says in 1.81 s); it has no male Tamil speaker | `backend/app/tts/parler_engine.py`: CPU, float32, `local_files_only`, threads = physical cores, seed 0, one fixed speaker description per voice and speed. Parler sometimes stops mid-sentence, so audio under 40 ms per character is generated again with seed 1, then 2 |
| ta (default) | AI4Bharat Indic-TTS (FastPitch + HiFi-GAN, via coqui-tts) | `female` (default), `male` | `backend/app/tts/indic_tts_engine.py`: about 10x faster than Parler, same text always gives the same audio, cannot stop mid-sentence; real speed control (duration scale 1 / speed). Its alphabet is Tamil letters only, so the transliteration and number words below are required |

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

**Voice speed.** The input page offers Slow / Normal / Fast (0.9x / 1.0x / 1.1x; the API accepts `speed` 0.7-1.3). Kokoro and Indic-TTS
apply it directly; Parler only approximates it through its description. Bundled sample audio is at 1.0x, so a sample voiced at another speed
needs the engine; if that fails, the 1.0x bundled audio is used.

**MP4 export (step 10).** `export_lesson` defaults to **smooth** mode: one headless page seeks the render page every 1/15 s
and pipes JPEG frames (quality 90) straight into `ffmpeg -f image2pipe -framerate 15 -i - ...` (H.264 veryfast CRF 23, yuv420p, 30 fps
out, AAC 128k, `+faststart`). Frames where nothing can change re-send the previous image instead of a new screenshot (`fresh_frames` in
`backend/app/export/capture.py`). Smooth capture has a time budget of 3x the lesson length (at least 60 s), enforced by a watchdog that
kills ffmpeg; if smooth fails, runs over budget or its MP4 fails the check, the **keyframe** export (one frame per change) runs instead (G2).
`outputs/lessons/<id>/export.json` records the mode used, and the job status shows it plus the capture progress percent.

- Every MP4 is checked with ffprobe: 1280x720, h264, yuv420p, aac, duration within 0.2 s of the timeline. A failing MP4 is renamed
  `lesson.rejected.mp4` and the export fails loudly (`export_error` in the job, red error in the player; the lesson still plays).
- Captions are burned in (drawn by the browser in the bundled Noto fonts) **and** added as a soft `mov_text` track tagged eng/hin/tam.
  `captions.srt` (UTF-8, no BOM) sits next to the MP4.
- Downloads are named `<topic-slug>_<lang>.mp4` / `.srt`, e.g. `how-does-a-python-loop-work_ta.mp4`.
- Length is set with `-t`, not `-shortest`: with a subtitle input, `-shortest` makes ffmpeg stop reading piped frames without exiting.
- `python scripts/render_sample.py --lang ta [--sample binary_search] [--mode keyframe]` renders a sample.

Measured on this laptop (smooth): Python-loop en 43 s lesson in 33 s, hi 50 s in 38 s, ta 58 s in 46 s, Tamil binary search 63 s in 50 s;
all 0-26 ms from the timeline. Keyframe mode: 57 s lesson in 10 s. A forced 1 s budget fell back to keyframe and passed the check.

**Hindi and Tamil text.** The stage font stack comes from `timeline.language`; Hindi and Tamil lines are 1.25x taller (matras), and the
caption bar wraps with `Intl.Segmenter` (word boundaries, grapheme boundaries inside an over-long word) into at most two lines instead of a
CSS line clamp, which clipped matras.

#### Speed on this laptop (14 cores, 20 threads; not the weakest laptop)

| Stage | Real-time factor (synthesis time / audio time) | Whole sample (4 scenes) |
|---|---|---|
| English, Kokoro | 0.25 | about 30 s for 154 s of audio over all four samples |
| Hindi, Kokoro | 0.27 | about 54 s for 200 s of audio over all four samples |
| Tamil, Indic Parler-TTS (14 threads, float32) | **5.36** | 262 s to voice the 52.5 s `python_loop` sample (12 sentences, about 22 s each); a 60 s lesson takes about 5.5 min. A second run over the other three samples (34 sentences, 22 min wall) measured **8.6**, so budget 5-9x |
| Tamil, Indic-TTS Plan B (14 threads) | **0.48** | 26 s to voice the 58 s `python_loop` sample (female; male 0.48 too); model loads in about 3 s |

#### Tamil voice: Plan B decision

Rule: if Indic Parler-TTS is slower than 3x real time on the weakest laptop, add a second engine behind the same `TTSEngine` interface
(AI4Bharat Indic-TTS FastPitch + HiFi-GAN) and select it with `TAMIL_TTS` in `.env`.

**Measured (step 9):** Parler runs at **5.4x to 8.6x real time** on this 14-core development laptop, which is *not* the weakest one, so the rule
triggered. **Plan B is built**: Indic-TTS runs at **0.48x real time** on the same laptop, about 10x faster (26 s instead of 262 s for the Python-loop
lesson). Repeat with `TAMIL_TTS=indic-tts python -m app.timing.timeline --lang ta --no-cache` (from `backend/`).

**Decision (step 9): Indic-TTS is the default Tamil engine, voice `female`** (matches the female defaults in English and Hindi; `male` is
available). The bundled Tamil sample audio in `shared/tts_cache/` is Indic-TTS (all four samples voiced in 80 s).
- `TAMIL_TTS=indic-tts` (default): live Tamil in well under real time.
- `TAMIL_TTS=parler`: Jaya, opt-in. Its sample audio is no longer bundled, so even the samples are voiced live (5-9 min per minute of lesson);
  run `TAMIL_TTS=parler python scripts/pregen_audio.py --lang ta` first if you switch.

Install notes: coqui-tts is installed **without dependencies** (see `backend/requirements-models.txt`), because its normal install would upgrade
transformers and huggingface_hub and break IndicTrans2 and Parler. The released config points its speaker list at the authors' training folder, so the
engine writes a corrected copy at load time.

### Bonus features (step 11, feature freeze)

- **Reuse cache.** A finished lesson is indexed by sha1(normalised topic, level, language, length, voice, speed, `PIPELINE_VERSION`)
  in `outputs/cache/lessons/`. Repeating the request returns that lesson at once (`"cached": true`; measured 27 ms). Only lessons with
  an MP4 and no fallback are cached, so a sample shown while Ollama was down is not reused later. Bump `PIPELINE_VERSION` in
  `backend/app/config.py` when a change makes old lessons stale.
- **Voice and speed.** The input form offers Female / Male and Slow / Normal / Fast (0.9 / 1.0 / 1.1). Female/male map per language:
  Kokoro `hf_alpha` / `hm_omega` (en, hi), Indic-TTS `female` / `male` (ta); Parler has no male Tamil voice and stays on Jaya.
  Timing still comes from the generated audio. Bundled sample audio is female at 1.0x; other choices are voiced live.
- **Re-voice.** The player's "Same lesson in" dropdown calls `POST /api/lessons/{id}/revoice {language}`: the stored English plan
  (`lesson.en.json`) is reused, then translated, voiced, timed and exported as a new lesson with the same topic, level, length, voice and
  speed (a repeat comes from the cache). Bundled samples have no stored plan and answer 409.
- **Speed panel.** Under the player: seconds and peak memory per stage, from `timings.json`. `python scripts/bench.py [lesson_id|--all]`
  (`make bench`) prints the same as a table. Peak RSS is sampled every 0.1 s per stage: the app plus its children (ffmpeg, the capture
  browser); the Ollama server is a separate process and is measured only during planning (`plan (ollama)`), and with the model on a GPU
  its RSS is small.
- **Not done:** a fourth language (optional item; left out at feature freeze).

Measured through the app on this laptop: English lesson (male voice) planned in 10 s, voiced in 47 s, smooth MP4 in 30 s; re-voiced into
Hindi in 113 s total (plan reused in 0.002 s, translate 23 s, voice 48 s, export 43 s), peak 1.85 GB during export. Kokoro ran at
0.85-1.14x real time in these runs against 0.25x when measured alone earlier (re-measured in step 12, below).

### Mini quiz (bonus B1)

After the last scene, the player shows a multiple-choice quiz over the stage, one question at a time. Picking an option gives
instant feedback (a green tick on the right answer, a red cross on a wrong pick), then the explanation and Next. The end card shows
the score ("2 / 3") and Replay lesson. Keys are 1-4 to pick and Enter for Next, buttons are at least 44 px, and on phones the quiz
takes the stage's place. The UI words (`frontend/src/i18n/strings.ts`) follow the lesson language and use the stage's Indic fonts.
A lesson without a quiz ends exactly as before.

- **One planner call.** The quiz is part of the same Ollama reply as the lesson. The forced output format requires it, and the
  prompt asks for 3 questions about the lesson's own scenes, with 4 short options each, one correct, and a one-sentence
  explanation. The few-shot Python-loop example carries a quiz. Quiz words do not count toward the narration budget.
- **Never costs the lesson.** The quiz is taken out of the reply before the lesson is validated and is checked on its own
  (`clean_quiz` in `backend/app/planner/validate.py`): question up to 160 characters, 4 unique options of 1-80, `answer_index` 0-3,
  explanation up to 200, the usual markup screen, English only, and no "all/none of the above". A bad question is dropped, and fewer
  than 2 good ones drops the quiz. Warnings go to `planner_raw.txt`, and `quiz_dropped` goes to `timings.json`. A bad quiz never
  triggers a retry or a fallback. Drill: `BLU_DRILL=quiz-garbage` (`scripts/drill.py --only quiz-garbage`).
- **Answers shuffled.** Options are shuffled with a seed from the lesson id and `answer_index` follows. In testing the model put
  the answer in the same place every time, for example "[2, 2, 2]".
- **Translated like scene text.** Questions, options and explanations go through `protect.py`. Code-like options such as
  `range(3)` stay as written. A question whose translated options collide or come out too long stays whole in English, and a
  failed quiz translation leaves the English quiz. The lesson's own translation is never affected.
- **Not narrated, not in the MP4.** The quiz is copied into `timeline.json` (optional `quiz`, checked against the lesson schema)
  for the player only. Exporting the same lesson with and without its quiz gave 1302 / 1302 identical frames, 43.41 s each, and
  byte-identical audio.
- **Fallback.** `shared/samples/python_loop.{en,hi,ta}.json` carry a hand-written 3-question quiz. The Hindi and Tamil need a
  native speaker's check before the demo, as do the UI words.
- **Switch.** `QUIZ_QUESTIONS` in `.env`: 3 (default), 2, or 0 to turn the quiz off. `PIPELINE_VERSION` is 15 (B2), so cached lessons
  made without a quiz are not reused.

**Planner time with the quiz** (dev laptop, CPU only with `OLLAMA_NUM_GPU=0`, 45 s lessons, seconds per planner call):

| Topic | no quiz | 3 questions | 2 questions |
|---|---|---|---|
| How do vaccines work? | 30.8, 30.7 | 51.8, 53.2 | 56.6, 46.6 |
| What is gravity? | 30.0 | 50.1, 49.1 | 46.5, 42.9 |
| How does a hash table work? | 32.0, 29.6 | 58.6 | 51.3, 54.3 |
| **Mean per call** | **30.6** | **52.6 (+22.0)** | **49.7 (+19.1)** |

Two values in a cell mean the first plan was rejected and retried (for over-long diagram labels, the step-13 rule), so the plan
took both calls. The quiz adds about 22 s per call on this CPU, more than the 8-12 s estimate, and puts a call at about 50 s.
Two questions save only about 3 s, because most of the cost is the quiz itself and the longer example in the prompt. So the
default stays at 3 questions. On a CPU-only laptop where the 5-minute budget is tight, `QUIZ_QUESTIONS=0` saves about 22 s per call.
With the GPU, as in normal use on this laptop, plans took 14-24 s with the quiz.

Three new topics (vaccines, gravity, hash tables) were planned in English and re-voiced into Hindi and Tamil. All nine lessons
showed their quiz: 3 questions each, except vaccines, where an "all of the above" question was dropped and 2 remained. Feedback
was checked in the player in English (desktop), Hindi (desktop) and Tamil (phone width).

### Learning habit: next topics, streak, revise list (bonus B2)

No account and no server state: everything personal stays in this browser.

- **Next topics.** The same planner call returns `next_topics`: two English topics, each one step harder or one step sideways.
  English is what the try-next request sends. For Hindi and Tamil lessons, translation adds `next_topic_labels` for the button text.
  Invalid or missing topics are dropped, never retried (`clean_next_topics`). The fallback is the matching sample's entry in
  `shared/next_topics.json` (all four samples have one, with hi/ta labels), and with no entry there are no suggestions. Both fields
  are carried in `timeline.json`.
- **Try next.** Two cards appear on the quiz end card, or under the player at the end of a lesson without a quiz. Tapping one opens the
  input page with the topic, level, language, length, voice and speed filled in, and generation starts at once with the usual
  progress view.
- **Streak.** A lesson counts when its quiz is finished, or when 90% of it has played if it has no quiz. Days are the device's local
  calendar day (`YYYY-MM-DD`, not UTC). The same day changes nothing, the next day adds 1, a gap of 2 or more days restarts at 1,
  and a clock moved backwards changes nothing. A flame badge shows the count on the input page and the end card.
- **Revise list.** A "Save to revise" toggle is on the end card, and a quiz score below 2/3 adds the lesson by itself. The input page
  lists saved lessons newest first, with title, language and score. Tapping one re-opens `/lesson/:id` from the lesson files on
  disk, which works offline. Each row has a Remove button. The list keeps at most 50 entries.
- **Storage.** One localStorage key, `blu.habit.v1` = `{version: 1, streak: {count, last_day}, revise: [...]}`
  (`frontend/src/habit/storage.ts`). Every read and write is guarded. If storage is blocked or the JSON is corrupt, the habit UI hides
  itself and lessons play as usual. Cleared site data simply starts fresh.
- **Tests.** `npm test` in `frontend/` (Vitest, 20 tests) covers the streak rules (same day, next day, month and year ends, gaps,
  clock moved backwards), corrupt or blocked storage, and the revise cap. `make test` runs it after the typecheck. The backend tests
  are in `backend/tests/test_next_topics.py`.
- **Checked in the browser.** A low quiz score was auto-saved to Revise and re-opened from the input page. The streak went 1 to 2 with
  the page's clock moved forward a day (`Date` overridden in the page; the laptop's clock was not changed). In a Hindi lesson the end
  card showed the Hindi words, and Try next started a new Hindi lesson that was planned live. Corrupt and cleared storage both left
  the app working.
- **Known rough edge.** The Hindi and Tamil labels are IndicTrans2 output and can be clumsy: "Python for loop" came out as
  "लूप के लिए पायथन". The request itself stays English, so the next lesson is still right.

### One-page lesson summary (bonus B3)

`/summary/:id` is a one-page A4 summary built only from the lesson's own JSON (`lesson.json`). There is no second model call: the
page and the PDF route never touch Ollama. The page shows:
- the title and level;
- one block per scene, in two columns: the heading, and the first sentence of the narration as the key point (the whole narration if
  it is one sentence; a short opener such as "Welcome!" is skipped);
- each `code_walkthrough` in a mono box (12 lines at most, then "...");
- each diagram as a small SVG, drawn by the player's own `DiagramScene` at its final state;
- the quiz as a worksheet, with the answer key at the bottom;
- the two next topics;
- a footer reading "Made offline with Blu Visual Teacher" and the date.

All text is rendered as React text nodes. Labels are in `strings.ts` (en/hi/ta), with the stage's Indic fonts and line height.

- **One page, always.** The sheet is exactly the A4 printable area (`@page { size: A4; margin: 12mm }`) and is measured on screen
  after the fonts load. If it overflows, it shrinks in this order: drop the diagrams, cut key points to 140 characters at a word,
  cut code to 6 lines, then use smaller type. Anything still over is clipped by the sheet, so it can never spill onto a second page.
- **Print.** "Print / Save as PDF" on the page calls `window.print()`, with no backend involved. "Summary" appears on the player's end
  card and next to the MP4 download, with "Summary PDF" beside it.
- **Server PDF.** `GET /api/lessons/{id}/summary.pdf` opens `/summary/:id?print=1` in the capture browser, waits until the sheet has
  fitted itself (after `document.fonts.ready`), and prints it as A4 with backgrounds to `outputs/lessons/<id>/summary.<lang>.pdf`.
  The file is cached and made again only when `lesson.json` or the app build is newer. It took about 1.6 s here; a cached copy came
  back in 4 ms.
- **Checked.** The three B1 topics (vaccines, gravity, hash tables) in en, hi and ta all fit one A4 page both as the server PDF and
  as the browser print. Each title was in the right script and nothing overflowed. The longest, the Tamil hash-table summary, took
  the first shrink step (diagrams dropped).
- **Tests** (`backend/tests/test_summary.py`, real Chromium, real PDFs, pages counted in the file):
  - the fallback lesson in en, hi and ta gives one page;
  - a 6-scene lesson with code, diagrams, a quiz and next topics gives one page;
  - a lesson with no quiz and no next topics renders cleanly;
  - an overfull Hindi lesson shrinks in order without clipping;
  - the headings and title come from the lesson;
  - the cache is reused and invalidated correctly;
  - the PDF route works with outbound network blocked.

  `frontend/src/summary/text.test.ts` covers the key-point, cutting and shrink rules.
- **Not done here:** adding a summary PDF per language to the Step 12 drill matrix, and a summary PDF beside the submission MP4s.

### Offline testing and hardening (step 12)

```
make offline-check                 # python scripts/check_offline.py [--deep]
make drill ARGS=--wifi-off         # python scripts/drill.py: 18-lesson matrix + 6 failure drills -> docs/offline-test.md
python scripts/bench.py --run      # fresh 60 s lessons in en/hi/ta -> docs/bench.md (OLLAMA_NUM_GPU=0 for a CPU-only planner)
make serve-lan                     # the app on the LAN for the phone check; python scripts/phone_check.py emulates one
```

Without make, `make serve-lan` is `(cd frontend && npm run build)` then
`.venv/Scripts/python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000`.

- **`check_offline.py`** forces `HF_HUB_OFFLINE` / `TRANSFORMERS_OFFLINE`, blocks every non-loopback socket inside its own process, then checks
  that the Ollama model, IndicTrans2, Kokoro, Indic-TTS (and Parler when `TAMIL_TTS=parler`), the fonts, the samples and their bundled
  narration, FFmpeg (libx264 + aac), Playwright and a launchable Chromium/Chrome/Edge are all on disk. It also scans the source and the
  *built* frontend for external URLs (XML namespace URIs and React's error-decoder text are allowed). `--deep` runs IndicTrans2, Kokoro and
  Indic-TTS once with the network blocked. It exits non-zero with the list of what is missing.
- **Drills.** `scripts/drill.py` runs the real pipeline in-process behind the same socket guard. The six drills are: Ollama unreachable
  (`OLLAMA_URL` on a closed port), planner junk (`BLU_DRILL=planner-garbage`), `models/indictrans2` renamed, `models/indic-tts-ta` renamed,
  `models/indic-parler-tts` renamed with `TAMIL_TTS=parler`, and capture browser failing (`BLU_DRILL=export-fail`). Each one must end with
  a playable lesson and the matching badge in the player (fallback lesson / translation unavailable / MP4 export failed + Retry export).
  Renamed folders are put back afterwards, and again on the next run if a run was killed. `BLU_DRILL` is read per call and is empty in normal use.
- **Results on this laptop** (i7-13650HX, 24 GB): 18/18 matrix lessons and 6/6 drills passed, every matrix lesson with a smooth MP4
  (`docs/offline-test.md`). These runs used the in-process socket guard **with Wi-Fi still on**: the Wi-Fi-off run on both laptops is still
  to do (`make drill ARGS=--wifi-off`), and so is the real phone check. Hindi and Tamil lessons run 45-73 s for a 45 s target (the translated
  narration is longer than the English plan the length is budgeted for).

Bugs found and fixed, each with a regression test:

| Bug | Fix | Test |
|---|---|---|
| With `TAMIL_TTS=parler` and no Parler model, the sample fallback looked for Parler-voiced sample audio, which is not bundled, so a fresh laptop failed the job (it only passed here because Parler audio from step 9 was still in `outputs/cache`) | the fallback always voices the sample with the engine its audio was bundled with (`registry.bundled_engine`) | `test_tamil_voice_fallback_uses_bundled_audio_whichever_engine_is_chosen` |
| After an app restart a lesson whose MP4 export failed (or never finished) showed a Download button that never enabled and no Retry | the export error is saved in `export.json`; the status rebuilt from disk reports it, the export mode and the typed topic | `test_failed_export_is_still_reported_after_a_restart`, `test_lesson_whose_export_never_finished_offers_retry_after_a_restart` |
| "plan (ollama)" peak memory showed ~120 MB: the model runs in Ollama's child `llama-server.exe` (2.4 GB) | count the Ollama processes and all their children, once each | `test_planner_memory_counts_the_ollama_runner_child` |
| Indic-TTS drops "=" and "+", so "i = 0" was read as "i zero" | spoken words from `shared/glossary.json` `tts_symbols` (Tamil; captions keep the symbol) | `test_tamil_symbols_are_spoken_not_dropped` |
| Phone jank: the caption bar re-wrapped its text every frame and each new cue measured dozens of prefixes (about 80 ms stalls at 6x CPU throttle); each new scene measured its labels on first draw | caption wraps are memoised and every cue and scene layout is measured once when the lesson loads (hidden, never painted) | `scripts/phone_check.py` (exits non-zero on jank) |
| `doctor.py` still looked for `.ttf` Indic fonts (now `.woff2`) and required the opt-in Parler model | woff2 names; Parler is a warning unless `TAMIL_TTS=parler` | `python scripts/doctor.py` |

**Phone check (emulated).** `scripts/phone_check.py` plays a lesson in a Pixel 5 viewport with the CPU slowed 4x or 6x and records every frame.
After the fixes, the 72.6 s Tamil photosynthesis lesson ran at a median of 7 ms per frame, with a p95 of 14 ms and a worst frame of 62 ms (4x), or 21 ms and 132 ms (6x).
0.3% / 1.3% of frames were over 33 ms; before the fixes the worst frames were 181 ms / 444 ms. Only `transform` and `opacity` animate, plus the arrow
draw-on (`stroke-dashoffset`), which the profile did not implicate, so it stays.

**Memory.** Loading, using and unloading IndicTrans2, Indic-TTS and Kokoro three times in one process settles at about 0.9 GB resident after the
first round and does not grow (torch / onnxruntime keep their arenas). Peaks: the planner 2.4 GB in Ollama (planning only; `keep_alive: 0`
frees it), translation about 1.7 GB, Tamil voice about 2.1 GB, export up to 2.2 GB (app + Chromium + ffmpeg).

### Design pass (D1, tag `design-1`)

The pass changed the app chrome around the stage:
- **Tokens.** Spacing and type-scale tokens, plus chrome-only colour tokens that meet WCAG AA.
- **Buttons.** One button system (primary, secondary, ghost) with hover, pressed, focus and disabled states.
- **Phone layout.** The 360 px layout works with no horizontal scroll.
- **States.** Real loading, empty and error states.

The stage CSS was not touched and the `make sample` MP4 is frame-for-frame identical (ffmpeg `framemd5`). Only `transform` and `opacity`
animate in the chrome, and not at all under "reduce motion". The problem list and before/after notes are in `docs/design-pass.md`.

D2 (tag `design-2`) is a second pass with the taste-skill's linter and real-browser inspector. It made these changes:
- **Headline.** Display size on the input page; at most two lines for every title.
- **Hairlines and resting shadows.** Removed: secondary controls are flat tone fills.
- **Labels and glyphs.** The eyebrow kicker is gone, and our own SVG icons replace emoji and glyphs.
- **Colour.** One accent.
- **Motion.** A short staggered entrance (transform and opacity only).

The only remaining inspector FAIL is `few-pictures`: it wants found photographs from the internet, which H2 rules out.
That and the other open items are explained in `docs/design-pass.md`.

### HTTP API (`backend/app/api/routes.py`)

| Method and path | What it does |
|---|---|
| `POST /api/lessons` `{topic, level, language, target_seconds}` | queues a lesson (one runs at a time), returns `{job_id, ...status}` |
| `GET /api/lessons/{id}` | status: `stage` (plan, translate, voice, timing, export, done), `progress`, `fallback_used`, `timings`, `timeline_ready`, `mp4_ready` |
| `GET /api/lessons/{id}/events` | the same status as Server-Sent Events, until the job is done or failed |
| `POST /api/lessons/{id}/export` | retry the MP4 export (the lesson keeps playing if export fails) |
| `GET /api/lessons/{id}/lesson` | the lesson plan, with `meta.fallback`, `meta.source`, `meta.reason` |
| `GET /api/lessons/{id}/summary.pdf` | one-page A4 summary PDF (bonus B3), cached as `summary.<lang>.pdf` |

Results (`timeline.json`, `lesson.wav`, `lesson.mp4`, `captions.srt`) are served under `/media/lessons/{id}/`.
