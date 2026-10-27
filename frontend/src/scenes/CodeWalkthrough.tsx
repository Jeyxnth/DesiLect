import { useMemo } from "react";
import type { Beat, CodeWalkthroughScene } from "../types/lesson";
import { GLIDE_S, activeHighlight, fadeIn, glide, previousHighlight } from "./anim";
import { fitSize, textWidth, useFontsReady } from "./measure";
import type { SceneProps } from "./registry";
import { HEADING_PX, HEADING_Y, MIN_CODE_PX, SAFE, STAGE_W } from "./tokens";
import { say } from "./i18n";
import { codeLang, codeTerms, keyTerm, tokenizeLine } from "./tokenize";

const CARD_TOP = 92;
const CARD_MAX_H = 412;
const PAD = 22;
const NOTE_W = 280;
const NOTE_GAP = 28;
const CODE_MAX_PX = 28; // body size; long or many lines shrink it
const NOTE_IN_S = 0.3;

export function codeAnimationStarts(beats: Beat[]): number[] {
  return beats.filter((b) => b.action === "highlight").map((b) => b.t);
}

/**
 * Code card with line numbers and coloured tokens (SVG text only, never executed: H4). The highlight
 * bar glides to the line of the current beat; a side note shows the key term of the current caption.
 * Long lines shrink the font (the schema caps code at 12 lines of 50 columns, so it always fits).
 */
export default function CodeWalkthrough({ scene, localT, beats, cues, lang: uiLang }: SceneProps<CodeWalkthroughScene>) {
  const fonts = useFontsReady();
  const lines = useMemo(() => scene.code.split("\n"), [scene]);
  const lang = codeLang(scene.language_hint, scene.code);
  const tokens = useMemo(() => lines.map((l) => tokenizeLine(l, lang)), [lines, lang]);

  // Key term per caption: the longest code identifier the caption mentions.
  const terms = useMemo(() => codeTerms(scene.code), [scene]);
  const cueTerms = useMemo(() => cues.map((c) => keyTerm(c.text, terms)), [cues, terms]);
  const hasNotes = cueTerms.some((t) => t !== null);

  const geom = useMemo(() => {
    const cardW = hasNotes ? STAGE_W - 2 * SAFE - NOTE_W - NOTE_GAP : STAGE_W - 2 * SAFE;
    const gutter = textWidth(String(lines.length), CODE_MAX_PX, { mono: true }) + 28;
    const widest = lines.reduce((a, b) => (b.length > a.length ? b : a), "") || " ";
    const byWidth = fitSize(widest, CODE_MAX_PX, MIN_CODE_PX, cardW - 2 * PAD - gutter, { mono: true });
    const byHeight = Math.floor((CARD_MAX_H - 2 * PAD) / (lines.length * 1.5));
    const size = Math.max(MIN_CODE_PX, Math.min(byWidth, byHeight));
    const lineH = size * 1.5;
    return { cardW, gutter: textWidth(String(lines.length), size, { mono: true }) + 24, size, lineH, cardH: lines.length * lineH + 2 * PAD };
  }, [lines, hasNotes, fonts]); // fonts: re-measure once the real fonts have loaded

  const { cardW, gutter, size, lineH, cardH } = geom;
  const x0 = SAFE;
  const lineY = (n: number) => CARD_TOP + PAD + (n - 1) * lineH; // top of 1-based line n

  // Highlight bar: glides from the previous highlighted line to the current one.
  const hl = activeHighlight(beats, localT);
  const prev = hl ? previousHighlight(beats, hl) : null;
  const barY = hl ? glide(lineY(prev?.value ?? hl.value), lineY(hl.value), localT, hl.t, GLIDE_S) : 0;
  const barAlpha = hl ? (prev ? 1 : fadeIn(localT, hl.t, GLIDE_S)) : 0;
  const dim = hl ? fadeIn(localT, hl.t, GLIDE_S) : 0;

  // Side note: the key term of the latest caption that has started (stays through sentence gaps).
  let cueIndex = -1;
  cues.forEach((c, i) => { if (c.start <= localT) cueIndex = i; });
  let noteIndex = -1;
  for (let i = cueIndex; i >= 0; i--) if (cueTerms[i]) { noteIndex = i; break; }
  const term = noteIndex >= 0 ? cueTerms[noteIndex] : null;
  const noteAlpha = term ? fadeIn(localT, cues[noteIndex]?.start ?? 0, NOTE_IN_S) : 0;
  const noteX = x0 + cardW + NOTE_GAP;
  const headingSize = fitSize(scene.heading, HEADING_PX, 30, STAGE_W - 2 * SAFE, { bold: true, lang: uiLang });

  return (
    <svg viewBox="0 0 1280 528" role="img" aria-label={scene.heading}>
      <text className="scene-text" x={x0} y={HEADING_Y} fontWeight="700" fontSize={headingSize}>{scene.heading}</text>
      <rect x={x0} y={CARD_TOP} width={cardW} height={cardH} rx="16" fill="var(--code-bg)" stroke="var(--box-edge)" strokeWidth="1.5" />
      {hl && (
        <g opacity={barAlpha} transform={`translate(0 ${barY})`}>
          <rect x={x0 + 6} y={0} width={cardW - 12} height={lineH} rx="8" fill="var(--accent)" opacity="0.18" />
          <rect x={x0 + 6} y={0} width={5} height={lineH} rx="2.5" fill="var(--accent)" />
        </g>
      )}
      {tokens.map((toks, i) => {
        const on = hl?.value === i + 1;
        const baseline = lineY(i + 1) + lineH * 0.7;
        return (
          <g key={i} opacity={on ? 1 : 1 - 0.4 * dim}>
            <text className="scene-code code-ln" x={x0 + PAD + gutter - 18} y={baseline} textAnchor="end" fontSize={size}>{i + 1}</text>
            <text className="scene-code" x={x0 + PAD + gutter} y={baseline} fontSize={size} xmlSpace="preserve">
              {toks.map((t, k) => <tspan key={k} className={`tok-${t.kind}`}>{t.text}</tspan>)}
            </text>
          </g>
        );
      })}
      {term && (
        <g opacity={noteAlpha} transform={`translate(${(1 - noteAlpha) * 16} 0)`}>
          <rect x={noteX} y={CARD_TOP} width={NOTE_W} height={132} rx="16" fill="var(--panel-2)" stroke="var(--accent)" strokeWidth="2" />
          <text className="scene-text scene-muted" x={noteX + 22} y={CARD_TOP + 42} fontSize="20">{say(uiLang, "keyTerm")}</text>
          <text className="scene-code tok-kw" x={noteX + 22} y={CARD_TOP + 96} fontSize={fitSize(term, 34, 18, NOTE_W - 44, { mono: true })}>{term}</text>
        </g>
      )}
    </svg>
  );
}
