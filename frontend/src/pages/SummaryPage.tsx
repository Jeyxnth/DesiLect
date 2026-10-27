import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { getLesson } from "../api/jobs";
import { ui } from "../i18n/strings";
import { navigate } from "../router";
import DiagramScene from "../scenes/DiagramScene";
import { useFontsReady } from "../scenes/measure";
import { FIT_STEPS, cutAtWord, cutLines, firstSentence, type Fit } from "../summary/text";
import type { Lesson, Scene } from "../types/lesson";

declare global {
  interface Window {
    /** Set once the sheet is laid out in its final, one-page form (the server PDF waits for it). */
    __summaryReady?: boolean;
  }
}

const OPTION_LETTERS = ["a", "b", "c", "d"];

/**
 * /summary/:id (bonus B3): a one-page A4 summary built only from the lesson JSON (no second model call):
 * title and level, one block per scene (heading, key point, code, diagram at its final state), the quiz as a
 * worksheet with the answer key at the bottom, the next topics and a footer. All text is rendered as React text
 * nodes (H4). ?print=1 is the server-PDF view (no toolbar). The sheet shrinks step by step until it fits one page.
 */
export default function SummaryPage({ id }: { id: string }) {
  const [lesson, setLesson] = useState<Lesson | null>(null);
  const [error, setError] = useState("");
  const [step, setStep] = useState(0);
  const sheet = useRef<HTMLDivElement>(null);
  const fonts = useFontsReady();
  const printMode = new URLSearchParams(window.location.search).get("print") === "1";

  useEffect(() => {
    window.__summaryReady = false;
    getLesson(id).then(setLesson).catch((e: Error) => setError(e.message));
  }, [id]);
  useEffect(() => setStep(0), [fonts]); // measure again with the real fonts

  // After each render: if the sheet overflows A4, take the next shrink step; otherwise it is final.
  useLayoutEffect(() => {
    const el = sheet.current;
    if (!lesson || !el || !fonts) return;
    const overflows = el.scrollHeight > el.clientHeight + 1;
    if (overflows && step < FIT_STEPS.length - 1) setStep(step + 1);
    else window.__summaryReady = true; // anything still over is clipped by the sheet: never a second page
  }, [lesson, fonts, step]);

  if (error) return <div className="page"><p className="error" role="alert">{error}</p></div>;
  if (!lesson) return <div className="page"><p>Loading...</p></div>;

  const lang = lesson.language;
  const fit = FIT_STEPS[step] ?? FIT_STEPS[FIT_STEPS.length - 1]!;
  const quiz = lesson.quiz ?? [];
  const nextLabels = lesson.next_topic_labels ?? lesson.next_topics ?? [];

  return (
    <div className={`summary-page${printMode ? " print-mode" : ""}`}>
      {!printMode && (
        <div className="summary-toolbar">
          <a href={`/lesson/${encodeURIComponent(id)}`} onClick={(e) => { e.preventDefault(); navigate(`/lesson/${encodeURIComponent(id)}`); }}>
            {ui(lang, "back")}
          </a>
          <button type="button" className="button" onClick={() => window.print()}>{ui(lang, "printPdf")}</button>
        </div>
      )}
      <div className="summary-sheet" lang={lang} ref={sheet} style={{ fontSize: `${fit.scale * 10.5}pt` }}>
        <header className="summary-head">
          <h1>{lesson.title}</h1>
          <p className="summary-meta">{ui(lang, "summary")} · {ui(lang, lesson.level)}</p>
        </header>

        <h2>{ui(lang, "keyPoints")}</h2>
        <div className="summary-scenes">
          {lesson.scenes.map((scene, k) => <SceneBlock key={k} scene={scene} fit={fit} lang={lang} />)}
        </div>

        {quiz.length > 0 && (
          <section className="summary-quiz">
            <h2>{ui(lang, "quiz")}</h2>
            <ol>
              {quiz.map((q, n) => (
                <li key={n}>
                  <p>{q.question}</p>
                  <ol className="summary-options">
                    {q.options.map((o, k) => <li key={k}><span className="summary-letter">{OPTION_LETTERS[k]})</span> {o}</li>)}
                  </ol>
                </li>
              ))}
            </ol>
          </section>
        )}

        {nextLabels.length === 2 && (
          <section className="summary-next">
            <h2>{ui(lang, "tryNext")}</h2>
            <p>{nextLabels[0]} · {nextLabels[1]}</p>
          </section>
        )}

        <footer className="summary-foot">
          {quiz.length > 0 && (
            <p className="summary-key">
              <strong>{ui(lang, "answer")}:</strong>{" "}
              {quiz.map((q, n) => `${n + 1} ${OPTION_LETTERS[q.answer_index] ?? "?"}`).join(" · ")}
            </p>
          )}
          <p>{ui(lang, "madeOffline")} · {new Date().toLocaleDateString(`${lang}-IN`)}</p>
        </footer>
      </div>
    </div>
  );
}

function SceneBlock({ scene, fit, lang }: { scene: Scene; fit: Fit; lang: Lesson["language"] }) {
  const point = firstSentence(scene.narration);
  return (
    <section className="summary-scene">
      <h3>{scene.heading}</h3>
      <p>{fit.keyPointMax ? cutAtWord(point, fit.keyPointMax) : point}</p>
      {scene.type === "code_walkthrough" && (
        <pre className="summary-code" aria-label={ui(lang, "code")}>{cutLines(scene.code, fit.codeLines)}</pre>
      )}
      {scene.type === "diagram" && fit.diagrams && (
        <div className="summary-diagram">
          {/* our own component at its final state (all items and arrows shown); the block heading replaces its own */}
          <DiagramScene scene={{ ...scene, heading: "" }} localT={1e6} beats={[]} cues={[]} lang={lang} />
        </div>
      )}
    </section>
  );
}
