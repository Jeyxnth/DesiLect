import { useEffect, useState, type FormEvent } from "react";
import { createLesson, watchStatus, type Job } from "../api/jobs";
import BrandMark from "../components/BrandMark";
import FallbackNotice from "../components/FallbackNotice";
import { StreakBadge } from "../habit/LessonEnd";
import { currentStreak, localDay, removeRevise, useHabit } from "../habit/storage";
import { ui } from "../i18n/strings";
import { navState, navigate } from "../router";
import type { ConceptRequest, Language, Level, Voice } from "../types/lesson";

/** Topics the built-in samples cover, so the demo always has a known-good path. */
const EXAMPLES = ["How does a Python loop work?", "Photosynthesis", "How does binary search work?"];

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

/** Narration speed choices (multipliers the TTS engines apply; see ConceptRequest.speed). */
const SPEEDS: { value: number; label: string }[] = [
  { value: 0.9, label: "Slow" },
  { value: 1.0, label: "Normal" },
  { value: 1.1, label: "Fast" },
];

const LANGUAGE_NAMES: Record<Language, string> = { en: "English", hi: "हिन्दी", ta: "தமிழ்" };

const VOICES: { value: Voice; label: string }[] = [
  { value: "female", label: "Female" },
  { value: "male", label: "Male" },
];

type StageState = "done" | "active" | "todo" | "skipped" | "failed";

/** Stage 1: concept input, then live job progress until the lesson can play. */
export default function InputPage() {
  const [req, setReq] = useState<ConceptRequest>({
    topic: "How does a Python loop work?",
    level: "beginner",
    language: "en",
    target_seconds: 45,
    speed: 1.0,
    voice: "female",
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

  const start = async (request: ConceptRequest) => {
    setError("");
    setJob(null);
    try {
      setJob(await createLesson({ ...request, topic: request.topic.trim() }));
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setError(msg === "Failed to fetch" ? "The backend is not reachable. Is the backend running?" : msg);
    }
  };
  const submit = (e: FormEvent) => {
    e.preventDefault();
    void start(req);
  };

  // "Try next" from a finished lesson (bonus B2): topic, level and language pre-filled, generation starts at once.
  useEffect(() => {
    const { prefill, autostart } = navState();
    if (!prefill?.topic) return;
    const request = { ...req, ...prefill };
    setReq(request);
    window.history.replaceState({}, "", window.location.pathname); // a reload or Back must not start it again
    if (autostart) void start(request);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { habit, update } = useHabit();
  const streak = habit ? currentStreak(habit, localDay()) : 0;

  const language = job?.request?.language ?? req.language;
  const failedAt = job?.state === "failed" ? job.status.failed_stage : null;
  const currentIndex = STAGES.findIndex((s) => s.id === (failedAt ?? job?.status.stage));
  const stageState = (id: string, i: number): StageState => {
    if (id === "translate" && language === "en") return "skipped";
    if (failedAt) return i < currentIndex ? "done" : i === currentIndex ? "failed" : "todo";
    if (job?.status.stage === "done") return "done";
    return i < currentIndex ? "done" : i === currentIndex ? "active" : "todo";
  };
  const ahead = job?.state === "queued" ? job.status.queue_ahead : null;

  return (
    <main className="page input-page">
      <header className="input-head">
        <div>
          <div className="brand">
            <BrandMark />
            <h1>Blu Visual Teacher</h1>
          </div>
          <p className="tagline">Type a concept and get a short narrated lesson with diagrams and code, in English, Hindi or Tamil. Made on this laptop, offline.</p>
        </div>
        <StreakBadge count={streak} lang={req.language} />
      </header>
      <form className="form" onSubmit={submit}>
        <div className="concept">
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
        </div>
        <div className="form-row">
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
        </div>
        <div className="form-row">
          <div className="field">
            <span className="field-label" id="voice-label">Voice</span>
            <div className="toggle" role="group" aria-labelledby="voice-label">
              {VOICES.map((v) => (
                <button
                  type="button"
                  key={v.value}
                  aria-pressed={req.voice === v.value}
                  disabled={busy}
                  onClick={() => setReq({ ...req, voice: v.value })}
                >
                  {v.label}
                </button>
              ))}
            </div>
          </div>
          <div className="field">
            <span className="field-label" id="speed-label">Voice speed</span>
            <div className="toggle" role="group" aria-labelledby="speed-label">
              {SPEEDS.map((s) => (
                <button
                  type="button"
                  key={s.value}
                  aria-pressed={req.speed === s.value}
                  disabled={busy}
                  onClick={() => setReq({ ...req, speed: s.value })}
                >
                  {s.label}
                </button>
              ))}
            </div>
          </div>
        </div>
        <label>
          <span className="range-head">Length <output>{req.target_seconds} s</output></span>
          <input type="range" min={30} max={90} step={5} disabled={busy} value={req.target_seconds} onChange={(e) => setReq({ ...req, target_seconds: Number(e.target.value) })} />
        </label>
        <button type="submit" className="primary" aria-busy={busy} disabled={busy || req.topic.trim().length < 3}>
          {busy ? <><span className="pulse" aria-hidden="true" /> Generating...</> : error && job ? "Try again" : "Generate"}
        </button>
      </form>

      {job && (
        <section className="job" aria-live="polite" aria-labelledby="job-heading">
          <h2 id="job-heading">
            {job.state === "failed" ? "Lesson not made" : "Making your lesson"}
            {job.request?.topic && <span className="job-topic">{job.request.topic}</span>}
          </h2>
          {ahead !== null && ahead > 0 && (
            <p className="muted">Waiting for {ahead} other lesson{ahead > 1 ? "s" : ""} to finish (one is made at a time).</p>
          )}
          <ol className="stages">
            {STAGES.map((s, i) => {
              const state = stageState(s.id, i);
              const seconds = job.status.timings[s.id];
              return (
                <li key={s.id} className={`stage-${state}`}>
                  <span className="stage-mark" aria-hidden="true">{{ done: "✓", active: "▶", todo: "·", skipped: "–", failed: "✗" }[state]}</span>
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
          <p className="job-note">The player opens and starts as soon as the narration is ready; the MP4 keeps exporting there.</p>
        </section>
      )}

      {error && <p className="error" role="alert"><strong>The lesson could not be made.</strong> {error}</p>}

      {habit && habit.revise.length > 0 && (
        <section className="revise-list" lang={req.language} aria-labelledby="revise-heading">
          <h2 id="revise-heading">{ui(req.language, "revise")}</h2>
          <ul>
            {habit.revise.map((e) => (
              <li key={e.lesson_id}>
                <a href={`/lesson/${encodeURIComponent(e.lesson_id)}`} lang={e.language}
                  onClick={(ev) => { ev.preventDefault(); navigate(`/lesson/${encodeURIComponent(e.lesson_id)}`); }}>
                  {e.title}
                </a>
                <span className="muted">{LANGUAGE_NAMES[e.language] ?? e.language}{e.score ? ` · ${e.score.correct} / ${e.score.total}` : ""}</span>
                <button type="button" onClick={() => update((s) => removeRevise(s, e.lesson_id))}>{ui(req.language, "remove")}</button>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
