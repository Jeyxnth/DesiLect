import { useEffect, useState } from "react";
import { getTimings, type Timings } from "../api/jobs";

/** timings.json key -> label, in pipeline order (export is one row: smooth, or keyframe capture + encode). */
const ROWS: { label: string; keys: string[] }[] = [
  { label: "Planning", keys: ["plan"] },
  { label: "Translating", keys: ["translate"] },
  { label: "Voicing + timing", keys: ["narrate"] },
  { label: "MP4 export", keys: ["export_smooth", "export_capture", "export_encode"] },
];

const num = (v: unknown): number | null => (typeof v === "number" ? v : null);

/** Real per-stage seconds and peak memory of this lesson, read from its timings.json. refresh: re-read it. */
export default function SpeedPanel({ id, refresh }: { id: string; refresh: unknown }) {
  const [timings, setTimings] = useState<Timings | null>(null);
  useEffect(() => { getTimings(id).then(setTimings).catch(() => setTimings(null)); }, [id, refresh]);
  if (!timings) return null;

  const rss = timings.rss_mb ?? {};
  const rows = ROWS.flatMap(({ label, keys }) => {
    const present = keys.filter((k) => num(timings[k]) !== null);
    if (present.length === 0) return [];
    const seconds = present.reduce((sum, k) => sum + (num(timings[k]) ?? 0), 0);
    const peaks = present.map((k) => rss[k]).filter((v): v is number => typeof v === "number");
    if (label === "Planning" && typeof rss.plan_ollama === "number") peaks.push(rss.plan_ollama);
    return [{ label, seconds, peak: peaks.length ? Math.max(...peaks) : null }];
  });
  if (rows.length === 0) return null;
  const total = rows.reduce((sum, r) => sum + r.seconds, 0);
  const tl = timings.timeline;

  return (
    <details className="speed-panel">
      <summary>How long this lesson took: {total.toFixed(1)} s</summary>
      <table>
        <thead><tr><th>Stage</th><th>Seconds</th><th>Peak memory</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}><td>{r.label}</td><td>{r.seconds.toFixed(1)}</td><td>{r.peak !== null ? `${Math.round(r.peak)} MB` : "-"}</td></tr>
          ))}
        </tbody>
      </table>
      {tl?.total_seconds !== undefined && (
        <p className="muted">
          {tl.total_seconds.toFixed(1)} s of narration{tl.tts_engine ? ` by ${tl.tts_engine}` : ""}
          {typeof tl.tts_rtf === "number" ? `, ${tl.tts_rtf.toFixed(2)}x real time` : " (from the voice cache)"}.
          Planning memory includes the Ollama server.
        </p>
      )}
    </details>
  );
}
