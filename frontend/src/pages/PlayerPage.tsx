import { useEffect, useState } from "react";
import { getLesson, retryExport, watchStatus, type Job } from "../api/jobs";
import FallbackNotice from "../components/FallbackNotice";
import { loadTimeline } from "../player/loadTimeline";
import Player from "../player/Player";
import { navState, navigate } from "../router";
import type { Lesson, Timeline } from "../types/lesson";

/** /lesson/:id: plays the lesson; shows the fallback notice, MP4 export status and downloads. */
export default function PlayerPage({ id }: { id: string }) {
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [watch, setWatch] = useState(0); // bump to follow the status again (after Retry export)
  const [autoplay] = useState(() => navState().autoplay === true);

  useEffect(() => {
    loadTimeline(id).then(setTimeline).catch((e: Error) => setError(e.message));
    getLesson(id).then(setLesson).catch(() => setLesson(null));
  }, [id]);

  useEffect(() => watchStatus(id, setJob, () => setJob(null)), [id, watch]);

  const retry = async () => {
    try {
      setJob(await retryExport(id));
      setWatch((n) => n + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const media = `/media/lessons/${encodeURIComponent(id)}`;
  const status = job?.status;
  const exporting = job !== null && !status?.mp4_ready && !job.export_error && (job.state === "running" || job.state === "queued");
  const fallback = lesson?.meta?.fallback ? lesson.meta : null;

  return (
    <div className="page">
      <header className="player-header">
        <h1>{lesson?.title ?? "Lesson"}</h1>
        <a href="/" onClick={(e) => { e.preventDefault(); navigate("/"); }}>New lesson</a>
      </header>
      {fallback && <FallbackNotice reason={fallback.reason} source={fallback.source} topic={fallback.topic} />}
      {error && <p className="error" role="alert">{error}</p>}
      {timeline ? <Player key={timeline.lesson_id} timeline={timeline} autoplay={autoplay} /> : !error && <p>Loading...</p>}
      {timeline && (
        <div className="downloads">
          {status?.mp4_ready ? (
            <a className="button" href={`${media}/lesson.mp4`} download={`${id}.mp4`}>Download MP4</a>
          ) : (
            <button type="button" className="button" disabled>
              {exporting ? `Exporting MP4... ${Math.round(status?.timings.export ?? 0)} s` : "Download MP4"}
            </button>
          )}
          {job?.export_error && (
            <button type="button" className="button" onClick={retry}>Retry export</button>
          )}
          <a href={`${media}/captions.srt`} download={`${id}.srt`}>Download captions (.srt)</a>
        </div>
      )}
      {job?.export_error && <p className="error" role="alert">MP4 export failed: {job.export_error}. The lesson still plays here.</p>}
      {timeline && !job && <p className="muted downloads">MP4 status unavailable.</p>}
    </div>
  );
}
