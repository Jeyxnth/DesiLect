import { activeCue } from "../scenes/anim";
import { wrapCaption } from "../scenes/measure";
import { CAPTION_PX, SAFE, STAGE_W } from "../scenes/tokens";
import type { Language, TimelineScene } from "../types/lesson";

const MAX_W = STAGE_W - 2 * SAFE;
const MIN_PX = 22;

/**
 * Caption in the lesson's own script on a 70% band: the cue active at absolute time t.
 * Wrapped by us (Intl.Segmenter: word boundaries, grapheme boundaries inside an over-long word) into at most two
 * lines; a long sentence shrinks the font so it still fits in two. Explicit lines instead of a CSS line clamp,
 * which clips Devanagari and Tamil matras.
 */
/** Wrap every cue of the lesson once (after the fonts load), so a new caption never measures text mid-playback. */
export function warmCaptions(scenes: TimelineScene[], lang: Language): void {
  for (const s of scenes) for (const c of s.cues) wrapCaption(c.text, CAPTION_PX, MIN_PX, MAX_W, lang);
}

export default function CaptionBar({ scene, t, lang }: { scene: TimelineScene | null; t: number; lang: Language }) {
  const text = (scene ? activeCue(scene.cues, t) : null)?.text ?? "";
  const { lines, size } = text ? wrapCaption(text, CAPTION_PX, MIN_PX, MAX_W, lang) : { lines: [], size: CAPTION_PX };
  return (
    <div className={`caption-bar${text ? "" : " empty"}`} lang={lang} aria-live="polite">
      {text && (
        <span className="caption-text" style={{ fontSize: size }}>
          {lines.map((line, i) => <span key={i} className="caption-line">{line}</span>)}
        </span>
      )}
    </div>
  );
}
