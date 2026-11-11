"""Rebuilds fonts/dela-gothic-one-subset.woff2, the font of the logo and the big percentage.

Only the characters in fonts/display-text.txt are kept, so the file stays a few KB.
Run this again after changing the logo text, or after using the display font for new text.
tests/smoke_test.py fails when the page shows a character that is not in display-text.txt.

    pip install fonttools brotli
    python3 tools/subset_display_font.py path/to/DelaGothicOne-Regular.ttf

The full font is in https://github.com/google/fonts/tree/main/ofl/delagothicone
(SIL Open Font License 1.1, no Reserved Font Name, so a subset may keep its name).
"""
import pathlib
import sys

from fontTools import subset
from fontTools.ttLib import TTFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEXT_FILE = ROOT / "fonts" / "display-text.txt"
OUT = ROOT / "fonts" / "dela-gothic-one-subset.woff2"


def main(src):
    text = "".join(TEXT_FILE.read_text(encoding="utf-8").split())
    cmap = TTFont(src).getBestCmap()
    missing = [c for c in text if ord(c) not in cmap]
    if missing:
        print("The font has no glyph for: " + " ".join(missing))
        return 1
    options = subset.Options()
    options.flavor = "woff2"
    font = subset.load_font(src, options)
    subsetter = subset.Subsetter(options)
    subsetter.populate(text=text)
    subsetter.subset(font)
    subset.save_font(font, str(OUT), options)
    print(f"{OUT.relative_to(ROOT)}: {len(set(text))} characters, {OUT.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
