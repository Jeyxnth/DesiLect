import { useMemo } from "react";
import type { Arrow, Beat, DiagramScene as Diagram } from "../types/lesson";
import { ARROW_DELAY_S, ARROW_DRAW_S, ITEM_IN_S, clamp01, fadeIn, progress, revealTime } from "./anim";
import { fitSize, textWidth, useFontsReady, wrapLabel } from "./measure";
import type { SceneProps } from "./registry";
import { BODY_PX, HEADING_PX, HEADING_Y, MIN_BODY_PX, SAFE, STAGE_W } from "./tokens";

// Content area inside the 1280x528 scene SVG, below the heading.
const LEFT = SAFE;
const RIGHT = STAGE_W - SAFE;
const TOP = 100;
const BOTTOM = 516;
const AREA_W = RIGHT - LEFT;
const AREA_H = BOTTOM - TOP;

const PAD_X = 34;
const PAD_Y = 22; // row and cycle; stacks use STACK_PAD_Y so five boxes still fit at body size
const STACK_PAD_Y = 12;
const STACK_MIN_GAP = 40;
const MIN_BOX_W = 168;
const MIN_GAP = 64; // shortest arrow between neighbours
const LABEL_ROOM = 28; // space around an arrow label inside a gap
const EDGE = 6; // arrows stop this far from a box

interface Box {
  cx: number;
  cy: number;
  w: number;
  h: number;
  lines: string[];
}

interface Layout {
  boxes: Box[];
  size: number; // label font size, the same for every box (consistent sizes)
  labelSize: number; // arrow label font size
  scale: number; // < 1 only if nothing fits even at the smallest size
}

type Pt = { x: number; y: number };

const arrowLabelSize = (size: number) => Math.max(16, size - 6);

/** Box sizes for every label at one font size (one line, or two balanced lines if that is narrower). */
function sizeBoxes(items: string[], size: number, maxLineW: number, padY = PAD_Y): { w: number; h: number; lines: string[] }[] {
  const wrapped = items.map((label) => wrapLabel(label, size, maxLineW));
  const lineCount = Math.max(...wrapped.map((w) => w.lines.length));
  const h = lineCount * size * 1.25 + 2 * padY;
  return wrapped.map((w) => ({ w: Math.max(MIN_BOX_W, w.width + 2 * PAD_X), h, lines: w.lines }));
}

/** Width an arrow label needs, or 0. */
function labelW(arrow: Arrow | undefined, size: number): number {
  return arrow?.label ? textWidth(arrow.label, arrowLabelSize(size)) : 0;
}

function adjacentArrow(arrows: Arrow[], a: number, b: number): Arrow | undefined {
  return arrows.find((x) => (x.from === a && x.to === b) || (x.from === b && x.to === a));
}

function layoutRow(items: string[], arrows: Arrow[]): Layout {
  const n = items.length;
  const hasCurves = arrows.some((a) => Math.abs(a.to - a.from) > 1);
  for (let size = BODY_PX; size >= MIN_BODY_PX; size--) {
    const gaps = Array.from({ length: n - 1 }, (_, k) => Math.max(MIN_GAP, labelW(adjacentArrow(arrows, k, k + 1), size) + LABEL_ROOM));
    const maxLineW = (AREA_W - gaps.reduce((a, b) => a + b, 0)) / n - 2 * PAD_X;
    const sized = sizeBoxes(items, size, maxLineW);
    const total = sized.reduce((a, b) => a + b.w, 0) + gaps.reduce((a, b) => a + b, 0);
    if (total <= AREA_W || size === MIN_BODY_PX) {
      const cy = hasCurves ? TOP + AREA_H * 0.62 : TOP + AREA_H * 0.5;
      let x = LEFT + (AREA_W - total) / 2;
      const boxes = sized.map((b, k) => {
        const box = { ...b, cx: x + b.w / 2, cy };
        x += b.w + (gaps[k] ?? 0);
        return box;
      });
      return { boxes, size, labelSize: arrowLabelSize(size), scale: Math.min(1, AREA_W / total) };
    }
  }
  throw new Error("unreachable");
}

function layoutStack(items: string[], arrows: Arrow[]): Layout {
  const n = items.length;
  for (let size = BODY_PX; size >= MIN_BODY_PX; size--) {
    const sized = sizeBoxes(items, size, AREA_W * 0.5, STACK_PAD_Y);
    const w = Math.max(...sized.map((b) => b.w)); // one column, equal widths
    const h = sized[0]?.h ?? 0;
    const room = Math.min(56, (AREA_H - n * h) / Math.max(1, n - 1));
    if (room >= STACK_MIN_GAP || size === MIN_BODY_PX) {
      const gap = Math.max(room, STACK_MIN_GAP); // arrows stay long enough to read
      const total = n * h + (n - 1) * gap;
      const sideLabels = Math.max(0, ...arrows.map((a) => labelW(a, size)));
      const cx = 640 - (sideLabels ? Math.min(160, sideLabels / 2 + 20) : 0);
      const y0 = TOP + (AREA_H - total) / 2;
      const boxes = sized.map((b, k) => ({ ...b, w, cx, cy: y0 + k * (h + gap) + h / 2 }));
      return { boxes, size, labelSize: arrowLabelSize(size), scale: Math.min(1, AREA_H / total) };
    }
  }
  throw new Error("unreachable");
}

function layoutCycle(items: string[]): Layout {
  const n = items.length;
  for (let size = BODY_PX; size >= MIN_BODY_PX; size--) {
    const sized = sizeBoxes(items, size, 250);
    const maxW = Math.max(...sized.map((b) => b.w));
    const h = sized[0]?.h ?? 0;
    const ry = (AREA_H - h) / 2;
    const rx = Math.min(AREA_W / 2 - maxW / 2, Math.max(ry * 1.5, 220));
    const centre = { x: 640, y: TOP + AREA_H / 2 };
    const boxes = sized.map((b, k) => {
      const a = -Math.PI / 2 + (2 * Math.PI * k) / n; // clockwise from the top (screen y points down)
      return { ...b, cx: centre.x + rx * Math.cos(a), cy: centre.y + ry * Math.sin(a) };
    });
    const overlap = boxes.some((b, i) => boxes.some((o, j) => j > i && Math.abs(b.cx - o.cx) < (b.w + o.w) / 2 + 12 && Math.abs(b.cy - o.cy) < (b.h + o.h) / 2 + 12));
    if ((!overlap && rx > 0) || size === MIN_BODY_PX) return { boxes, size, labelSize: arrowLabelSize(size), scale: 1 };
  }
  throw new Error("unreachable");
}

/** Where the ray from the box centre toward (tx, ty) leaves the box (plus a small margin). */
function edgePoint(b: Box, tx: number, ty: number): Pt {
  const dx = tx - b.cx;
  const dy = ty - b.cy;
  const s = Math.min(dx ? (b.w / 2 + EDGE) / Math.abs(dx) : Infinity, dy ? (b.h / 2 + EDGE) / Math.abs(dy) : Infinity);
  return { x: b.cx + dx * s, y: b.cy + dy * s };
}

interface ArrowGeom {
  d: string;
  end: Pt;
  dir: Pt; // direction at the end, for the arrowhead
  label: Pt;
  anchor: "start" | "middle" | "end";
}

function quad(a: Pt, c: Pt, b: Pt): string {
  return `M${a.x.toFixed(1)} ${a.y.toFixed(1)} Q${c.x.toFixed(1)} ${c.y.toFixed(1)} ${b.x.toFixed(1)} ${b.y.toFixed(1)}`;
}

/** Geometry of one arrow for the given layout kind. Labels sit beside the line. */
function arrowGeom(kind: Diagram["layout"], from: Box, to: Box, adjacent: boolean, centre: Pt): ArrowGeom {
  if (kind === "row" && adjacent) {
    const right = to.cx > from.cx;
    const a = { x: from.cx + (right ? 1 : -1) * (from.w / 2 + EDGE), y: from.cy };
    const b = { x: to.cx - (right ? 1 : -1) * (to.w / 2 + EDGE), y: to.cy };
    return { d: `M${a.x} ${a.y} L${b.x} ${b.y}`, end: b, dir: { x: right ? 1 : -1, y: 0 }, label: { x: (a.x + b.x) / 2, y: a.y - 14 }, anchor: "middle" };
  }
  if (kind === "row") {
    const a = { x: from.cx, y: from.cy - from.h / 2 - EDGE };
    const b = { x: to.cx, y: to.cy - to.h / 2 - EDGE };
    const c = { x: (a.x + b.x) / 2, y: Math.min(a.y, b.y) - 110 };
    return { d: quad(a, c, b), end: b, dir: { x: b.x - c.x, y: b.y - c.y }, label: { x: c.x, y: (a.y + c.y) / 2 - 6 }, anchor: "middle" };
  }
  if (kind === "stack" && adjacent) {
    const down = to.cy > from.cy;
    const a = { x: from.cx, y: from.cy + (down ? 1 : -1) * (from.h / 2 + EDGE) };
    const b = { x: to.cx, y: to.cy - (down ? 1 : -1) * (to.h / 2 + EDGE) };
    return { d: `M${a.x} ${a.y} L${b.x} ${b.y}`, end: b, dir: { x: 0, y: down ? 1 : -1 }, label: { x: a.x + 16, y: (a.y + b.y) / 2 + 7 }, anchor: "start" };
  }
  if (kind === "stack") {
    const a = { x: from.cx - from.w / 2 - EDGE, y: from.cy };
    const b = { x: to.cx - to.w / 2 - EDGE, y: to.cy };
    const c = { x: Math.min(a.x, b.x) - 90, y: (a.y + b.y) / 2 };
    return { d: quad(a, c, b), end: b, dir: { x: b.x - c.x, y: b.y - c.y }, label: { x: (a.x + c.x) / 2 - 8, y: c.y + 7 }, anchor: "end" };
  }
  // cycle: bow outward so the arrow follows the circle clockwise
  const chord = { x: to.cx - from.cx, y: to.cy - from.cy };
  const len = Math.hypot(chord.x, chord.y) || 1;
  const out = { x: chord.y / len, y: -chord.x / len }; // perpendicular, on the outer side for clockwise travel
  const mid = { x: (from.cx + to.cx) / 2, y: (from.cy + to.cy) / 2 };
  const bulge = Math.max(48, len * 0.34);
  const c = { x: mid.x + out.x * bulge, y: mid.y + out.y * bulge };
  const a = edgePoint(from, c.x, c.y);
  const b = edgePoint(to, c.x, c.y);
  const apex = { x: 0.25 * a.x + 0.5 * c.x + 0.25 * b.x, y: 0.25 * a.y + 0.5 * c.y + 0.25 * b.y };
  const side = { x: apex.x - centre.x, y: apex.y - centre.y };
  const anchor = side.x > 40 ? "start" : side.x < -40 ? "end" : "middle";
  return {
    d: quad(a, c, b),
    end: b,
    dir: { x: b.x - c.x, y: b.y - c.y },
    label: { x: apex.x + out.x * 14, y: apex.y + out.y * 14 + (anchor === "middle" ? (out.y < 0 ? -4 : 22) : 8) },
    anchor,
  };
}

function arrowStart(reveal: number[], a: Arrow): number {
  return Math.max(reveal[a.from] ?? 0, reveal[a.to] ?? 0) + ARROW_DELAY_S;
}

export function diagramAnimationStarts(scene: Diagram, beats: Beat[]): number[] {
  const reveal = scene.items.map((_, k) => revealTime(beats, k));
  return [...reveal, ...(scene.arrows ?? []).map((a) => arrowStart(reveal, a))];
}

/**
 * Diagram: items as boxes in a row, on a cycle or in a stack. Item k scales in at its beat; arrows
 * draw on once both ends are visible. Only transform, opacity and stroke-dashoffset change over time.
 */
export default function DiagramScene({ scene, localT, beats }: SceneProps<Diagram>) {
  const fonts = useFontsReady();
  const arrows = useMemo(
    () => (scene.arrows ?? []).filter((a) => a.from !== a.to && scene.items[a.from] !== undefined && scene.items[a.to] !== undefined),
    [scene],
  );
  const layout = useMemo(
    () => (scene.layout === "cycle" ? layoutCycle(scene.items) : scene.layout === "stack" ? layoutStack(scene.items, arrows) : layoutRow(scene.items, arrows)),
    [scene, arrows, fonts], // fonts: re-measure once the real fonts have loaded
  );
  const centre = { x: 640, y: TOP + AREA_H / 2 };
  const reveal = scene.items.map((_, k) => revealTime(beats, k));
  let newest = -1;
  reveal.forEach((r, k) => { if (r <= localT && (newest < 0 || r >= (reveal[newest] ?? 0))) newest = k; });

  const headingSize = fitSize(scene.heading, HEADING_PX, 30, AREA_W, { bold: true });
  const content = layout.scale < 1 ? `translate(640 ${centre.y}) scale(${layout.scale}) translate(-640 ${-centre.y})` : undefined;

  return (
    <svg viewBox="0 0 1280 528" role="img" aria-label={`${scene.heading}: ${scene.items.join(", ")}`}>
      <text className="scene-text" x={LEFT} y={HEADING_Y} fontWeight="700" fontSize={headingSize}>{scene.heading}</text>
      <g transform={content}>
        {arrows.map((a, idx) => {
          const from = layout.boxes[a.from];
          const to = layout.boxes[a.to];
          if (!from || !to) return null;
          const g = arrowGeom(scene.layout, from, to, Math.abs(a.to - a.from) === 1, centre);
          const p = progress(localT, arrowStart(reveal, a), ARROW_DRAW_S);
          if (p <= 0) return null;
          const len = Math.hypot(g.dir.x, g.dir.y) || 1;
          const ux = g.dir.x / len;
          const uy = g.dir.y / len;
          const head = `M${g.end.x} ${g.end.y} L${g.end.x - 16 * ux + 8 * uy} ${g.end.y - 16 * uy - 8 * ux} L${g.end.x - 16 * ux - 8 * uy} ${g.end.y - 16 * uy + 8 * ux} Z`;
          return (
            <g key={idx}>
              <path d={g.d} fill="none" stroke="var(--line)" strokeWidth="4" strokeLinecap="round"
                pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - p} />
              <path d={head} fill="var(--line)" opacity={clamp01((p - 0.8) / 0.2)} />
              {a.label && (
                <text className="scene-text scene-label" x={g.label.x} y={g.label.y} textAnchor={g.anchor}
                  fontSize={layout.labelSize} opacity={clamp01((p - 0.3) / 0.4)}>
                  {a.label}
                </text>
              )}
            </g>
          );
        })}

        {layout.boxes.map((b, k) => {
          const s = fadeIn(localT, reveal[k] ?? 0, ITEM_IN_S);
          if (s <= 0) return null;
          const isNew = k === newest;
          const lineH = layout.size * 1.25;
          const firstBaseline = b.cy - ((b.lines.length - 1) * lineH) / 2 + layout.size * 0.35;
          return (
            <g key={k} opacity={s} transform={`translate(${b.cx} ${b.cy}) scale(${0.85 + 0.15 * s}) translate(${-b.cx} ${-b.cy})`}>
              <rect x={b.cx - b.w / 2} y={b.cy - b.h / 2} width={b.w} height={b.h} rx="16"
                fill="var(--panel-2)" stroke={isNew ? "var(--accent)" : "var(--box-edge)"} strokeWidth={isNew ? 4 : 2} />
              <text className="scene-text" x={b.cx} y={firstBaseline} textAnchor="middle" fontSize={layout.size}>
                {b.lines.map((line, i) => (
                  <tspan key={i} x={b.cx} dy={i === 0 ? 0 : lineH}>{line}</tspan>
                ))}
              </text>
            </g>
          );
        })}
      </g>
    </svg>
  );
}
