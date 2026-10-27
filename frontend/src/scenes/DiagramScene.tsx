import type { DiagramScene as Diagram } from "../types/lesson";
import { revealedCount } from "./anim";
import type { SceneProps } from "./registry";

/** Labelled boxes with arrows. TODO(step 3): row/cycle/stack layouts and arrows; TODO(step 7): polish. */
export default function DiagramScene({ data, t, beats }: SceneProps<Diagram>) {
  const shown = revealedCount(beats, t);
  const gap = 1180 / data.items.length;
  return (
    <svg viewBox="0 0 1280 720" role="img" aria-label={data.heading}>
      <text className="scene-text" x="640" y="90" textAnchor="middle" fontSize="44" fontWeight="700">{data.heading}</text>
      {data.items.map((label, i) => (
        <g key={i} opacity={i < shown ? 1 : 0}>
          <rect x={50 + i * gap + 10} y="300" width={gap - 20} height="120" rx="16" fill="#334155" stroke="#38bdf8" strokeWidth="3" />
          <text className="scene-text" x={50 + i * gap + gap / 2} y="372" textAnchor="middle" fontSize="36">{label}</text>
        </g>
      ))}
    </svg>
  );
}
