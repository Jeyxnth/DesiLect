import { useEffect, useState } from "react";
import { getLesson, retryExport, watchStatus, type Job } from "../api/jobs";
import { downloadName } from "../api/slug";
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
  // Downloads are named <topic-slug>_<lang>: the topic the learner typed, else the lesson's own topic or title
  const topic = job?.request?.topic ?? lesson?.meta?.topic ?? lesson?.title ?? id;
  const lang = timeline?.language ?? "en";
  const exportLabel = status?.export_progress != null
    ? `Exporting MP4... ${Math.round(status.export_progress * 100)}%`
    : `Exporting MP4... ${Math.round(status?.timings.export ?? 0)} s`;

  return (
    <div className="page">
      <header className="player-header">
        <h1>{lesson?.title ?? "Lesson"}</h1>
        <a href="/" onClick={(e) => { e.preventDefault(); navigate("/"); }}>New lesson</a>
      </header>
      {fallback && <FallbackNotice reason={fallback.reason} source={fallback.source} topic={fallback.topic} />}
      {lesson?.meta?.translation_fallback && (
        <div className="fallback-notice" role="status">
          <strong>⚠ Translation unavailable</strong>
          <p>The lesson could not be translated on this machine, so it is shown and narrated in English.</p>
        </div>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      {timeline ? <Player key={timeline.lesson_id} timeline={timeline} autoplay={autoplay} /> : !error && <p>Loading...</p>}
      {timeline && (
        <div className="downloads">
          {status?.mp4_ready ? (
            <a className="button" href={`${media}/lesson.mp4`} download={downloadName(topic, lang, "mp4")}
              title={status.export_mode === "keyframe" ? "Made with the keyframe export (smooth export was not possible)" : undefined}>
              Download MP4
            </a>
          ) : (
            <button type="button" className="button" disabled>
              {exporting ? exportLabel : "Download MP4"}
            </button>
          )}
          {job?.export_error && (
            <button type="button" className="button" onClick={retry}>Retry export</button>
          )}
          <a href={`${media}/captions.srt`} download={downloadName(topic, lang, "srt")}>Download captions (.srt)</a>
        </div>
      )}
      {job?.export_error && <p className="error" role="alert">MP4 export failed: {job.export_error}. The lesson still plays here.</p>}
      {timeline && !job && <p className="muted downloads">MP4 status unavailable.</p>}
    </div>
  );
}
