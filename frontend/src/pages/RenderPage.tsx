import { useEffect, useMemo, useState } from "react";
import { ManualClock, useClock } from "../player/clock";
import { loadTimeline } from "../player/loadTimeline";
import { Stage } from "../player/Player";
import { SETTLE_S, keyframes } from "../scenes/anim";
import type { Timeline } from "../types/lesson";

declare global {
  interface Window {
    /** Show lesson time t, resolving after the next paint and after fonts are ready. */
    __seek?: (t: number) => Promise<void>;
    /** True once the timeline is loaded, fonts are ready and the first frame is painted. */
    __ready?: boolean;
    /** Every time (seconds) at which the picture changes (incl. 1 s progress ticks), ascending. */
    __keyframes?: () => number[];
    /** Seconds scene animations need to finish after a keyframe (capture at keyframe + this, before the next keyframe). */
    __settle?: number;
  }
}

const nextPaint = () =>
  new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));

/**
 * /render/:id?t=12: exactly 1280x720, no controls, driven only by window.__seek (G3).
 * No timers or transitions: the picture is a pure function of the time last seeked to.
 */
export default function RenderPage({ id }: { id: string }) {
  const clock = useMemo(() => new ManualClock(), []);
  const { t, refresh } = useClock(clock);
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    window.__ready = false;
    loadTimeline(id).then(setTimeline).catch((e: Error) => setError(e.message));
  }, [id]);

  useEffect(() => {
    if (!timeline) return;
    const seek = async (x: number) => {
      await Promise.resolve(); // leave React's effect phase so flushSync is allowed
      clock.seek(x);
      refresh();
      await document.fonts.ready;
      await nextPaint();
    };
    window.__seek = seek;
    window.__keyframes = () => keyframes(timeline);
    window.__settle = SETTLE_S;
    const start = Number(new URLSearchParams(window.location.search).get("t") ?? 0);
    void seek(Number.isFinite(start) ? start : 0).then(() => { window.__ready = true; });
    return () => {
      delete window.__seek;
      delete window.__keyframes;
      delete window.__settle;
      window.__ready = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [timeline, clock]);

  return (
    <div className="render-root">
      {error && <p className="notice">{error}</p>}
      {timeline && <Stage timeline={timeline} t={t} />}
    </div>
  );
}
