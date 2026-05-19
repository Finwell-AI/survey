#!/usr/bin/env python3
"""Publish one article from blog-scheduled/ into the live blog/ pipeline.

Usage:
    python3 scripts/publish_blog.py <stem-or-md-name> [--alt "alt text"]
    python3 scripts/publish_blog.py --list
    python3 scripts/publish_blog.py --next   # most-recently-published-eligible stem

Where <stem-or-md-name> is either the full filename
("2026-05-19-2026-federal-budget-tax-changes-australia.md") or the bare stem
("2026-05-19-2026-federal-budget-tax-changes-australia"). The script:

  1. Locates the matching <stem>.md and <stem>.jpg.png in blog-scheduled/.
  2. Resizes the hero image to 1200x675 (16:9, OG-safe) and emits
     assets/images/img-<hash>.{jpg,webp,avif} — content-hashed so the
     filename never collides with an existing image.
  3. Strips the trailing "## Notes for Val" block from the markdown.
  4. Injects `hero_image: img-<hash>` (and optionally hero_image_alt) into
     the frontmatter if not already present.
  5. Writes the cleaned markdown to blog/<slug>.md, where <slug> comes from
     the frontmatter.
  6. Runs build_blog.py to regenerate blog/index.html, blog/<slug>/index.html,
     and sitemap-blog.xml.
  7. Deletes the originals in blog-scheduled/ on success (use --keep-source
     to retain them for re-runs during testing).

The script never deploys. After it runs cleanly, the deploy is a manual
`netlify build && netlify deploy --prod --dir .` step (see CLAUDE.md).
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError as exc:  # pragma: no cover - bootstrap guard
    raise SystemExit("Pillow is required: pip install Pillow") from exc

ROOT = Path(__file__).resolve().parent.parent
SCHEDULED_DIR = ROOT / "blog-scheduled"
BLOG_DIR = ROOT / "blog"
ASSETS_DIR = ROOT / "assets" / "images"
BUILD_BLOG = ROOT / "scripts" / "build_blog.py"

HERO_WIDTH = 1200
HERO_HEIGHT = 675  # matches the 16:9 hero <img> in build_blog.render_article
JPG_QUALITY = 88
WEBP_QUALITY = 82
AVIF_QUALITY = 55  # avifenc -q range 0..100; 55 ~= visually transparent

NOTES_BLOCK_RE = re.compile(
    r"\n+##\s+Notes for Val.*?\Z",
    re.DOTALL | re.IGNORECASE,
)
# Trailing "## Sources" heading + the source list that follows. The list may
# already be in `[^N]:` footnote form or in plain `N. text` numbered form.
# Captures the list body so the converter can rewrite plain numbers into
# footnote definitions if needed. Stops at the next `##` heading, a JSON-LD
# HTML comment, or end-of-string.
SOURCES_BLOCK_RE = re.compile(
    r"\n+##\s+Sources\s*\n+(.*?)(?=\n##\s+|\n<!--|\Z)",
    re.DOTALL | re.IGNORECASE,
)
SOURCES_ITEM_RE = re.compile(r"^\s*(\d+)\.\s+(.+?)\s*$")
FOOTNOTE_DEF_LINE_RE = re.compile(r"^\[\^[0-9A-Za-z_-]+\]:\s+")
FRONTMATTER_RE = re.compile(r"^(---\s*\n)(.*?)(\n---\s*\n)", re.DOTALL)
SLUG_RE = re.compile(r"^slug:\s*(.+?)\s*$", re.MULTILINE)
HAS_HERO_RE = re.compile(r"^hero_image:\s*", re.MULTILINE)
HAS_HERO_ALT_RE = re.compile(r"^hero_image_alt:\s*", re.MULTILINE)


# ------------------------------------------------------------------ discovery
def resolve_stem(arg: str) -> str:
    """Accept "<stem>", "<stem>.md", or "blog-scheduled/<stem>.md"."""
    name = Path(arg).name
    if name.endswith(".md"):
        name = name[:-3]
    return name


def find_pair(stem: str) -> tuple[Path, Path]:
    md_path = SCHEDULED_DIR / f"{stem}.md"
    if not md_path.is_file():
        raise SystemExit(f"Markdown not found: {md_path}")
    # Image extension in blog-scheduled/ is "<stem>.jpg.png" (PNG on disk).
    candidates = [
        SCHEDULED_DIR / f"{stem}.jpg.png",
        SCHEDULED_DIR / f"{stem}.png",
        SCHEDULED_DIR / f"{stem}.jpg",
        SCHEDULED_DIR / f"{stem}.jpeg",
    ]
    for path in candidates:
        if path.is_file():
            return md_path, path
    looked = "\n  ".join(str(c) for c in candidates)
    raise SystemExit(f"Hero image not found. Looked for:\n  {looked}")


def list_scheduled() -> list[str]:
    if not SCHEDULED_DIR.is_dir():
        return []
    stems = sorted({p.stem.replace(".jpg", "") for p in SCHEDULED_DIR.glob("*.md")})
    return stems


# ------------------------------------------------------------------ image
def hash_basename(jpg_bytes: bytes) -> str:
    return "img-" + hashlib.sha1(jpg_bytes).hexdigest()[:8]


def emit_image_set(source: Path) -> tuple[str, dict[str, int]]:
    """Convert <source> to 1200x675 JPG, WebP, AVIF in assets/images/.

    Returns (basename, {ext: bytes_written}) where basename is img-<hash>
    derived from the JPG bytes.
    """
    with Image.open(source) as im:
        im = im.convert("RGB")
        # Center-crop to 16:9 then resize. Source for these articles is already
        # 16:9 so this is a no-op crop in practice; safe for off-ratio inputs.
        target_ratio = HERO_WIDTH / HERO_HEIGHT
        src_ratio = im.width / im.height
        if src_ratio > target_ratio:
            new_w = int(im.height * target_ratio)
            left = (im.width - new_w) // 2
            im = im.crop((left, 0, left + new_w, im.height))
        elif src_ratio < target_ratio:
            new_h = int(im.width / target_ratio)
            top = (im.height - new_h) // 2
            im = im.crop((0, top, im.width, top + new_h))
        im = im.resize((HERO_WIDTH, HERO_HEIGHT), Image.LANCZOS)

        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        # Write JPG first to a temp path so we can hash its bytes for the name.
        tmp_jpg = ASSETS_DIR / ".publish_blog.tmp.jpg"
        im.save(tmp_jpg, "JPEG", quality=JPG_QUALITY, optimize=True, progressive=True)
        jpg_bytes = tmp_jpg.read_bytes()
        basename = hash_basename(jpg_bytes)

        jpg_path = ASSETS_DIR / f"{basename}.jpg"
        webp_path = ASSETS_DIR / f"{basename}.webp"
        avif_path = ASSETS_DIR / f"{basename}.avif"

        tmp_jpg.replace(jpg_path)
        im.save(webp_path, "WEBP", quality=WEBP_QUALITY, method=6)

    # AVIF via avifenc (Pillow needs an extra plugin we don't have installed).
    subprocess.run(
        ["avifenc", "--min", "0", "--max", "63", "-a", "end-usage=q",
         "-a", f"cq-level={AVIF_QUALITY}", "-j", "all", "--speed", "4",
         str(jpg_path), str(avif_path)],
        check=True, capture_output=True,
    )

    return basename, {
        "jpg": jpg_path.stat().st_size,
        "webp": webp_path.stat().st_size,
        "avif": avif_path.stat().st_size,
    }


# ------------------------------------------------------------------ markdown
def strip_notes_block(md: str) -> str:
    cleaned, _ = NOTES_BLOCK_RE.subn("\n", md)
    # Also drop any trailing "---" separator left behind right before the
    # Notes block — common pattern in the supplied articles.
    cleaned = re.sub(r"\n+---\s*\n*\Z", "\n", cleaned)
    return cleaned.rstrip() + "\n"


def convert_sources_to_footnotes(md: str) -> tuple[str, dict[str, int]]:
    """Normalise a trailing `## Sources` block into `[^N]:` footnote defs.

    build_blog.py renders `[^N]:` definitions into a styled
    `<aside class="blog-footnotes">` placed AFTER the article CTA, with its
    own "Sources" heading. So:
      - Strip the inline `## Sources` heading (otherwise it renders twice in
        the page, once as a body H2 and once in the styled aside).
      - If the block contains plain `N. text` items, rewrite them as
        `[^N]: text` so build_blog.py picks them up as footnotes.
      - Footnote-style defs already in the block are kept verbatim.

    Returns (rewritten_md, stats). Stats keys:
      - "items_converted": numbered list items rewritten as footnotes
      - "defs_kept": existing `[^N]:` defs preserved as-is
      - "heading_stripped": 1 if the `## Sources` heading was removed, else 0
    """
    stats = {"items_converted": 0, "defs_kept": 0, "heading_stripped": 0}
    match = SOURCES_BLOCK_RE.search(md)
    if not match:
        return md, stats

    block_lines = match.group(1).splitlines()
    converted: list[str] = []
    for raw_line in block_lines:
        stripped = raw_line.strip()
        if not stripped:
            converted.append("")
            continue
        if FOOTNOTE_DEF_LINE_RE.match(stripped):
            converted.append(stripped)
            stats["defs_kept"] += 1
            continue
        item = SOURCES_ITEM_RE.match(stripped)
        if item:
            converted.append(f"[^{item.group(1)}]: {item.group(2).strip()}")
            stats["items_converted"] += 1
            continue
        # Anything else inside the Sources block (e.g. an orphan disclaimer
        # paragraph that pre-dates the footnote refactor) is kept inline.
        converted.append(stripped)

    stats["heading_stripped"] = 1
    rewritten_block = "\n".join(line for line in converted if line is not None).strip()
    replacement = ("\n\n" + rewritten_block + "\n") if rewritten_block else "\n"
    return md[: match.start()] + replacement + md[match.end():], stats


def extract_slug(frontmatter_body: str) -> str:
    match = SLUG_RE.search(frontmatter_body)
    if not match:
        raise SystemExit("Frontmatter is missing a `slug:` field.")
    return match.group(1).strip().strip("'\"")


def inject_hero(md: str, hero_basename: str, hero_alt: str | None) -> str:
    fm_match = FRONTMATTER_RE.match(md)
    if not fm_match:
        raise SystemExit("Markdown is missing a `---` frontmatter block at the top.")
    fm_body = fm_match.group(2)

    additions: list[str] = []
    if not HAS_HERO_RE.search(fm_body):
        additions.append(f"hero_image: {hero_basename}")
    if hero_alt and not HAS_HERO_ALT_RE.search(fm_body):
        # Quote the alt text in case it contains a colon.
        safe = hero_alt.replace('"', '\\"')
        additions.append(f'hero_image_alt: "{safe}"')

    if not additions:
        return md

    new_fm = fm_body.rstrip() + "\n" + "\n".join(additions)
    return fm_match.group(1) + new_fm + fm_match.group(3) + md[fm_match.end():]


# ------------------------------------------------------------------ build
def run_build() -> None:
    subprocess.run([sys.executable, str(BUILD_BLOG)], check=True, cwd=ROOT)


# ------------------------------------------------------------------ main
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("stem", nargs="?", help="Filename or stem inside blog-scheduled/.")
    parser.add_argument("--alt", help="Hero image alt text. Falls back to article title.")
    parser.add_argument("--keep-source", action="store_true",
                        help="Don't delete blog-scheduled/ originals after success.")
    parser.add_argument("--list", action="store_true",
                        help="List stems available in blog-scheduled/ and exit.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run image conversion + frontmatter rewrite but skip writes to blog/ and build.")
    args = parser.parse_args()

    if args.list:
        for stem in list_scheduled():
            print(stem)
        return 0

    if not args.stem:
        parser.error("stem argument required (or use --list)")

    stem = resolve_stem(args.stem)
    md_src, img_src = find_pair(stem)
    print(f"Source MD:    {md_src.relative_to(ROOT)}")
    print(f"Source image: {img_src.relative_to(ROOT)}")

    basename, sizes = emit_image_set(img_src)
    print(f"Hero asset:   assets/images/{basename}.{{jpg,webp,avif}}")
    for ext, size in sizes.items():
        print(f"  .{ext:<4} {size:>9,} bytes")

    raw = md_src.read_text(encoding="utf-8")
    fm_match = FRONTMATTER_RE.match(raw)
    if not fm_match:
        raise SystemExit("Source markdown is missing frontmatter.")
    slug = extract_slug(fm_match.group(2))

    cleaned = strip_notes_block(raw)
    cleaned, src_stats = convert_sources_to_footnotes(cleaned)
    if src_stats["heading_stripped"]:
        bits: list[str] = []
        if src_stats["items_converted"]:
            bits.append(f'{src_stats["items_converted"]} numbered item(s) → footnote defs')
        if src_stats["defs_kept"]:
            bits.append(f'{src_stats["defs_kept"]} existing footnote def(s) kept')
        bits.append("inline `## Sources` heading stripped")
        print("Sources:      " + ", ".join(bits))
    cleaned = inject_hero(cleaned, basename, args.alt)

    dest_md = BLOG_DIR / f"{slug}.md"
    if args.dry_run:
        print(f"[dry-run] Would write {dest_md.relative_to(ROOT)} ({len(cleaned):,} bytes)")
        return 0

    BLOG_DIR.mkdir(parents=True, exist_ok=True)
    dest_md.write_text(cleaned, encoding="utf-8")
    print(f"Wrote:        {dest_md.relative_to(ROOT)} ({len(cleaned):,} bytes)")

    run_build()

    if not args.keep_source:
        md_src.unlink()
        img_src.unlink()
        print(f"Removed scheduled sources for {stem}")
    else:
        print(f"--keep-source: left {stem} in blog-scheduled/")

    print()
    print(f"Done. Article URL after deploy: https://finwellai.com.au/blog/{slug}/")
    print("Next step: netlify build && netlify deploy --prod --dir .")
    return 0


if __name__ == "__main__":
    sys.exit(main())
