import { useEffect, useRef, useState, type ReactNode } from "react";
import Icon from "../components/Icon";
import { ui } from "../i18n/strings";
import type { Language, QuizQuestion } from "../types/lesson";

/**
 * End-of-lesson quiz (bonus B1), shown over the stage when playback ends: one question at a time, instant
 * feedback (green tick on the right answer, red cross on a wrong pick), the explanation, then Next; an end
 * card with the score and Replay lesson. Keyboard: 1-4 pick, Enter next. Text is rendered as text only (H4).
 */
export default function Quiz({ quiz, lang, onReplay, onSkip, onDone, extra }: {
  quiz: QuizQuestion[];
  lang: Language;
  onReplay: () => void;
  onSkip: () => void;
  onDone?: (score: number, total: number) => void; // once, when the last question is answered and Next pressed
  extra?: ReactNode; // shown on the end card (bonus B2: try next, streak, save to revise)
}) {
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const [score, setScore] = useState(0);
  const done = index >= quiz.length;
  const q = done ? null : quiz[index];
  const reported = useRef(false);
  useEffect(() => {
    if (done && !reported.current) {
      reported.current = true;
      onDone?.(score, quiz.length);
    }
  }, [done, score, quiz.length, onDone]);

  const pick = (k: number) => {
    if (!q || picked !== null) return;
    setPicked(k);
    if (k === q.answer_index) setScore((s) => s + 1);
  };
  const next = () => {
    if (picked === null) return;
    setPicked(null);
    setIndex((i) => i + 1);
  };

  const keys = useRef({ pick, next, answered: false });
  keys.current = { pick, next, answered: picked !== null };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.altKey || e.ctrlKey || e.metaKey) return;
      if (e.key >= "1" && e.key <= "4") {
        e.preventDefault();
        keys.current.pick(Number(e.key) - 1);
      } else if (e.key === "Enter" && keys.current.answered) {
        e.preventDefault(); // otherwise the focused Next button would also click
        keys.current.next();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="quiz" lang={lang} role="dialog" aria-label={ui(lang, "quiz")}>
      {q ? (
        <div className="quiz-card">
          <div className="quiz-head">
            <span className="quiz-count">{ui(lang, "questionOf", { n: index + 1, total: quiz.length })}</span>
            <button type="button" className="quiz-skip" onClick={onSkip}>{ui(lang, "skipQuiz")}</button>
          </div>
          <p className="quiz-question">{q.question}</p>
          <ol className="quiz-options">
            {q.options.map((option, k) => {
              const state = picked === null ? "" : k === q.answer_index ? "right" : k === picked ? "wrong" : "other";
              return (
                <li key={k}>
                  <button type="button" className={`quiz-option ${state}`} disabled={picked !== null} onClick={() => pick(k)}
                    aria-keyshortcuts={String(k + 1)}>
                    <span className="quiz-key" aria-hidden="true">{k + 1}</span>
                    <span className="quiz-text">{option}</span>
                    {state === "right" && <span className="quiz-mark"><Icon name="check" label={ui(lang, "correct")} /></span>}
                    {state === "wrong" && <span className="quiz-mark"><Icon name="cross" label={ui(lang, "notQuite")} /></span>}
                  </button>
                </li>
              );
            })}
          </ol>
          {picked !== null && (
            <div className="quiz-feedback" role="status">
              <p>
                <strong className={picked === q.answer_index ? "right" : "wrong"}>
                  {ui(lang, picked === q.answer_index ? "correct" : "notQuite")}
                </strong>{" "}
                {q.explanation}
              </p>
              <button type="button" className="quiz-btn" onClick={next} autoFocus>{ui(lang, "next")}</button>
            </div>
          )}
        </div>
      ) : (
        <div className="quiz-card quiz-end">
          <p className="quiz-count">{ui(lang, "yourScore")}</p>
          <p className="quiz-score">{score} / {quiz.length}</p>
          <button type="button" className="quiz-btn" onClick={onReplay} autoFocus>{ui(lang, "replayLesson")}</button>
          {extra}
        </div>
      )}
    </div>
  );
}
