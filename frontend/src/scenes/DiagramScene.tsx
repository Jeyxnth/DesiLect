import type { DiagramScene as Diagram } from "../types/lesson";
import { fadeIn, fitFontSize, revealTime } from "./anim";
import type { SceneProps } from "./registry";

const W = 1280;
const BOX_Y = 190;
const BOX_H = 140;
const GAP = 80;
const MARGIN = 50;

/**
 * Items as rounded boxes in a row, arrows as SVG lines with markers, all revealed by beats.
 * TODO(step 7): real cycle and stack layouts (they fall back to the row for now).
 */
export default function DiagramScene({ scene, localT, beats }: SceneProps<Diagram>) {
  const n = scene.items.length;
  const boxW = Math.min(240, (W - 2 * MARGIN - (n - 1) * GAP) / n);
  const total = n * boxW + (n - 1) * GAP;
  const x0 = (W - total) / 2;
  const left = (i: number) => x0 + i * (boxW + GAP);
  const reveal = scene.items.map((_, k) => revealTime(beats, k));
  const alpha = reveal.map((r) => fadeIn(localT, r));
  // The most recently revealed item gets the accent outline.
  let newest = -1;
  reveal.forEach((r, k) => { if (r <= localT && (newest < 0 || r >= (reveal[newest] ?? 0))) newest = k; });

  return (
    <svg viewBox="0 0 1280 540" role="img" aria-label={scene.heading}>
      <defs>
        <marker id="arrowhead" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto">
          <path d="M0 0 L10 5 L0 10 z" fill="var(--accent-2)" />
        </marker>
      </defs>
      <text className="scene-text" x="640" y="80" textAnchor="middle" fontWeight="700"
        fontSize={fitFontSize(scene.heading, 48, 28, 1120)}>
        {scene.heading}
      </text>

      {(scene.arrows ?? []).map((a, idx) => {
        const from = scene.items[a.from];
        const to = scene.items[a.to];
        if (from === undefined || to === undefined) return null;
        const o = fadeIn(localT, Math.max(reveal[a.from] ?? 0, reveal[a.to] ?? 0) + 0.15);
        const cy = BOX_Y + BOX_H / 2;
        const forward = a.to > a.from;
        const adjacent = Math.abs(a.to - a.from) === 1;
        const xa = forward ? left(a.from) + boxW : left(a.from);
        const xb = forward ? left(a.to) - 4 : left(a.to) + boxW + 4;
        const mid = (xa + xb) / 2;
        const labelY = adjacent ? cy - 16 : BOX_Y - 100;
        const d = adjacent
          ? `M${xa + (forward ? 4 : -4)} ${cy} L${xb} ${cy}`
          : `M${left(a.from) + boxW / 2} ${BOX_Y} Q${(left(a.from) + left(a.to) + boxW) / 2} ${BOX_Y - 150} ${left(a.to) + boxW / 2} ${BOX_Y - 4}`;
        return (
          <g key={idx} opacity={o}>
            <path d={d} fill="none" stroke="var(--accent-2)" strokeWidth="4" markerEnd="url(#arrowhead)" />
            {a.label && (
              <text className="scene-text scene-muted" x={adjacent ? mid : (left(a.from) + left(a.to) + boxW) / 2}
                y={labelY} textAnchor="middle" fontSize="24">
                {a.label}
              </text>
            )}
          </g>
        );
      })}

      {scene.items.map((label, k) => (
        <g key={k} opacity={alpha[k]} transform={`translate(0 ${(1 - (alpha[k] ?? 0)) * 18})`}>
          <rect x={left(k)} y={BOX_Y} width={boxW} height={BOX_H} rx="22" fill="var(--panel-2)"
            stroke={k === newest ? "var(--accent)" : "var(--muted)"} strokeWidth={k === newest ? 5 : 2} />
          <text className="scene-text" x={left(k) + boxW / 2} y={BOX_Y + BOX_H / 2 + 12} textAnchor="middle"
            fontSize={fitFontSize(label, 40, 16, boxW - 28)}>
            {label}
          </text>
        </g>
      ))}
    </svg>
  );
}
