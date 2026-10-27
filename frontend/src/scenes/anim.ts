// Pure helpers: every visual state is a function of (timeline, t) (G3).
import type { Beat, Cue, TimelineScene } from "../types/lesson";

export const clamp01 = (x: number): number => Math.min(1, Math.max(0, x));

/** 0..1 progress of t inside [start, end]. */
export function progress(t: number, start: number, end: number): number {
  return end > start ? clamp01((t - start) / (end - start)) : 1;
}

export const easeOutCubic = (x: number): number => 1 - Math.pow(1 - clamp01(x), 3);

/** Opacity ramp for something that appears at time `at`, fading in over `dur` seconds. */
export function fadeIn(t: number, at: number, dur = 0.4): number {
  return easeOutCubic((t - at) / dur);
}

/** Number of items revealed so far: highest reveal value among beats with beat.t <= t. */
export function revealedCount(beats: Beat[], t: number): number {
  let n = 0;
  for (const b of beats) if (b.action === "reveal" && b.t <= t) n = Math.max(n, b.value + 1);
  return n;
}

/** Latest highlighted index, or null before the first highlight beat. */
export function highlightAt(beats: Beat[], t: number): number | null {
  let value: number | null = null;
  let at = -Infinity;
  for (const b of beats) if (b.action === "highlight" && b.t <= t && b.t >= at) { value = b.value; at = b.t; }
  return value;
}

export function activeCue(cues: Cue[], t: number): Cue | null {
  return cues.find((c) => t >= c.start && t < c.end) ?? null;
}

/** Scene containing t (the last scene once t passes the end). */
export function sceneAt(scenes: TimelineScene[], t: number): TimelineScene | null {
  if (scenes.length === 0) return null;
  return scenes.find((s) => t >= s.start && t < s.end) ?? (t >= (scenes[scenes.length - 1]?.end ?? 0) ? scenes[scenes.length - 1]! : scenes[0]!);
}
