import { useEffect, useState, type FormEvent } from "react";
import { createLesson, watchStatus, type Job } from "../api/jobs";
import FallbackNotice from "../components/FallbackNotice";
import { navigate } from "../router";
import type { ConceptRequest, Language, Level } from "../types/lesson";

/** Topics the built-in samples cover, so the demo always has a known-good path. */
const EXAMPLES = ["How does a Python loop work?", "Photosynthesis", "The Pythagorean theorem"];

/** Pipeline stages in order (ids from backend/app/pipeline/orchestrator.py); times are typical on a CPU-only laptop. */
const STAGES: { id: string; label: string; hint?: string }[] = [
  { id: "plan", label: "Planning", hint: "about 35 s, up to 65 s if the plan needs a retry" },
  { id: "translate", label: "Translating" },
  { id: "voice", label: "Voicing" },
  { id: "timing", label: "Timing" },
  { id: "export", label: "Exporting", hint: "continues in the player" },
];

const LEVELS: { value: Level; label: string }[] = [
  { value: "beginner", label: "Beginner" },
  { value: "intermediate", label: "Intermediate" },
];

type StageState = "done" | "active" | "todo" | "skipped";

/** Stage 1: concept input, then live job progress until the lesson can play. */
export default function InputPage() {
  const [req, setReq] = useState<ConceptRequest>({
    topic: "How does a Python loop work?",
    level: "beginner",
    language: "en",
    target_seconds: 45,
  });
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const busy = job !== null && (job.state === "queued" || job.state === "running") && !error;
  const jobId = job?.job_id;

  useEffect(() => {
    if (!jobId) return;
    return watchStatus(
      jobId,
      (next) => {
        setJob(next);
        if (next.state === "failed") setError(next.error ?? "Lesson generation failed.");
        else if (next.status.timeline_ready) navigate(`/lesson/${encodeURIComponent(next.lesson_id)}`, { autoplay: true });
      },
      setError,
    );
  }, [jobId]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setJob(null);
    try {
      setJob(await createLesson({ ...req, topic: req.topic.trim() }));
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg === "Failed to fetch" ? "The backend is not reachable. Is make dev running?" : msg);
    }
  };

  const language = job?.request?.language ?? req.language;
  const currentIndex = STAGES.findIndex((s) => s.id === job?.status.stage);
  const stageState = (id: string, i: number): StageState => {
    if (id === "translate" && language === "en") return "skipped";
    if (job?.status.stage === "done") return "done";
    return i < currentIndex ? "done" : i === currentIndex ? "active" : "todo";
  };
  const ahead = job?.state === "queued" ? job.status.queue_ahead : null;

  return (
    <div className="page input-page">
      <h1>Blu Visual Teacher</h1>
      <form className="form" onSubmit={submit}>
        <label>Concept
          <input
            value={req.topic}
            minLength={3}
            maxLength={120}
            required
            disabled={busy}
            placeholder="Type any concept, e.g. How does a Python loop work?"
            onChange={(e) => setReq({ ...req, topic: e.target.value })}
          />
        </label>
        <div className="chips" aria-label="Examples">
          {EXAMPLES.map((t) => (
            <button type="button" key={t} className="chip" disabled={busy} onClick={() => setReq({ ...req, topic: t })}>{t}</button>
          ))}
        </div>
        <div className="field">
          <span className="field-label" id="level-label">Level</span>
          <div className="toggle" role="group" aria-labelledby="level-label">
            {LEVELS.map((l) => (
              <button
                type="button"
                key={l.value}
                aria-pressed={req.level === l.value}
                disabled={busy}
                onClick={() => setReq({ ...req, level: l.value })}
              >
                {l.label}
              </button>
            ))}
          </div>
        </div>
        <label>Language
          <select value={req.language} disabled={busy} onChange={(e) => setReq({ ...req, language: e.target.value as Language })}>
            <option value="en">English</option>
            <option value="hi">हिन्दी</option>
            <option value="ta">தமிழ்</option>
          </select>
        </label>
        <label>Length: {req.target_seconds} s
          <input type="range" min={30} max={90} step={5} disabled={busy} value={req.target_seconds} onChange={(e) => setReq({ ...req, target_seconds: Number(e.target.value) })} />
        </label>
        <button type="submit" className="primary" disabled={busy || req.topic.trim().length < 3}>
          {busy ? "Generating..." : error && job ? "Try again" : "Generate"}
        </button>
      </form>

      {job && (
        <section className="job" aria-live="polite">
          {ahead !== null && ahead > 0 && (
            <p className="muted">Waiting for {ahead} other lesson{ahead > 1 ? "s" : ""} to finish (one is made at a time).</p>
          )}
          <ol className="stages">
            {STAGES.map((s, i) => {
              const state = stageState(s.id, i);
              const seconds = job.status.timings[s.id];
              return (
                <li key={s.id} className={`stage-${state}`}>
                  <span className="stage-mark" aria-hidden="true">{{ done: "✓", active: "▶", todo: "·", skipped: "–" }[state]}</span>
                  <span className="stage-label">{s.label}</span>
                  <span className="stage-time">
                    {state === "skipped" ? "not needed" : seconds !== undefined ? `${seconds.toFixed(1)} s` : ""}
                  </span>
                  {state === "active" && s.hint && <span className="stage-hint">{s.hint}</span>}
                </li>
              );
            })}
          </ol>
          <div className="job-bar"><div className="job-bar-fill" style={{ width: `${Math.round(job.status.progress * 100)}%` }} /></div>
          {job.status.fallback_used && <FallbackNotice reason={job.status.fallback_reason} topic={job.request?.topic} />}
          <p className="muted">The player opens and starts as soon as the narration is ready; the MP4 keeps exporting there.</p>
        </section>
      )}

      {error && <p className="error" role="alert">{error}</p>}
    </div>
  );
}
