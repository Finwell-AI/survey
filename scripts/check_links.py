#!/usr/bin/env python3
"""Fail the build if any HTML references a missing local static asset.

Runs as the LAST Netlify build step, after optimize_assets.sh has minified,
content-hashed, and rewritten asset paths. By validating the final on-disk
state it catches the class of regression where a stylesheet/script/image URL
points at a file that does not exist (e.g. blog pages referencing the
un-hashed `/assets/css/styles.css` after the rewrite step was skipped).

Scope is deliberately narrow: only references that map 1:1 to a file on disk
are checked — anything carrying a static file extension (.css, .js, fonts,
images). Pretty page URLs like `/survey` or `/blog/` are intentionally NOT
checked here because Netlify resolves those via redirects, not the filesystem,
so a filesystem check would produce false positives.

Exit code 0 = all asset references resolve. Exit code 1 = at least one missing.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Directories whose HTML we never deploy / never want to validate.
EXCLUDE_DIRS = {"node_modules", "docs", "tests", ".netlify", ".git", "test-results"}

# Only URLs ending in one of these extensions map directly to a file on disk.
ASSET_EXTENSIONS = {
    ".css", ".js", ".mjs",
    ".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".otf",
    ".json", ".xml", ".txt", ".webmanifest",
}

# href="...", src="...", and srcset="... 1x, ... 2x" attributes.
_ATTR_RE = re.compile(r'(?:href|src)\s*=\s*"([^"]+)"', re.IGNORECASE)
_SRCSET_RE = re.compile(r'srcset\s*=\s*"([^"]+)"', re.IGNORECASE)


def _iter_html_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*.html"):
        if any(part in EXCLUDE_DIRS for part in path.relative_to(ROOT).parts):
            continue
        files.append(path)
    return sorted(files)


def _candidate_urls(html: str) -> set[str]:
    urls: set[str] = set(_ATTR_RE.findall(html))
    for srcset in _SRCSET_RE.findall(html):
        # "url1 1x, url2 2x" or "url1 320w, url2 640w" -> take the URL token.
        for candidate in srcset.split(","):
            token = candidate.strip().split()
            if token:
                urls.add(token[0])
    return urls


def _is_asset(url: str) -> bool:
    if url.startswith(("http://", "https://", "//", "mailto:", "tel:", "data:", "#")):
        return False
    clean = url.split("?", 1)[0].split("#", 1)[0]
    return Path(clean).suffix.lower() in ASSET_EXTENSIONS


def _resolve(url: str, html_file: Path) -> Path:
    clean = url.split("?", 1)[0].split("#", 1)[0]
    if clean.startswith("/"):
        return ROOT / clean.lstrip("/")
    return (html_file.parent / clean).resolve()


def main() -> int:
    missing: list[tuple[Path, str]] = []
    checked = 0
    html_files = _iter_html_files()

    for html_file in html_files:
        html = html_file.read_text(encoding="utf-8")
        for url in _candidate_urls(html):
            if not _is_asset(url):
                continue
            checked += 1
            if not _resolve(url, html_file).is_file():
                missing.append((html_file.relative_to(ROOT), url))

    if missing:
        print(f"check_links: FAIL — {len(missing)} broken asset reference(s):", file=sys.stderr)
        for rel_path, url in sorted(missing):
            print(f"  {rel_path}  ->  {url}", file=sys.stderr)
        print(
            "\nAsset URLs must point at a file that exists on disk after the build. "
            "If this is a hashed asset, optimize_assets.sh did not rewrite the "
            "reference — check that the un-hashed source (e.g. assets/css/styles.css) "
            "exists at build time so the rewrite step runs.",
            file=sys.stderr,
        )
        return 1

    print(f"check_links: OK — {checked} asset reference(s) across {len(html_files)} HTML file(s) all resolve.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
