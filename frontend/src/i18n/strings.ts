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
  // bonus B2: learning habit
  tryNext: { en: "Try next", hi: "आगे सीखें", ta: "அடுத்து படிங்க" },
  streak: { en: "Streak", hi: "लगातार", ta: "தொடர்ச்சி" },
  days: { en: "{n} days", hi: "{n} दिन", ta: "{n} நாள்" },
  day: { en: "{n} day", hi: "{n} दिन", ta: "{n} நாள்" },
  saveToRevise: { en: "Save to revise", hi: "दोहराने के लिए सहेजें", ta: "திருப்பிப் படிக்க சேமிங்க" },
  revise: { en: "Revise", hi: "दोहराएँ", ta: "திருப்பிப் படிக்க" },
  remove: { en: "Remove", hi: "हटाएँ", ta: "நீக்குங்க" },
  // bonus B3: one-page summary
  summary: { en: "Summary", hi: "सारांश", ta: "சுருக்கம்" },
  summaryPdf: { en: "Summary PDF", hi: "सारांश PDF", ta: "சுருக்கம் PDF" },
  keyPoints: { en: "Key points", hi: "मुख्य बातें", ta: "முக்கியக் கருத்துகள்" },
  code: { en: "Code", hi: "कोड", ta: "Code" },
  answer: { en: "Answers", hi: "उत्तर", ta: "விடைகள்" },
  printPdf: { en: "Print / Save as PDF", hi: "प्रिंट / PDF सहेजें", ta: "Print / PDF-ஆ சேமிங்க" },
  madeOffline: { en: "Made offline with OffGridGuru", hi: "OffGridGuru से ऑफ़लाइन बनाया गया", ta: "OffGridGuru-ல offline-ஆ உருவாக்கப்பட்டது" },
  beginner: { en: "Beginner", hi: "शुरुआती", ta: "தொடக்க நிலை" },
  intermediate: { en: "Intermediate", hi: "मध्यम", ta: "இடைநிலை" },
  back: { en: "Back to the lesson", hi: "पाठ पर वापस", ta: "பாடத்துக்குத் திரும்ப" },
} satisfies Record<string, Record<Language, string>>;

export type StringKey = keyof typeof STRINGS;

export function ui(lang: Language, key: StringKey, vars: Record<string, string | number> = {}): string {
  return STRINGS[key][lang].replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? ""));
}
