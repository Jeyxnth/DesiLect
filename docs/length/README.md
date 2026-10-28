# Lesson length: does the planner write as much as was asked?

Real llama3.2:3b runs on this laptop, measured on the first planner attempt only, which is the prompt's own effect.

- **Grid:** 5 topics (binary search, photosynthesis, vaccines, hash table, caffeine) × 60 s and 90 s × beginner and
  intermediate, so 20 plans per prompt version.
- **Measured:** the words of narration written against the words a lesson of that length needs (2.3 words per
  second), and whether the plan passes validation as it stands.
- **Script:** `python scripts/measure_length.py --label <name> [--compare docs/length/before.json]`.

| Length, level | Before: words written / asked | After | First try passes |
|---|---|---|---|
| 60 s, beginner | 91% median (61–109%) | 96% median (93–109%) | 3/5 → **5/5** |
| 60 s, intermediate | 85% median (67–143%) | 107% median (87–130%) | 1/5 → **3/5** |
| 90 s, beginner | 77% median (66–89%) | 102% median (76–114%) | 3/5 → **4/5** |
| 90 s, intermediate | **59%** median (52–80%) | **100%** median (91–130%) | 1/5 → **4/5** |

In all, 8 of 20 plans passed on the first try before and 16 of 20 after. Rejections for length fell from 9 to 3.
The rest of the rejections are diagram mistakes (a repeated item, an arrow to a missing item), and the retry fixes
those. Files: `before.json`, `after-beginner.json`, `after-intermediate.json`.

## Why it was short, and what changed (`backend/app/planner/prompts.py`)

1. **Length as a sentence count, not a word total.**
   - The old rule said "2 to 3 *short* sentences per scene" next to "about 35 words per scene", and the model kept
     to the short sentences.
   - It now asks for a plain number of sentences per scene, `sentences_per_scene`: 2 at 30–60 s and 3 at 90 s,
     including both title cards. Each sentence is "short, about 12 words".
   - The model obeys a sentence count closely; it cannot count words.
2. **The example's length is named.** The few-shot example is the 45 s Python-loop lesson, and a 3B model copies its
   size. The rule now says the example is a short 45-second lesson, so this lesson's narrations must be longer (or
   shorter).
3. **Each level gets its own brief** (`LEVEL_BRIEF`).
   - Before, "intermediate" changed only one word ("simple English for an intermediate learner"), so intermediate
     plans were no longer, and often shorter, than beginner ones.
   - Beginner: everyday words and a familiar comparison.
   - Intermediate: the correct terms, how and why it works step by step, a concrete example with real values, and a
     common mistake or limitation.
4. **The retry says how much to change** (`length_fix`). Instead of only quoting the error, it says, for example,
   "Your narration had 103 words but needs about 207. Add about 9 more sentences in total, spread over the scenes."

## Calibration (the first after-run overshot)

- **First after-run:** I assumed about 9 words per sentence and asked for 4 sentences at 90 s. The model obeyed the
  count but wrote about 12 words per sentence, so plans came out at 130–160% and were rejected as too long.
- **Second run:** measured at 10–13 words per sentence in every run, so `WORDS_PER_SENTENCE = 12`. That fixed 90 s,
  but asking 60 s for "2 to 3 sentences" got the upper end, 3 long ones.
- **Final changes:**
  - a single rounded count instead of a range;
  - "keep each sentence short, about 12 words", because intermediate sentences ran longer.

The table above is from the final prompt only. The intermediate runs were only used for calibration and are not
kept.
