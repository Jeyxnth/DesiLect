import { useEffect, useMemo, useRef, useState } from "react";
import { SETTLE_S, sceneAt } from "../scenes/anim";
import { say } from "../scenes/i18n";
import { renderScene } from "../scenes/registry";
import { STAGE_H, STAGE_W } from "../scenes/tokens";
import type { Timeline } from "../types/lesson";
import { useFontsReady } from "../scenes/measure";
import CaptionBar, { warmCaptions } from "./CaptionBar";
import { AudioClock, ManualClock, useClock, type Clock } from "./clock";
import Controls from "./Controls";
import ProgressBar from "./ProgressBar";
import Quiz from "./Quiz";

export { STAGE_H, STAGE_W };

/**
 * The 1280x720 logical stage: step pill, scene, caption band, progress bar with scene ticks.
 * A pure function of (timeline, t): the render page and the player both use it.
 * poster: paused at 0:00, show the first scene settled (its title) instead of an empty frame.
 */
export function Stage({ timeline, t, onSeek, showProgress = true, poster = false }: {
  timeline: Timeline;
  t: number;
  onSeek?: (t: number) => void;
  showProgress?: boolean;
  poster?: boolean;
}) {
  const scene = sceneAt(timeline.scenes, t);
  const lang = timeline.language;
  const visualT = poster && scene ? Math.min(scene.end - 0.01, scene.start + SETTLE_S) : t;
  return (
    <div className="stage-canvas" lang={lang}>
      {scene && (
        <div className="step-pill">{say(lang, "step", { n: scene.index + 1, total: timeline.scenes.length })}</div>
      )}
      <div className="scene-area">{scene && renderScene(scene, visualT, lang)}</div>
      <CaptionBar scene={poster ? null : scene} t={t} lang={lang} />
      {showProgress && <ProgressBar t={t} total={timeline.total_seconds} ticks={timeline.scenes.slice(1).map((s) => s.start)} onSeek={onSeek} />}
    </div>
  );
}

/** Width of `ref` in px, kept current with a ResizeObserver. */
function useWidth(ref: React.RefObject<HTMLElement>): number {
  const [w, setW] = useState(STAGE_W);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setW(el.clientWidth || STAGE_W));
    ro.observe(el);
    setW(el.clientWidth || STAGE_W);
    return () => ro.disconnect();
  }, [ref]);
  return w;
}

/** Typing in a form field must not trigger player shortcuts. */
function isTyping(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  return !!el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
}

/**
 * Interactive player: audio drives the clock; controls seek by scene.
 * Keyboard: Space play/pause, Left/Right previous/next scene, R replay.
 * autoplay starts playback on mount (the browser may still refuse it; then Play works as usual).
 */
export default function Player({ timeline, autoplay = false }: { timeline: Timeline; autoplay?: boolean }) {
  const [audioFailed, setAudioFailed] = useState(false);
  const clock = useMemo<Clock>(() => {
    if (audioFailed) return new ManualClock(); // no audio: scrubbing only
    const audio = new Audio();
    audio.preload = "auto";
    audio.addEventListener("error", () => setAudioFailed(true));
    audio.src = timeline.audio_url;
    return new AudioClock(audio);
  }, [timeline, audioFailed]);
  useEffect(() => () => clock.pause(), [clock]);
  useEffect(() => {
    if (autoplay) clock.play();
  }, [clock, autoplay]);

  // Measure all captions and scene layouts once, while paused, so a phone does not stall at each new cue
  // or scene (step 12). The hidden copy is never painted and is dropped after one render.
  const fontsReady = useFontsReady();
  const [warmed, setWarmed] = useState<Timeline | null>(null);
  useEffect(() => {
    if (!fontsReady) return;
    warmCaptions(timeline.scenes, timeline.language);
    setWarmed(timeline);
  }, [timeline, fontsReady]);

  const { t, playing } = useClock(clock);
  const fitRef = useRef<HTMLDivElement>(null);
  const scale = useWidth(fitRef) / STAGE_W;

  const total = timeline.total_seconds;
  // End-of-lesson quiz (bonus B1): shown once playback has ended; any playback hides it and a new round starts fresh.
  const ended = !playing && t >= total - 0.05;
  const [quizRound, setQuizRound] = useState(0);
  const [quizSkipped, setQuizSkipped] = useState(false);
  useEffect(() => {
    if (!playing) return;
    setQuizSkipped(false);
    setQuizRound((n) => n + 1);
  }, [playing]);
  const showQuiz = ended && !quizSkipped && (timeline.quiz?.length ?? 0) > 0;
  const scene = sceneAt(timeline.scenes, t);
  const goToScene = (i: number) => clock.seek(timeline.scenes[Math.max(0, Math.min(timeline.scenes.length - 1, i))]?.start ?? 0);

  const toggle = () => {
    if (clock.isPlaying()) return clock.pause();
    if (clock.now() >= total - 0.05) clock.seek(0);
    clock.play();
  };
  // Previous restarts the current scene first, and goes to the one before when already near its start.
  const prev = () => goToScene(scene && t - scene.start > 1 ? scene.index : (scene?.index ?? 0) - 1);
  const next = () => goToScene((scene?.index ?? 0) + 1);
  const replay = () => { clock.seek(0); clock.play(); };

  const keys = useRef({ toggle, prev, next, replay });
  keys.current = { toggle, prev, next, replay };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey || e.ctrlKey || e.metaKey || isTyping(e.target)) return;
      const action = { " ": "toggle", ArrowLeft: "prev", ArrowRight: "next", r: "replay", R: "replay" }[e.key] as keyof typeof keys.current | undefined;
      if (!action) return;
      e.preventDefault(); // Space would otherwise scroll the page or press the focused button twice
      keys.current[action]();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="player">
      <div className={`stage-fit${showQuiz ? " quiz-open" : ""}`} ref={fitRef}>
        <div className="stage-scaler" style={{ transform: `scale(${scale})` }}>
          <Stage timeline={timeline} t={t} onSeek={(x) => clock.seek(x)} poster={!playing && t < 0.001} />
        </div>
        {showQuiz && timeline.quiz && (
          <Quiz key={quizRound} quiz={timeline.quiz} lang={timeline.language} onReplay={replay} onSkip={() => setQuizSkipped(true)} />
        )}
      </div>
      {fontsReady && warmed !== timeline && (
        <div hidden aria-hidden="true">
          {timeline.scenes.map((s) => <div key={s.index}>{renderScene(s, s.end, timeline.language)}</div>)}
        </div>
      )}
      {audioFailed && <p className="notice">Audio could not be loaded; scrub only.</p>}
      <Controls playing={playing} onToggle={toggle} onPrev={prev} onNext={next} onReplay={replay} />
    </div>
  );
}
