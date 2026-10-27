import { useEffect, useState } from "react";
import { loadTimeline } from "../player/loadTimeline";
import Player from "../player/Player";
import type { Timeline } from "../types/lesson";

/** /lesson/:id: loads the timeline and plays it. */
export default function PlayerPage({ id }: { id: string }) {
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setTimeline(null);
    setError("");
    loadTimeline(id).then(setTimeline).catch((e: Error) => setError(e.message));
  }, [id]);

  return (
    <div className="page">
      {error && <p className="notice">{error}</p>}
      {timeline ? <Player key={timeline.lesson_id} timeline={timeline} /> : !error && <p>Loading...</p>}
    </div>
  );
}
