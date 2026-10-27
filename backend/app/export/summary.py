"""Server-side summary PDF (bonus B3): the /summary/:id page printed to A4 by the capture browser. No model call."""
from __future__ import annotations

import threading
from pathlib import Path

from .capture import _launch, ensure_frontend_built

READY_TIMEOUT_S = 30
_lock = threading.Lock()  # one browser at a time (H3)


def summary_pdf_path(out_dir: Path, language: str) -> Path:
    return out_dir / f"summary.{language}.pdf"


def is_stale(pdf: Path, *sources: Path) -> bool:
    """A cached PDF is reused until one of its sources (the lesson JSON, the built summary page) is newer than it."""
    if not pdf.is_file():
        return True
    made = pdf.stat().st_mtime
    return any(src.is_file() and src.stat().st_mtime > made for src in sources)


def render_summary_pdf(lesson_id: str, base_url: str, dest: Path) -> Path:
    """Open {base_url}/summary/<id>?print=1, wait until the sheet has fitted itself to one page (fonts loaded),
    and print it as A4 with backgrounds. Written atomically to dest."""
    from playwright.sync_api import sync_playwright

    ensure_frontend_built()
    with _lock, sync_playwright() as p:
        browser = _launch(p)
        try:
            page = browser.new_page()
            page.goto(f"{base_url.rstrip('/')}/summary/{lesson_id}?print=1", wait_until="networkidle")
            page.wait_for_function("window.__summaryReady === true", timeout=READY_TIMEOUT_S * 1000)
            page.evaluate("document.fonts.ready.then(() => true)")
            tmp = dest.with_name(dest.stem + ".tmp.pdf")
            page.pdf(path=str(tmp), format="A4", print_background=True, prefer_css_page_size=True)
            tmp.replace(dest)
        finally:
            browser.close()
    return dest
