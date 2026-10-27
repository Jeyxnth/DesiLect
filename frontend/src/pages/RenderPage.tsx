import { useEffect, useMemo, useState } from "react";
import CaptionBar from "../player/CaptionBar";
import { ManualClock, useClockTime } from "../player/clock";
import { sceneAt } from "../scenes/anim";
import { renderScene } from "../scenes/registry";
import type { Timeline } from "../types/lesson";

declare global {
  interface Window {
    /** Set by Playwright to render the frame at time t (seconds). */
    __setTime?: (t: number) => void;
    /** True once the timeline is loaded and fonts are ready. */
    __ready?: boolean;
  }
}

/** 1280x720 deterministic render target for export: no timers, no transitions (G3). URL: /render?lesson=<id>. */
export default function RenderPage() {
  const lessonId = new URLSearchParams(window.location.search).get("lesson");
  const clock = useMemo(() => new ManualClock(), []);
  const t = useClockTime(clock);
  const [timeline, setTimeline] = useState<Timeline | null>(null);

  useEffect(() => {
    window.__setTime = (x: number) => clock.set(x);
    return () => { delete window.__setTime; };
  }, [clock]);

  useEffect(() => {
    if (!lessonId) return;
    fetch(`/api/lessons/${encodeURIComponent(lessonId)}/timeline`)
      .then((r) => r.json() as Promise<Timeline>)
      .then(async (tl) => {
        await document.fonts.ready;
        setTimeline(tl);
        window.__ready = true; // TODO(step 4): ensure React committed before flagging
      });
  }, [lessonId]);

  const scene = timeline ? sceneAt(timeline.scenes, t) : null;
  return (
    <div className="render-root">
      <div className="stage">{scene && renderScene(scene, t)}</div>
      <CaptionBar scene={scene} t={t} />
    </div>
  );
}
