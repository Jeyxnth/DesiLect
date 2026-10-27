// Learning habit (bonus B2): daily streak and revise list, kept only in this browser (no account, no server state).
// One localStorage key. Every read and write is guarded: blocked storage or corrupt JSON hides the feature,
// and the lesson still plays.
import { useCallback, useState } from "react";
import type { Language } from "../types/lesson";

export const HABIT_KEY = "blu.habit.v1";
export const REVISE_CAP = 50;

export interface ReviseEntry {
  lesson_id: string;
  title: string;
  language: Language;
  added_at: string; // ISO time
  score?: { correct: number; total: number };
}

export interface HabitState {
  version: 1;
  streak: { count: number; last_day: string | null }; // last_day: local calendar day YYYY-MM-DD
  revise: ReviseEntry[]; // newest first
}

export const emptyHabit = (): HabitState => ({ version: 1, streak: { count: 0, last_day: null }, revise: [] });

/** The device's local calendar day (not UTC), YYYY-MM-DD. */
export function localDay(d: Date = new Date()): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Whole days between two YYYY-MM-DD days (b - a), by calendar, so DST changes do not matter. */
export function daysBetween(a: string, b: string): number {
  const toNum = (day: string) => {
    const [y, m, d] = day.split("-").map(Number);
    return Date.UTC(y ?? 0, (m ?? 1) - 1, d ?? 1) / 86_400_000;
  };
  return Math.round(toNum(b) - toNum(a));
}

/** A finished lesson on `today`: same day no change, next day +1, a gap of 2+ days restarts at 1,
 *  and a clock moved backwards changes nothing. */
export function recordStreak(state: HabitState, today: string): HabitState {
  const { count, last_day } = state.streak;
  if (last_day === null) return { ...state, streak: { count: 1, last_day: today } };
  const gap = daysBetween(last_day, today);
  if (gap <= 0) return state;
  return { ...state, streak: { count: gap === 1 ? count + 1 : 1, last_day: today } };
}

/** The streak to show today: it lapses (0) once a whole day has been missed. */
export function currentStreak(state: HabitState, today: string): number {
  const { count, last_day } = state.streak;
  if (last_day === null) return 0;
  const gap = daysBetween(last_day, today);
  return gap <= 1 ? count : 0;
}

/** Add (or refresh) a lesson at the top of the revise list, keeping at most REVISE_CAP entries. */
export function addRevise(state: HabitState, entry: ReviseEntry): HabitState {
  const rest = state.revise.filter((e) => e.lesson_id !== entry.lesson_id);
  return { ...state, revise: [entry, ...rest].slice(0, REVISE_CAP) };
}

export function removeRevise(state: HabitState, lessonId: string): HabitState {
  return { ...state, revise: state.revise.filter((e) => e.lesson_id !== lessonId) };
}

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null && !Array.isArray(v);

/** Parse stored text; null when it is corrupt or not version 1 (the feature then hides itself). */
export function parseHabit(text: string | null): HabitState | null {
  if (text === null) return emptyHabit();
  try {
    const v: unknown = JSON.parse(text);
    if (!isObj(v) || v.version !== 1 || !isObj(v.streak) || !Array.isArray(v.revise)) return null;
    const { count, last_day } = v.streak;
    if (typeof count !== "number" || !(last_day === null || (typeof last_day === "string" && /^\d{4}-\d{2}-\d{2}$/.test(last_day)))) return null;
    const revise = v.revise.filter((e): e is ReviseEntry =>
      isObj(e) && typeof e.lesson_id === "string" && typeof e.title === "string" && typeof e.language === "string" && typeof e.added_at === "string");
    return { version: 1, streak: { count, last_day }, revise: revise.slice(0, REVISE_CAP) };
  } catch {
    return null;
  }
}

/** Minimal Storage interface, so tests can pass a fake (or a throwing one). */
export interface KeyValueStore {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

function browserStore(): KeyValueStore | null {
  try {
    return window.localStorage; // can throw when site data is blocked
  } catch {
    return null;
  }
}

/** The saved state, or null when storage is blocked or the data is corrupt. */
export function loadHabit(store: KeyValueStore | null = browserStore()): HabitState | null {
  if (!store) return null;
  try {
    return parseHabit(store.getItem(HABIT_KEY));
  } catch {
    return null;
  }
}

/** Save; false when storage refuses (quota, blocked). */
export function saveHabit(state: HabitState, store: KeyValueStore | null = browserStore()): boolean {
  if (!store) return false;
  try {
    store.setItem(HABIT_KEY, JSON.stringify(state));
    return true;
  } catch {
    return false;
  }
}

/** React access to the habit state. `habit` is null when the feature is unavailable (then render nothing). */
export function useHabit() {
  const [habit, setHabit] = useState<HabitState | null>(() => loadHabit());
  const update = useCallback((change: (s: HabitState) => HabitState) => {
    setHabit((current) => {
      const base = loadHabit() ?? current; // another tab or page may have written since
      if (!base) return null;
      const next = change(base);
      return saveHabit(next) ? next : null; // storage gone: hide the feature
    });
  }, []);
  return { habit, update };
}
