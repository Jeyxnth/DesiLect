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
`.venv/bin/python`. If the other laptop already has everything, copying `models/` across is enough for step 4.

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
previous/next scene, R replay. `.venv/Scripts/python scripts/render_sample.py` (`make sample`) renders a bundled sample with no planner at all.

## How fallback works

The demo never breaks: each stage has a fallback, and the screen always says when one was used.

| Stage fails | What plays instead | What the screen says |
|---|---|---|
| Planner: Ollama stopped, model missing, timeout, or two invalid plans | the closest of four built-in lessons (Python loop, binary search, photosynthesis, Pythagoras), in the chosen language | "Fallback lesson used: a built-in sample", the reason, and which sample |
| Translation: model missing or bad output | a built-in sample uses its checked translation; a new lesson stays in English | "Translation unavailable" |
| Voice: model missing, out of memory, engine error | the closest sample, voiced from its bundled audio (no model has to load) | "Fallback lesson used", reason "Voice generation failed" |
| Smooth MP4 export: browser error, over its time budget, or a bad file | the keyframe export (one frame per change) | the MP4 still downloads |
| Both exports | nothing to download, but the lesson plays in the browser | "MP4 export failed" with a **Retry export** button |

The planner's JSON is checked against `shared/schema/lesson.schema.json` plus content rules (scene count, word budget for the
length, short distinct diagram labels, code at most 12 x 50, no markup, English only). A rejected first plan is retried once with
the errors listed. Failure drills for all of this: `.venv/Scripts/python scripts/drill.py` (`make drill`; see step 12 below).

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
- **Speed.** A lesson takes about 2 to 3 minutes on the dev laptop with the planner on its CPU. With a GPU, Ollama plans in about
  10 s. The opt-in Parler Tamil voice is 5 to 9 times slower than real time.
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

### HTTP API (`backend/app/api/routes.py`)

| Method and path | What it does |
|---|---|
| `POST /api/lessons` `{topic, level, language, target_seconds}` | queues a lesson (one runs at a time), returns `{job_id, ...status}` |
| `GET /api/lessons/{id}` | status: `stage` (plan, translate, voice, timing, export, done), `progress`, `fallback_used`, `timings`, `timeline_ready`, `mp4_ready` |
| `GET /api/lessons/{id}/events` | the same status as Server-Sent Events, until the job is done or failed |
| `POST /api/lessons/{id}/export` | retry the MP4 export (the lesson keeps playing if export fails) |
| `GET /api/lessons/{id}/lesson` | the lesson plan, with `meta.fallback`, `meta.source`, `meta.reason` |

Results (`timeline.json`, `lesson.wav`, `lesson.mp4`, `captions.srt`) are served under `/media/lessons/{id}/`.
