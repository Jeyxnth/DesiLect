import type { CodeWalkthroughScene } from "../types/lesson";
import { highlightAt } from "./anim";
import type { SceneProps } from "./registry";

/** Code shown as plain SVG text only, never executed or injected as HTML (H4). TODO(step 3/7). */
export default function CodeWalkthrough({ data, t, beats }: SceneProps<CodeWalkthroughScene>) {
  const lines = data.code.split("\n");
  const active = highlightAt(beats, t);
  return (
    <svg viewBox="0 0 1280 720" role="img" aria-label={data.heading}>
      <text className="scene-text" x="640" y="90" textAnchor="middle" fontSize="44" fontWeight="700">{data.heading}</text>
      {lines.map((line, i) => (
        <g key={i}>
          {active === i + 1 && <rect x="140" y={200 + i * 52} width="1000" height="48" rx="8" fill="#38bdf8" opacity="0.25" />}
          <text className="scene-code" x="160" y={236 + i * 52} fontSize="34" style={{ whiteSpace: "pre" }}>{line}</text>
        </g>
      ))}
    </svg>
  );
}
