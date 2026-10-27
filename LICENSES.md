# Third-party licences

Every model, voice, font and asset must be listed here (and in README) before it is committed (rule H5).

| Name | Kind | Used for | Licence | Source |
|------|------|----------|---------|--------|
| Kokoro-82M (`kokoro-v1.0.onnx`, `voices-v1.0.bin`; voices hf_alpha, hm_omega) | model + voices | English (Indian accent) and Hindi TTS | Apache-2.0 | thewh1teagle/kokoro-onnx release `model-files-v1.0` (weights by hexgrad) |
| kokoro-onnx | Python library | runs Kokoro on CPU via ONNX Runtime | MIT | PyPI `kokoro-onnx` |
| espeakng-loader / eSpeak NG | library | phonemes for Kokoro | GPL-3.0-or-later (eSpeak NG, loaded as a shared library) | PyPI `espeakng-loader` |
| ONNX Runtime | library | CPU inference | MIT | PyPI `onnxruntime` |
| soundfile / NumPy | libraries | WAV I/O, audio arrays | BSD-3-Clause | PyPI |
| Llama 3.2 3B Instruct (`llama3.2:3b`, via Ollama) | LLM | lesson planner (JSON plans) | Llama 3.2 Community License (requires the "Built with Llama" notice and the Acceptable Use Policy) | Ollama library `llama3.2` (Meta) |
| Ollama | local model server | runs the planner on CPU | MIT | ollama.com |
| httpx | Python library | talks to Ollama on 127.0.0.1 | BSD-3-Clause | PyPI |
| IndicTrans2 en-indic distilled 200M (`ai4bharat/indictrans2-en-indic-dist-200M`) | translation model | English -> Hindi, Tamil (Telugu, Bengali, Marathi ready) | MIT | Hugging Face `ai4bharat/indictrans2-en-indic-dist-200M` (AI4Bharat), saved in `models/indictrans2/` |
| IndicTransToolkit `IndicProcessor` (vendored as a pure-Python port in `backend/app/translate/indic_processor.py`) | code | IndicTrans2 pre/post-processing, Devanagari -> target script | MIT (Copyright (c) Varun Gumma) | PyPI `IndicTransToolkit` 1.1.1 |
| indic-nlp-library-itt / regex | Python libraries | Indic tokenise, detokenise, transliterate; regex engine | MIT / Apache-2.0 | PyPI |
| PyTorch (CPU build) | library | runs IndicTrans2 on CPU | BSD-3-Clause | download.pytorch.org/whl/cpu |
| Transformers | library | loads IndicTrans2 | Apache-2.0 | PyPI `transformers` |
| SentencePiece / sacremoses / huggingface_hub | libraries | tokenisation; model download (download script only) | Apache-2.0 / MIT / Apache-2.0 | PyPI |
| Noto Sans (`NotoSans-Regular.ttf`, `NotoSans-Bold.ttf`) | font | UI, headings, captions (Latin) | SIL Open Font License 1.1 (`frontend/public/fonts/OFL.txt`) | github.com/notofonts/notofonts.github.io (hinted TTF) |
| Noto Sans Mono (`NotoSansMono-Regular.ttf`) | font | code in `code_walkthrough` scenes | SIL Open Font License 1.1 | github.com/notofonts/notofonts.github.io (hinted TTF) |
