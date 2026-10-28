"""Bonus B3: one-page summary PDF, printed from /summary/<id> by the capture browser. No model call."""
import os
import re
import shutil
import socket
import sys
import time

import httpx
import pytest

from app.cache.store import lesson_dir, write_json
from app.config import REPO_ROOT, SAMPLES_DIR
from app.export.summary import is_stale
from app.planner.fallback import fallback_lesson
from app.planner.validate import validate_lesson


def pages(pdf: bytes) -> int:
    """Page objects in a PDF (no pypdf needed): /Type /Page, not /Pages."""
    return len(re.findall(rb"/Type\s*/Page(?![s\w])", pdf))


def _missing_prereq():
    if not (REPO_ROOT / "frontend" / "dist" / "index.html").is_file() and shutil.which("npm") is None:
        return "frontend not built"
    try:
        import playwright  # noqa: F401
    except ImportError:
        return "playwright not installed"
    return None


def six_scene_lesson() -> dict:
    """A long lesson: 6 scenes (code and diagrams), a 3-question quiz and next topics."""
    loop = fallback_lesson("How does a Python loop work?", "beginner", "en")
    photo = fallback_lesson("Photosynthesis", "beginner", "en")
    diagrams = [s for s in photo["scenes"] if s["type"] == "diagram"]
    loop["scenes"] = loop["scenes"][:3] + diagrams[:2] + loop["scenes"][3:]
    loop["title"] = "Loops and leaves: a long six-scene lesson"
    assert len(loop["scenes"]) == 6 and loop["quiz"] and loop["next_topics"] and validate_lesson(loop) == []
    return loop


def bare_lesson() -> dict:
    lesson = fallback_lesson("Photosynthesis", "beginner", "en")
    lesson.pop("quiz", None), lesson.pop("next_topics", None), lesson.pop("next_topic_labels", None)
    return lesson


@pytest.fixture(scope="module")
def server():
    if _missing_prereq():
        pytest.skip(_missing_prereq())
    from app.export.capture import local_server

    with local_server() as url:
        yield url


def make(lesson_id: str, lesson: dict) -> None:
    out = lesson_dir(lesson_id)
    for stale in out.glob("summary.*.pdf"):
        stale.unlink()
    write_json(out / "lesson.json", lesson)


@pytest.mark.parametrize("lang", ["en", "hi", "ta"])
def test_fallback_lesson_summary_is_one_page_in_every_language(server, lang):
    lesson_id = f"summary-test-{lang}"
    make(lesson_id, fallback_lesson("How does a Python loop work?", "beginner", lang))
    r = httpx.get(f"{server}/api/lessons/{lesson_id}/summary.pdf", timeout=60)
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF") and pages(r.content) == 1
    assert (lesson_dir(lesson_id) / f"summary.{lang}.pdf").is_file()


def test_six_scenes_and_a_quiz_still_fit_one_page(server):
    make("summary-test-six", six_scene_lesson())
    r = httpx.get(f"{server}/api/lessons/summary-test-six/summary.pdf", timeout=60)
    assert r.status_code == 200 and pages(r.content) == 1


def test_no_quiz_and_no_next_topics_renders_cleanly(server):
    from playwright.sync_api import sync_playwright

    from app.export.capture import _launch

    make("summary-test-bare", bare_lesson())
    with sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{server}/summary/summary-test-bare?print=1", wait_until="networkidle")
        page.wait_for_function("window.__summaryReady === true", timeout=30_000)
        text = page.inner_text(".summary-sheet")
        overflow = page.evaluate("(() => { const s = document.querySelector('.summary-sheet'); return s.scrollHeight - s.clientHeight; })()")
        browser.close()
    assert not errors and overflow <= 1
    assert "Quiz" not in text and "Try next" not in text and "Answers" not in text
    assert "Made offline with CodeStorm24" in text
    r = httpx.get(f"{server}/api/lessons/summary-test-bare/summary.pdf", timeout=60)
    assert pages(r.content) == 1


def test_summary_text_comes_only_from_the_lesson(server):
    from playwright.sync_api import sync_playwright

    from app.export.capture import _launch

    lesson = fallback_lesson("Photosynthesis", "beginner", "ta")
    make("summary-test-ta-text", lesson)
    with sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page()
        page.goto(f"{server}/summary/summary-test-ta-text?print=1", wait_until="networkidle")
        page.wait_for_function("window.__summaryReady === true", timeout=30_000)
        headings = page.eval_on_selector_all(".summary-scene h3", "els => els.map(e => e.textContent)")
        title = page.inner_text(".summary-head h1")
        browser.close()
    assert title == lesson["title"] and headings == [s["heading"] for s in lesson["scenes"]]


def test_pdf_is_cached_until_the_lesson_changes(server):
    make("summary-test-cache", fallback_lesson("Photosynthesis", "beginner", "en"))
    url = f"{server}/api/lessons/summary-test-cache/summary.pdf"
    httpx.get(url, timeout=60)
    pdf = lesson_dir("summary-test-cache") / "summary.en.pdf"
    first = pdf.stat().st_mtime
    start = time.perf_counter()
    httpx.get(url, timeout=60)
    assert pdf.stat().st_mtime == first and time.perf_counter() - start < 1.0  # served from the cache
    lesson_json = lesson_dir("summary-test-cache") / "lesson.json"
    os.utime(lesson_json, (first + 5, first + 5))  # the lesson is now newer than the PDF
    httpx.get(url, timeout=60)
    assert pdf.stat().st_mtime > first


def test_pdf_route_works_with_the_network_blocked(server, monkeypatch):
    """Offline: this process may reach only loopback (scripts/check_offline.py's guard), like Wi-Fi off."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import check_offline

    monkeypatch.setattr(socket, "create_connection", socket.create_connection)
    monkeypatch.setattr(socket.socket, "connect", socket.socket.connect)
    monkeypatch.setattr(socket.socket, "connect_ex", socket.socket.connect_ex)
    check_offline.block_outbound()
    make("summary-test-offline", fallback_lesson("Pythagoras theorem", "beginner", "hi"))
    r = httpx.get(f"{server}/api/lessons/summary-test-offline/summary.pdf", timeout=60)
    assert r.status_code == 200 and pages(r.content) == 1 and check_offline.BLOCKED == []


def test_unknown_lesson_has_no_summary():
    from fastapi.testclient import TestClient

    from app.main import app

    assert TestClient(app).get("/api/lessons/nope-nope/summary.pdf").status_code == 404


def test_is_stale(tmp_path):
    lesson_json, pdf = tmp_path / "lesson.json", tmp_path / "summary.en.pdf"
    lesson_json.write_text("{}", encoding="utf-8")
    assert is_stale(pdf, lesson_json)
    pdf.write_bytes(b"%PDF")
    os.utime(lesson_json, (1000, 1000))
    assert not is_stale(pdf, lesson_json)
    os.utime(lesson_json, (pdf.stat().st_mtime + 10,) * 2)
    assert is_stale(pdf, lesson_json)
    os.utime(lesson_json, (1000, 1000))
    build = tmp_path / "index.html"
    build.write_text("", encoding="utf-8")
    os.utime(build, (pdf.stat().st_mtime + 10,) * 2)
    assert is_stale(pdf, lesson_json, build)  # a newer app build re-makes the PDF
    assert not is_stale(pdf, lesson_json, tmp_path / "missing.html")


def test_sample_dir_untouched():
    assert (SAMPLES_DIR / "python_loop.en.json").is_file()  # summaries never write next to the samples


def stress_lesson() -> dict:
    """Too much for one page on purpose: six diagram scenes with long Hindi sentences and a long quiz."""
    lesson = fallback_lesson("Photosynthesis", "beginner", "hi")
    diagram = next(s for s in lesson["scenes"] if s["type"] == "diagram")
    long = "पौधे सूरज की रोशनी, पानी और हवा से अपना भोजन बनाते हैं और इस काम में पत्तियों का हरा रंग बहुत मदद करता है जिससे ऊर्जा बनती है " * 3
    lesson["scenes"] = [lesson["scenes"][0]] + [{**diagram, "heading": f"चरण {k}", "narration": long.strip() + "। दूसरा वाक्य।"} for k in range(5)]
    q = {"question": "पत्तियाँ " * 30 + "?", "options": ["पहला लंबा उत्तर " * 4, "दूसरा लंबा उत्तर " * 4, "तीसरा लंबा उत्तर " * 4, "चौथा लंबा उत्तर " * 4],
         "answer_index": 2, "explanation": "क्योंकि।"}
    lesson["quiz"] = [q, {**q, "answer_index": 0}, {**q, "answer_index": 3}]
    return lesson


def test_overfull_lesson_shrinks_in_order_and_never_clips(server):
    from playwright.sync_api import sync_playwright

    from app.export.capture import _launch

    make("summary-test-stress", stress_lesson())
    with sync_playwright() as p:
        browser = _launch(p)
        page = browser.new_page()
        page.goto(f"{server}/summary/summary-test-stress?print=1", wait_until="networkidle")
        page.wait_for_function("window.__summaryReady === true", timeout=30_000)
        state = page.evaluate("""(() => { const s = document.querySelector('.summary-sheet');
            return {overflow: s.scrollHeight - s.clientHeight, diagrams: document.querySelectorAll('.summary-diagram').length,
                    cut: [...document.querySelectorAll('.summary-scene p')].some(p => p.textContent.endsWith('...'))}; })()""")
        browser.close()
    assert state["diagrams"] == 0 and state["cut"]  # step 1 dropped the diagrams, step 2 cut the key points
    assert state["overflow"] <= 1  # it fits: nothing hidden by the clip
    r = httpx.get(f"{server}/api/lessons/summary-test-stress/summary.pdf", timeout=60)
    assert pages(r.content) == 1
