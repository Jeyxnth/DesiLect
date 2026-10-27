// Text measurement for layout (boxes sized to their labels). Deterministic once fonts are loaded,
// so layouts stay a pure function of the scene: the render page waits for document.fonts before drawing.
import { useEffect, useState } from "react";
import { FONT_CODE, FONT_UI } from "./tokens";

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
if (typeof document !== "undefined" && document.fonts) {
  for (const spec of ['400 28px "Noto Sans"', '700 28px "Noto Sans"', '400 28px "Noto Sans Mono"']) {
    void document.fonts.load(spec).catch(() => {});
  }
}

/** Width in px of `text` at `size` px. Falls back to an average-glyph estimate without a canvas. */
export function textWidth(text: string, size: number, opts: { bold?: boolean; mono?: boolean } = {}): number {
  const font = `${opts.bold ? 700 : 400} ${size}px ${opts.mono ? FONT_CODE : FONT_UI}`;
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
export function fitSize(text: string, max: number, min: number, width: number, opts: { bold?: boolean; mono?: boolean } = {}): number {
  const w = textWidth(text, max, opts);
  if (w <= width) return max;
  return Math.max(min, Math.floor((max * width) / w));
}

/**
 * Split a label into one line, or two balanced lines at a space when that is narrower.
 * Returns the lines and the width of the widest one at `size`.
 */
export function wrapLabel(text: string, size: number, maxWidth: number, opts: { bold?: boolean } = {}): { lines: string[]; width: number } {
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
