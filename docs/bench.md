# Benchmarks

Appended by `python scripts/bench.py --run`; newest run last. Peak RSS is the app plus its children (ffmpeg, the capture browser); "plan (ollama)" is the Ollama server and its model runner. "Voice ... x real time" counts only sentences not in the voice cache, model load included, so it reads high when most sentences were cached.

## 2026-10-28 01:01: LOQ

- Machine: 13th Gen Intel(R) Core(TM) i7-13650HX, 14 cores / 20 threads, 23.7 GB RAM (7.4 GB free at start), Windows 11
- Planner llama3.2:3b (OLLAMA_NUM_GPU=0), Tamil voice indic-tts, topic "How does a Python loop work?", 60 s target, beginner.

### en: 58.0 s lesson in 112 s wall, within budget

Voice kokoro at 1.916x real time; MP4 export: smooth.

| stage | seconds | peak RSS MB |
|---|---:|---:|
| plan | 45.2 | 63 |
| plan (ollama) | - | 2662 |
| voice + timing | 11.6 | 524 |
| export (smooth) | 53.5 | 1301 |
| total | 110.3 | 2662 |

### hi: 62.2 s lesson in 144 s wall, within budget

Voice kokoro at 0.59x real time; MP4 export: smooth.

| stage | seconds | peak RSS MB |
|---|---:|---:|
| plan | 44.8 | 113 |
| plan (ollama) | - | 2661 |
| translate | 18.7 | 1727 |
| voice + timing | 18.0 | 1474 |
| export (smooth) | 60.1 | 2101 |
| total | 141.6 | 2661 |

### ta: 77.4 s lesson in 173 s wall, within budget

Voice indic-tts at 1.274x real time; MP4 export: smooth.

| stage | seconds | peak RSS MB |
|---|---:|---:|
| plan | 46.4 | 946 |
| plan (ollama) | - | 2651 |
| translate | 10.8 | 1686 |
| voice + timing | 37.0 | 2102 |
| export (smooth) | 76.3 | 2144 |
| total | 170.6 | 2651 |
