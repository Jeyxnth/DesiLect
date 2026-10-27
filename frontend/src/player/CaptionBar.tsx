import { activeCue } from "../scenes/anim";
import type { Language, TimelineScene } from "../types/lesson";

/** Caption in the lesson's own script: the cue active at absolute time t. */
export default function CaptionBar({ scene, t, lang }: { scene: TimelineScene | null; t: number; lang: Language }) {
  const cue = scene ? activeCue(scene.cues, t) : null;
  return <div className="caption-bar" lang={lang} aria-live="polite">{cue?.text ?? ""}</div>;
}
