import Icon from "../components/Icon";
import { ui } from "../i18n/strings";
import type { Language } from "../types/lesson";

/** Flame badge with the current streak (bonus B2); nothing when the streak is 0. */
export function StreakBadge({ count, lang }: { count: number; lang: Language }) {
  if (count <= 0) return null;
  return (
    <span className="streak-badge" lang={lang} title={ui(lang, "streak")} aria-label={`${ui(lang, "streak")}: ${ui(lang, count === 1 ? "day" : "days", { n: count })}`}>
      <Icon name="flame" /> {ui(lang, count === 1 ? "day" : "days", { n: count })}
    </span>
  );
}

/**
 * What a finished lesson offers (bonus B2): two "Try next" cards, the streak and a "Save to revise" toggle.
 * Shown on the quiz end card, or under the player when the lesson has no quiz. Habit parts are omitted when
 * browser storage is unavailable (streak null).
 */
export default function LessonEnd({ lang, nextTopics, nextLabels, onTryNext, streak, saved, onToggleSave, onSummary }: {
  lang: Language;
  nextTopics?: string[];
  nextLabels?: string[];
  onTryNext: (topic: string) => void;
  streak: number | null;
  saved: boolean | null;
  onToggleSave: () => void;
  onSummary?: () => void; // bonus B3: open the one-page summary
}) {
  const topics = nextTopics?.length === 2 ? nextTopics : [];
  if (topics.length === 0 && streak === null && !onSummary) return null;
  return (
    <div className="lesson-end" lang={lang}>
      {topics.length > 0 && (
        <section className="try-next" aria-labelledby="try-next-heading">
          <h2 id="try-next-heading">{ui(lang, "tryNext")}</h2>
          {topics.map((topic, k) => (
            <button type="button" key={topic} className="try-next-card" onClick={() => onTryNext(topic)}>
              {nextLabels?.[k] ?? topic} <Icon name="right" />
            </button>
          ))}
        </section>
      )}
      {(streak !== null || onSummary) && (
        <div className="lesson-end-row">
          {streak !== null && <StreakBadge count={streak} lang={lang} />}
          {onSummary && <button type="button" className="revise-toggle" onClick={onSummary}>{ui(lang, "summary")}</button>}
          {streak !== null && saved !== null && (
            <button type="button" className="revise-toggle" aria-pressed={saved} onClick={onToggleSave}>
              {saved && <Icon name="check" />}{ui(lang, "saveToRevise")}
            </button>
          )}
        </div>
      )}
    </div>
  );
}
