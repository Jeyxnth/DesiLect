import { activeCue } from "../scenes/anim";
import { textWidth } from "../scenes/measure";
import { CAPTION_PX, SAFE, STAGE_W } from "../scenes/tokens";
import type { Language, TimelineScene } from "../types/lesson";

const MAX_W = STAGE_W - 2 * SAFE;
const MIN_PX = 22;

/**
 * Caption in the lesson's own script on a 70% band: the cue active at absolute time t.
 * Wraps to at most two lines; a long sentence shrinks the font so it still fits in two.
 */
export default function CaptionBar({ scene, t, lang }: { scene: TimelineScene | null; t: number; lang: Language }) {
  const text = (scene ? activeCue(scene.cues, t) : null)?.text ?? "";
  const oneLine = text ? textWidth(text, CAPTION_PX) : 0;
  const budget = 2 * MAX_W * 0.9; // two lines, with room for wrapping at word breaks
  const size = oneLine > budget ? Math.max(MIN_PX, Math.floor((CAPTION_PX * budget) / oneLine)) : CAPTION_PX;
  return (
    <div className={`caption-bar${text ? "" : " empty"}`} lang={lang} aria-live="polite">
      {text && <span style={{ fontSize: size }}>{text}</span>}
    </div>
  );
}
