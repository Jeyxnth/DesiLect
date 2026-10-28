"""Measure how well the planner meets the requested length: real Ollama runs, first attempt only (the prompt's effect).

    python scripts/measure_length.py --label before
    python scripts/measure_length.py --label after --compare docs/length/before.json

Sends each topic x length x level to the local model exactly as the app does (same system prompt, user prompt,
JSON schema and options) and records, per plan: narration words against the budget, scenes, words and sentences per
scene, and whether it passes validation on the first try. Results go to docs/length/<label>.json and a table is
printed. Needs Ollama running with the planner model. Takes about 20 x 20 s on a CPU laptop.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.config import get_settings  # noqa: E402
from app.planner.ollama_client import OllamaClient, lesson_format_schema  # noqa: E402
from app.planner.prompts import build_system_prompt, build_user_prompt, word_budget  # noqa: E402
from app.planner.validate import extract_json_text, parse_and_validate  # noqa: E402

TOPICS = ["How does binary search work?", "Photosynthesis", "How do vaccines work?", "How does a hash table work?",
          "Explain how caffeine works"]
CASES = [(60, "beginner"), (60, "intermediate"), (90, "beginner"), (90, "intermediate")]
OUT_DIR = REPO_ROOT / "docs" / "length"
SENTENCE = re.compile(r"[.!?](?=\s|$)")


def measure(client: OllamaClient, topic: str, seconds: int, level: str, quiz: int) -> dict:
    start = time.perf_counter()
    raw = client.chat_json(build_system_prompt(level, seconds, quiz), build_user_prompt(topic, level, seconds), lesson_format_schema(quiz))
    took = round(time.perf_counter() - start, 1)
    budget = word_budget(seconds)
    row = {"topic": topic, "seconds": seconds, "level": level, "budget": budget, "seconds_taken": took}
    try:
        data = json.loads(extract_json_text(raw))
        narr = [s.get("narration", "") for s in data.get("scenes", []) if isinstance(s, dict)]
    except (json.JSONDecodeError, AttributeError):
        return {**row, "words": 0, "ratio": 0.0, "scenes": 0, "per_scene": [], "sentences": [], "passes": False, "errors": ["invalid JSON"]}
    per_scene = [len(n.split()) for n in narr]
    words = sum(per_scene)
    _, errors = parse_and_validate(raw, seconds)
    return {**row, "words": words, "ratio": round(words / budget, 2), "scenes": len(narr), "per_scene": per_scene,
            "sentences": [len(SENTENCE.findall(n)) or 1 for n in narr], "passes": not errors, "errors": errors[:3]}


def table(rows: list[dict], other: list[dict] | None = None) -> str:
    def cell(rs: list[dict]) -> str:
        if not rs:
            return "-"
        ratios = sorted(r["ratio"] for r in rs)
        passed = sum(r["passes"] for r in rs)
        return f"{statistics.median(ratios):.0%} median ({min(ratios):.0%}-{max(ratios):.0%}), {passed}/{len(rs)} pass"
    lines = ["| Length, level | " + ("Before | After |" if other else "Words written / asked, first try |"),
             "|---|---|" + ("---|" if other else "")]
    for seconds, level in CASES:
        pick = lambda rows_: [r for r in rows_ if r["seconds"] == seconds and r["level"] == level]  # noqa: E731
        lines.append(f"| {seconds} s, {level} | " + (f"{cell(pick(other))} | " if other else "") + f"{cell(pick(rows))} |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--label", required=True)
    ap.add_argument("--compare", type=Path, help="an earlier results file, shown as the Before column")
    ap.add_argument("--seconds", type=int, help="measure only this length (the table compares only it)")
    ap.add_argument("--level", choices=["beginner", "intermediate"], help="measure only this level")
    args = ap.parse_args()
    client = OllamaClient()
    quiz = get_settings().quiz_questions
    rows: list[dict] = []
    for seconds, level in CASES:
        if (args.seconds and seconds != args.seconds) or (args.level and level != args.level):
            continue
        for topic in TOPICS:
            row = measure(client, topic, seconds, level, quiz)
            rows.append(row)
            print(f"{seconds}s {level:12s} {topic[:32]:32s} {row['words']:3d}/{row['budget']} words "
                  f"({row['ratio']:.0%}) scenes={row['scenes']} per-scene={row['per_scene']} "
                  f"{'PASS' if row['passes'] else 'fail: ' + '; '.join(row['errors'])[:90]}  [{row['seconds_taken']}s]", flush=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{args.label}.json"
    out.write_text(json.dumps({"model": client.model, "rows": rows}, indent=1, ensure_ascii=False), encoding="utf-8")
    other = json.loads(args.compare.read_text(encoding="utf-8"))["rows"] if args.compare else None
    if other:
        other = [r for r in other if (not args.seconds or r["seconds"] == args.seconds) and (not args.level or r["level"] == args.level)]
    print("\n" + table(rows, other) + f"\n\nsaved {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
