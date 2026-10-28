import { useCallback, useEffect, useState } from "react";
import { getLesson, retryExport, revoiceLesson, watchStatus, type Job } from "../api/jobs";
import { downloadName } from "../api/slug";
import { ui } from "../i18n/strings";
import FallbackNotice, { ShortNotice } from "../components/FallbackNotice";
import Icon from "../components/Icon";
import SpeedPanel from "../components/SpeedPanel";
import LessonEnd from "../habit/LessonEnd";
import { addRevise, currentStreak, localDay, recordStreak, removeRevise, useHabit } from "../habit/storage";
import { loadTimeline } from "../player/loadTimeline";
import Player, { type LessonResult } from "../player/Player";
import { navState, navigate } from "../router";
import type { Language, Lesson, Timeline } from "../types/lesson";

const LANGUAGES: { value: Language; label: string }[] = [
  { value: "en", label: "English" },
  { value: "hi", label: "हिन्दी" },
  { value: "ta", label: "தமிழ்" },
];

/** /lesson/:id: plays the lesson; shows the fallback notice, MP4 export status and downloads. */
export default function PlayerPage({ id }: { id: string }) {
  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState("");
  const [watch, setWatch] = useState(0); // bump to follow the status again (after Retry export)
  const [autoplay] = useState(() => navState().autoplay === true);
  const [revoice, setRevoice] = useState<Job | null>(null); // the job making this lesson in another language

  useEffect(() => {
    loadTimeline(id).then(setTimeline).catch((e: Error) => setError(e.message));
    getLesson(id).then(setLesson).catch(() => setLesson(null));
  }, [id]);

  useEffect(() => watchStatus(id, setJob, () => setJob(null)), [id, watch]);

  // Re-voicing: follow the new lesson's job and open it as soon as it can play.
  const revoiceId = revoice?.lesson_id;
  useEffect(() => {
    if (!revoiceId) return;
    return watchStatus(
      revoiceId,
      (next) => {
        setRevoice(next);
        if (next.state === "failed") setError(next.error ?? "Re-voicing failed.");
        else if (next.status.timeline_ready) navigate(`/lesson/${encodeURIComponent(next.lesson_id)}`, { autoplay: true });
      },
      setError,
    );
  }, [revoiceId]);

  const startRevoice = async (language: Language) => {
    setError("");
    try {
      setRevoice(await revoiceLesson(id, language));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  // Learning habit (bonus B2): streak, revise list, try next. All in this browser; hidden if storage is unavailable.
  const { habit, update } = useHabit();
  const title = lesson?.title ?? timeline?.scenes[0]?.heading ?? id;
  const entry = (result?: LessonResult) => ({
    lesson_id: id, title, language: timeline?.language ?? "en", added_at: new Date().toISOString(),
    ...(result?.total ? { score: { correct: result.score ?? 0, total: result.total } } : {}),
  });
  const onComplete = useCallback((result: LessonResult) => {
    update((s) => {
      const next = recordStreak(s, localDay());
      // a low quiz score (below 2/3) goes on the revise list by itself
      return result.total && (result.score ?? 0) / result.total < 2 / 3 ? addRevise(next, entry(result)) : next;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [update, id, title, timeline?.language]);
  const saved = habit ? habit.revise.some((e) => e.lesson_id === id) : null;
  const toggleSave = () => update((s) => (s.revise.some((e) => e.lesson_id === id) ? removeRevise(s, id) : addRevise(s, entry())));
  const tryNext = (topic: string) => {
    const req = job?.request;
    navigate("/", {
      autostart: true,
      prefill: { topic, level: lesson?.level ?? req?.level ?? "beginner", language: timeline?.language ?? "en",
        ...(req ? { target_seconds: req.target_seconds, voice: req.voice, speed: req.speed } : {}) },
    });
  };

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

  const goHome = () => navigate("/");
  // Generate again (fallback or short lesson): the same request, planned afresh on the input page. Neither kind of lesson
  // is in the reuse cache, so this never returns the same lesson.
  const againTopic = job?.request?.topic ?? lesson?.meta?.topic;
  const generateAgain = againTopic ? () => navigate("/", {
    autostart: true,
    prefill: job?.request ?? { topic: againTopic, level: lesson?.level ?? "beginner", language: lang,
      ...(lesson?.meta?.short_of ? { target_seconds: lesson.meta.short_of.target_seconds } : {}) },
  }) : undefined;
  const summaryHref = `/summary/${encodeURIComponent(id)}`;

  // Nothing to play: a clear error with a way forward, not a red line under an empty header.
  if (error && !timeline) {
    return (
      <main className="page">
        <section className="state-card" role="alert">
          <h2>This lesson could not be opened</h2>
          <p>{error}</p>
          <button type="button" className="button primary" onClick={goHome}>Make a new lesson</button>
        </section>
      </main>
    );
  }

  return (
    <main className="page">
      <header className="player-header">
        <h1 lang={timeline?.language}>{timeline || lesson ? title : "Lesson"}</h1>
        <a className="button small" href="/" onClick={(e) => { e.preventDefault(); goHome(); }}>
          <Icon name="plus" /> New lesson
        </a>
      </header>
      {fallback && <FallbackNotice reason={fallback.reason} source={fallback.source} topic={fallback.topic} onRetry={generateAgain} />}
      {lesson?.meta?.short_of && timeline && (
        <ShortNotice seconds={timeline.total_seconds} targetSeconds={lesson.meta.short_of.target_seconds} onRetry={generateAgain} />
      )}
      {lesson?.meta?.translation_fallback && (
        <div className="fallback-notice" role="status">
          <strong><Icon name="alert" /> Translation unavailable</strong>
          <p>The lesson could not be translated on this machine, so it is shown and narrated in English.</p>
        </div>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      {timeline ? (
        <Player key={timeline.lesson_id} timeline={timeline} autoplay={autoplay} onComplete={onComplete}
          endExtra={
            <LessonEnd lang={timeline.language} nextTopics={timeline.next_topics} nextLabels={timeline.next_topic_labels} onTryNext={tryNext}
              streak={habit ? currentStreak(habit, localDay()) : null} saved={saved} onToggleSave={toggleSave}
              onSummary={lesson ? () => navigate(summaryHref) : undefined} />
          } />
      ) : (
        <div className="stage-skeleton" role="status"><span className="pulse" aria-hidden="true" /> Loading lesson...</div>
      )}
      {timeline && (
        <div className="downloads">
          {status?.mp4_ready ? (
            <a className="button primary" href={`${media}/lesson.mp4`} download={downloadName(topic, lang, "mp4")}
              title={status.export_mode === "keyframe" ? "Made with the keyframe export (smooth export was not possible)" : undefined}>
              Download MP4
            </a>
          ) : (
            <button type="button" className="button primary" disabled>
              {exporting && <span className="pulse" aria-hidden="true" />}
              {exporting ? exportLabel : "Download MP4"}
            </button>
          )}
          {job?.export_error && (
            <button type="button" className="button" onClick={retry}>Retry export</button>
          )}
          <a className="button small" href={`${media}/captions.srt`} download={downloadName(topic, lang, "srt")}>Captions (.srt)</a>
          {/* the summary is built from lesson.json; a lesson without one (a sample render) has none */}
          {lesson && (
            <>
              <a className="button small" href={summaryHref} onClick={(e) => { e.preventDefault(); navigate(summaryHref); }}>
                {ui(lang, "summary")}
              </a>
              <a className="button small" href={`/api/lessons/${encodeURIComponent(id)}/summary.pdf`}
                download={downloadName(topic, lang, "pdf").replace(/\.pdf$/, "_summary.pdf")}>
                {ui(lang, "summaryPdf")}
              </a>
            </>
          )}
        </div>
      )}
      {job?.export_error && (
        <p className="error" role="alert"><strong>MP4 export failed.</strong> {job.export_error}. The lesson still plays here.</p>
      )}
      {timeline && (lesson || job || revoice) && (
        <div className="player-extras">
          {lesson && (
            <div className="revoice">
              <label>Same lesson in
                <select value={lang} disabled={revoice !== null} onChange={(e) => void startRevoice(e.target.value as Language)}>
                  {LANGUAGES.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
                </select>
              </label>
              {revoice && (
                <span className="muted">
                  {revoice.cached ? "Opening the earlier version..." : `Re-voicing (no re-planning): ${revoice.status.stage}...`}
                </span>
              )}
            </div>
          )}
          <SpeedPanel id={id} refresh={`${status?.mp4_ready}-${status?.stage}`} />
        </div>
      )}
      {timeline && !job && <p className="muted downloads">MP4 status unavailable.</p>}
    </main>
  );
}
