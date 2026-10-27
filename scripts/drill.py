"""Offline test matrix and failure drills (step 12). Run it with Wi-Fi off.

    python scripts/drill.py --wifi-off              # matrix (3 topics x 3 languages x 2 levels) + every drill
    python scripts/drill.py --drills                # drills only
    python scripts/drill.py --matrix                # matrix only
    python scripts/drill.py --only parler-missing   # one drill (or matrix case, e.g. "stack/ta/beginner")

Each case runs the real pipeline (plan, translate, voice, time, MP4 export) in this process with outbound
sockets blocked (scripts/check_offline.py), checks that it ended with a playable lesson (timeline + audio)
and that the UI shows the right badge, and appends a results table to docs/offline-test.md.
Drills: Ollama unreachable, planner returning junk (BLU_DRILL), a model folder renamed (restored afterwards,
also on the next run if this one was killed), the capture browser failing (BLU_DRILL).
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import platform
import sys
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from bench import machine  # noqa: E402
from check_offline import BLOCKED, block_outbound  # noqa: E402  (also forces HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE)

from app.cache.store import lesson_dir, read_json  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.pipeline.jobs import JOBS, ConceptRequest  # noqa: E402
from app.pipeline.orchestrator import run_pipeline  # noqa: E402
from app.tts.registry import release_all  # noqa: E402

REPORT = REPO_ROOT / "docs" / "offline-test.md"
OFF = ".drill-off"  # suffix of a model folder renamed by a drill

TOPICS = {
    "loop": "How does a Python loop work?",
    "photosynthesis": "Photosynthesis",
    "stack": "What is a stack data structure?",
}
DEAD_OLLAMA = "http://127.0.0.1:9"  # nothing listens there: the app sees Ollama as stopped


@dataclass
class Case:
    name: str
    topic: str
    level: str = "beginner"
    language: str = "en"
    env: dict[str, str] = field(default_factory=dict)
    rename: str | None = None  # models/<rename> is moved away for this case
    expect: str = "ok"  # ok | plan-fallback | translation-fallback | voice-fallback | export-error
    seconds: int = 45


DRILLS = [
    Case("ollama-down", "Newton's first law of motion", language="hi", env={"OLLAMA_URL": DEAD_OLLAMA}, expect="plan-fallback"),
    Case("planner-garbage", "Newton's first law of motion", env={"BLU_DRILL": "planner-garbage"}, expect="plan-fallback"),
    Case("translation-missing", "What is a stack data structure?", language="ta", rename="indictrans2", expect="translation-fallback"),
    Case("indic-tts-missing", "What is a stack data structure?", language="ta", rename="indic-tts-ta", expect="voice-fallback"),
    Case("parler-missing", "What is a stack data structure?", language="ta", env={"TAMIL_TTS": "parler"},
         rename="indic-parler-tts", expect="voice-fallback"),
    Case("export-fail", "How does a Python loop work?", env={"BLU_DRILL": "export-fail"}, expect="export-error"),
]


def matrix() -> list[Case]:
    return [Case(f"{key}/{lang}/{level}", topic, level, lang)
            for key, topic in TOPICS.items() for lang in ("en", "hi", "ta") for level in ("beginner", "intermediate")]


def restore_models() -> None:
    """Put back model folders a killed earlier run left renamed."""
    models = get_settings().models_dir
    for p in models.glob(f"*{OFF}"):
        target = p.with_name(p.name[: -len(OFF)])
        if not target.exists():
            p.rename(target)
            print(f"restored {target}")


def wav_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as w:
        return w.getnframes() / w.getframerate()


def badges(job: Any, lesson: dict[str, Any]) -> list[str]:
    """What the player shows (frontend/src/pages/PlayerPage.tsx, components/FallbackNotice.tsx)."""
    meta = lesson.get("meta", {})
    out = []
    if meta.get("fallback"):
        out.append(f"Fallback lesson used ({meta.get('source')}): {meta.get('reason')}")
    if meta.get("translation_fallback"):
        out.append("Translation unavailable (narrated in English)")
    if job.export_error:
        out.append("MP4 export failed + Retry export")
    elif job.export_mode == "keyframe":
        out.append("MP4 made with the keyframe export")
    return out


def run_case(case: Case) -> dict[str, Any]:
    saved = {k: os.environ.get(k) for k in case.env}
    os.environ.update(case.env)
    get_settings.cache_clear()
    release_all()
    moved = None
    if case.rename:
        src = get_settings().models_dir / case.rename
        moved = src.with_name(src.name + OFF)
        src.rename(moved)
    try:
        req = ConceptRequest(topic=case.topic, level=case.level, language=case.language, target_seconds=case.seconds)  # type: ignore[arg-type]
        job = JOBS.create(req)
        start = time.perf_counter()
        run_pipeline(job.id)
        wall = time.perf_counter() - start
    finally:
        if moved is not None:
            moved.rename(moved.with_name(moved.name[: -len(OFF)]))
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        get_settings.cache_clear()
        release_all()

    job = JOBS.get(job.id)
    out = lesson_dir(job.id)
    lesson = read_json(out / "lesson.json") if (out / "lesson.json").is_file() else {}
    meta = lesson.get("meta", {})
    timeline = read_json(out / "timeline.json") if (out / "timeline.json").is_file() else {}
    wav = out / "lesson.wav"
    audio = wav_seconds(wav) if wav.is_file() else 0.0
    playable = job.state == "done" and job.timeline_ready and bool(timeline.get("scenes")) and audio > 1.0
    problems = [] if playable else [f"not playable (state={job.state}, error={job.error})"]

    reason = (meta.get("reason") or "").lower()
    if case.expect == "ok":
        if not job.mp4_ready:
            problems.append(f"no MP4: {job.export_error}")
    elif case.expect == "plan-fallback":
        if not meta.get("fallback"):
            problems.append("expected the fallback lesson badge")
    elif case.expect == "translation-fallback":
        if not (meta.get("translation_fallback") or meta.get("fallback")):
            problems.append("expected the translation-unavailable badge")
    elif case.expect == "voice-fallback":
        if not (meta.get("fallback") and "voice generation failed" in reason):
            problems.append("expected the fallback badge naming the failed voice")
        if lesson.get("language") != case.language:
            problems.append(f"narrated in {lesson.get('language')}, not {case.language}")
    elif case.expect == "export-error":
        if job.mp4_ready or not job.export_error:
            problems.append("expected an MP4 export error")
    if case.expect != "export-error" and not job.mp4_ready:
        problems.append(f"no MP4: {job.export_error}")
    timings = read_json(out / "timings.json") if (out / "timings.json").is_file() else {}
    rss = timings.get("rss_mb", {})
    return {
        "case": case.name,
        "id": job.id,
        "lang": lesson.get("language", "?"),
        "plan": meta.get("source", "?"),
        "audio_s": audio,
        "wall_s": wall,
        "export": job.export_mode or ("failed" if job.export_error else "-"),
        "peak_mb": max(rss.values()) if rss else None,
        "badges": badges(job, lesson),
        "problems": problems,
        "tts": timeline.get("tts_engine") or read_json(out / "timings.json").get("timeline", {}).get("tts_engine", "?")
        if (out / "timings.json").is_file() else "?",
    }


def write_report(results: list[dict[str, Any]], wifi_off: bool) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    s = get_settings()
    lines = [
        f"\n## {dt.datetime.now():%Y-%m-%d %H:%M}: {platform.node()}\n",
        f"- Machine: {machine()}",
        f"- Network: outbound sockets blocked in the test process; Wi-Fi {'**off**' if wifi_off else 'not confirmed off'}"
        f" (pass `--wifi-off` when it is). Blocked attempts: {', '.join(sorted(set(BLOCKED))) or 'none'}.",
        f"- Planner {s.ollama_model}, Tamil voice engine {s.tamil_tts}. "
        f"Passed {sum(not r['problems'] for r in results)}/{len(results)}.\n",
        "| case | result | plan | voiced | audio s | wall s | peak MB | MP4 | badge shown |",
        "|---|---|---|---|---:|---:|---:|---|---|",
    ]
    for r in results:
        verdict = "pass" if not r["problems"] else "**FAIL**: " + "; ".join(r["problems"])
        peak = f"{r['peak_mb']:.0f}" if r["peak_mb"] else "-"
        lines.append(f"| {r['case']} | {verdict} | {r['plan']} | {r['lang']} ({r['tts']}) | {r['audio_s']:.1f} | "
                     f"{r['wall_s']:.0f} | {peak} | {r['export']} | {'; '.join(r['badges']) or '-'} |")
    if not REPORT.is_file():
        REPORT.write_text("# Offline test matrix and failure drills\n\nAppended by `python scripts/drill.py`; newest run last.\n",
                          encoding="utf-8")
    with REPORT.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--matrix", action="store_true", help="only the 18-lesson matrix")
    ap.add_argument("--drills", action="store_true", help="only the failure drills")
    ap.add_argument("--only", action="append", default=[], help="run just this case (repeatable)")
    ap.add_argument("--wifi-off", action="store_true", help="record that Wi-Fi was physically off for this run")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import logging

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    block_outbound()
    restore_models()

    cases = (matrix() if not args.drills else []) + (DRILLS if not args.matrix else [])
    if args.only:
        cases = [c for c in matrix() + DRILLS if c.name in args.only]
        if not cases:
            print("no such case; names:", ", ".join(c.name for c in matrix() + DRILLS))
            return 2
    results = []
    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case.name}: {case.topic!r} {case.language}/{case.level} ...", flush=True)
        r = run_case(case)
        results.append(r)
        print(f"    {'pass' if not r['problems'] else 'FAIL ' + '; '.join(r['problems'])}  "
              f"({r['wall_s']:.0f} s, {r['audio_s']:.1f} s audio, plan {r['plan']}, MP4 {r['export']}) {r['id']}", flush=True)
        for b in r["badges"]:
            print("    badge:", b)
    write_report(results, args.wifi_off)
    failed = [r["case"] for r in results if r["problems"]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed; report appended to {REPORT.relative_to(REPO_ROOT)}")
    if failed:
        print("failed:", ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
