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


def run_job_with_ollama_down(monkeypatch, payload, export=lambda *a, **k: None):
    """POST /api/lessons with Ollama down and TTS/export stubbed; return the finished job."""
    from app.pipeline import orchestrator as orch
    from app.planner.ollama_client import OllamaNotRunning

    class Down:
        model = "llama3.2:3b"

        def chat_json(self, *a, **k):
            raise OllamaNotRunning("down")

    monkeypatch.setattr(orch, "OllamaClient", Down)
    monkeypatch.setattr(orch, "build_timeline", lambda lesson, lang, out: {})
    monkeypatch.setattr(orch, "ensure_frontend_built", lambda: False)
    monkeypatch.setattr(orch, "export_lesson", export)

    class Srv:
        def __enter__(self):
            return "http://127.0.0.1:1"

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(orch, "local_server", Srv)
    r = client.post("/api/lessons", json=payload)
    assert r.status_code == 202
    job_id = r.json()["id"]
    for _ in range(50):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["state"] in ("done", "failed"):
            break
        time.sleep(0.1)
    return job


def test_pipeline_runs_with_ollama_down_and_reports_status(monkeypatch):
    job = run_job_with_ollama_down(monkeypatch, {"topic": "How does a Python loop work?", "language": "en"})
    assert job["state"] == "done", job
    assert job["status"] == {
        "stage": "done",
        "progress": 1.0,
        "fallback_used": True,
        "fallback_reason": "The local planner (Ollama) is not running.",
        "timeline_ready": True,
        "mp4_ready": True,
    }
    lesson = client.get(f"/api/lessons/{job['id']}").json()
    assert lesson["meta"]["fallback"] is True and lesson["title"] == "How does a Python loop work?"
    assert lesson["meta"]["reason"] == "The local planner (Ollama) is not running."
    assert "plan" in client.get(f"/api/lessons/{job['id']}/timings").json()


def test_translated_fallback_keeps_the_closest_sample(monkeypatch):
    job = run_job_with_ollama_down(monkeypatch, {"topic": "Photosynthesis", "language": "hi"})
    lesson = client.get(f"/api/lessons/{job['id']}").json()
    assert lesson["language"] == "hi"
    assert lesson["meta"]["source"] == "sample:photosynthesis" and lesson["meta"]["topic"] == "Photosynthesis"
    assert lesson["meta"]["reason"] == "The local planner (Ollama) is not running."  # the root cause wins
    assert job["status"]["fallback_used"] is True


def test_translation_fallback_reason_when_the_plan_was_fine():
    from app.translate.indictrans import translate_lesson

    plan = {"title": "Leaves", "level": "beginner", "language": "en", "scenes": [],
            "meta": {"fallback": False, "source": "ollama:llama3.2:3b", "topic": "How do plants make food?"}}
    lesson = translate_lesson(plan, "ta")
    assert lesson["language"] == "ta" and lesson["meta"]["source"] == "sample:photosynthesis"
    assert lesson["meta"]["reason"] == "Translation to this language is not available yet."


def test_failed_export_still_leaves_a_playable_lesson(monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("ffmpeg exploded")

    job = run_job_with_ollama_down(monkeypatch, {"topic": "loops", "language": "en"}, export=broken)
    assert job["state"] == "done" and job["error"] is None
    assert job["status"]["timeline_ready"] is True and job["status"]["mp4_ready"] is False
    assert job["export_error"] == "ffmpeg exploded"


def test_friendly_reasons():
    from app.pipeline.orchestrator import friendly_reason

    assert friendly_reason("OllamaTimeout: took 120s") == "The planner took too long to answer."
    assert friendly_reason("OllamaModelMissing: 404") == "The planner model is not installed."
    assert friendly_reason("invalid plan: scenes too short") == "The planner's lesson failed validation twice."
    assert friendly_reason("HTTPError: 500") == "The local planner returned an error."
    assert friendly_reason(None) == "The planner did not return a lesson."


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
