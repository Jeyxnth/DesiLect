import { useEffect, useMemo } from "react";
import { renderScene } from "../scenes/registry";
import { sceneAt } from "../scenes/anim";
import type { Timeline } from "../types/lesson";
import CaptionBar from "./CaptionBar";
import { PlaybackClock, useClockTime } from "./clock";
import Controls from "./Controls";
import ProgressBar from "./ProgressBar";

/** Interactive player. TODO(step 3): sync with <audio>, keyboard, fullscreen. */
export default function Player({ timeline }: { timeline: Timeline }) {
  const clock = useMemo(() => new PlaybackClock(timeline.total_seconds), [timeline]);
  const t = useClockTime(clock);
  useEffect(() => () => clock.pause(), [clock]);

  const scene = sceneAt(timeline.scenes, t);
  const jump = (offset: number) => {
    const i = Math.min(timeline.scenes.length - 1, Math.max(0, (scene?.index ?? 0) + offset));
    clock.set(timeline.scenes[i]?.start ?? 0);
  };

  return (
    <div>
      <div className="step-heading">
        {scene ? `Step ${scene.index + 1} of ${timeline.scenes.length}: ${scene.heading}` : ""}
      </div>
      <div className="stage">{scene && renderScene(scene, t)}</div>
      <CaptionBar scene={scene} t={t} />
      <ProgressBar t={t} total={timeline.total_seconds} onSeek={(x) => clock.set(x)} />
      <Controls
        playing={clock.isPlaying()}
        onToggle={() => (clock.isPlaying() ? clock.pause() : clock.play())}
        onPrev={() => jump(-1)}
        onNext={() => jump(1)}
        onReplay={() => { clock.set(0); clock.play(); }}
      />
    </div>
  );
}
