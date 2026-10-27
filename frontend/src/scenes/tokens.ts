// Design tokens for the 1280x720 stage. theme.css mirrors these as CSS variables; change both together.

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
export const FONT_CODE = '"Noto Sans Mono", ui-monospace, Consolas, monospace';

/** Scene heading baseline inside the scene SVG. */
export const HEADING_Y = 58;
