"""Benchmark stage wall times and peak RAM on this laptop (make bench). TODO(step 12)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.cache.store import lesson_dir, read_json  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("lesson_id", nargs="?", default="sample-en", help="lesson whose timings.json to print")
    args = ap.parse_args()

    path = lesson_dir(args.lesson_id, create=False) / "timings.json"
    if not path.is_file():
        print(f"no timings for {args.lesson_id}; run `make sample` first (TODO(step 12): full bench)")
        return 0
    print(json.dumps(read_json(path), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
