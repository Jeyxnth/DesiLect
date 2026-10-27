// Text measurement for layout (boxes sized to their labels). Deterministic once fonts are loaded,
// so layouts stay a pure function of the scene: the render page waits for document.fonts before drawing.
import { useEffect, useState } from "react";
import type { Language } from "../types/lesson";
import { FONT_CODE, FONT_UI, FONT_UI_BY_LANG } from "./tokens";

export interface TextOpts {
  bold?: boolean;
  mono?: boolean;
  /** Lesson language: measures with that script's font stack (the one the stage draws with). */
  lang?: Language;
}

/** True once the bundled fonts have loaded; layouts memoised on it are measured again then. */
export function useFontsReady(): boolean {
  const [ready, setReady] = useState(() => typeof document === "undefined" || document.fonts?.status === "loaded");
  useEffect(() => {
    if (ready || !document.fonts) return;
    let live = true;
    void document.fonts.ready.then(() => { if (live) setReady(true); });
    return () => { live = false; };
  }, [ready]);
  return ready;
}

let ctx: CanvasRenderingContext2D | null = null;
const cache = new Map<string, number>();

// Ask the browser to load the bundled faces now; canvas measuring alone does not trigger a load.
// document.fonts.ready (awaited by __seek) then also waits for the Devanagari and Tamil faces.
if (typeof document !== "undefined" && document.fonts) {
  const specs: [string, string][] = [
    ['400 28px "Noto Sans"', "A"], ['700 28px "Noto Sans"', "A"], ['400 28px "Noto Sans Mono"', "A"],
    ['400 28px "Noto Sans Devanagari"', "क"], ['700 28px "Noto Sans Devanagari"', "क"],
    ['400 28px "Noto Sans Tamil"', "த"], ['700 28px "Noto Sans Tamil"', "த"],
  ];
  for (const [spec, sample] of specs) void document.fonts.load(spec, sample).catch(() => {});
}

/** Width in px of `text` at `size` px. Falls back to an average-glyph estimate without a canvas. */
export function textWidth(text: string, size: number, opts: TextOpts = {}): number {
  const family = opts.mono ? FONT_CODE : opts.lang ? FONT_UI_BY_LANG[opts.lang] : FONT_UI;
  const font = `${opts.bold ? 700 : 400} ${size}px ${family}`;
  const key = `${font}|${text}`;
  const hit = cache.get(key);
  if (hit !== undefined) return hit;
  if (!ctx && typeof document !== "undefined") ctx = document.createElement("canvas").getContext("2d");
  let w: number;
  if (ctx) {
    ctx.font = font;
    w = ctx.measureText(text).width;
  } else {
    w = [...text].length * size * (opts.mono ? 0.6 : 0.55);
  }
  // Only remember results measured with the real fonts, so a first frame drawn early cannot stick.
  if (typeof document === "undefined" || document.fonts?.status === "loaded") cache.set(key, w);
  return w;
}

/** Largest size in [min, max] (whole px) at which `text` fits in `width`. */
export function fitSize(text: string, max: number, min: number, width: number, opts: TextOpts = {}): number {
  const w = textWidth(text, max, opts);
  if (w <= width) return max;
  return Math.max(min, Math.floor((max * width) / w));
}

/**
 * Split a label into one line, or two balanced lines at a space when that is narrower.
 * Returns the lines and the width of the widest one at `size`.
 */
export function wrapLabel(text: string, size: number, maxWidth: number, opts: TextOpts = {}): { lines: string[]; width: number } {
  const one = textWidth(text, size, opts);
  const words = text.split(" ");
  if (one <= maxWidth || words.length < 2) return { lines: [text], width: one };
  let best: { lines: string[]; width: number } = { lines: [text], width: one };
  for (let i = 1; i < words.length; i++) {
    const a = words.slice(0, i).join(" ");
    const b = words.slice(i).join(" ");
    const width = Math.max(textWidth(a, size, opts), textWidth(b, size, opts));
    if (width < best.width) best = { lines: [a, b], width };
  }
  return best;
}

/**
 * Words with the spaces and punctuation that follow them, so a line never starts with "," or a space.
 * Intl.Segmenter knows word boundaries in Devanagari and Tamil; without it, split at spaces.
 */
export function wordPieces(text: string, lang: Language): string[] {
  if (typeof Intl === "undefined" || !("Segmenter" in Intl)) return text.split(/(?<=\s)/);
  const pieces: string[] = [];
  for (const s of new Intl.Segmenter(lang, { granularity: "word" }).segment(text)) {
    if (s.isWordLike || pieces.length === 0) pieces.push(s.segment);
    else pieces[pieces.length - 1] += s.segment;
  }
  return pieces;
}

/** User-perceived characters: a consonant and its matras stay together, so a forced break never splits them. */
export function graphemes(text: string, lang: Language): string[] {
  if (typeof Intl === "undefined" || !("Segmenter" in Intl)) return Array.from(text);
  return Array.from(new Intl.Segmenter(lang, { granularity: "grapheme" }).segment(text), (s) => s.segment);
}

/** Greedy line wrap at word boundaries; a single piece wider than the line is broken at grapheme boundaries. */
export function wrapLines(text: string, size: number, maxWidth: number, lang: Language): string[] {
  const fits = (s: string) => textWidth(s.trimEnd(), size, { lang }) <= maxWidth;
  const lines: string[] = [];
  let line = "";
  for (const piece of wordPieces(text, lang)) {
    if (fits(line + piece)) { line += piece; continue; }
    if (line) lines.push(line.trimEnd());
    line = "";
    if (fits(piece)) { line = piece; continue; }
    for (const g of graphemes(piece, lang)) {
      if (line && !fits(line + g)) { lines.push(line.trimEnd()); line = ""; }
      line += g;
    }
  }
  if (line.trim()) lines.push(line.trimEnd());
  return lines;
}

/** Caption lines: the largest size in [min, max] at which `text` wraps into at most maxLines lines. */
export function wrapCaption(text: string, max: number, min: number, maxWidth: number, lang: Language, maxLines = 2): { lines: string[]; size: number } {
  for (let size = max; size > min; size--) {
    const lines = wrapLines(text, size, maxWidth, lang);
    if (lines.length <= maxLines) return { lines, size };
  }
  return { lines: wrapLines(text, min, maxWidth, lang), size: min };
}
