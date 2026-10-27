import { describe, expect, it } from "vitest";
import { FIT_STEPS, cutAtWord, cutLines, firstSentence } from "./text";

describe("summary text", () => {
  it("takes the first sentence as the key point, or all of a one-sentence narration", () => {
    expect(firstSentence("Welcome! Today we learn loops. Ready?")).toBe("Today we learn loops."); // greeting skipped
    expect(firstSentence("Welcome!")).toBe("Welcome!");
    expect(firstSentence("आपका स्वागत है! आज हम गुरुत्वाकर्षण सीखेंगे।")).toBe("आज हम गुरुत्वाकर्षण सीखेंगे।");
    expect(firstSentence("range(3) gives 0, 1 and 2.")).toBe("range(3) gives 0, 1 and 2.");
    expect(firstSentence("नमस्ते! आज हम loop सीखेंगे।")).toBe("आज हम loop सीखेंगे।");
    expect(firstSentence("Python 3.11 is fast")).toBe("Python 3.11 is fast"); // no sentence end: whole text
  });
  it("cuts at a word boundary", () => {
    const s = cutAtWord("one two three four five six seven", 20);
    expect(s.length).toBeLessThanOrEqual(20);
    expect(s).toBe("one two three...");
    expect(cutAtWord("short", 140)).toBe("short");
  });
  it("cuts code to N lines with a marker", () => {
    const code = Array.from({ length: 10 }, (_, i) => `line ${i}`).join("\n");
    expect(cutLines(code, 6).split("\n")).toEqual(["line 0", "line 1", "line 2", "line 3", "line 4", "line 5", "..."]);
    expect(cutLines("a\nb", 6)).toBe("a\nb");
  });
  it("drops diagrams first, then cuts key points, then code", () => {
    expect(FIT_STEPS.map((f) => [f.diagrams, f.keyPointMax, f.codeLines])).toEqual([
      [true, null, 12], [false, null, 12], [false, 140, 12], [false, 140, 6], [false, 140, 6], [false, 140, 6],
    ]);
  });
});
