"""Convert the bundled Noto TTFs for Hindi and Tamil to WOFF2 (step 10). Run once after updating a TTF.

Noto publishes these scripts as TTF/OTF only; WOFF2 is the same font, Brotli-compressed (about half the size).
Needs fontTools and brotli (dev tools, not used at runtime). Writes frontend/public/fonts/<name>.woff2 and removes
the TTF it came from, so only one copy is served.

    python scripts/fonts_to_woff2.py
"""
from __future__ import annotations

from pathlib import Path

from fontTools.ttLib import TTFont

FONTS = Path(__file__).resolve().parents[1] / "frontend" / "public" / "fonts"
NAMES = ["NotoSansDevanagari-Regular", "NotoSansDevanagari-Bold", "NotoSansTamil-Regular", "NotoSansTamil-Bold"]


def main() -> int:
    for name in NAMES:
        ttf, woff2 = FONTS / f"{name}.ttf", FONTS / f"{name}.woff2"
        if not ttf.is_file():
            print(f"{name}: no TTF ({'woff2 present' if woff2.is_file() else 'MISSING'})")
            continue
        font = TTFont(ttf)
        font.flavor = "woff2"
        font.save(woff2)
        print(f"{name}: {ttf.stat().st_size // 1024} KB ttf -> {woff2.stat().st_size // 1024} KB woff2")
        ttf.unlink()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
