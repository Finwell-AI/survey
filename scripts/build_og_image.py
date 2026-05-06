#!/usr/bin/env python3
"""Generate a placeholder Open Graph image for social sharing.

Output: assets/og-image.png (1200x630).

Style: Deep Trust navy gradient background, large Finwell AI wordmark, tagline.
This is a stand-in until Alex supplies a designer-built OG card. Replace with
a final asset before public launch.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "og-image.png"

# Brand colours — straight from the brand guidelines doc.
DEEP_TRUST = (11, 31, 59)        # #0B1F3B
DARK_BG_MID = (2, 17, 46)        # #02112E
AI_BLUE = (47, 128, 237)         # #2F80ED
LIGHT_BLUE = (86, 204, 242)      # #56CCF2
WHITE = (255, 255, 255)
SOFT = (219, 234, 254)


def gradient_background(size: tuple[int, int], top: tuple[int, int, int], bot: tuple[int, int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGB", size, top)
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top[0] * (1 - t) + bot[0] * t)
        g = int(top[1] * (1 - t) + bot[1] * t)
        b = int(top[2] * (1 - t) + bot[2] * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b))
    return img


def find_font(size: int) -> ImageFont.ImageFont:
    """Best-effort: try Inter from Google Fonts, fall back to system bold."""
    candidates = [
        ROOT / "assets" / "fonts" / "inter-var.woff2",  # variable WOFF2 — PIL can't load
        Path("/Library/Fonts/Helvetica Neue.ttc"),
        Path("/System/Library/Fonts/HelveticaNeue.ttc"),
        Path("/System/Library/Fonts/SFNS.ttf"),
        Path("/System/Library/Fonts/SFNSDisplay-Bold.otf"),
        Path("/Library/Fonts/Arial Bold.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ]
    for c in candidates:
        if c.exists() and c.suffix in {".ttf", ".otf", ".ttc"}:
            try:
                return ImageFont.truetype(str(c), size)
            except Exception:
                continue
    return ImageFont.load_default()


def main() -> None:
    W, H = 1200, 630
    img = gradient_background((W, H), DEEP_TRUST, DARK_BG_MID)
    draw = ImageDraw.Draw(img)

    # Subtle node-graph hint: a few glowing dots in a corner
    for x, y, r in [(80, 80, 4), (110, 130, 3), (160, 100, 5), (200, 160, 3), (140, 200, 4), (90, 250, 3)]:
        draw.ellipse([x - r, y - r, x + r, y + r], fill=LIGHT_BLUE)
    # Connecting strokes
    draw.line([(80, 80), (110, 130), (160, 100), (200, 160), (140, 200), (90, 250)], fill=AI_BLUE, width=2)

    # Wordmark
    big = find_font(112)
    medium = find_font(36)
    small = find_font(24)

    title_text = "Finwell"
    accent_text = "AI"
    tagline = "Financial wellness, smarter future."
    cta = "Join the founding 500 — finwellai.com.au"

    # Layout: title centred at ~y=240, accent in AI Blue beside it.
    title_bbox = draw.textbbox((0, 0), title_text, font=big)
    accent_bbox = draw.textbbox((0, 0), accent_text, font=big)
    title_w = title_bbox[2] - title_bbox[0]
    accent_w = accent_bbox[2] - accent_bbox[0]
    gap = 24
    total_w = title_w + gap + accent_w
    title_x = (W - total_w) // 2
    accent_x = title_x + title_w + gap
    y_title = 230
    draw.text((title_x, y_title), title_text, font=big, fill=WHITE)
    draw.text((accent_x, y_title), accent_text, font=big, fill=AI_BLUE)

    # Tagline below
    tag_bbox = draw.textbbox((0, 0), tagline, font=medium)
    draw.text(((W - (tag_bbox[2] - tag_bbox[0])) // 2, y_title + 140), tagline, font=medium, fill=SOFT)

    # CTA at bottom
    cta_bbox = draw.textbbox((0, 0), cta, font=small)
    draw.text(((W - (cta_bbox[2] - cta_bbox[0])) // 2, H - 70), cta, font=small, fill=LIGHT_BLUE)

    img.save(OUT, "PNG", optimize=True)
    print(f"Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
