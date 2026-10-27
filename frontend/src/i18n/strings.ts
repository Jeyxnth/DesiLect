// Player UI words outside the stage, in each lesson language (bonus B1: the end-of-lesson quiz).
// The quiz text itself arrives already translated from the backend. hi/ta: check with a native speaker before the demo.
import type { Language } from "../types/lesson";

const STRINGS = {
  quiz: { en: "Quiz", hi: "प्रश्नोत्तरी", ta: "வினாடி வினா" },
  questionOf: { en: "Question {n} of {total}", hi: "प्रश्न {n} / {total}", ta: "கேள்வி {n} / {total}" },
  correct: { en: "Correct!", hi: "सही!", ta: "சரி!" },
  notQuite: { en: "Not quite", hi: "सही नहीं", ta: "சரியில்லை" },
  next: { en: "Next", hi: "आगे", ta: "அடுத்து" },
  yourScore: { en: "Your score", hi: "आपका स्कोर", ta: "உங்க மதிப்பெண்" },
  replayLesson: { en: "Replay lesson", hi: "पाठ फिर से चलाएँ", ta: "பாடத்தை மறுபடியும் பாருங்க" },
  skipQuiz: { en: "Skip quiz", hi: "क्विज़ छोड़ें", ta: "வினாடி வினாவை விடுங்க" },
} satisfies Record<string, Record<Language, string>>;

export type StringKey = keyof typeof STRINGS;

export function ui(lang: Language, key: StringKey, vars: Record<string, string | number> = {}): string {
  return STRINGS[key][lang].replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? ""));
}
