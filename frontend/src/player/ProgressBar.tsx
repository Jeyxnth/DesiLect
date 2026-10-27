import type { MouseEvent } from "react";

export default function ProgressBar({ t, total, onSeek }: { t: number; total: number; onSeek?: (t: number) => void }) {
  const click = (e: MouseEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    onSeek?.(((e.clientX - r.left) / r.width) * total);
  };
  return (
    <div className="progress" onClick={click} role="progressbar" aria-valuemin={0} aria-valuemax={total} aria-valuenow={t}>
      <div style={{ width: `${total > 0 ? Math.min(100, (t / total) * 100) : 0}%` }} />
    </div>
  );
}
