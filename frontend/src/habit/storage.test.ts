import { describe, expect, it } from "vitest";
import {
  HABIT_KEY, REVISE_CAP, addRevise, currentStreak, daysBetween, emptyHabit, loadHabit, localDay, parseHabit,
  recordStreak, removeRevise, saveHabit, type HabitState, type KeyValueStore, type ReviseEntry,
} from "./storage";

const withStreak = (count: number, last_day: string | null): HabitState => ({ ...emptyHabit(), streak: { count, last_day } });

describe("streak", () => {
  it("starts at 1", () => {
    expect(recordStreak(emptyHabit(), "2026-10-28").streak).toEqual({ count: 1, last_day: "2026-10-28" });
  });
  it("same day: no change", () => {
    const s = withStreak(3, "2026-10-28");
    expect(recordStreak(s, "2026-10-28")).toBe(s);
  });
  it("next day: count + 1", () => {
    expect(recordStreak(withStreak(1, "2026-10-28"), "2026-10-29").streak).toEqual({ count: 2, last_day: "2026-10-29" });
  });
  it("next day across a month and a year end", () => {
    expect(recordStreak(withStreak(4, "2026-10-31"), "2026-11-01").streak.count).toBe(5);
    expect(recordStreak(withStreak(4, "2026-12-31"), "2027-01-01").streak.count).toBe(5);
  });
  it("gap of 2+ days: reset to 1", () => {
    expect(recordStreak(withStreak(7, "2026-10-28"), "2026-10-30").streak).toEqual({ count: 1, last_day: "2026-10-30" });
  });
  it("clock moved backwards: no change", () => {
    const s = withStreak(5, "2026-10-28");
    expect(recordStreak(s, "2026-10-20")).toBe(s);
  });
  it("shows 0 once a whole day was missed", () => {
    expect(currentStreak(withStreak(4, "2026-10-28"), "2026-10-29")).toBe(4);
    expect(currentStreak(withStreak(4, "2026-10-28"), "2026-10-30")).toBe(0);
    expect(currentStreak(emptyHabit(), "2026-10-30")).toBe(0);
  });
  it("uses the local calendar day, and day arithmetic ignores DST", () => {
    expect(localDay(new Date(2026, 0, 5, 23, 59))).toBe("2026-01-05");
    expect(daysBetween("2026-03-28", "2026-03-30")).toBe(2);
  });
});

describe("storage", () => {
  const memory = (initial: string | null = null): KeyValueStore & { data: Map<string, string> } => {
    const data = new Map<string, string>(initial === null ? [] : [[HABIT_KEY, initial]]);
    return { data, getItem: (k) => data.get(k) ?? null, setItem: (k, v) => void data.set(k, v) };
  };
  const throwing: KeyValueStore = {
    getItem: () => { throw new Error("SecurityError"); },
    setItem: () => { throw new Error("QuotaExceededError"); },
  };

  it("empty storage gives a fresh state", () => {
    expect(loadHabit(memory())).toEqual(emptyHabit());
  });
  it("round-trips", () => {
    const store = memory();
    const s = recordStreak(emptyHabit(), "2026-10-28");
    expect(saveHabit(s, store)).toBe(true);
    expect(loadHabit(store)).toEqual(s);
  });
  it.each(["{not json", "[]", '{"version":2,"streak":{"count":1,"last_day":null},"revise":[]}',
    '{"version":1,"streak":{"count":"x","last_day":null},"revise":[]}', '{"version":1,"streak":{"count":1,"last_day":"yesterday"},"revise":[]}'])(
    "corrupt data is ignored (feature hidden): %s", (text) => {
      expect(loadHabit(memory(text))).toBeNull();
    });
  it("blocked storage hides the feature instead of throwing", () => {
    expect(loadHabit(throwing)).toBeNull();
    expect(loadHabit(null)).toBeNull();
    expect(saveHabit(emptyHabit(), throwing)).toBe(false);
  });
  it("drops malformed revise rows but keeps good ones", () => {
    const text = JSON.stringify({ ...emptyHabit(), revise: [{ lesson_id: "a", title: "A", language: "en", added_at: "t" }, { nope: 1 }] });
    expect(parseHabit(text)?.revise.map((e) => e.lesson_id)).toEqual(["a"]);
  });
});

describe("revise list", () => {
  const entry = (n: number): ReviseEntry => ({ lesson_id: `id${n}`, title: `Lesson ${n}`, language: "en", added_at: `t${n}` });

  it("newest first, and re-adding moves a lesson to the top without duplicating it", () => {
    let s = addRevise(addRevise(emptyHabit(), entry(1)), entry(2));
    s = addRevise(s, { ...entry(1), score: { correct: 1, total: 3 } });
    expect(s.revise.map((e) => e.lesson_id)).toEqual(["id1", "id2"]);
    expect(s.revise[0]?.score).toEqual({ correct: 1, total: 3 });
  });
  it(`is capped at ${REVISE_CAP}, dropping the oldest`, () => {
    let s = emptyHabit();
    for (let n = 0; n < REVISE_CAP + 7; n++) s = addRevise(s, entry(n));
    expect(s.revise).toHaveLength(REVISE_CAP);
    expect(s.revise[0]?.lesson_id).toBe(`id${REVISE_CAP + 6}`);
    expect(s.revise.some((e) => e.lesson_id === "id0")).toBe(false);
  });
  it("removes one row", () => {
    const s = removeRevise(addRevise(addRevise(emptyHabit(), entry(1)), entry(2)), "id1");
    expect(s.revise.map((e) => e.lesson_id)).toEqual(["id2"]);
  });
});
