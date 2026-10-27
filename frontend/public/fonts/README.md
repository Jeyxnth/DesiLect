# Fonts (bundled locally, no Google Fonts URLs, H2)

All files are SIL Open Font License 1.1 (`OFL.txt`) and listed in `LICENSES.md` (H5).
`src/styles/theme.css` declares the `@font-face` rules that point to these file names.

| File | Used for | Status |
|------|----------|--------|
| `NotoSans-Regular.ttf`, `NotoSans-Bold.ttf` | English UI, headings and captions | bundled (step 7) |
| `NotoSansMono-Regular.ttf` | Code in `code_walkthrough` | bundled (step 7) |
| `NotoSansDevanagari-Regular.ttf`, `NotoSansDevanagari-Bold.ttf` | Hindi captions and headings | bundled (step 9) |
| `NotoSansTamil-Regular.ttf`, `NotoSansTamil-Bold.ttf` | Tamil captions and headings | bundled (step 9) |

The MP4 captions are drawn by the browser on the render page, so these files also decide how captions look in the video,
whatever fonts the laptop has installed.
Source: github.com/notofonts/notofonts.github.io (`fonts/<Family>/hinted/ttf/`).
