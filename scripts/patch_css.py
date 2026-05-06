#!/usr/bin/env python3
"""Patch the extracted styles.css:

1. Prepend @font-face for self-hosted Inter (variable WOFF2).
2. Replace inline data:image base64 URIs with relative file paths.

Idempotent: rerunning won't double-prepend the font-face block.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = ROOT / "assets" / "css" / "styles.css"

FONT_FACE = """\
/* ===== Self-hosted Inter (variable WOFF2) ===== */
@font-face {
  font-family: 'Inter';
  font-style: normal;
  font-weight: 100 900;
  font-display: swap;
  font-named-instance: 'Regular';
  src: url('../fonts/inter-var.woff2') format('woff2-variations'),
       url('../fonts/inter-var.woff2') format('woff2');
}

"""

DATA_URI_RE = re.compile(
    r"data:image/(?P<mime>png|jpeg|jpg|webp);base64,(?P<b64>[A-Za-z0-9+/=]+)"
)
EXT = {"png": "png", "jpeg": "jpg", "jpg": "jpg", "webp": "webp"}


def main() -> None:
    css = CSS.read_text(encoding="utf-8")

    # Replace data URIs with relative paths (use .webp version — universal browser support)
    def repl(m: re.Match) -> str:
        digest = hashlib.sha1(m.group("b64").encode()).hexdigest()[:10]
        return f"../images/img-{digest}.webp"

    new_css, n = DATA_URI_RE.subn(repl, css)
    print(f"Replaced {n} data URI(s) with file paths")

    # Prepend @font-face only once
    if "Self-hosted Inter" not in new_css:
        new_css = FONT_FACE + new_css
        print("Prepended @font-face for Inter")
    else:
        print("@font-face already present, skipping")

    CSS.write_text(new_css, encoding="utf-8")
    print(f"Wrote {CSS.relative_to(ROOT)} ({CSS.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
