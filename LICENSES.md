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
| Indic Parler-TTS (`ai4bharat/indic-parler-tts`) | TTS model | Tamil narration (voice `jaya`) | Apache-2.0 (confirm on the model card when downloading) | Hugging Face `ai4bharat/indic-parler-tts` (AI4Bharat), gated, saved in `models/indic-parler-tts/` |
| parler-tts | Python library | runs Indic Parler-TTS on CPU | Apache-2.0 | github.com/huggingface/parler-tts |
| Description tokenizer of Indic Parler-TTS (its text encoder, `models/indic-parler-tts/description_tokenizer/`) | tokenizer files | encodes the fixed speaker description | Apache-2.0 | Hugging Face, repo named in the model's `config.json` (`text_encoder._name_or_path`) |
| psutil | Python library | physical core count for `torch.set_num_threads` | BSD-3-Clause | PyPI |
| Pre-generated fallback narration (`shared/tts_cache/*.flac`) | generated audio | sample lessons play with no TTS at demo time | output of the Kokoro (Apache-2.0) and Indic Parler-TTS models above; our own text | `scripts/pregen_audio.py` |
| Descript Audio Codec (`descript-audio-codec`) and `descript-audiotools` | Python libraries | the audio codec Indic Parler-TTS decodes speech with (its weights are inside the Parler checkpoint) | MIT | PyPI (pulled in by parler-tts) |
| torchaudio / SciPy | Python libraries | audio ops used by parler-tts | BSD-2-Clause / BSD-3-Clause | PyPI (pulled in by parler-tts) |
| Other libraries parler-tts loads at runtime | Python libraries | config, logging, codec helpers | MIT: argbind, julius, einops, flatten-dict, ffmpy, randomname, docstring_parser, rich, markdown-it-py, mdurl, PyYAML; Apache-2.0: absl-py, tensorboard, importlib_resources; BSD-3-Clause: protobuf, Jinja2, MarkupSafe; BSD-2-Clause: Pygments; MIT-CMU: Pillow; MPL-2.0: certifi; MPL-2.0 AND MIT: tqdm | PyPI; list taken from the package metadata of what `import parler_tts` and a Tamil synthesis load (step 9). parler-tts also installs librosa, numba, matplotlib and IPython, which the app does not load |
| AI4Bharat Indic-TTS Tamil checkpoint (FastPitch + HiFi-GAN, `ta.zip`) | TTS model | Plan B Tamil narration (`TAMIL_TTS=indic-tts`, voices female, male) | MIT (released in the MIT-licensed `AI4Bharat/Indic-TTS` repo; no separate model licence is stated) | github.com/AI4Bharat/Indic-TTS release `v1-checkpoints-release`, saved in `models/indic-tts-ta/` |
| coqui-tts (Idiap fork of Coqui TTS) | Python library | runs the Indic-TTS FastPitch + HiFi-GAN models | MPL-2.0 (used unmodified as a library) | PyPI `coqui-tts` 0.28.0, installed without dependencies |
| coqui-tts-trainer / coqpit-config / torchcodec | Python libraries | model loading and config for coqui-tts; torchcodec is required to import it (not used for audio) | Apache-2.0 / MIT / BSD-3-Clause | PyPI |
| Other libraries the Indic-TTS engine loads | Python libraries | text cleaning, sentence handling, numerics | MIT: monotonic-alignment-search, pysbd, platformdirs, six; ISC: anyascii, librosa; BSD-3-Clause: cloudpickle, fsspec, joblib, lazy-loader, pooch; BSD-2-Clause: decorator; BSD: numba, mpmath, sympy; BSD-2-Clause AND Apache-2.0 WITH LLVM-exception: llvmlite; Apache-2.0: msgpack | PyPI; list from the package metadata of what one Indic-TTS synthesis loads (step 9) |
| Noto Sans Devanagari (`NotoSansDevanagari-Regular.woff2`, `NotoSansDevanagari-Bold.woff2`, converted from the hinted TTF) | font | Hindi headings and captions (also burned into the MP4) | SIL Open Font License 1.1 | github.com/notofonts/notofonts.github.io (hinted TTF) |
| Noto Sans Tamil (`NotoSansTamil-Regular.woff2`, `NotoSansTamil-Bold.woff2`, converted from the hinted TTF) | font | Tamil headings and captions (also burned into the MP4) | SIL Open Font License 1.1 | github.com/notofonts/notofonts.github.io (hinted TTF) |
| fontTools / brotli | Python libraries (dev only) | convert the Noto TTFs to WOFF2 (`scripts/fonts_to_woff2.py`) | MIT / MIT | PyPI |
