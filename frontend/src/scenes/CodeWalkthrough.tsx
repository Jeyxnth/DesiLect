import type { CodeWalkthroughScene } from "../types/lesson";
import { activeHighlight, fadeIn, fitFontSize } from "./anim";
import type { SceneProps } from "./registry";

/**
 * Code as plain SVG text nodes only (H4): never executed, never injected as HTML.
 * The highlighted line comes from the latest highlight beat.
 */
export default function CodeWalkthrough({ scene, localT, beats }: SceneProps<CodeWalkthroughScene>) {
  const lines = scene.code.split("\n");
  const lineH = Math.min(56, 400 / lines.length);
  const widest = Math.max(...lines.map((l) => l.length), 1);
  const fs = Math.min(34, lineH * 0.65, fitFontSize("x".repeat(widest), 34, 12, 860, 0.6));
  const top = 105;
  const hl = activeHighlight(beats, localT);
  const hlAlpha = hl ? fadeIn(localT, hl.t, 0.3) : 0;

  return (
    <svg viewBox="0 0 1280 540" role="img" aria-label={scene.heading}>
      <text className="scene-text" x="640" y="70" textAnchor="middle" fontWeight="700"
        fontSize={fitFontSize(scene.heading, 48, 28, 1120)}>
        {scene.heading}
      </text>
      <rect x="120" y={top - 20} width="1040" height={lines.length * lineH + 40} rx="18" fill="#0b1220" />
      {lines.map((line, i) => {
        const y = top + i * lineH;
        const on = hl !== null && hl.value === i + 1;
        const dim = hl !== null && !on ? 1 - 0.45 * hlAlpha : 1;
        return (
          <g key={i}>
            {on && <rect x="132" y={y} width="1016" height={lineH} rx="8" fill="var(--accent)" opacity={0.28 * hlAlpha} />}
            {on && <rect x="132" y={y} width="6" height={lineH} rx="3" fill="var(--accent)" opacity={hlAlpha} />}
            <text className="scene-code scene-muted" x="210" y={y + lineH * 0.7} textAnchor="end" fontSize={fs} opacity={dim}>
              {i + 1}
            </text>
            <text className="scene-code" x="240" y={y + lineH * 0.7} fontSize={fs} opacity={dim} style={{ whiteSpace: "pre" }}>
              {line}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
