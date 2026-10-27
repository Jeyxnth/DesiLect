import type { ConceptRequest, Language, Lesson } from "../types/lesson";

/** Mirror of Job.public() in backend/app/pipeline/jobs.py. Change both together. */
export interface JobStatus {
  stage: string; // queued | plan | translate | voice | timing | export | done
  progress: number; // 0..1
  fallback_used: boolean;
  fallback_reason: string | null;
  timeline_ready: boolean; // the lesson can play
  mp4_ready: boolean;
  timings: Record<string, number>; // seconds per stage; the running stage counts up live
  failed_stage: string | null; // the stage that raised, when the job failed
  queue_ahead: number | null; // jobs before this one (0 = running or next), null when not queued
  export_progress: number | null; // 0..1 while the MP4 is captured, null before export starts
  export_mode: "smooth" | "keyframe" | null; // how the MP4 was made, once it is ready
}

export interface Job {
  id: string;
  job_id: string;
  lesson_id: string;
  state: "queued" | "running" | "done" | "failed";
  stage: string;
  status: JobStatus;
  error: string | null;
  export_error: string | null; // MP4 failed; the lesson still plays
  request: ConceptRequest | null; // null for a lesson this server did not generate
  cached?: boolean; // POST answers: true when an identical finished lesson was reused
}

const lessonUrl = (id: string) => `/api/lessons/${encodeURIComponent(id)}`;

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

export function finished(job: Job): boolean {
  return job.state === "done" || job.state === "failed";
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

/** The lesson's status, or null when the server knows nothing about it. */
export async function getStatus(id: string): Promise<Job | null> {
  const res = await fetch(lessonUrl(id));
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(await errorText(res));
  return (await res.json()) as Job;
}

/** lesson.json (with meta), or null when the lesson has none (e.g. samples rendered by make sample). */
export async function getLesson(id: string): Promise<Lesson | null> {
  const res = await fetch(`${lessonUrl(id)}/lesson`);
  return res.ok ? ((await res.json()) as Lesson) : null;
}

/** The same lesson in another language, from its stored English plan (no re-planning); may answer from the cache. */
export async function revoiceLesson(id: string, language: Language): Promise<Job> {
  const res = await fetch(`${lessonUrl(id)}/revoice`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language }),
  });
  if (!res.ok) throw new Error(await errorText(res));
  return (await res.json()) as Job;
}

/** timings.json: seconds per stage, "rss_mb" peak memory per stage, "timeline" TTS stats; null if none yet. */
export async function getTimings(id: string): Promise<Timings | null> {
  const res = await fetch(`${lessonUrl(id)}/timings`);
  return res.ok ? ((await res.json()) as Timings) : null;
}

export interface Timings {
  [stage: string]: number | Record<string, number | string | null> | undefined;
  rss_mb?: Record<string, number>;
  timeline?: { total_seconds?: number; tts_rtf?: number | null; tts_engine?: string };
}

/** Queue the MP4 export again (after an export failure). */
export async function retryExport(id: string): Promise<Job> {
  const res = await fetch(`${lessonUrl(id)}/export`, { method: "POST" });
  if (!res.ok) throw new Error(await errorText(res));
  return (await res.json()) as Job;
}

/**
 * Follow a lesson's status with Server-Sent Events until it is done or failed; falls back to polling
 * if the stream breaks. Returns a function that stops watching.
 */
export function watchStatus(id: string, onStatus: (job: Job) => void, onError: (message: string) => void): () => void {
  let stopped = false;
  let timer = 0;
  const source = new EventSource(`${lessonUrl(id)}/events`);

  const poll = async () => {
    if (stopped) return;
    try {
      const job = await getStatus(id);
      if (stopped) return;
      if (!job) return onError("The server does not know this lesson (was it restarted?).");
      onStatus(job);
      if (!finished(job)) timer = window.setTimeout(poll, 1000);
    } catch {
      if (!stopped) onError("The backend is not reachable. Is it still running?");
    }
  };

  source.onmessage = (e: MessageEvent<string>) => {
    const job = JSON.parse(e.data) as Job;
    onStatus(job);
    if (finished(job)) source.close();
  };
  source.onerror = () => {
    if (stopped) return;
    source.close(); // do not let EventSource reconnect forever; poll instead
    void poll();
  };

  return () => {
    stopped = true;
    source.close();
    window.clearTimeout(timer);
  };
}
