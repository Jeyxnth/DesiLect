import fakeTimeline from "../dev/fakeTimeline.json";
import type { Timeline } from "../types/lesson";

/**
 * Loads /media/lessons/<id>/timeline.json (written by the backend).
 * In dev only, a missing sample-* lesson falls back to the bundled fake timeline.
 */
export async function loadTimeline(id: string): Promise<Timeline> {
  const res = await fetch(`/media/lessons/${encodeURIComponent(id)}/timeline.json`);
  if (res.ok) return (await res.json()) as Timeline;
  if (import.meta.env.DEV && id.startsWith("sample-")) return fakeTimeline as Timeline;
  throw new Error(`Lesson "${id}" not found (HTTP ${res.status})`);
}
