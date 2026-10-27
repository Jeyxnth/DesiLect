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

## Models and licences

| Model / library | Used for | Licence |
|---|---|---|
| Kokoro-82M via kokoro-onnx (voices `hf_alpha`, `hm_omega`) | English (Indian accent) and Hindi TTS | Apache-2.0 (kokoro-onnx: MIT) |
| Llama 3.2 3B Instruct via Ollama (`llama3.2:3b`) | lesson planner. **Built with Llama.** | Llama 3.2 Community License |
| eSpeak NG (via espeakng-loader) | phonemes | GPL-3.0-or-later |
| ONNX Runtime, NumPy, soundfile | CPU inference, audio | MIT / BSD-3-Clause |

Full list: `LICENSES.md`.

> Translation review status: `shared/samples/python_loop.hi.json` and `python_loop.ta.json` are machine-assisted translations that **need a native speaker check** (`_review`).

## Tested laptops

## Architecture
