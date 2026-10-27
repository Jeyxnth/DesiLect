# Fonts (bundled locally, no Google Fonts URLs, H2)

Drop these files here (SIL Open Font License 1.1) and list each in `LICENSES.md` before committing (H5).
`src/styles/theme.css` already declares `@font-face` rules that point to these file names.

| File | Used for |
|------|----------|
| `NotoSans-Regular.ttf`, `NotoSans-Bold.ttf` | English UI and captions |
| `NotoSansDevanagari-Regular.ttf`, `NotoSansDevanagari-Bold.ttf` | Hindi captions and headings |
| `NotoSansTamil-Regular.ttf`, `NotoSansTamil-Bold.ttf` | Tamil captions and headings |
| `NotoSansMono-Regular.ttf` | Code in `code_walkthrough` |

Until the files are added, the CSS falls back to locally installed fonts, then system fonts.
TODO(step 10): add the files, subset them, and verify burned-in captions in the MP4.
