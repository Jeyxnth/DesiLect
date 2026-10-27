import type { MouseEvent } from "react";

/** Thin progress bar; clicking seeks. */
export default function ProgressBar({ t, total, onSeek }: { t: number; total: number; onSeek?: (t: number) => void }) {
  const click = (e: MouseEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    onSeek?.(Math.min(total, Math.max(0, ((e.clientX - r.left) / r.width) * total)));
  };
  return (
    <div className="progress" onClick={onSeek ? click : undefined} role="progressbar"
      aria-valuemin={0} aria-valuemax={Math.round(total)} aria-valuenow={Math.round(t)}>
      <div className="progress-track">
        <div className="progress-fill" style={{ width: `${total > 0 ? Math.min(100, (t / total) * 100) : 0}%` }} />
      </div>
    </div>
  );
}
