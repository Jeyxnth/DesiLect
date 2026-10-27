import { activeCue } from "../scenes/anim";
import type { TimelineScene } from "../types/lesson";

/** Caption in the lesson's own script, from the current scene's cues. */
export default function CaptionBar({ scene, t }: { scene: TimelineScene | null; t: number }) {
  const cue = scene ? activeCue(scene.cues, t) : null;
  return <div className="caption-bar" aria-live="polite">{cue?.text ?? ""}</div>;
}
