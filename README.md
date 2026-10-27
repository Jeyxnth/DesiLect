# DesiLect (Blu Visual Teacher)

## Setup

```
make setup
.venv/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu   # CPU-only build
.venv/Scripts/python -m pip install -r backend/requirements-models.txt
.venv/Scripts/hf auth login            # once: IndicTrans2 is gated (accept its terms on huggingface.co first)
.venv/Scripts/python scripts/download_models.py kokoro ollama indictrans2   # one-time, needs network (H2 exception)
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
| Noto Sans, Noto Sans Mono (bundled in `frontend/public/fonts`) | UI, captions, code | SIL Open Font License 1.1 |

Full list: `LICENSES.md`.

> Translation review status: the Hindi and Tamil samples are machine translations that **need a native speaker check**.
> Made by the IndicTrans2 pipeline (step 8): `shared/samples/photosynthesis.{hi,ta}.json`, `shared/samples/binary_search.{hi,ta}.json`.
> Earlier machine-assisted drafts: `shared/samples/python_loop.{hi,ta}.json`, `shared/samples/pythagorean_theorem.{hi,ta}.json`.
> Things to look at: word order around English terms kept by the glossary (e.g. "oxygen", "sorted list"), and diagram labels.

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
