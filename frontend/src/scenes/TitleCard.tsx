import type { TitleCardScene } from "../types/lesson";
import { easeOutCubic, fadeIn, fitFontSize } from "./anim";
import type { SceneProps } from "./registry";

/** Heading then subheading fade in; an accent rule grows under them. Pure function of localT. */
export default function TitleCard({ scene, localT }: SceneProps<TitleCardScene>) {
  const h = fadeIn(localT, 0, 0.6);
  const s = fadeIn(localT, 0.5, 0.6);
  const rule = easeOutCubic((localT - 0.3) / 0.8);
  return (
    <svg viewBox="0 0 1280 540" role="img" aria-label={scene.heading}>
      <text className="scene-text" x="640" y={250 + (1 - h) * 24} textAnchor="middle" fontWeight="700"
        fontSize={fitFontSize(scene.heading, 72, 36, 1120)} opacity={h}>
        {scene.heading}
      </text>
      <rect x={640 - 160 * rule} y="285" width={320 * rule} height="6" rx="3" fill="var(--accent)" />
      {scene.subheading && (
        <text className="scene-text scene-muted" x="640" y={350 + (1 - s) * 16} textAnchor="middle"
          fontSize={fitFontSize(scene.subheading, 38, 24, 1120)} opacity={s}>
          {scene.subheading}
        </text>
      )}
    </svg>
  );
}
