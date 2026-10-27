import type { MouseEvent } from "react";

/** Thin progress bar with a tick at each scene start; clicking seeks. The fill moves by transform only. */
export default function ProgressBar({ t, total, ticks = [], onSeek }: {
  t: number;
  total: number;
  ticks?: number[];
  onSeek?: (t: number) => void;
}) {
  const click = (e: MouseEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    onSeek?.(Math.min(total, Math.max(0, ((e.clientX - r.left) / r.width) * total)));
  };
  const frac = total > 0 ? Math.min(1, Math.max(0, t / total)) : 0;
  return (
    <div className="progress" onClick={onSeek ? click : undefined} role="progressbar"
      aria-valuemin={0} aria-valuemax={Math.round(total)} aria-valuenow={Math.round(t)}>
      <div className="progress-track">
        <div className="progress-fill" style={{ transform: `scaleX(${frac})` }} />
        {total > 0 && ticks.map((x, i) => (
          <div key={i} className={`progress-tick${x <= t ? " passed" : ""}`} style={{ left: `${(x / total) * 100}%` }} />
        ))}
      </div>
    </div>
  );
}
