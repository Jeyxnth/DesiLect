# DesiLect (Blu Visual Teacher)

## Setup

```
make setup
.venv/Scripts/python scripts/download_models.py kokoro ollama   # one-time, needs network (H2 exception)
python scripts/doctor.py --smoke                         # preflight: checks every dependency, prints the fix for each gap
```

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

Built-in samples (the G2 fallback when the planner fails): `python_loop` (programming), `photosynthesis` (science),
`pythagorean_theorem` (maths), each in en/hi/ta. The closest one to the requested topic is used, and the UI says so.

The planner takes about 35 s per plan on a CPU-only laptop (about 65 s when the first plan is rejected and retried);
with a GPU Ollama is about 4x faster. Set `OLLAMA_NUM_GPU=0` in `.env` to measure the CPU-only time on a GPU laptop.

## Models and licences

| Model / library | Used for | Licence |
|---|---|---|
| Kokoro-82M via kokoro-onnx (voices `hf_alpha`, `hm_omega`) | English (Indian accent) and Hindi TTS | Apache-2.0 (kokoro-onnx: MIT) |
| Llama 3.2 3B Instruct via Ollama (`llama3.2:3b`) | lesson planner. **Built with Llama.** | Llama 3.2 Community License |
| eSpeak NG (via espeakng-loader) | phonemes | GPL-3.0-or-later |
| ONNX Runtime, NumPy, soundfile | CPU inference, audio | MIT / BSD-3-Clause |

Full list: `LICENSES.md`.

> Translation review status: the Hindi and Tamil samples (`shared/samples/*.hi.json`, `*.ta.json`) are machine-assisted translations that **need a native speaker check**.

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
