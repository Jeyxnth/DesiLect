import { useEffect, useState } from "react";
import { getJob, getLesson, mp4Exists } from "../api/jobs";
import FallbackNotice from "../components/FallbackNotice";
import { loadTimeline } from "../player/loadTimeline";
import Player from "../player/Player";
import type { Lesson, Timeline } from "../types/lesson";

const POLL_MS = 2000;

type Mp4State = { kind: "checking" } | { kind: "exporting" } | { kind: "ready" } | { kind: "missing"; error?: string };

/** /lesson/:id: loads the timeline and plays it; shows the fallback notice and the MP4 when it is ready. */
export default function PlayerPage({ id }: { id: string }) {
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [error, setError] = useState("");
  const [mp4, setMp4] = useState<Mp4State>({ kind: "checking" });

  useEffect(() => {
    setTimeline(null);
    setLesson(null);
    setError("");
    loadTimeline(id).then(setTimeline).catch((e: Error) => setError(e.message));
    getLesson(id).then(setLesson).catch(() => setLesson(null));
  }, [id]);

  // Follow the export: poll the job while it runs; without a job (samples, restarted server) just look for the file.
  useEffect(() => {
    let stopped = false;
    let timer = 0;
    const check = async () => {
      try {
        const job = await getJob(id);
        if (stopped) return;
        if (!job) {
          setMp4((await mp4Exists(id)) ? { kind: "ready" } : { kind: "missing" });
        } else if (job.status.mp4_ready) {
          setMp4({ kind: "ready" });
        } else if (job.state === "done" || job.state === "failed") {
          setMp4({ kind: "missing", error: job.export_error ?? job.error ?? undefined });
        } else {
          setMp4({ kind: "exporting" });
          timer = window.setTimeout(check, POLL_MS);
        }
      } catch {
        if (!stopped) setMp4({ kind: "missing" });
      }
    };
    void check();
    return () => {
      stopped = true;
      window.clearTimeout(timer);
    };
  }, [id]);

  const media = `/media/lessons/${encodeURIComponent(id)}`;
  return (
    <div className="page">
      <header className="player-header">
        <h1>{lesson?.title ?? "Lesson"}</h1>
        <a href="/">New lesson</a>
      </header>
      {lesson?.meta?.fallback && <FallbackNotice reason={lesson.meta.reason} source={lesson.meta.source} topic={lesson.meta.topic} />}
      {error && <p className="error" role="alert">{error}</p>}
      {timeline ? <Player key={timeline.lesson_id} timeline={timeline} /> : !error && <p>Loading...</p>}
      {timeline && (
        <p className="downloads">
          {mp4.kind === "ready" && <a href={`${media}/lesson.mp4`} download={`${id}.mp4`}>Download MP4</a>}
          {mp4.kind === "exporting" && <span className="muted">Exporting the MP4 (about 40 s)...</span>}
          {mp4.kind === "missing" && <span className="muted">MP4 not available{mp4.error ? `: ${mp4.error}` : ""}</span>}
          <a href={`${media}/captions.srt`} download={`${id}.srt`}>Download captions (.srt)</a>
        </p>
      )}
    </div>
  );
}
