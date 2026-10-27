// Pure helpers: every visual state is a function of (timeline, t) (G3). No timers, no transitions.
import type { Beat, Cue, Scene, Timeline, TimelineScene } from "../types/lesson";

/** Fade/slide length used by the scenes. Exporters capture at keyframe + SETTLE_S for a settled picture. */
export const FADE_S = 0.5;

/** Diagram item scale-in, arrow draw-on (and its delay after both ends are visible), code highlight glide. */
export const ITEM_IN_S = 0.3;
export const ARROW_DELAY_S = 0.1;
export const ARROW_DRAW_S = 0.5;
export const GLIDE_S = 0.35;

/** Longest time any scene animation needs to finish after a keyframe (title icon: starts 0.4 s, lasts 0.5 s). */
export const SETTLE_S = 0.9;

export const clamp01 = (x: number): number => Math.min(1, Math.max(0, x));

export const easeOutCubic = (x: number): number => 1 - Math.pow(1 - clamp01(x), 3);

/** 0 before `at`, easing up to 1 over `dur` seconds. */
export function fadeIn(localT: number, at: number, dur = FADE_S): number {
  return easeOutCubic((localT - at) / dur);
}

/** Progress 0..1 of an animation that starts at `at` and lasts `dur`, linear (for stroke draw-on). */
export function progress(localT: number, at: number, dur: number): number {
  return clamp01((localT - at) / dur);
}

/** Smooth move between two values: from `a` toward `b`, starting at `at`, over `dur` seconds. */
export function glide(a: number, b: number, localT: number, at: number, dur: number): number {
  return a + (b - a) * easeOutCubic((localT - at) / dur);
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

/** The previous highlight beat before `beat` (where the highlight glides from), or null. */
export function previousHighlight(beats: Beat[], beat: Beat): Beat | null {
  let best: Beat | null = null;
  for (const b of beats) if (b.action === "highlight" && b.t < beat.t && (!best || b.t >= best.t)) best = b;
  return best;
}

/**
 * Every time the picture changes: scene starts, beats, cue starts and cue ends (caption goes blank),
 * every animation start the scenes report (absolute times), plus a progress-bar tick every `tick`
 * seconds so the bar never lags more than that in keyframe export.
 */
export function keyframes(timeline: Timeline, animationStarts: (scene: TimelineScene) => number[] = () => [], tick = 1): number[] {
  const times = new Set<number>([0]);
  for (let t = tick; t < timeline.total_seconds; t += tick) times.add(t);
  for (const s of timeline.scenes) {
    times.add(s.start);
    s.beats.forEach((b) => times.add(b.t));
    s.cues.forEach((c) => { times.add(c.start); times.add(c.end); });
    animationStarts(s).forEach((t) => times.add(t));
  }
  return [...times]
    .map((t) => Math.round(t * 1000) / 1000)
    .filter((t) => t >= 0 && t < timeline.total_seconds)
    .sort((a, b) => a - b)
    .filter((t, i, all) => i === 0 || t !== all[i - 1]);
}

export type { Scene };
