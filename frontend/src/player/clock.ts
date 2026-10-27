import { useSyncExternalStore } from "react";

/** Source of lesson time t (seconds). The player and the render page share this interface. */
export interface Clock {
  now(): number;
  set(t: number): void;
  play(): void;
  pause(): void;
  isPlaying(): boolean;
  subscribe(listener: () => void): () => void;
}

/** Time only moves when set() is called. Used by the render page (G3: no timers). */
export class ManualClock implements Clock {
  protected t = 0;
  protected listeners = new Set<() => void>();
  now(): number { return this.t; }
  set(t: number): void { this.t = Math.max(0, t); this.emit(); }
  play(): void {}
  pause(): void {}
  isPlaying(): boolean { return false; }
  subscribe(listener: () => void): () => void {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }
  protected emit(): void { this.listeners.forEach((l) => l()); }
}

/** Interactive clock driven by requestAnimationFrame. TODO(step 3): drive from the audio element. */
export class PlaybackClock extends ManualClock {
  private playing = false;
  private last = 0;
  private raf = 0;
  constructor(private readonly duration: number) { super(); }
  override play(): void {
    if (this.playing) return;
    if (this.t >= this.duration) this.t = 0;
    this.playing = true;
    this.last = performance.now();
    const tick = (now: number) => {
      if (!this.playing) return;
      this.t = Math.min(this.duration, this.t + (now - this.last) / 1000);
      this.last = now;
      if (this.t >= this.duration) this.playing = false;
      this.emit();
      if (this.playing) this.raf = requestAnimationFrame(tick);
    };
    this.raf = requestAnimationFrame(tick);
    this.emit();
  }
  override pause(): void {
    this.playing = false;
    cancelAnimationFrame(this.raf);
    this.emit();
  }
  override isPlaying(): boolean { return this.playing; }
}

/** React hook: re-render whenever the clock changes; returns current t. */
export function useClockTime(clock: Clock): number {
  return useSyncExternalStore(clock.subscribe.bind(clock), clock.now.bind(clock));
}
