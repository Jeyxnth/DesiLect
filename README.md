# DesiLect (Blu Visual Teacher)

## Setup

```
make setup
.venv/Scripts/python scripts/download_models.py kokoro   # one-time, needs network (H2 exception)
```

## Run offline

## Models and licences

| Model / library | Used for | Licence |
|---|---|---|
| Kokoro-82M via kokoro-onnx (voices `hf_alpha`, `hm_omega`) | English (Indian accent) and Hindi TTS | Apache-2.0 (kokoro-onnx: MIT) |
| eSpeak NG (via espeakng-loader) | phonemes | GPL-3.0-or-later |
| ONNX Runtime, NumPy, soundfile | CPU inference, audio | MIT / BSD-3-Clause |

Full list: `LICENSES.md`.

> Translation review status: `shared/samples/python_loop.hi.json` and `python_loop.ta.json` are machine-assisted translations that **need a native speaker check** (`_review`).

## Tested laptops

## Architecture
