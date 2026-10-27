"""Stage times and peak memory of a lesson (make bench): reads outputs/lessons/<id>/timings.json.

    python scripts/bench.py                 # the most recently finished lesson
    python scripts/bench.py 7ff7c16f8930    # a given lesson
    python scripts/bench.py --all           # one row per lesson, total time
    python scripts/bench.py --run           # make a fresh 60 s lesson in en, hi and ta, append them to docs/bench.md

--run is the weakest-laptop benchmark (step 12): it plans, translates, voices and exports for real (no reuse
cache), then appends this machine's specs and one table per language to docs/bench.md, flagging any lesson
whose total passes the 5-minute budget. Set OLLAMA_NUM_GPU=0 to keep the planner on the CPU.
Peak RSS is sampled every 0.1 s during each stage: the app process plus its children (ffmpeg, the capture browser).
The planner's model runs inside the Ollama server, a separate process; its peak is shown as "plan (ollama)".
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import platform
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.cache.store import read_json  # noqa: E402
from app.config import REPO_ROOT, get_settings  # noqa: E402

BENCH_MD = REPO_ROOT / "docs" / "bench.md"
BUDGET_S = 300  # a 60 s lesson should be ready (MP4 included) in about 5 minutes on the weakest laptop

# timings.json key -> label, in pipeline order
STAGES = [
    ("plan", "plan"),
    ("translate", "translate"),
    ("narrate", "voice + timing"),
    ("export_smooth", "export (smooth)"),
    ("export_capture", "export capture (keyframe)"),
    ("export_encode", "export encode (keyframe)"),
]


def _lessons() -> list[Path]:
    root = get_settings().outputs_dir / "lessons"
    found = [p for p in root.glob("*/timings.json")] if root.is_dir() else []
    return sorted(found, key=lambda p: p.stat().st_mtime)


def table(timings: dict) -> list[tuple[str, str, str]]:
    rss = timings.get("rss_mb", {})
    rows = []
    for key, label in STAGES:
        if isinstance(timings.get(key), (int, float)):
            rows.append((label, f"{timings[key]:.1f}", f"{rss[key]:.0f}" if key in rss else "-"))
        if key == "plan" and "plan_ollama" in rss:
            rows.append(("plan (ollama)", "", f"{rss['plan_ollama']:.0f}"))
    total = sum(timings[k] for k, _ in STAGES if isinstance(timings.get(k), (int, float)))
    rows.append(("total", f"{total:.1f}", f"{max(rss.values()):.0f}" if rss else "-"))
    return rows


def print_table(lesson: str, timings: dict) -> None:
    tl = timings.get("timeline", {})
    head = f"lesson {lesson}"
    if tl:
        head += f": {tl.get('total_seconds', 0):.1f} s of audio, {tl.get('tts_engine', '?')} rtf {tl.get('tts_rtf')}"
    print(head)
    print(f"  {'stage':<28}{'seconds':>9}{'peak RSS MB':>14}")
    for label, secs, mb in table(timings):
        print(f"  {label:<28}{secs:>9}{mb:>14}")


def cpu_name() -> str:
    """The marketing name ("13th Gen Intel(R) Core(TM) i7-13650HX"); platform.processor() is only the family."""
    if sys.platform == "win32":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as k:
                return str(winreg.QueryValueEx(k, "ProcessorNameString")[0]).strip()
        except OSError:
            pass
    elif Path("/proc/cpuinfo").is_file():
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor() or platform.machine()


def machine() -> str:
    import psutil

    vm = psutil.virtual_memory()
    return (f"{cpu_name()}, {psutil.cpu_count(logical=False)} cores / "
            f"{psutil.cpu_count()} threads, {vm.total / 2**30:.1f} GB RAM ({vm.available / 2**30:.1f} GB free at start), "
            f"{platform.system()} {platform.release()}")


def run(topic: str, languages: list[str], seconds: int) -> int:
    """Make one fresh lesson per language and append the tables to docs/bench.md."""
    from app.pipeline.jobs import JOBS, ConceptRequest
    from app.pipeline.orchestrator import run_pipeline

    s = get_settings()
    head = [
        f"\n## {dt.datetime.now():%Y-%m-%d %H:%M}: {platform.node()}\n",
        f"- Machine: {machine()}",
        f"- Planner {s.ollama_model} (OLLAMA_NUM_GPU={os.environ.get('OLLAMA_NUM_GPU', 'unset')}), "
        f"Tamil voice {s.tamil_tts}, topic \"{topic}\", {seconds} s target, beginner.\n",
    ]
    sections, over = [], []
    for lang in languages:
        job = JOBS.create(ConceptRequest(topic=topic, level="beginner", language=lang, target_seconds=seconds))  # type: ignore[arg-type]
        print(f"{lang}: lesson {job.id} ...", flush=True)
        start = time.perf_counter()
        run_pipeline(job.id)
        wall = time.perf_counter() - start
        timings = read_json(s.outputs_dir / "lessons" / job.id / "timings.json")
        print_table(job.id, timings)
        tl = timings.get("timeline", {})
        done = JOBS.get(job.id)
        mode = done.export_mode if done and done.mp4_ready else f"failed ({done.export_error if done else '?'})"
        verdict = "within budget" if wall <= BUDGET_S else f"**over the {BUDGET_S // 60}-minute budget**"
        if wall > BUDGET_S:
            over.append(lang)
        fallback = f" (fallback used: {done.fallback_reason})" if done and done.fallback_used else ""
        rtf = tl.get("tts_rtf")
        lines = [
            f"### {lang}: {tl.get('total_seconds', 0):.1f} s lesson in {wall:.0f} s wall, {verdict}{fallback}\n",
            f"Voice {tl.get('tts_engine', '?')} at {rtf if rtf is not None else '-'}x real time; MP4 export: {mode}.\n",
            "| stage | seconds | peak RSS MB |",
            "|---|---:|---:|",
        ]
        lines += [f"| {label} | {secs or '-'} | {mb} |" for label, secs, mb in table(timings)]
        sections.append("\n".join(lines))
    if not BENCH_MD.is_file():
        BENCH_MD.parent.mkdir(parents=True, exist_ok=True)
        BENCH_MD.write_text("# Benchmarks\n\nAppended by `python scripts/bench.py --run`; newest run last. Peak RSS is the "
                            "app plus its children (ffmpeg, the capture browser); \"plan (ollama)\" is the Ollama server and its model runner.\n",
                            encoding="utf-8")
    with BENCH_MD.open("a", encoding="utf-8") as f:
        f.write("\n".join(head) + "\n" + "\n\n".join(sections) + "\n")
    print(f"appended to {BENCH_MD.relative_to(REPO_ROOT)}" + (f"; over budget: {', '.join(over)}" if over else ""))
    return 1 if over else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lesson_id", nargs="?", help="lesson to report (default: the latest)")
    ap.add_argument("--all", action="store_true", help="one line per lesson")
    ap.add_argument("--run", action="store_true", help="make fresh lessons and append them to docs/bench.md")
    ap.add_argument("--topic", default="How does a Python loop work?", help="topic for --run")
    ap.add_argument("--languages", default="en,hi,ta", help="comma-separated, for --run")
    ap.add_argument("--seconds", type=int, default=60, help="lesson length for --run")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args.run:
        return run(args.topic, [x.strip() for x in args.languages.split(",") if x.strip()], args.seconds)

    lessons = _lessons()
    if args.all:
        for path in lessons:
            rows = table(read_json(path))
            print(f"{path.parent.name:<32} total {rows[-1][1]:>7} s   peak {rows[-1][2]:>6} MB")
        return 0
    path = (get_settings().outputs_dir / "lessons" / args.lesson_id / "timings.json") if args.lesson_id else (lessons[-1] if lessons else None)
    if path is None or not path.is_file():
        print("no timings yet; generate a lesson or run `make sample` first")
        return 1
    print_table(path.parent.name, read_json(path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
