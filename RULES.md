# RULES

Obey these in every step. Hard rules are disqualifying; ground rules are how we build.

## HARD RULES (breaking one disqualifies us)

- **H1** No external AI APIs or cloud services: no OpenAI, Gemini, Claude, ElevenLabs, Google Translate, Google/Microsoft cloud voices. All models run locally.
- **H2** Fully offline at runtime. No CDN links, no Google Fonts URLs, no telemetry, no runtime model downloads. `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1` are set by the app. Only `scripts/download_models.py` may use the network.
- **H3** CPU-only, 8-16 GB RAM. Load one model at a time and unload it after its stage. No CUDA-only code paths.
- **H4** Data, not code. The LLM returns JSON only. Never eval, exec, import or render as HTML anything the model wrote. Code in `code_walkthrough` is displayed as text only. Visuals come only from our components.
- **H5** Every model, voice, font and asset is listed in `LICENSES.md` and README with its licence before it is committed.
- **H6** Light for students: the player must run smoothly on a modest phone (SVG + CSS, no heavy animation or 3D libraries).

## GROUND RULES (how we build)

- **G1** `shared/` is the contract. Do not change a schema without updating both backend validation and frontend types in the same change.
- **G2** The demo never breaks: every stage has a fallback (planner -> sample lesson; translation -> pre-translated sample; TTS -> cached sample audio; smooth export -> keyframe export).
- **G3** Determinism: every visual state is a pure function of `(timeline, t)`. No `setTimeout`, no CSS transitions in render mode.
- **G4** Audio-first timing: only `backend/app/timing/timeline.py` decides durations.
- **G5** Keep code, numbers and technical terms in English inside translated narration.
- **G6** Every stage logs its wall time and writes `outputs/lessons/<id>/timings.json`.
- **G7** Small, working increments: after each step `make test` passes and `make dev` runs.
- **G8** No secrets, no API keys, no accounts needed.
- **G9** Python 3.11, FastAPI, Pydantic v2, pytest. Node 20, Vite, React 18, TypeScript strict.
