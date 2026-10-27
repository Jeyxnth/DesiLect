import { ui } from "../i18n/strings";
import type { Language } from "../types/lesson";

/** Flame badge with the current streak (bonus B2); nothing when the streak is 0. */
export function StreakBadge({ count, lang }: { count: number; lang: Language }) {
  if (count <= 0) return null;
  return (
    <span className="streak-badge" lang={lang} title={ui(lang, "streak")} aria-label={`${ui(lang, "streak")}: ${ui(lang, count === 1 ? "day" : "days", { n: count })}`}>
      <span aria-hidden="true">🔥</span> {ui(lang, count === 1 ? "day" : "days", { n: count })}
    </span>
  );
}

/**
 * What a finished lesson offers (bonus B2): two "Try next" cards, the streak and a "Save to revise" toggle.
 * Shown on the quiz end card, or under the player when the lesson has no quiz. Habit parts are omitted when
 * browser storage is unavailable (streak null).
 */
export default function LessonEnd({ lang, nextTopics, nextLabels, onTryNext, streak, saved, onToggleSave }: {
  lang: Language;
  nextTopics?: string[];
  nextLabels?: string[];
  onTryNext: (topic: string) => void;
  streak: number | null;
  saved: boolean | null;
  onToggleSave: () => void;
}) {
  const topics = nextTopics?.length === 2 ? nextTopics : [];
  if (topics.length === 0 && streak === null) return null;
  return (
    <div className="lesson-end" lang={lang}>
      {topics.length > 0 && (
        <div className="try-next">
          {topics.map((topic, k) => (
            <button type="button" key={topic} className="try-next-card" onClick={() => onTryNext(topic)}>
              <span className="try-next-kicker">{ui(lang, "tryNext")}</span>
              <span className="try-next-topic">{nextLabels?.[k] ?? topic}</span>
            </button>
          ))}
        </div>
      )}
      {streak !== null && (
        <div className="lesson-end-row">
          <StreakBadge count={streak} lang={lang} />
          {saved !== null && (
            <button type="button" className="revise-toggle" aria-pressed={saved} onClick={onToggleSave}>
              {saved ? "✓ " : ""}{ui(lang, "saveToRevise")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
