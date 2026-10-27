# Offline test matrix and failure drills

Appended by `python scripts/drill.py`; newest run last.

## 2026-10-27 23:55 on LOQ: Intel64 Family 6 Model 183 Stepping 1, GenuineIntel, 20 threads, 24 GB RAM, Windows-11-10.0.26300-SP0

- Network: outbound sockets blocked in the test process; Wi-Fi not confirmed off (pass `--wifi-off` when it is). Blocked attempts: none.
- Planner llama3.2:3b, Tamil voice engine indic-tts. Passed 6/6.

| case | result | plan | voiced | audio s | wall s | peak MB | MP4 | badge shown |
|---|---|---|---|---:|---:|---:|---|---|
| ollama-down | pass | sample:python_loop | hi (kokoro) | 50.2 | 50 | 1237 | smooth | Fallback lesson used (sample:python_loop): The local planner (Ollama) is not running. |
| planner-garbage | pass | sample:python_loop | en (kokoro) | 43.4 | 43 | 1250 | smooth | Fallback lesson used (sample:python_loop): The planner's lesson failed validation twice. |
| translation-missing | pass | ollama:llama3.2:3b | en (kokoro) | 41.0 | 91 | 1279 | smooth | Translation unavailable (narrated in English) |
| indic-tts-missing | pass | sample:python_loop | ta (indic-tts) | 57.8 | 94 | 2301 | smooth | Fallback lesson used (sample:python_loop): Voice generation failed (FileNotFoundError). |
| parler-missing | pass | sample:python_loop | ta (parler) | 51.0 | 83 | 2154 | smooth | Fallback lesson used (sample:python_loop): Voice generation failed (FileNotFoundError). |
| export-fail | pass | ollama:llama3.2:3b | en (kokoro) | 34.1 | 39 | 1424 | failed | MP4 export failed + Retry export |

## 2026-10-28 00:27: LOQ

- Machine: 13th Gen Intel(R) Core(TM) i7-13650HX, 14 cores / 20 threads, 23.7 GB RAM (6.7 GB free at start), Windows 11
- Network: outbound sockets blocked in the test process; Wi-Fi not confirmed off (pass `--wifi-off` when it is). Blocked attempts: none.
- Planner llama3.2:3b, Tamil voice engine indic-tts. Passed 18/18.

| case | result | plan | voiced | audio s | wall s | peak MB | MP4 | badge shown |
|---|---|---|---|---:|---:|---:|---|---|
| loop/en/beginner | pass | ollama:llama3.2:3b | en (kokoro) | 40.6 | 73 | 1273 | smooth | - |
| loop/en/intermediate | pass | ollama:llama3.2:3b | en (kokoro) | 40.2 | 76 | 1294 | smooth | - |
| loop/hi/beginner | pass | ollama:llama3.2:3b | hi (kokoro) | 68.4 | 156 | 1638 | smooth | - |
| loop/hi/intermediate | pass | sample:python_loop | hi (kokoro) | 50.2 | 67 | 1648 | smooth | Fallback lesson used (sample:python_loop): The planner's lesson failed validation twice. |
| loop/ta/beginner | pass | ollama:llama3.2:3b | ta (indic-tts) | 61.5 | 115 | 2179 | smooth | - |
| loop/ta/intermediate | pass | ollama:llama3.2:3b | ta (indic-tts) | 58.8 | 105 | 2296 | smooth | - |
| photosynthesis/en/beginner | pass | ollama:llama3.2:3b | en (kokoro) | 34.5 | 70 | 2072 | smooth | - |
| photosynthesis/en/intermediate | pass | ollama:llama3.2:3b | en (kokoro) | 40.8 | 71 | 2086 | smooth | - |
| photosynthesis/hi/beginner | pass | ollama:llama3.2:3b | hi (kokoro) | 57.5 | 121 | 2672 | smooth | - |
| photosynthesis/hi/intermediate | pass | ollama:llama3.2:3b | hi (kokoro) | 49.9 | 91 | 2403 | smooth | - |
| photosynthesis/ta/beginner | pass | ollama:llama3.2:3b | ta (indic-tts) | 72.6 | 143 | 2427 | smooth | - |
| photosynthesis/ta/intermediate | pass | ollama:llama3.2:3b | ta (indic-tts) | 63.1 | 96 | 2341 | smooth | - |
| stack/en/beginner | pass | ollama:llama3.2:3b | en (kokoro) | 37.2 | 83 | 2317 | smooth | - |
| stack/en/intermediate | pass | ollama:llama3.2:3b | en (kokoro) | 39.8 | 71 | 2309 | smooth | - |
| stack/hi/beginner | pass | ollama:llama3.2:3b | hi (kokoro) | 44.3 | 95 | 2792 | smooth | - |
| stack/hi/intermediate | pass | ollama:llama3.2:3b | hi (kokoro) | 54.0 | 104 | 2718 | smooth | - |
| stack/ta/beginner | pass | ollama:llama3.2:3b | ta (indic-tts) | 57.8 | 78 | 2340 | smooth | - |
| stack/ta/intermediate | pass | ollama:llama3.2:3b | ta (indic-tts) | 57.6 | 108 | 2512 | smooth | - |

## 2026-10-28 04:24: LOQ

- Machine: 13th Gen Intel(R) Core(TM) i7-13650HX, 14 cores / 20 threads, 23.7 GB RAM (8.4 GB free at start), Windows 11
- Network: outbound sockets blocked in the test process; Wi-Fi not confirmed off (pass `--wifi-off` when it is). Blocked attempts: none.
- Planner llama3.2:3b, Tamil voice engine indic-tts. Passed 1/1.

| case | result | plan | voiced | audio s | wall s | peak MB | MP4 | badge shown |
|---|---|---|---|---:|---:|---:|---|---|
| quiz-garbage | pass | ollama:llama3.2:3b | en (kokoro) | 25.5 | 53 | 908 | smooth | - |
