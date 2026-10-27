# Third-party licences

Every model, voice, font, tool and library the app uses, with the version we run and the licence as it is
named in its own licence file or model card (rule H5). "Checked against" says where the licence name was read
(step 13). Versions are the ones installed on the development laptop (`pip show`, `npm ls`, `ollama --version`).

**Built with Llama.** The lesson planner is Meta Llama 3.2, licensed under the Llama 3.2 Community License,
Copyright (c) Meta Platforms, Inc. All Rights Reserved. Use is subject to the Llama 3.2 Acceptable Use Policy.

## Models and voices

| Name | Version | Used for | Licence | Source | Checked against |
|---|---|---|---|---|---|
| Llama 3.2 3B Instruct (`llama3.2:3b`, Q4_K_M) | Llama 3.2, released 25 Sep 2024 | lesson planner (English JSON plans) | **Llama 3.2 Community License Agreement** (requires "Built with Llama" to be displayed, the Acceptable Use Policy, and a copy of the agreement when redistributed) | Ollama library `llama3.2:3b` (Meta) | `ollama show llama3.2:3b --license` (local) |
| IndicTrans2 en-indic distilled 200M (`ai4bharat/indictrans2-en-indic-dist-200M`) | Hugging Face snapshot in `models/indictrans2/` | English to Hindi and Tamil translation | **MIT License**, Copyright (c) AI4Bharat | Hugging Face (AI4Bharat, gated) | `models/indictrans2/LICENSE` and `README.md` (`license: mit`) |
| Kokoro-82M, ONNX export (`kokoro-v1.0.onnx`, `voices-v1.0.bin`; voices `hf_alpha`, `hm_omega`) | v1.0 (`model-files-v1.0`) | English (Indian accent) and Hindi narration | **Apache-2.0** ("This is an Apache-licensed model") | weights by hexgrad (`hexgrad/Kokoro-82M`); ONNX files from the `thewh1teagle/kokoro-onnx` release | `hexgrad/Kokoro-82M` model card (no card file ships with the two ONNX files) |
| AI4Bharat Indic-TTS Tamil (FastPitch + HiFi-GAN, `ta.zip`; voices `female`, `male`) | `v1-checkpoints-release` | Tamil narration (default engine) | **MIT License** (the licence of the `AI4Bharat/Indic-TTS` repository that releases the checkpoints; the release states no separate model licence) | github.com/AI4Bharat/Indic-TTS releases, saved in `models/indic-tts-ta/` | repository LICENSE (the zip has no licence file) |
| Indic Parler-TTS (`ai4bharat/indic-parler-tts`; voice `jaya`) | Hugging Face snapshot in `models/indic-parler-tts/` | Tamil narration, opt-in (`TAMIL_TTS=parler`) | **apache-2.0** | Hugging Face (AI4Bharat, gated) | `models/indic-parler-tts/README.md` front matter (`license: apache-2.0`) |
| Indic Parler-TTS description tokenizer (from `google/flan-t5-large`) | tokenizer files only | encodes the fixed speaker description | **Apache 2.0** | Hugging Face `google/flan-t5-large` (repo named in the Parler `config.json`, `text_encoder._name_or_path`) | `google/flan-t5-large` model card |
| Descript Audio Codec weights | inside the Parler checkpoint | Parler's audio decoder | MIT (descript-audio-codec) | bundled in `ai4bharat/indic-parler-tts` | package licence |

Generated assets: the bundled sample narration `shared/tts_cache/*.flac` is output of Kokoro (Apache-2.0) and Indic-TTS (MIT) speaking our
own sample text; `submissions/*.mp4` are rendered by this app (planner Llama 3.2, see "Built with Llama" above).

## Fonts

| Name | Files | Used for | Licence | Source | Checked against |
|---|---|---|---|---|---|
| Noto Sans | `NotoSans-Regular.ttf`, `NotoSans-Bold.ttf` | UI, headings, English captions | **SIL Open Font License, Version 1.1** | github.com/notofonts/notofonts.github.io (hinted TTF) | `frontend/public/fonts/OFL.txt` |
| Noto Sans Mono | `NotoSansMono-Regular.ttf` | code in `code_walkthrough` scenes | SIL Open Font License, Version 1.1 | same | same |
| Noto Sans Devanagari | `NotoSansDevanagari-{Regular,Bold}.woff2` (converted from the hinted TTF) | Hindi headings and captions, burned into the MP4 | SIL Open Font License, Version 1.1 | same | same |
| Noto Sans Tamil | `NotoSansTamil-{Regular,Bold}.woff2` (converted from the hinted TTF) | Tamil headings and captions, burned into the MP4 | SIL Open Font License, Version 1.1 | same | same |

## Tools

| Name | Version | Used for | Licence | Source |
|---|---|---|---|---|
| Ollama | 0.40.2 | local model server for the planner (127.0.0.1 only) | MIT | ollama.com |
| FFmpeg with libx264 | 8.1 (gyan.dev `full_build`, `--enable-gpl --enable-version3`) | MP4 encode (H.264 + AAC), ffprobe checks | FFmpeg: **GPL-3.0-or-later** for this build; libx264: GPL-2.0-or-later. Used as a separate program, not linked or shipped | `winget install Gyan.FFmpeg` |
| Playwright for Python | 1.64.1 | drives a headless browser to capture the render page | Apache-2.0 | PyPI `playwright` |
| Chromium (Playwright build), or the installed Chrome / Edge | Playwright's bundled build; this laptop fell back to Chrome 155 | headless capture | Chromium: BSD-3-Clause (plus its third-party notices); Chrome / Edge: their vendors' terms, used as installed and not shipped | `python -m playwright install chromium` |
| eSpeak NG (inside `espeakng-loader`: `espeak-ng.dll` + `espeak-ng-data`) | as bundled by espeakng-loader 0.2.4 | phonemes for Kokoro | eSpeak NG: GPL-3.0-or-later; espeakng-loader: MIT License | PyPI `espeakng-loader` (github.com/thewh1teagle/espeakng-loader) |
| Node.js | 20 required (dev laptop: 22.20.0) | frontend build | MIT | nodejs.org |

## Frontend libraries (`frontend/package.json`)

| Name | Version | Licence |
|---|---|---|
| React, React DOM | 18.3.1 | MIT |
| Vite, @vitejs/plugin-react | 5.4.21, 4.7.0 | MIT |
| TypeScript | 5.9.3 | Apache-2.0 |
| @types/react, @types/react-dom | 18.3.31, 18.3.7 | MIT |

## Python libraries (versions on the dev laptop; licence from the package metadata or its LICENSE file)

| Name | Version | Used for | Licence |
|---|---|---|---|
| Python | 3.13.3 (target 3.11) | runtime | PSF-2.0 |
| FastAPI | 0.162.0 | HTTP API | MIT |
| Uvicorn | 0.54.0 | server | BSD-3-Clause |
| Pydantic | 2.14.1 | request models | MIT |
| jsonschema | 4.26.0 | lesson and timeline validation | MIT |
| httpx | 0.28.1 | talks to Ollama on 127.0.0.1 | BSD-3-Clause |
| NumPy | 2.5.4 | audio arrays | BSD-3-Clause (and bundled 0BSD, MIT, Zlib, CC0-1.0 parts) |
| soundfile | 0.14.0 | WAV / FLAC I/O | BSD-3-Clause |
| kokoro-onnx | 0.6.1 | runs Kokoro | MIT License |
| ONNX Runtime | 1.31.1 | CPU inference for Kokoro | MIT License |
| PyTorch (CPU build) | 2.14.1+cpu | IndicTrans2, Indic-TTS, Parler | BSD-3-Clause (with Apache-2.0 and other bundled parts) |
| Transformers | 4.46.3 (pinned) | loads IndicTrans2 and Parler | Apache-2.0 |
| SentencePiece / sacremoses / huggingface_hub | 0.2.2 / 0.2.0 / 0.36.2 | tokenisation; model download (download script only) | Apache-2.0 / MIT / Apache-2.0 |
| IndicTransToolkit `IndicProcessor` (vendored pure-Python port, `backend/app/translate/indic_processor.py`) | port of 1.1.1 | IndicTrans2 pre/post-processing | MIT (Copyright (c) Varun Gumma) |
| indic-nlp-library-itt / regex | 0.1.1 / 2026.9.29 | Indic tokenise and transliterate; regex engine | MIT / Apache-2.0 AND CNRI-Python |
| parler-tts | 0.2.2 | runs Indic Parler-TTS (also installs libraries Indic-TTS needs) | Apache License 2.0 |
| descript-audio-codec / descript-audiotools | 1.0.0 | Parler's audio codec | MIT |
| torchaudio / SciPy / librosa | 2.11.0 / 1.18.1 / 1.0.0 | audio ops used by parler-tts and coqui-tts | BSD-2-Clause / BSD-3-Clause / ISC |
| coqui-tts (Idiap fork of Coqui TTS) | 0.28.0 | runs Indic-TTS FastPitch + HiFi-GAN, used unmodified as a library | MPL-2.0 |
| coqui-tts-trainer / coqpit-config / torchcodec | 0.4.0 / 0.2.5 / 0.17.0 | config and loading for coqui-tts (torchcodec only to import it) | Apache-2.0 / MIT / BSD-3-Clause |
| psutil | 7.2.2 | core count for torch threads; peak memory per stage | BSD-3-Clause |
| pytest | 8.4.2 | tests (dev) | MIT |
| fontTools / brotli | 4.67.0 / 1.2.1 | convert Noto TTF to WOFF2 (`scripts/fonts_to_woff2.py`, dev only) | MIT / MIT |
| Other libraries parler-tts loads at runtime | | config, logging, codec helpers | MIT: argbind, julius, einops, flatten-dict, ffmpy, randomname, docstring_parser, rich, markdown-it-py, mdurl, PyYAML; Apache-2.0: absl-py, tensorboard, importlib_resources; BSD-3-Clause: protobuf, Jinja2, MarkupSafe; BSD-2-Clause: Pygments; MIT-CMU: Pillow; MPL-2.0: certifi; MPL-2.0 AND MIT: tqdm (from the package metadata of what `import parler_tts` and a Tamil synthesis load, step 9) |
| Other libraries the Indic-TTS engine loads | | text cleaning, sentence handling, numerics | MIT: monotonic-alignment-search, pysbd, platformdirs, six; ISC: anyascii; BSD-3-Clause: cloudpickle, fsspec, joblib, lazy-loader, pooch; BSD-2-Clause: decorator; BSD: numba, mpmath, sympy; BSD-2-Clause AND Apache-2.0 WITH LLVM-exception: llvmlite; Apache-2.0: msgpack (step 9) |
