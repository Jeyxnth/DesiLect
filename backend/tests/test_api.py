import json
import time

from fastapi.testclient import TestClient

from app.main import app
from app.translate.protect import protect, restore

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert set(body["models"]) == {"kokoro", "indictrans2", "indic_parler_tts"}
    assert "python" in body["versions"]


def test_unknown_api_is_404():
    assert client.get("/api/nope").status_code == 404


def test_samples_endpoint():
    assert client.get("/api/samples/python_loop.hi").json()["language"] == "hi"
    assert client.get("/api/samples/../x").status_code == 404


def test_pipeline_runs_with_ollama_down_and_reports_status(monkeypatch):
    from app.pipeline import orchestrator as orch
    from app.planner.ollama_client import OllamaNotRunning

    class Down:
        model = "llama3.2:3b"

        def chat_json(self, *a, **k):
            raise OllamaNotRunning("down")

    monkeypatch.setattr(orch, "OllamaClient", Down)
    monkeypatch.setattr(orch, "build_timeline", lambda lesson, lang, out: {})
    monkeypatch.setattr(orch, "ensure_frontend_built", lambda: False)
    monkeypatch.setattr(orch, "export_lesson", lambda *a, **k: None)

    class Srv:
        def __enter__(self):
            return "http://127.0.0.1:1"

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(orch, "local_server", Srv)
    r = client.post("/api/lessons", json={"topic": "How does a Python loop work?", "language": "en"})
    assert r.status_code == 202
    job_id = r.json()["id"]
    for _ in range(50):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["state"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert job["state"] == "done", job
    assert job["status"] == {"stage": "done", "progress": 1.0, "fallback_used": True}
    lesson = client.get(f"/api/lessons/{job_id}").json()
    assert lesson["meta"]["fallback"] is True and lesson["title"] == "How does a Python loop work?"
    assert "plan" in client.get(f"/api/lessons/{job_id}/timings").json()


def test_rejects_bad_target_seconds():
    assert client.post("/api/lessons", json={"topic": "loops", "target_seconds": 500}).status_code == 422


def test_protect_roundtrip():
    text = "The range(3) call gives 0, 1 and 2 to the loop."
    masked, mapping = protect(text)
    assert "range" not in masked and "loop" not in masked
    assert restore(masked, mapping) == text


def test_ping_is_instant_and_independent_of_ollama(monkeypatch):
    import app.api.routes as routes

    def boom(*a, **k):
        raise AssertionError("ping must not touch Ollama")

    monkeypatch.setattr(routes.OllamaClient, "list_models", boom)
    assert client.get("/api/ping").json() == {"ok": True}


def test_health_survives_ollama_down(monkeypatch):
    import app.api.routes as routes
    from app.planner.ollama_client import OllamaNotRunning

    def down(self, timeout=0.5):
        raise OllamaNotRunning("down")

    monkeypatch.setattr(routes.OllamaClient, "list_models", down)
    body = client.get("/api/health").json()
    assert body["ollama"]["running"] is False and body["ollama"]["model_present"] is False
