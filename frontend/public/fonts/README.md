# Fonts (bundled locally, no Google Fonts URLs, H2)

All files are SIL Open Font License 1.1 (`OFL.txt`) and listed in `LICENSES.md` (H5).
`src/styles/theme.css` declares the `@font-face` rules that point to these file names.

| File | Used for | Status |
|------|----------|--------|
| `NotoSans-Regular.ttf`, `NotoSans-Bold.ttf` | English UI, body text and captions | bundled (step 7) |
| `NotoSansMono-Regular.ttf` | Code in `code_walkthrough` | bundled (step 7) |
| `NotoSansDevanagari-Regular.woff2`, `NotoSansDevanagari-Bold.woff2` | Hindi captions and body text | bundled as WOFF2 (step 10) |
| `NotoSansTamil-Regular.woff2`, `NotoSansTamil-Bold.woff2` | Tamil captions and body text | bundled as WOFF2 (step 10) |
| `NotoSerif-Bold.woff2`, `NotoSerifDevanagari-Bold.woff2`, `NotoSerifTamil-Bold.woff2` | Headings (app and stage) in en / hi / ta | bundled as WOFF2 (chalkboard theme) |

The MP4 captions are drawn by the browser on the render page, so these files also decide how captions look in the video,
whatever fonts the laptop has installed.
Source: github.com/notofonts/notofonts.github.io (`fonts/<Family>/hinted/ttf/`). Noto publishes no WOFF2 for these, so
`python scripts/fonts_to_woff2.py` converts the TTFs (fontTools + brotli; same font, about a third of the size).
The stage picks the stack from `timeline.language` (theme.css `[lang]` rules, `FONT_UI_BY_LANG` in src/scenes/tokens.ts).
