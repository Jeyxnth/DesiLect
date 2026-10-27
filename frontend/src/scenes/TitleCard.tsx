import type { ReactElement } from "react";
import type { TitleCardScene } from "../types/lesson";
import { fadeIn } from "./anim";
import { fitSize, wrapLabel } from "./measure";
import type { SceneProps } from "./registry";
import { BODY_PX, SAFE, STAGE_W } from "./tokens";

const HEADING_IN = 0; // heading slides up and fades in over 0.5 s
const SUB_IN = 0.25; // the subheading follows
const ICON_IN = 0.4; // then the topic icon
const IN_S = 0.5;

const TITLE_MAX = 60;
const TITLE_MIN = 40;
const WIDTH = STAGE_W - 2 * SAFE;

export function titleAnimationStarts(): number[] {
  return [HEADING_IN, SUB_IN, ICON_IN];
}

/** Topic icon from generic shapes, chosen by words in the heading (no images, no model output drawn). */
type IconKind = "code" | "science" | "maths" | "recap" | "idea";

const ICON_WORDS: [IconKind, RegExp][] = [
  ["recap", /\b(recap|summary|review|key ideas?)\b/i],
  ["code", /\b(python|loops?|code|coding|program\w*|function|algorithm|search|sort\w*|array|list|variable|javascript|java|recursion)\b/i],
  ["science", /\b(photosynthesis|plants?|leaf|cells?|atoms?|energy|light|water|biology|chemistry|physics|science|oxygen)\b/i],
  ["maths", /\b(theorem|triangles?|maths?|mathematics|equations?|numbers?|angles?|algebra|geometry|fractions?)\b/i],
];

function iconKind(text: string): IconKind {
  return ICON_WORDS.find(([, re]) => re.test(text))?.[0] ?? "idea";
}

function Icon({ kind }: { kind: IconKind }): ReactElement {
  const s = { fill: "none", stroke: "var(--accent)", strokeWidth: 5, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  switch (kind) {
    case "code":
      return (
        <g {...s}>
          <rect x="-48" y="-36" width="96" height="72" rx="10" />
          <path d="M-20 -12 L-34 0 L-20 12 M20 -12 L34 0 L20 12 M6 -16 L-6 16" />
        </g>
      );
    case "science":
      return (
        <g {...s}>
          <path d="M0 40 C-40 20 -40 -30 0 -42 C40 -30 40 20 0 40 Z" />
          <path d="M0 40 L0 -26 M0 4 L-16 -10 M0 16 L16 2" />
        </g>
      );
    case "maths":
      return (
        <g {...s}>
          <path d="M-40 32 L40 32 L-40 -36 Z" />
          <path d="M-40 18 L-26 18 L-26 32" />
        </g>
      );
    case "recap":
      return (
        <g {...s}>
          <circle r="40" />
          <path d="M-18 0 L-4 14 L20 -12" />
        </g>
      );
    default:
      return (
        <g {...s}>
          <circle cy="-8" r="28" />
          <path d="M-12 26 L12 26 M-8 36 L8 36 M-10 18 L10 18" />
        </g>
      );
  }
}

/**
 * Title card: the heading slides up and fades in over 0.5 s, the subheading follows, then a small
 * topic icon. Only transform and opacity animate. Pure function of localT.
 */
export default function TitleCard({ scene, localT }: SceneProps<TitleCardScene>) {
  const h = fadeIn(localT, HEADING_IN, IN_S);
  const s = fadeIn(localT, SUB_IN, IN_S);
  const ic = fadeIn(localT, ICON_IN, IN_S);

  // One line at the largest size that fits; otherwise two balanced lines.
  let size = fitSize(scene.heading, TITLE_MAX, TITLE_MIN, WIDTH, { bold: true });
  let lines = [scene.heading];
  if (size === TITLE_MIN) {
    size = 48;
    lines = wrapLabel(scene.heading, size, WIDTH, { bold: true }).lines;
  }
  const lineH = size * 1.2;
  const headTop = 268 - ((lines.length - 1) * lineH) / 2;
  const sub = scene.subheading ?? "";
  const subSize = sub ? fitSize(sub, BODY_PX + 4, BODY_PX - 6, WIDTH) : 0;
  const subY = headTop + (lines.length - 1) * lineH + 70;

  return (
    <svg viewBox="0 0 1280 528" role="img" aria-label={scene.heading}>
      <g opacity={ic} transform={`translate(640 ${130}) scale(${0.8 + 0.2 * ic})`}>
        <Icon kind={iconKind(`${scene.heading} ${sub}`)} />
      </g>
      <g opacity={h} transform={`translate(0 ${(1 - h) * 28})`}>
        <text className="scene-text" x="640" y={headTop} textAnchor="middle" fontWeight="700" fontSize={size}>
          {lines.map((line, i) => (
            <tspan key={i} x="640" dy={i === 0 ? 0 : lineH}>{line}</tspan>
          ))}
        </text>
      </g>
      {sub && (
        <g opacity={s} transform={`translate(0 ${(1 - s) * 20})`}>
          <text className="scene-text scene-muted" x="640" y={subY} textAnchor="middle" fontSize={subSize}>
            {sub}
          </text>
        </g>
      )}
    </svg>
  );
}
