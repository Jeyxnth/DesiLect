import { useEffect, useState } from "react";
import { flushSync } from "react-dom";

/** Source of lesson time (seconds). Scenes never read it: they get localT from the Player. */
export interface Clock {
  now(): number;
  play(): void;
  pause(): void;
  seek(t: number): void;
  isPlaying(): boolean;
}

/** Time is whatever the caller last set. Used by the render page (G3: no timers, no playback). */
export class ManualClock implements Clock {
  private t = 0;
  now(): number { return this.t; }
  play(): void {}
  pause(): void {}
  seek(t: number): void { this.t = Math.max(0, t); }
  isPlaying(): boolean { return false; }
}

/** Time comes from the audio element playing lesson.wav, so picture and voice cannot drift apart. */
export class AudioClock implements Clock {
  constructor(private readonly audio: HTMLAudioElement) {}
  now(): number { return this.audio.currentTime; }
  play(): void { void this.audio.play().catch(() => {}); }
  pause(): void { this.audio.pause(); }
  seek(t: number): void { this.audio.currentTime = Math.max(0, t); }
  isPlaying(): boolean { return !this.audio.paused && !this.audio.ended; }
}

export interface ClockState {
  t: number;
  playing: boolean;
  /** Synchronously re-read the clock and commit the render (used by the render page). */
  refresh: () => void;
}

/** A requestAnimationFrame loop reads clock.now() and re-renders when it changed. */
export function useClock(clock: Clock): ClockState {
  const [state, setState] = useState(() => ({ t: clock.now(), playing: clock.isPlaying() }));
  const read = () => setState((s) => {
    const next = { t: clock.now(), playing: clock.isPlaying() };
    return s.t === next.t && s.playing === next.playing ? s : next;
  });
  useEffect(() => {
    let raf = 0;
    const loop = () => { read(); raf = requestAnimationFrame(loop); };
    read();
    raf = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(raf);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clock]);
  return { ...state, refresh: () => flushSync(read) };
}
