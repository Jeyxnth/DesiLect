"""Step 12: the offline check (scripts/check_offline.py) and the failure-drill switches (BLU_DRILL)."""
import socket
import sys

import pytest

from app.config import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import check_offline  # noqa: E402


@pytest.fixture
def guarded(monkeypatch):
    """Install the socket guard for one test; monkeypatch puts the real functions back afterwards."""
    monkeypatch.setattr(socket, "create_connection", socket.create_connection)
    monkeypatch.setattr(socket.socket, "connect", socket.socket.connect)
    monkeypatch.setattr(socket.socket, "connect_ex", socket.socket.connect_ex)
    check_offline.block_outbound()
    yield
    check_offline.BLOCKED.clear()


def test_guard_blocks_the_internet_but_not_loopback(guarded):
    with pytest.raises(check_offline.OutboundBlocked):
        socket.create_connection(("1.1.1.1", 443), timeout=1)
    with pytest.raises(check_offline.OutboundBlocked):
        socket.socket().connect(("93.184.216.34", 80))
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    with socket.create_connection(server.getsockname(), timeout=1):  # 127.0.0.1 is allowed
        pass
    server.close()
    assert check_offline.BLOCKED == ["1.1.1.1:443", "93.184.216.34:80"]


def test_loopback_names():
    assert check_offline.is_loopback("127.0.0.1") and check_offline.is_loopback("::1") and check_offline.is_loopback("localhost")
    assert not check_offline.is_loopback("10.0.0.5") and not check_offline.is_loopback("huggingface.co")


def test_url_scan_flags_external_urls_but_not_namespaces(tmp_path, monkeypatch):
    monkeypatch.setattr(check_offline, "REPO_ROOT", tmp_path)
    (tmp_path / "a.js").write_text('fetch("https://cdn.example.com/x.js");'
                                   'createElementNS("http://www.w3.org/2000/svg","svg");'
                                   'get("http://127.0.0.1:8000/api")', encoding="utf-8")
    problems = check_offline.scan_urls([tmp_path], check_offline.ALLOWED_URL)
    assert any("https://cdn.example.com/x.js" in p for p in problems)
    assert not any("w3.org" in p or "127.0.0.1" in p for p in problems)


def test_built_frontend_has_no_external_urls():
    dist = REPO_ROOT / "frontend" / "dist"
    if not dist.is_dir():
        pytest.skip("frontend not built")
    assert check_offline.scan_urls([dist], check_offline.ALLOWED_URL) == []


def test_planner_garbage_drill_ends_in_the_fallback_lesson(monkeypatch):
    from app.pipeline.orchestrator import plan_lesson
    from app.planner.ollama_client import OllamaClient

    monkeypatch.setenv("BLU_DRILL", "planner-garbage")
    lesson, meta = plan_lesson("Newton's first law", "beginner", 45, client=OllamaClient(base_url="http://127.0.0.1:9"))
    assert meta["fallback"] is True and meta["attempts"] == 2
    assert lesson["meta"]["fallback"] is True
    assert lesson["meta"]["reason"] == "The planner's lesson failed validation twice."


def test_export_fail_drill_stops_the_capture_browser(monkeypatch):
    from app.export.capture import _launch

    monkeypatch.setenv("BLU_DRILL", "export-fail")
    with pytest.raises(RuntimeError, match="no Chromium"):
        _launch(object())


def test_drill_switch_is_off_by_default(monkeypatch):
    from app.config import drill

    monkeypatch.delenv("BLU_DRILL", raising=False)
    assert not drill("export-fail")
    monkeypatch.setenv("BLU_DRILL", "planner-garbage, export-fail")
    assert drill("export-fail") and drill("planner-garbage") and not drill("ollama-down")


def test_planner_memory_counts_the_ollama_runner_child():
    """Step 12 bug: the model runs in Ollama's child llama-server.exe, which the name match missed (2.4 GB vs 120 MB)."""
    from types import SimpleNamespace

    from app.cache.store import ollama_rss

    class Proc:
        def __init__(self, pid, name, mb, children=()):
            self.pid, self.info, self._mb, self._children = pid, {"name": name}, mb, list(children)

        def children(self, recursive=False):
            out = list(self._children)
            if recursive:
                for c in self._children:
                    out += c.children(recursive=True)
            return out

        def memory_info(self):
            return SimpleNamespace(rss=self._mb * 2**20)

    runner = Proc(3, "llama-server.exe", 2400)
    server = Proc(2, "ollama.exe", 50, [runner])
    tray = Proc(1, "ollama app.exe", 30, [server])
    fake_ps = SimpleNamespace(Error=OSError, process_iter=lambda attrs: [tray, server, runner, Proc(9, "chrome.exe", 900)])
    assert ollama_rss(fake_ps) == (2400 + 50 + 30) * 2**20  # the runner counted, each process once, chrome not at all
