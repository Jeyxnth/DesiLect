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
