import type { ConceptRequest, Lesson } from "../types/lesson";

/** Mirror of Job.public() in backend/app/pipeline/jobs.py. Change both together. */
export interface JobStatus {
  stage: string; // queued | plan | translate | narrate | export | done
  progress: number; // 0..1
  fallback_used: boolean;
  fallback_reason: string | null;
  timeline_ready: boolean; // the lesson can play
  mp4_ready: boolean;
}

export interface Job {
  id: string;
  lesson_id: string;
  state: "queued" | "running" | "done" | "failed";
  stage: string;
  status: JobStatus;
  error: string | null;
  export_error: string | null; // MP4 failed; the lesson still plays
  request: ConceptRequest;
}

async function errorText(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) return "Please check the form: " + body.detail.map((d: { msg?: string }) => d.msg).join("; ");
  } catch {
    // not JSON
  }
  return `HTTP ${res.status}`;
}

export async function createLesson(req: ConceptRequest): Promise<Job> {
  const res = await fetch("/api/lessons", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(await errorText(res));
  return (await res.json()) as Job;
}

/** The job, or null when the server does not know it (a sample, or the server restarted). */
export async function getJob(id: string): Promise<Job | null> {
  const res = await fetch(`/api/jobs/${encodeURIComponent(id)}`);
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(await errorText(res));
  return (await res.json()) as Job;
}

/** lesson.json (with meta), or null when the lesson has none (e.g. samples rendered by make sample). */
export async function getLesson(id: string): Promise<Lesson | null> {
  const res = await fetch(`/api/lessons/${encodeURIComponent(id)}`);
  return res.ok ? ((await res.json()) as Lesson) : null;
}

export async function mp4Exists(id: string): Promise<boolean> {
  const res = await fetch(`/media/lessons/${encodeURIComponent(id)}/lesson.mp4`, { method: "HEAD" });
  return res.ok;
}
