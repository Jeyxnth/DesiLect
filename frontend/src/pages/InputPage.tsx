import { useState, type FormEvent } from "react";
import type { ConceptRequest, Language, Level } from "../types/lesson";

/** Stage 1: concept input. TODO(step 6): job progress, errors, sample shortcuts. */
export default function InputPage() {
  const [req, setReq] = useState<ConceptRequest>({
    topic: "How does a Python loop work?",
    level: "beginner",
    language: "en",
    target_seconds: 45,
  });
  const [status, setStatus] = useState("");

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setStatus("Starting...");
    const res = await fetch("/api/lessons", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    if (!res.ok) return setStatus(`Error ${res.status}`);
    const job = (await res.json()) as { lesson_id: string };
    setStatus(`Lesson ${job.lesson_id} started`);
  };

  return (
    <div className="page">
      <h1>Blu Visual Teacher</h1>
      <form className="form" onSubmit={submit}>
        <label>Concept
          <input value={req.topic} minLength={3} maxLength={200} onChange={(e) => setReq({ ...req, topic: e.target.value })} />
        </label>
        <label>Level
          <select value={req.level} onChange={(e) => setReq({ ...req, level: e.target.value as Level })}>
            <option value="beginner">Beginner</option>
            <option value="intermediate">Intermediate</option>
          </select>
        </label>
        <label>Language
          <select value={req.language} onChange={(e) => setReq({ ...req, language: e.target.value as Language })}>
            <option value="en">English</option>
            <option value="hi">हिन्दी</option>
            <option value="ta">தமிழ்</option>
          </select>
        </label>
        <label>Length: {req.target_seconds} s
          <input type="range" min={30} max={90} value={req.target_seconds} onChange={(e) => setReq({ ...req, target_seconds: Number(e.target.value) })} />
        </label>
        <button type="submit">Create lesson</button>
      </form>
      <p>{status}</p>
    </div>
  );
}
