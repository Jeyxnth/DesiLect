import { useEffect, useRef, useState, type FormEvent } from "react";
import { createLesson, getJob, type Job } from "../api/jobs";
import FallbackNotice from "../components/FallbackNotice";
import type { ConceptRequest, Language, Level } from "../types/lesson";

const POLL_MS = 1000;

/** Topics the built-in samples cover, so the demo always has a known-good path. */
const SHORTCUTS = ["How does a Python loop work?", "Photosynthesis", "The Pythagorean theorem"];

/** Stages in pipeline order with what the user sees; times are typical on a CPU-only laptop. */
const STAGES: { id: string; label: string; hint?: string }[] = [
  { id: "plan", label: "Planning the lesson", hint: "about 35 s, up to 65 s if the plan needs a retry" },
  { id: "translate", label: "Translating" },
  { id: "narrate", label: "Recording the narration" },
];

/** Stage 1: concept input, then job progress until the lesson can play. */
export default function InputPage() {
  const [req, setReq] = useState<ConceptRequest>({
    topic: "How does a Python loop work?",
    level: "beginner",
    language: "en",
    target_seconds: 45,
  });
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const startedAt = useRef(0);
  const jobId = job?.id;

  useEffect(() => {
    if (!busy || !jobId) return;
    const timer = window.setInterval(async () => {
      setElapsed(Math.round((Date.now() - startedAt.current) / 1000));
      try {
        const next = await getJob(jobId);
        if (!next) throw new Error("The server lost this job (was it restarted?). Please try again.");
        setJob(next);
        if (next.state === "failed") {
          setBusy(false);
          setError(next.error ?? "Lesson generation failed.");
        } else if (next.status.timeline_ready) {
          window.location.assign(`/lesson/${encodeURIComponent(next.lesson_id)}`);
        }
      } catch (e) {
        setBusy(false);
        setError(e instanceof Error ? e.message : String(e));
      }
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [busy, jobId]);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    setJob(null);
    setElapsed(0);
    startedAt.current = Date.now();
    try {
      setJob(await createLesson({ ...req, topic: req.topic.trim() }));
      setBusy(true);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg === "Failed to fetch" ? "The backend is not reachable. Is make dev running?" : msg);
    }
  };

  const stages = STAGES.filter((s) => s.id !== "translate" || req.language !== "en");
  const currentIndex = stages.findIndex((s) => s.id === job?.status.stage);

  return (
    <div className="page input-page">
      <h1>Blu Visual Teacher</h1>
      <form className="form" onSubmit={submit}>
        <label>Concept
          <input
            value={req.topic}
            minLength={3}
            maxLength={200}
            required
            disabled={busy}
            onChange={(e) => setReq({ ...req, topic: e.target.value })}
          />
        </label>
        <div className="shortcuts">
          <span>Try:</span>
          {SHORTCUTS.map((t) => (
            <button type="button" key={t} disabled={busy} onClick={() => setReq({ ...req, topic: t })}>{t}</button>
          ))}
        </div>
        <label>Level
          <select value={req.level} disabled={busy} onChange={(e) => setReq({ ...req, level: e.target.value as Level })}>
            <option value="beginner">Beginner</option>
            <option value="intermediate">Intermediate</option>
          </select>
        </label>
        <label>Language
          <select value={req.language} disabled={busy} onChange={(e) => setReq({ ...req, language: e.target.value as Language })}>
            <option value="en">English</option>
            <option value="hi">हिन्दी</option>
            <option value="ta">தமிழ்</option>
          </select>
        </label>
        <label>Length: {req.target_seconds} s
          <input type="range" min={30} max={90} disabled={busy} value={req.target_seconds} onChange={(e) => setReq({ ...req, target_seconds: Number(e.target.value) })} />
        </label>
        <button type="submit" disabled={busy || req.topic.trim().length < 3}>
          {busy ? "Creating..." : error && job ? "Try again" : "Create lesson"}
        </button>
      </form>

      {job && (busy || job.state === "failed") && (
        <section className="job" aria-live="polite">
          <ol className="stages">
            {stages.map((s, i) => {
              const state = i < currentIndex ? "done" : i === currentIndex ? "active" : "todo";
              return (
                <li key={s.id} className={`stage-${state}`}>
                  <span className="stage-mark">{state === "done" ? "✓" : state === "active" ? "▶" : "·"}</span>
                  {s.label}
                  {state === "active" && s.hint && <span className="stage-hint"> ({s.hint})</span>}
                </li>
              );
            })}
          </ol>
          <div className="job-bar"><div className="job-bar-fill" style={{ width: `${Math.round(job.status.progress * 100)}%` }} /></div>
          <p className="muted">{elapsed} s elapsed. The player opens as soon as the narration is ready; the MP4 keeps exporting there.</p>
          {job.status.fallback_used && <FallbackNotice reason={job.status.fallback_reason} topic={job.request.topic} />}
        </section>
      )}

      {error && <p className="error" role="alert">{error}</p>}
    </div>
  );
}
