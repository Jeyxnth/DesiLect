import type { TitleCardScene } from "../types/lesson";
import { fadeIn } from "./anim";
import type { SceneProps } from "./registry";

/** Title card. TODO(step 3): layout; TODO(step 7): polish. */
export default function TitleCard({ data, t, start }: SceneProps<TitleCardScene>) {
  const local = t - start;
  return (
    <svg viewBox="0 0 1280 720" role="img" aria-label={data.heading}>
      <text className="scene-text" x="640" y="330" textAnchor="middle" fontSize="64" fontWeight="700" opacity={fadeIn(local, 0)}>
        {data.heading}
      </text>
      {data.subheading && (
        <text className="scene-text" x="640" y="410" textAnchor="middle" fontSize="34" opacity={fadeIn(local, 0.5)}>
          {data.subheading}
        </text>
      )}
    </svg>
  );
}
