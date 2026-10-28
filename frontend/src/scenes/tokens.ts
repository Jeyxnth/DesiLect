// Design tokens for the 1280x720 stage. theme.css mirrors these as CSS variables; change both together.
import type { Language } from "../types/lesson";

export const STAGE_W = 1280;
export const STAGE_H = 720;

/** Safe margin on every side of the stage. */
export const SAFE = 64;

/** The scene SVG area: below the step pill, above the caption band. */
export const SCENE_TOP = 72;
export const SCENE_H = 528;

export const HEADING_PX = 44;
export const BODY_PX = 28;
export const CAPTION_PX = 30;

/** Smallest sizes text may shrink to before it would be unreadable on a phone. */
export const MIN_BODY_PX = 18;
export const MIN_CODE_PX = 15;

export const FONT_UI = '"Noto Sans", "Noto Sans Devanagari", "Noto Sans Tamil", system-ui, sans-serif';
export const FONT_CODE = '"Noto Sans Mono", ui-monospace, Consolas, monospace'; // taste-skill-ignore: real code in code scenes

/** Headings (title card, scene headings): the bold serif, per language (theme.css --font-head on [lang]). */
export const FONT_HEAD = '"Noto Serif", "Noto Serif Devanagari", "Noto Serif Tamil", "Noto Sans", serif';
export const FONT_HEAD_BY_LANG: Record<Language, string> = {
  en: '"Noto Serif", "Noto Sans", serif',
  hi: '"Noto Serif Devanagari", "Noto Serif", "Noto Sans Devanagari", serif',
  ta: '"Noto Serif Tamil", "Noto Serif", "Noto Sans Tamil", serif',
};

/** Stage font stack per lesson language (theme.css sets the same stacks on [lang]); the script's own font first. */
export const FONT_UI_BY_LANG: Record<Language, string> = {
  en: '"Noto Sans", system-ui, sans-serif',
  hi: '"Noto Sans Devanagari", "Noto Sans", system-ui, sans-serif',
  ta: '"Noto Sans Tamil", "Noto Sans", system-ui, sans-serif',
};

/** Line-spacing multiplier: Devanagari and Tamil matras reach above and below Latin text, so their lines are taller. */
export const LINE_SCALE: Record<Language, number> = { en: 1, hi: 1.25, ta: 1.25 };

/** Scene heading baseline inside the scene SVG. */
export const HEADING_Y = 58;
