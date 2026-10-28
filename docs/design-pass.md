# Design pass D1 (tag `design-1`)

A polish pass over the app chrome: the input page, player page, quiz, end-of-lesson card, summary page and notices.
Design changes only. The lesson JSON, the timeline, the audio timing, the backend and the stage are not touched.
The stage covers the scenes, step pill, captions and progress bar. Its CSS rules are byte-identical to before, and so
are the MP4 frames (see "Checks").

Audited with the redesign-skill checklist at 1280 px and 360 px. Each page was captured with Playwright before and
after, including mocked busy and error states.

## Problems found, and what changed

| Area | Before | After |
|---|---|---|
| **Spacing and type** | Gaps chosen one by one (4/6/8/10/12 px), browser-default headings (32 px h1 on input, 22 px on player), labels the same weight as hints | Tokens on `:root`: spacing on a 4 px base (`--sp-1`..`--sp-7`), a rem type scale (`--fs-sm`..`--fs-xl`), radii, a 44 px `--tap`. Bold labels, muted hints, balanced headings, 1.5 line height in the chrome |
| Input page | Bare title, seven fields in one column at every width | App mark, a one-line description of what the app does, Level+Language and Voice+Speed in two-column rows (one column on phones), the Length value shown at the right in tabular figures |
| **Contrast (WCAG AA)** | Quiz option borders 2.2:1 (controls need 3:1); job progress track 1.1:1 (invisible); busy "Generating..." button faded to about 3:1 | New chrome-only tokens: `--ui-edge` #6a82a6 (3.5:1 or more on every surface), `--ui-track` #34496f (accent fill on it 4.2:1). The busy button keeps full-contrast accent text on the panel colour. All text pairs measure 4.5:1 or more |
| Quiz overlay | 97% opaque: the scene title showed through behind the question and score | Opaque `--ui-overlay` |
| Native controls | White select and a blue/white range slider, outside the palette | `color-scheme: dark` on the chrome's form controls, `accent-color` for the slider; selects share the input style |
| **Buttons and states** | Four looks (filled, outlined, ghost, bare underlined links); no hover, pressed or custom focus styles | One shape (44 px, 8 px radius) in three kinds: primary (accent fill), secondary (outline), ghost (text). Hover is a fill change, pressed is a 1 px move, focus is a 3 px accent ring on `:focus-visible`, disabled is 55% opacity with a not-allowed cursor |
| Player actions | Filled "Download MP4" next to three bare links | Play is the one primary control under the stage. Download MP4 is primary in the actions row; Captions, Summary and Summary PDF are small secondary buttons |
| Keyboard hints | ← → drawn in the mono font came out as broken glyphs | Hints use the UI font; on the Play button they are dark on the accent |
| End-of-lesson card | Streak, Summary and Save spread to the edges by `space-between` | Centred row with even gaps |
| Example chips | 30 px tall | 36 px tall, with a hover state |
| **360 px layout** | Summary page 359 px wider than the screen; "Skip quiz" wrapped to two lines; "Summary PDF" alone on its own row | Summary sheet zooms to fit (0.42 at 420 px and below; print and PDF unaffected), no horizontal scroll on any page. "Skip quiz" stays on one line at the right. The small action buttons share rows and fill them |
| **Loading** | A bare "Loading..." line | Player: a 16:9 placeholder in the stage's place with a pulsing dot. Summary: a status card |
| Empty | A sample lesson (no `lesson.json`) left its summary on "Loading..." forever, and the player linked to that page and to a PDF that 404s | "No summary for this lesson" card with a way back. The player hides Summary links when there is no lesson plan, and titles sample lessons by their first heading instead of "Lesson" |
| **Error** | A bad lesson URL showed the header "Lesson" over a red line, with no way forward | "This lesson could not be opened" card with the reason and a "Make a new lesson" button. Error and warning notices share one callout shape (4 px left bar, bold first line). The export error no longer repeats itself ("MP4 export failed. The MP4 export did not finish...") |
| Job progress | Stage list loose under the form | A card titled "Making your lesson" with the topic, a pulsing marker on the active stage, and the visible track |
| Favicon and meta | None | Our own SVG mark (`public/favicon.svg`, listed in LICENSES.md), a description and a theme colour |

Kept on purpose:
- **The Noto fonts.** The skill suggests a different typeface, but these are bundled and cover Devanagari and Tamil.
- **The single accent colour.**
- **The dark palette of the stage.**

## Motion

Only `transform` (the 1 px press on buttons, quiz options and try-next cards, over 120 ms) and `opacity` (the
loading pulse) animate. Under `prefers-reduced-motion: reduce`, transitions and the pulse are switched off; this was
checked in Chromium with the setting on and off.

The lesson's own scene motion is part of the lesson and matches the MP4 frame for frame, so it is left as it is. It
is time-driven (G3) and already limited to short position and opacity moves.

## Checks

- `npx tsc --noEmit`: clean.
- `npm test`: 24 passed.
- Backend tests: 323 passed, including the summary PDF tests, which still fit one A4 page.
- `scripts/check_offline.py`: OK. No external URLs in the source or the built frontend.
- No page requested anything outside localhost (Playwright request log on the input, player, quiz and summary pages).
- `make sample` (`scripts/render_sample.py`): 1280x720, the same duration as before, and every frame hash (ffmpeg
  `framemd5`) identical to the render taken before this pass.

# Design pass D2 (tag `design-2`)

A second pass with the taste-skill (`design-taste-frontend`). Both checks were run:
- `lint.mjs` on `frontend/src` and `index.html`.
- `inspect.mjs`, a real-browser meter in the local Chrome at 1440, 768 and 390 px, on the input page and the player
  (an English and a Tamil lesson).

Same hard limits as D1.

The skill's own art-direction steps were not used: the direction draw, found photographs and footage. They are meant
for marketing sites; this is an app, and `assets.mjs` needs the internet (see "What still fails").

## Fixed

| Rule | Before | After |
|---|---|---|
| Headlines over two lines | Input h1 at 28px (1.9vw), no dominant element on the first screen. A long Tamil lesson title took 3 lines at phone width next to "New lesson" | Input h1 at display size, 72px (5vw) on one line at every width. On phones the lesson title gets the full width, so it takes 2 lines or fewer; "New lesson" sits above it at the right |
| Gradients | None | None |
| Resting shadows | The summary sheet's paper edge was a box-shadow plus a 1px line | A 12mm white outline: no shadow, no line, no layout change |
| Hairlines | A rule above the player extras; rules under the summary headings and over the summary footer; 1px outlines on every secondary button, the keyboard hints, the quiz keys, the streak badge, and the summary code and diagram boxes | Space instead of the rule. Secondary buttons, keyboard hints, quiz keys and the streak badge are flat tone fills (`--ui-fill`, text on it 12:1). Segmented toggles are filled segments 2px apart. The summary footer and diagrams sit on a tone step. Form fields keep their borders, as the skill allows |
| Decorative labels | A small "Try next" kicker inside each topic card (an eyebrow) | One real heading over the two topic buttons |
| Emoji and glyphs as UI | ⚠ 🔥 ✓ ✗ ▶ ⏮ ⏭ ❚❚ ↺ ← → in the chrome | Our own small SVG icon set (`components/Icon.tsx`): one 24px grid, 2px round strokes. Done/running/failed stage marks are icons; to-do stages are blank |
| Monospace outside code | The quiz option keys used the code font | The UI font, with tabular figures. The mono face stays only for real code: the code scenes and the summary code block, marked `taste-skill-ignore` |
| One accent | The streak badge was orange on brown, a second accent | Tone fill, with the flame in the one accent (sky blue) |
| Motion | Nothing moved on load (0 and 2 elements) | A staggered entrance for the chrome: each part rises 16px into place, about 70ms after the one before it. Transform and opacity only, once on load, never hiding content (fill `backwards`, so press feedback still works), and off under reduced motion. The stage's picture never moves; only its frame enters |
| Long lines | An export error ran about 134 characters per line | Callouts and notes capped at 72ch |

The stage frame in the player carries `data-ui`. In the skill's terms it is a real interface fragment: the live lesson,
the product's own output.

## Inspector result

Lint: **0 FAIL**. One WARN, `padStart(2, "0")` in `habit/storage.ts`, which builds the YYYY-MM-DD date for the streak,
not index numbers.

Inspect, input page and both players: headlines, gradient, shadow, hairline, outlined-box, eyebrow, mono, emoji,
contrast, measure, overflow and focal-point all pass. What remains:

- **FAIL `few-pictures`** (it wants at least four real photographs or clips per page).

  The skill gets them from open collections over the internet (`assets.mjs`). That breaks H2: no network at runtime,
  and no downloaded assets in the build. It is also the wrong fit for this app:
  - the pictures here are the lesson itself, drawn by our components;
  - a stock photograph cannot know the topic a learner will type.

  Skipped on purpose, as the brief asked.
- **WARN `no-footage`.** Same reason: no network, and the lesson is the moving picture.
- **WARN `still-page`.** 8 moving elements on the input page and 15 on the player; under 16 is a warning. More motion
  would cost phones frames (H6) for no learning value, and the lesson already moves.

## Checks

- `npx tsc --noEmit`: clean.
- `npm test`: 24 passed.
- Backend tests: 323 passed (summary PDFs still one A4 page).
- `scripts/check_offline.py`: OK.
- `make sample`: 1280x720, 43.41 s (unchanged), all 1302 frame hashes identical to the render taken before D1.

# Design pass D3: "Chalkboard and Paper" (tag `design-3`)

A new colour scheme and serif headings. Unlike D1 and D2, this pass changes the stage on purpose, so the MP4 frames
change. The lesson JSON, timeline, audio, timing and backend did not change. Every MP4 keeps its exact duration.

## The scheme

| Role | Colour | Where |
|---|---|---|
| Page (paper) | `#FBF6EC` cream | app background |
| Surface | `#FFFFFF` | cards, fields, quiz options |
| Text | `#2B2A26` soft charcoal (13.3:1) | all running text, including the tagline |
| Muted | `#6B665B` (5.3:1) | secondary notes |
| Stage | `#1F4D45` chalkboard green, chalk `#F7F3E8` text (8.6:1) | the lesson canvas, player and MP4 |
| Primary accent | `#E2711D` saffron | buttons (with charcoal text, 4.5:1), the stage progress bar, the newest diagram item, the title icon |
| Second accent | `#B8412F` terracotta | summary headings, the key-term note (a filled card, chalk text 4.9:1), errors |
| Highlight | `#F2C14E` marigold | the code highlight bar (7.3:1 on the code card) |
| Correct | `#3F8F5A` | quiz border and mark; the word "Correct" uses `#2F6E45` (5.3:1) |
| Wrong / error | `#B8412F` on `#FBE9E5` (4.7:1) | quiz and error callouts |
| Fallback notice | `#C98A1B` bar and icon on `#FFF3D6` | the title text uses `#8A5A0F` (5.4:1) |

Where the scheme's own colour fails as text, I added a darker "ink" of it:
- Saffron on cream is 2.95:1, so links, focus rings, the job bar and the active stage use `#A9520F` (5.0:1).
- The fallback amber is 2.7:1 on its own background, so its text uses `#8A5A0F`.

The scheme's colours stay as fills, bars and icons.

The quiz is a cream paper worksheet laid over the board, so the correct and wrong colours work as given. On the
green board they would be under 2:1.

Headings use **Noto Serif Bold**, with Noto Serif Devanagari and Noto Serif Tamil for Hindi and Tamil. That covers
the app headings, the stage's title cards and scene headings, the quiz question and score, and the summary
headings. Body text, captions and labels stay in Noto Sans.

The three faces came from the Noto repository: `github.com/notofonts/notofonts.github.io`, the same source as the
other fonts. All three are SIL OFL 1.1, checked in each font's name table. They are converted to WOFF2 by
`scripts/fonts_to_woff2.py` (360 KB in all) and listed in LICENSES.md. Stage headings are also measured with the
serif (`measure.ts`, `heading: true`), so layouts fit the real glyph widths.

## Bugs found and fixed while doing it

- The captions were charcoal on the dark caption band. They inherited `body`'s colour, and the stage never set its
  own. `.stage-canvas` now sets chalk text.
- The native range slider drew a near-black track on cream. It now has a flat track in the palette and a saffron
  thumb.

## Checks

- Contrast: every text pair is WCAG AA (4.5:1), and every control or progress edge is at least 3:1. Each pair was
  computed; the numbers are in the table and in `theme.css`.
- Typecheck clean. Vitest: 24 passed. Offline check: OK.
- Backend: 330 of 331 passed in the full run. The one failure is the timing gate
  `test_export_smoke_full_sample_under_60s`, which must render the sample in under 60 s. On its own it passes, with
  the render taking 40 s. In the full suite it runs after about 100 s of other browser and model tests on the same
  laptop and goes over. It was already close to the line before this pass (54 s in D1, 49 s in D2), so it is the
  intermittent failure noted earlier; it is not caused by the theme.
- Stage frames from the render page (the MP4 source) were checked in English, Hindi and Tamil, on title, code and
  diagram scenes. Matras are not clipped, captions read, and the serif shows in all three scripts.
- `make sample`: 1280x720, 43.41 s, exactly as before; the frames differ by design.
- Submission MP4s: re-exported from their own timelines and audio, with no new plan or voice
  (`scripts/reexport_submissions.py`). All four use the smooth export and match their timelines to within 0.03 s:

  | Video | Duration (timeline) |
  |---|---|
  | caffeine en | 41.00 s (41.00) |
  | caffeine hi | 61.00 s (60.97) |
  | binary search en | 41.73 s (41.71) |
  | binary search hi | 57.62 s (57.62) |

  The captions are unchanged.
- Taste lint: 0 FAIL. Taste inspector: the same single FAIL as D2 (`few-pictures`, see D2).

  One new WARN, `palette-cream`: the skill flags a cream ground as a generated-page habit. Here it is the chosen
  brand, the paper of a school notebook, so it stays. The skill's own guidance is to keep a brand's colours and say
  so in the report.

  The `grey-body` WARN it raised was right, and is fixed: the tagline is now in full ink.
