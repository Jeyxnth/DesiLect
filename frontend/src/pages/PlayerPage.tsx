import { useEffect, useState } from "react";
import Player from "../player/Player";
import type { Timeline } from "../types/lesson";

/** Loads /api/lessons/<id>/timeline and plays it. URL: /play?lesson=<id>. TODO(step 3). */
export default function PlayerPage() {
  const lessonId = new URLSearchParams(window.location.search).get("lesson");
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!lessonId) return setError("Missing ?lesson=<id>");
    fetch(`/api/lessons/${encodeURIComponent(lessonId)}/timeline`)
      .then((r) => (r.ok ? (r.json() as Promise<Timeline>) : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setTimeline)
      .catch((e: Error) => setError(e.message));
  }, [lessonId]);

  return (
    <div className="page">
      {error && <p>{error}</p>}
      {timeline ? <Player timeline={timeline} /> : !error && <p>Loading...</p>}
    </div>
  );
}
