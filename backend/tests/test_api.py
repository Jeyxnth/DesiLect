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


def test_pipeline_writes_lesson_and_timings():
    r = client.post("/api/lessons", json={"topic": "How does a Python loop work?", "language": "ta"})
    assert r.status_code == 202
    job_id = r.json()["id"]
    for _ in range(20):
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["state"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert job["state"] == "done"
    assert client.get(f"/api/lessons/{job_id}").json()["language"] == "ta"
    assert "plan" in client.get(f"/api/lessons/{job_id}/timings").json()


def test_rejects_bad_target_seconds():
    assert client.post("/api/lessons", json={"topic": "loops", "target_seconds": 500}).status_code == 422


def test_protect_roundtrip():
    text = "The range(3) call gives 0, 1 and 2 to the loop."
    masked, mapping = protect(text)
    assert "range" not in masked and "loop" not in masked
    assert restore(masked, mapping) == text
