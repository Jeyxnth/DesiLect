// The few words the stage itself draws, in each lesson language (the lesson text comes from the plan).
import type { Language } from "../types/lesson";

const STRINGS = {
  step: { en: "Step {n} of {total}", hi: "चरण {n} / {total}", ta: "படி {n} / {total}" },
  keyTerm: { en: "Key term", hi: "मुख्य शब्द", ta: "முக்கிய சொல்" },
} satisfies Record<string, Record<Language, string>>;

export function say(lang: Language, key: keyof typeof STRINGS, vars: Record<string, string | number> = {}): string {
  return STRINGS[key][lang].replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? ""));
}
