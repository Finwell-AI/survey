#!/usr/bin/env python3
"""Extract CSS, JS, and base64 images from the prototype HTML.

Reads docs/finwellai_prototype_v5 (1).html, splits into:
  - assets/css/styles.css
  - assets/js/app.js
  - assets/images/img-{hash}.png  (one per unique base64 PNG)

Returns a JSON manifest: {section_marker: line_range} so the page builder can
slice body fragments back out without re-parsing.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "finwellai_prototype_v5 (1).html"
ASSETS = ROOT / "assets"
CSS_OUT = ASSETS / "css" / "styles.css"
JS_OUT = ASSETS / "js" / "app.js"
IMG_DIR = ASSETS / "images"
MANIFEST = ROOT / "scripts" / "manifest.json"

DATA_URI_RE = re.compile(
    r'data:image/(?P<mime>png|jpeg|jpg|webp|svg\+xml|gif);base64,(?P<b64>[A-Za-z0-9+/=]+)'
)

EXT = {"png": "png", "jpeg": "jpg", "jpg": "jpg", "webp": "webp", "svg+xml": "svg", "gif": "gif"}


def main() -> None:
    raw = SRC.read_text(encoding="utf-8")

    # 1. Extract <style>...</style>
    style_match = re.search(r"<style>\s*(.*?)\s*</style>", raw, re.DOTALL)
    assert style_match, "no <style> block"
    css = style_match.group(1)

    # 2. Extract <script>...</script> (the main one, not external src)
    # Capture every inline script and concat
    inline_scripts = re.findall(
        r"<script>\s*(.*?)\s*</script>", raw, re.DOTALL
    )
    js = "\n\n/* ----- next inline script ----- */\n\n".join(inline_scripts)

    # 3. Find every unique base64 image data URI
    seen: dict[str, dict] = {}
    for m in DATA_URI_RE.finditer(raw):
        b64 = m.group("b64")
        digest = hashlib.sha1(b64.encode("ascii")).hexdigest()[:10]
        if digest in seen:
            continue
        ext = EXT[m.group("mime")]
        bytes_ = base64.b64decode(b64)
        seen[digest] = {
            "mime": m.group("mime"),
            "ext": ext,
            "size": len(bytes_),
            "filename": f"img-{digest}.{ext}",
            "data": bytes_,
        }

    # 4. Write outputs
    CSS_OUT.parent.mkdir(parents=True, exist_ok=True)
    JS_OUT.parent.mkdir(parents=True, exist_ok=True)
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    CSS_OUT.write_text(css, encoding="utf-8")
    JS_OUT.write_text(js, encoding="utf-8")

    for info in seen.values():
        (IMG_DIR / info["filename"]).write_bytes(info["data"])

    # 5. Manifest for the page builder
    manifest = {
        "css_path": "assets/css/styles.css",
        "js_path": "assets/js/app.js",
        "images": {
            digest: {k: v for k, v in info.items() if k != "data"}
            for digest, info in seen.items()
        },
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"CSS: {CSS_OUT.relative_to(ROOT)} ({CSS_OUT.stat().st_size:,} bytes)")
    print(f"JS:  {JS_OUT.relative_to(ROOT)} ({JS_OUT.stat().st_size:,} bytes)")
    print(f"Images: {len(seen)} unique → {IMG_DIR.relative_to(ROOT)}/")
    for d, info in seen.items():
        print(f"  - {info['filename']:30s} {info['size']:>9,} bytes ({info['mime']})")


if __name__ == "__main__":
    main()
