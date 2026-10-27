"""Static offline check (H2): no external URLs, CDNs, font links or telemetry in source."""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCAN = [REPO_ROOT / "frontend" / "src", REPO_ROOT / "frontend" / "index.html", REPO_ROOT / "backend" / "app"]
EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".json"}
URL_RE = re.compile(r"https?://[^\s\"'`)>]+")
LOCAL_RE = re.compile(r"^https?://(localhost|127\.0\.0\.1|0\.0\.0\.0)(:\d+)?(/|$)")
BAD_WORDS = re.compile(r"fonts\.googleapis|fonts\.gstatic|cdn\.|unpkg|jsdelivr|googletagmanager|sentry|analytics", re.I)


def iter_files():
    for base in SCAN:
        if base.is_file():
            yield base
        elif base.is_dir():
            for p in base.rglob("*"):
                if p.is_file() and p.suffix in EXTENSIONS and "node_modules" not in p.parts and "__pycache__" not in p.parts:
                    yield p


def main() -> int:
    problems: list[str] = []
    for path in iter_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            for url in URL_RE.findall(line):
                if not LOCAL_RE.match(url):
                    problems.append(f"{path.relative_to(REPO_ROOT)}:{n}: external URL {url}")
            if BAD_WORDS.search(line):
                problems.append(f"{path.relative_to(REPO_ROOT)}:{n}: suspicious reference: {line.strip()[:80]}")
    for p in problems:
        print(p)
    print("offline-check:", "FAIL" if problems else "OK (no external URLs in frontend/src, frontend/index.html, backend/app)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
