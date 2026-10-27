import { useEffect, useMemo, useRef, useState } from "react";
import { sceneAt } from "../scenes/anim";
import { renderScene } from "../scenes/registry";
import type { Timeline } from "../types/lesson";
import CaptionBar from "./CaptionBar";
import { AudioClock, ManualClock, useClock, type Clock } from "./clock";
import Controls from "./Controls";
import ProgressBar from "./ProgressBar";

export const STAGE_W = 1280;
export const STAGE_H = 720;

/**
 * The 1280x720 logical stage: step heading on top, scene, caption, thin progress bar.
 * A pure function of (timeline, t): the render page and the player both use it.
 */
export function Stage({ timeline, t, onSeek, showProgress = true }: {
  timeline: Timeline;
  t: number;
  onSeek?: (t: number) => void;
  showProgress?: boolean;
}) {
  const scene = sceneAt(timeline.scenes, t);
  const lang = timeline.language;
  return (
    <div className="stage-canvas" lang={lang}>
      <div className="step-heading">
        {scene ? `Step ${scene.index + 1} of ${timeline.scenes.length}: ${scene.heading}` : ""}
      </div>
      <div className="scene-area">{scene && renderScene(scene, t, lang)}</div>
      <CaptionBar scene={scene} t={t} lang={lang} />
      {showProgress && <ProgressBar t={t} total={timeline.total_seconds} onSeek={onSeek} />}
    </div>
  );
}

/** Width of `ref` in px, kept current with a ResizeObserver. */
function useWidth(ref: React.RefObject<HTMLElement>): number {
  const [w, setW] = useState(STAGE_W);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setW(el.clientWidth || STAGE_W));
    ro.observe(el);
    setW(el.clientWidth || STAGE_W);
    return () => ro.disconnect();
  }, [ref]);
  return w;
}

/** Interactive player: audio drives the clock; controls seek by scene. */
export default function Player({ timeline }: { timeline: Timeline }) {
  const [audioFailed, setAudioFailed] = useState(false);
  const clock = useMemo<Clock>(() => {
    if (audioFailed) return new ManualClock(); // no audio: scrubbing only
    const audio = new Audio();
    audio.preload = "auto";
    audio.addEventListener("error", () => setAudioFailed(true));
    audio.src = timeline.audio_url;
    return new AudioClock(audio);
  }, [timeline, audioFailed]);
  useEffect(() => () => clock.pause(), [clock]);

  const { t, playing } = useClock(clock);
  const fitRef = useRef<HTMLDivElement>(null);
  const scale = useWidth(fitRef) / STAGE_W;

  const total = timeline.total_seconds;
  const scene = sceneAt(timeline.scenes, t);
  const goToScene = (i: number) => clock.seek(timeline.scenes[Math.max(0, Math.min(timeline.scenes.length - 1, i))]?.start ?? 0);

  const toggle = () => {
    if (clock.isPlaying()) return clock.pause();
    if (clock.now() >= total - 0.05) clock.seek(0);
    clock.play();
  };
  // Previous restarts the current scene first, and goes to the one before when already near its start.
  const prev = () => goToScene(scene && t - scene.start > 1 ? scene.index : (scene?.index ?? 0) - 1);

  return (
    <div className="player">
      <div className="stage-fit" ref={fitRef}>
        <div className="stage-scaler" style={{ transform: `scale(${scale})` }}>
          <Stage timeline={timeline} t={t} onSeek={(x) => clock.seek(x)} />
        </div>
      </div>
      {audioFailed && <p className="notice">Audio could not be loaded; scrub only.</p>}
      <Controls
        playing={playing}
        onToggle={toggle}
        onPrev={prev}
        onNext={() => goToScene((scene?.index ?? 0) + 1)}
        onReplay={() => { clock.seek(0); clock.play(); }}
      />
    </div>
  );
}
