// Text helpers for the one-page summary (bonus B3). Pure: everything comes from the lesson JSON.

/** The first sentence of a narration (the whole text when it is a single sentence). A short opener
  *  such as "Welcome!" (three words at most) is skipped when more follows, so the key point says something. */
export function firstSentence(text: string): string {
  const rest = text.trim();
  const m = /^.*?[.?!।](?=\s|$)/s.exec(rest);
  if (!m) return rest;
  const first = m[0].trim();
  const after = rest.slice(m[0].length).trim();
  return first.split(/\s+/).length <= 3 && after ? firstSentence(after) : first;
}

/** Cut to at most `max` characters at a word boundary, with "..." when cut. */
export function cutAtWord(text: string, max: number): string {
  if (text.length <= max) return text;
  const cut = text.slice(0, max - 3);
  const space = cut.lastIndexOf(" ");
  return `${(space > max / 2 ? cut.slice(0, space) : cut).replace(/[\s,;:.।-]+$/, "")}...`;
}

/** At most `max` lines; a "..." line marks the cut. */
export function cutLines(code: string, max: number): string {
  const lines = code.split("\n");
  return lines.length <= max ? code : [...lines.slice(0, max), "..."].join("\n");
}

/**
 * Shrink steps tried in order until the page fits A4 (never a second page):
 * 0 everything, 1 no diagrams, 2 key points cut to 140 characters, 3 code cut to 6 lines, then smaller type.
 */
export interface Fit {
  diagrams: boolean;
  keyPointMax: number | null;
  codeLines: number;
  scale: number;
}

export const FIT_STEPS: Fit[] = [
  { diagrams: true, keyPointMax: null, codeLines: 12, scale: 1 },
  { diagrams: false, keyPointMax: null, codeLines: 12, scale: 1 },
  { diagrams: false, keyPointMax: 140, codeLines: 12, scale: 1 },
  { diagrams: false, keyPointMax: 140, codeLines: 6, scale: 1 },
  { diagrams: false, keyPointMax: 140, codeLines: 6, scale: 0.9 },
  { diagrams: false, keyPointMax: 140, codeLines: 6, scale: 0.8 },
];
