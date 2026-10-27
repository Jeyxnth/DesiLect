"""Player smoothness on an emulated modest phone (H6): Pixel 5 viewport, CPU slowed down, frame times while playing.

    python scripts/phone_check.py                              # latest lesson, app at http://127.0.0.1:8000
    python scripts/phone_check.py f7928753a388 --throttle 6    # a given lesson, 6x slower CPU

Needs the app running (make dev-backend, or make serve-lan). This only approximates a phone; the real check is
opening http://<laptop IP>:8000 on a phone on the same hotspot (make serve-lan). Exits non-zero when playback
janks: more than 5% of frames over 33 ms (below 30 fps) or a single stall over 500 ms.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.config import get_settings  # noqa: E402
from app.export.capture import _launch  # noqa: E402

# Records every animation-frame interval (ms) from the moment Play is pressed.
PROBE = """
window.__frames = [];
let last = performance.now();
const loop = (now) => { window.__frames.push(now - last); last = now; requestAnimationFrame(loop); };
requestAnimationFrame(loop);
"""


def latest_lesson() -> str | None:
    root = get_settings().outputs_dir / "lessons"
    found = sorted(root.glob("*/timeline.json"), key=lambda p: p.stat().st_mtime) if root.is_dir() else []
    return found[-1].parent.name if found else None


def measure(base: str, lesson: str, throttle: float, seconds: float) -> dict[str, float]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = _launch(p)
        ctx = browser.new_context(**p.devices["Pixel 5"])
        page = ctx.new_page()
        page.goto(f"{base}/lesson/{lesson}", wait_until="networkidle")
        page.wait_for_selector(".stage-canvas")
        page.wait_for_timeout(1500)  # fonts load and the player warms its layouts, as a learner would wait
        ctx.new_cdp_session(page).send("Emulation.setCPUThrottlingRate", {"rate": throttle})
        page.evaluate(PROBE)
        page.get_by_role("button", name="Play").first.click()
        page.wait_for_timeout(seconds * 1000)
        frames = sorted(page.evaluate("window.__frames")[5:])
        browser.close()
    n = len(frames)
    return {
        "fps": round(n / seconds, 1),
        "p50_ms": round(frames[n // 2], 1),
        "p95_ms": round(frames[int(0.95 * n)], 1),
        "worst_ms": round(frames[-1], 1),
        "over_33ms_pct": round(100 * sum(f > 33.4 for f in frames) / n, 1),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lesson_id", nargs="?", help="lesson to play (default: the latest)")
    ap.add_argument("--base", default="http://127.0.0.1:8000", help="where the app is served")
    ap.add_argument("--throttle", type=float, default=4, help="CPU slowdown factor (4 ~ a modest phone)")
    ap.add_argument("--seconds", type=float, default=30, help="how long to play")
    args = ap.parse_args()
    lesson = args.lesson_id or latest_lesson()
    if not lesson:
        print("no lesson yet; generate one first")
        return 1
    r = measure(args.base, lesson, args.throttle, args.seconds)
    print(json.dumps({"lesson": lesson, "throttle": args.throttle, **r}))
    janky = r["over_33ms_pct"] > 5 or r["worst_ms"] > 500
    print("phone-check:", "JANK" if janky else "smooth")
    return 1 if janky else 0


if __name__ == "__main__":
    sys.exit(main())
