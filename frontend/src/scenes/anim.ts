// Pure helpers: every visual state is a function of (timeline, t) (G3). No timers, no transitions.
import type { Beat, Cue, Scene, Timeline, TimelineScene } from "../types/lesson";

/** Fade/slide length used by the scenes. Exporters capture at keyframe + SETTLE_S for a settled picture. */
export const FADE_S = 0.5;

/** Longest time any scene animation needs to finish after a keyframe (title subheading: 0.5 + 0.6 s). */
export const SETTLE_S = 1.2;

export const clamp01 = (x: number): number => Math.min(1, Math.max(0, x));

export const easeOutCubic = (x: number): number => 1 - Math.pow(1 - clamp01(x), 3);

/** 0 before `at`, easing up to 1 over `dur` seconds. */
export function fadeIn(localT: number, at: number, dur = FADE_S): number {
  return easeOutCubic((localT - at) / dur);
}

/** Largest font size (<= max, >= min) so `text` fits in `width` px; em = average glyph width in em. */
export function fitFontSize(text: string, max: number, min: number, width: number, em = 0.6): number {
  const chars = Math.max(1, [...text].length);
  return Math.max(min, Math.min(max, width / (chars * em)));
}

/** Beats shifted from absolute lesson time to scene-local time. */
export function localBeats(scene: TimelineScene): Beat[] {
  return scene.beats.map((b) => ({ ...b, t: b.t - scene.start }));
}

/** Local time at which reveal item k appears; 0 if the scene has no reveal beats at all. */
export function revealTime(beats: Beat[], k: number): number {
  const reveals = beats.filter((b) => b.action === "reveal");
  if (reveals.length === 0) return 0;
  const hit = reveals.find((b) => b.value === k);
  return hit ? hit.t : Infinity;
}

/** The latest highlight beat that has happened by localT, or null. */
export function activeHighlight(beats: Beat[], localT: number): Beat | null {
  let best: Beat | null = null;
  for (const b of beats) if (b.action === "highlight" && b.t <= localT && (!best || b.t >= best.t)) best = b;
  return best;
}

export function activeCue(cues: Cue[], t: number): Cue | null {
  return cues.find((c) => t >= c.start && t < c.end) ?? null;
}

/** The scene playing at t; before the first it is the first, at or after the end it is the last. */
export function sceneAt(scenes: TimelineScene[], t: number): TimelineScene | null {
  const last = scenes[scenes.length - 1];
  if (!last) return null;
  if (t >= last.start) return last;
  return scenes.find((s) => t >= s.start && t < s.end) ?? scenes[0] ?? null;
}

/**
 * Every time the picture changes: scene starts, beats, cue starts and cue ends (caption goes blank),
 * plus a progress-bar tick every `tick` seconds so the bar never lags more than that in keyframe export.
 */
export function keyframes(timeline: Timeline, tick = 1): number[] {
  const times = new Set<number>([0]);
  for (let t = tick; t < timeline.total_seconds; t += tick) times.add(t);
  for (const s of timeline.scenes) {
    times.add(s.start);
    s.beats.forEach((b) => times.add(b.t));
    s.cues.forEach((c) => { times.add(c.start); times.add(c.end); });
  }
  return [...times]
    .map((t) => Math.round(t * 1000) / 1000)
    .filter((t) => t >= 0 && t < timeline.total_seconds)
    .sort((a, b) => a - b)
    .filter((t, i, all) => i === 0 || t !== all[i - 1]);
}

export type { Scene };
