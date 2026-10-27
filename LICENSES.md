# Third-party licences

Every model, voice, font and asset must be listed here (and in README) before it is committed (rule H5).

| Name | Kind | Used for | Licence | Source |
|------|------|----------|---------|--------|
| Kokoro-82M (`kokoro-v1.0.onnx`, `voices-v1.0.bin`; voices hf_alpha, hm_omega) | model + voices | English (Indian accent) and Hindi TTS | Apache-2.0 | thewh1teagle/kokoro-onnx release `model-files-v1.0` (weights by hexgrad) |
| kokoro-onnx | Python library | runs Kokoro on CPU via ONNX Runtime | MIT | PyPI `kokoro-onnx` |
| espeakng-loader / eSpeak NG | library | phonemes for Kokoro | GPL-3.0-or-later (eSpeak NG, loaded as a shared library) | PyPI `espeakng-loader` |
| ONNX Runtime | library | CPU inference | MIT | PyPI `onnxruntime` |
| soundfile / NumPy | libraries | WAV I/O, audio arrays | BSD-3-Clause | PyPI |
