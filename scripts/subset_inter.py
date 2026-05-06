#!/usr/bin/env python3
"""Subset the Inter variable WOFF2 to only the characters actually used in
the rendered HTML. Goes from ~47KB (Latin block) to ~15-20KB (only letters
that appear in our copy + a small safety buffer).

Reads:
    node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2
    plus every .html and .md file in the project.

Writes:
    assets/fonts/inter-var.woff2
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
SRC = (
    ROOT
    / "node_modules"
    / "@fontsource-variable"
    / "inter"
    / "files"
    / "inter-latin-wght-normal.woff2"
)
OUT = ROOT / "assets" / "fonts" / "inter-var.woff2"

# Pages and content sources whose visible text the font must cover.
TEXT_SOURCES = [
    *ROOT.glob("*.html"),
    *(ROOT / "content").glob("*.md"),
]


def collect_chars() -> set[str]:
    chars: set[str] = set()
    # Always-include: ASCII printable + a few smart-quote / dash variants the
    # design system uses, plus a tiny safety buffer for content edits.
    base = (
        " !\"#$%&'()*+,-./0123456789:;<=>?@"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`"
        "abcdefghijklmnopqrstuvwxyz{|}~"
        "‘’“”·•—–…"  # smart punctuation
        "✓✗★⌃▲▼"   # icons used inline
        "©®™"
    )
    chars.update(base)
    for src in TEXT_SOURCES:
        try:
            txt = src.read_text(encoding="utf-8")
        except Exception:
            continue
        # Strip HTML tags so we don't count attribute names etc. as text.
        txt = re.sub(r"<[^>]+>", " ", txt)
        chars.update(txt)
    # Drop control chars
    return {c for c in chars if ord(c) >= 0x20 or c == "\n"}


def main() -> None:
    if not SRC.exists():
        sys.exit(
            f"missing: {SRC}\n"
            "Run `npm install` first so @fontsource-variable/inter is on disk."
        )
    chars = collect_chars()
    print(f"unique characters used on site: {len(chars)}")

    font = TTFont(SRC)
    opts = Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga", "cv02", "cv03", "cv04", "cv11", "tnum"]
    opts.desubroutinize = False  # variable axis would die otherwise

    subs = Subsetter(options=opts)
    subs.populate(text="".join(sorted(chars)))
    subs.subset(font)

    font.flavor = "woff2"
    font.save(OUT)
    size = OUT.stat().st_size
    print(f"wrote {OUT.relative_to(ROOT)}: {size:,} bytes ({size / 1024:.1f}KB)")


if __name__ == "__main__":
    main()
