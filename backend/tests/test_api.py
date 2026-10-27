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
    assert set(body["models"]) == {"kokoro", "indictrans2", "indic_parler_tts", "indic_tts_ta"}
    assert "python" in body["versions"]


def test_unknown_api_is_404():
    assert client.get("/api/nope").status_code == 404


def test_samples_endpoint():
    assert client.get("/api/samples/python_loop.hi").json()["language"] == "hi"
    assert client.get("/api/samples/../x").status_code == 404


def stub_pipeline(monkeypatch, export=lambda *a, **k: None):
    """Ollama down, TTS replaced by a stub that writes an empty timeline.json, export stubbed."""
    from app.pipeline import orchestrator as orch
    from app.planner.ollama_client import OllamaNotRunning

    class Down:
        model = "llama3.2:3b"

        def chat_json(self, *a, **k):
            raise OllamaNotRunning("down")

    def fake_timeline(lesson, lang, out, on_stage=None):
        on_stage("voice")
        on_stage("timing")
        (out / "timeline.json").write_text("{}", encoding="utf-8")

    class Srv:
        def __enter__(self):
            return "http://127.0.0.1:1"

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(orch, "OllamaClient", Down)
    monkeypatch.setattr(orch, "build_timeline", fake_timeline)
    monkeypatch.setattr(orch, "ensure_frontend_built", lambda: False)
    monkeypatch.setattr(orch, "export_lesson", export)
    monkeypatch.setattr(orch, "local_server", Srv)


def wait_until_finished(lesson_id):
    for _ in range(100):
        job = client.get(f"/api/lessons/{lesson_id}").json()
        if job["state"] in ("done", "failed"):
            return job
        time.sleep(0.05)
    raise AssertionError(f"job {lesson_id} did not finish: {job}")


def run_job_with_ollama_down(monkeypatch, payload, export=lambda *a, **k: None):
    """POST /api/lessons with the pipeline stubbed; return the finished job's status."""
    stub_pipeline(monkeypatch, export)
    r = client.post("/api/lessons", json=payload)
    assert r.status_code == 202
    return wait_until_finished(r.json()["job_id"])


def test_pipeline_runs_with_ollama_down_and_reports_status(monkeypatch):
    job = run_job_with_ollama_down(monkeypatch, {"topic": "How does a Python loop work?", "language": "en"})
    assert job["state"] == "done", job
    status = job["status"]
    timings = status.pop("timings")
    assert status == {
        "stage": "done",
        "progress": 1.0,
        "fallback_used": True,
        "fallback_reason": "The local planner (Ollama) is not running.",
        "timeline_ready": True,
        "mp4_ready": True,
        "failed_stage": None,
        "queue_ahead": None,
    }
    assert set(timings) == {"plan", "voice", "timing", "export"}  # English skips translate
    lesson = client.get(f"/api/lessons/{job['id']}/lesson").json()
    assert lesson["meta"]["fallback"] is True and lesson["title"] == "How does a Python loop work?"
    assert lesson["meta"]["reason"] == "The local planner (Ollama) is not running."
    assert "plan" in client.get(f"/api/lessons/{job['id']}/timings").json()


def test_events_stream_status_until_done(monkeypatch):
    job = run_job_with_ollama_down(monkeypatch, {"topic": "loops", "language": "en"})
    with client.stream("GET", f"/api/lessons/{job['id']}/events") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        events = [json.loads(line[len("data: "):]) for line in r.iter_lines() if line.startswith("data: ")]
    assert events and events[-1]["state"] == "done" and events[-1]["status"]["mp4_ready"] is True


def test_unknown_lesson_is_404():
    assert client.get("/api/lessons/nope123").status_code == 404
    assert client.get("/api/lessons/nope123/events").status_code == 404
    assert client.post("/api/lessons/nope123/export").status_code == 404


def test_jobs_run_one_at_a_time_in_order():
    import threading

    from app.pipeline.jobs import WorkQueue

    q, order, running, overlaps = WorkQueue(), [], [], []
    done = threading.Event()

    def job(name):
        def run():
            if running:
                overlaps.append(name)
            running.append(name)
            time.sleep(0.05)
            order.append(name)
            running.remove(name)
            if name == "c":
                done.set()
        return run

    for name in "abc":
        q.submit(name, job(name))
    assert q.ahead("c") == 2
    assert done.wait(5)
    assert order == ["a", "b", "c"] and not overlaps


def test_topic_longer_than_120_chars_is_rejected():
    assert client.post("/api/lessons", json={"topic": "x" * 121}).status_code == 422


def test_translated_fallback_keeps_the_closest_sample(monkeypatch, tmp_path):
    from app.translate import indictrans

    monkeypatch.setattr(indictrans, "model_dir", lambda: tmp_path / "no-model")  # translation unavailable
    monkeypatch.setattr(indictrans, "translate_cache_path", lambda m, l, t: tmp_path / "empty-cache.json")
    job = run_job_with_ollama_down(monkeypatch, {"topic": "Photosynthesis", "language": "hi"})
    assert "translate" in job["status"]["timings"]
    lesson = client.get(f"/api/lessons/{job['id']}/lesson").json()
    assert lesson["language"] == "hi"
    assert lesson["meta"]["source"] == "sample:photosynthesis" and lesson["meta"]["topic"] == "Photosynthesis"
    assert lesson["meta"]["reason"] == "The local planner (Ollama) is not running."  # the root cause wins
    assert job["status"]["fallback_used"] is True


def test_failed_job_reports_the_stage_that_failed(monkeypatch):
    from app.pipeline import orchestrator as orch

    stub_pipeline(monkeypatch)

    def no_voice(lesson, lang, out, on_stage=None):
        on_stage("voice")
        raise FileNotFoundError("models/kokoro missing")

    monkeypatch.setattr(orch, "build_timeline", no_voice)
    # Ollama is down, so the lesson is already a sample: its cached voice failing too fails the job
    job = wait_until_finished(client.post("/api/lessons", json={"topic": "loops", "language": "en"}).json()["job_id"])
    assert job["state"] == "failed" and job["status"]["failed_stage"] == "voice"
    assert "voice" in job["status"]["timings"] and "export" not in job["status"]["timings"]


def test_failed_voice_falls_back_to_the_cached_sample(monkeypatch):
    """A planned (non-sample) lesson whose TTS fails is replaced by the closest sample, voiced from cache (G2)."""
    from app.pipeline import orchestrator as orch

    stub_pipeline(monkeypatch)
    planned = orch.fallback_lesson("Photosynthesis", "beginner", "en")
    planned["meta"] = {"fallback": False, "source": "ollama:test", "topic": "Photosynthesis"}
    monkeypatch.setattr(orch, "plan_lesson", lambda *a, **k: (planned, {"fallback": False}))
    voiced = []

    def voice_fails_for_new_lessons(lesson, lang, out, on_stage=None):
        on_stage("voice")
        if not lesson["meta"]["fallback"]:
            raise MemoryError("parler ran out of RAM")
        voiced.append(lesson["meta"]["source"])
        on_stage("timing")
        (out / "timeline.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(orch, "build_timeline", voice_fails_for_new_lessons)
    job = wait_until_finished(client.post("/api/lessons", json={"topic": "Photosynthesis", "language": "en"}).json()["job_id"])
    assert job["state"] == "done", job
    assert voiced == ["sample:photosynthesis"]
    assert job["status"]["fallback_used"] is True and "Voice generation failed" in job["status"]["fallback_reason"]
    lesson = client.get(f"/api/lessons/{job['id']}/lesson").json()
    assert lesson["meta"]["source"] == "sample:photosynthesis"


def test_failed_export_still_leaves_a_playable_lesson(monkeypatch):
    def broken(*a, **k):
        raise RuntimeError("ffmpeg exploded")

    job = run_job_with_ollama_down(monkeypatch, {"topic": "loops", "language": "en"}, export=broken)
    assert job["state"] == "done" and job["error"] is None
    assert job["status"]["timeline_ready"] is True and job["status"]["mp4_ready"] is False
    assert job["export_error"] == "ffmpeg exploded"

    # Retry export: queued again, and this time the export works
    from app.pipeline import orchestrator as orch

    monkeypatch.setattr(orch, "export_lesson", lambda *a, **k: None)
    r = client.post(f"/api/lessons/{job['id']}/export")
    assert r.status_code == 202
    retried = wait_until_finished(job["id"])
    assert retried["status"]["mp4_ready"] is True and retried["export_error"] is None


def test_retry_export_works_for_a_lesson_the_server_did_not_make(monkeypatch):
    from app.cache.store import lesson_dir

    stub_pipeline(monkeypatch)
    out = lesson_dir("adopted-lesson-1")
    (out / "timeline.json").write_text("{}", encoding="utf-8")
    status = client.get("/api/lessons/adopted-lesson-1").json()
    assert status["state"] == "done" and status["status"]["timeline_ready"] is True
    assert client.post("/api/lessons/adopted-lesson-1/export").status_code == 202
    assert wait_until_finished("adopted-lesson-1")["status"]["mp4_ready"] is True


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
