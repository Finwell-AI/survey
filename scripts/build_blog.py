#!/usr/bin/env python3
"""Render blog/*.md into the listings page and per-article pages.

Output:
  blog/index.html              -> listings (one card per published article)
  blog/{slug}/index.html       -> article page

Reads YAML-ish frontmatter for title/description/dates/category/tags + the
optional `hero_image` (basename of an existing asset under assets/images/).
Markdown subset is the same one build_legal_pages.py handles, plus:
  - blockquotes `> ...`
  - footnotes `[^N]` references and `[^N]: ...` definitions
  - inline HTML comment blocks containing `<script type="application/ld+json">`
    (extracted and emitted into <head>, un-commented)

The page shell, urgent banner, and shared footer come from build_legal_pages.
That module is the single source of truth for shared HTML so the blog cannot
drift away from the rest of the site.
"""
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from build_legal_pages import (
    CHAT_FAB,
    SHARED_FOOTER,
    URGENT_BANNER,
    _COOKIEBOT_BLOCK_DISABLED,
    _COOKIEBOT_BLOCK_ENABLED,
    COOKIEBOT_ENABLED,
)

ROOT = Path(__file__).resolve().parent.parent
BLOG_DIR = ROOT / "blog"
DEFAULT_HERO = "img-289e15f2a1"  # 1200x778 — guy with phone, fits financial/digital theme
SITE_URL = "https://finwellai.com.au"


# ---------------------------------------------------------------- frontmatter
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_LIST_INLINE_RE = re.compile(r"^\[(.*)\]\s*$")
_KV_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")


def _strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def _parse_list(value: str) -> list[str]:
    inner = value.strip()[1:-1]
    if not inner.strip():
        return []
    return [_strip_quotes(item.strip()) for item in inner.split(",")]


def parse_frontmatter(text: str) -> tuple[dict[str, object], str]:
    """Parse the leading `---` YAML-ish frontmatter block.

    Returns (data, body). Nested keys (objects/arrays on later indented lines)
    are skipped — we only need flat scalars and inline lists for blog metadata.
    """
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    block = match.group(1)
    body = text[match.end():]
    data: dict[str, object] = {}
    for raw_line in block.splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith(" ") or line.startswith("\t") or line.lstrip().startswith("-"):
            # nested values (e.g. internal_links list entries) — not needed
            continue
        kv = _KV_RE.match(line)
        if not kv:
            continue
        key, value = kv.group(1), kv.group(2).strip()
        if not value:
            continue
        if _LIST_INLINE_RE.match(value):
            data[key] = _parse_list(value)
        else:
            data[key] = _strip_quotes(value)
    return data, body


# ---------------------------------------------------------------- markdown
INLINE_RULES = [
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
    (re.compile(r"\*\*([^*]+)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)"), r"<em>\1</em>"),
    (
        re.compile(r"\[([^\]]+)\]\((https?://[^)]+|mailto:[^)]+|/[^)]*|#[^)]*)\)"),
        r'<a href="\2">\1</a>',
    ),
]

_FOOTNOTE_REF_RE = re.compile(r"\[\^([0-9A-Za-z_-]+)\]")
_FOOTNOTE_DEF_RE = re.compile(r"^\[\^([0-9A-Za-z_-]+)\]:\s*(.*)$")
_HTML_COMMENT_RE = re.compile(r"<!--(.*?)-->", re.DOTALL)
_JSONLD_INSIDE_COMMENT_RE = re.compile(
    r"<script type=\"application/ld\+json\">\s*(\{.*?\})\s*</script>",
    re.DOTALL,
)


@dataclass
class RenderedArticle:
    body_html: str
    footnotes: list[tuple[str, str]] = field(default_factory=list)
    extra_schema: list[dict] = field(default_factory=list)


def _render_inline(text: str) -> str:
    # Footnote references first so their brackets don't collide with link parser.
    text = _FOOTNOTE_REF_RE.sub(
        lambda m: (
            f'<sup class="fn-ref"><a href="#fn-{m.group(1)}" '
            f'id="fnref-{m.group(1)}">[{m.group(1)}]</a></sup>'
        ),
        text,
    )
    for pat, repl in INLINE_RULES:
        text = pat.sub(repl, text)
    return text


def md_to_html(md: str) -> RenderedArticle:
    # First sweep: pull out HTML comment blocks. Capture any JSON-LD scripts so
    # the article schema can be emitted into <head> rather than the body.
    extra_schema: list[dict] = []

    def _strip_comment(match: re.Match[str]) -> str:
        inner = match.group(1)
        for script in _JSONLD_INSIDE_COMMENT_RE.findall(inner):
            try:
                extra_schema.append(json.loads(script))
            except json.JSONDecodeError:
                # Malformed schema — drop silently rather than break the build.
                pass
        return ""

    md = _HTML_COMMENT_RE.sub(_strip_comment, md)

    # Second sweep: extract footnote definitions so they render as a sources
    # block at the bottom, not as inline lines.
    footnotes: list[tuple[str, str]] = []
    body_lines: list[str] = []
    for raw_line in md.splitlines():
        fn_match = _FOOTNOTE_DEF_RE.match(raw_line.strip())
        if fn_match:
            footnotes.append((fn_match.group(1), fn_match.group(2).strip()))
        else:
            body_lines.append(raw_line)

    out: list[str] = []
    in_ul = False
    in_blockquote = False
    in_p_buf: list[str] = []

    def flush_paragraph() -> None:
        if in_p_buf:
            out.append("<p>" + _render_inline(" ".join(in_p_buf)) + "</p>")
            in_p_buf.clear()

    def close_list() -> None:
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    def close_blockquote() -> None:
        nonlocal in_blockquote
        if in_blockquote:
            out.append("</blockquote>")
            in_blockquote = False

    for raw_line in body_lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            flush_paragraph()
            close_list()
            close_blockquote()
            continue
        if line.startswith("# "):
            flush_paragraph(); close_list(); close_blockquote()
            out.append(f"<h1>{_render_inline(stripped[2:].strip())}</h1>")
            continue
        if line.startswith("## "):
            flush_paragraph(); close_list(); close_blockquote()
            out.append(f"<h2>{_render_inline(stripped[3:].strip())}</h2>")
            continue
        if line.startswith("### "):
            flush_paragraph(); close_list(); close_blockquote()
            out.append(f"<h3>{_render_inline(stripped[4:].strip())}</h3>")
            continue
        if stripped == "---":
            flush_paragraph(); close_list(); close_blockquote()
            out.append("<hr/>")
            continue
        if line.startswith(">"):
            flush_paragraph()
            if not in_blockquote:
                close_list()
                out.append('<blockquote class="callout">')
                in_blockquote = True
            # Strip the leading `> ` (or `>` for blank quote lines)
            quoted = line[1:].lstrip()
            if not quoted:
                # Blank quote line — close any open list, paragraph break.
                close_list()
                continue
            if quoted.startswith("- "):
                if not in_ul:
                    out.append("<ul>")
                    in_ul = True
                out.append("<li>" + _render_inline(quoted[2:]) + "</li>")
            else:
                close_list()
                out.append("<p>" + _render_inline(quoted) + "</p>")
            continue
        if stripped.startswith("- "):
            flush_paragraph(); close_blockquote()
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append("<li>" + _render_inline(stripped[2:]) + "</li>")
            continue
        # default paragraph buffer
        close_list(); close_blockquote()
        in_p_buf.append(stripped)

    flush_paragraph(); close_list(); close_blockquote()
    return RenderedArticle(
        body_html="\n".join(out),
        footnotes=footnotes,
        extra_schema=extra_schema,
    )


# ---------------------------------------------------------------- page shell
def _picture(basename: str, alt: str, *, width: int, height: int, eager: bool) -> str:
    loading = "eager" if eager else "lazy"
    fetch = ' fetchpriority="high"' if eager else ""
    return (
        "<picture>"
        f'<source type="image/avif" srcset="/assets/images/{basename}.avif"/>'
        f'<source type="image/webp" srcset="/assets/images/{basename}.webp"/>'
        f'<img src="/assets/images/{basename}.jpg" width="{width}" height="{height}" '
        f'loading="{loading}" decoding="async"{fetch} class="blog-hero-image" alt="{html.escape(alt, quote=True)}"/>'
        "</picture>"
    )


_BLOG_STYLES = """
<style>
  .blog-shell { background: #fff; color: #0F172A; padding: 64px 24px 96px; }
  .blog-inner { max-width: 760px; margin: 0 auto; }
  .blog-back { display: inline-flex; align-items: center; gap: 6px; color: #2F80ED; text-decoration: none; font-weight: 600; margin: 0 0 24px; }
  .blog-meta { color: #64748B; font-size: 14px; margin: 0 0 8px; display: flex; gap: 12px; flex-wrap: wrap; }
  .blog-meta .dot { color: #CBD5E1; }
  .blog-hero { margin: 16px 0 40px; border-radius: 16px; overflow: hidden; box-shadow: 0 20px 60px -30px rgba(11, 31, 59, 0.25); aspect-ratio: 16 / 9; background: #EFF6FF; }
  .blog-hero img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .blog-inner h1 { font-size: clamp(34px, 5vw, 52px); font-weight: 800; letter-spacing: -0.025em; line-height: 1.08; color: #0B1F3B; margin: 0 0 16px; }
  .blog-inner h2 { font-size: clamp(22px, 2.4vw, 28px); font-weight: 800; letter-spacing: -0.015em; color: #0B1F3B; margin: 48px 0 14px; }
  .blog-inner h3 { font-size: 18px; font-weight: 700; color: #0B1F3B; margin: 28px 0 10px; }
  .blog-inner p { font-size: 17px; line-height: 1.7; color: #1F2937; margin: 0 0 18px; }
  .blog-inner ul { font-size: 17px; line-height: 1.7; color: #1F2937; padding-left: 24px; margin: 0 0 18px; }
  .blog-inner li { margin: 0 0 6px; }
  .blog-inner a { color: #2F80ED; text-decoration: underline; }
  .blog-inner hr { border: 0; border-top: 1px solid #E2E8F0; margin: 40px 0; }
  .blog-inner code { background: #F1F5F9; padding: 2px 6px; border-radius: 6px; font-size: 0.9em; }
  .blog-inner blockquote.callout { background: #F0F9FF; border-left: 4px solid #2F80ED; padding: 20px 24px; margin: 28px 0; border-radius: 0 12px 12px 0; }
  .blog-inner blockquote.callout p { margin: 0 0 12px; }
  .blog-inner blockquote.callout p:last-child { margin-bottom: 0; }
  .fn-ref a { text-decoration: none; color: #2F80ED; font-weight: 600; }
  .blog-footnotes { margin-top: 64px; padding-top: 28px; border-top: 1px solid #E2E8F0; }
  .blog-footnotes h2 { font-size: 20px; margin: 0 0 16px; }
  .blog-footnotes ol { padding-left: 24px; color: #475569; font-size: 14px; line-height: 1.6; }
  .blog-footnotes li { margin: 0 0 8px; word-break: break-word; }
  .blog-footnotes a { color: #2F80ED; }
  .blog-cta { background: linear-gradient(135deg, #0B1F3B, #1E3A8A); color: #fff; padding: 32px; border-radius: 16px; margin: 48px 0 0; }
  .blog-cta h3 { color: #fff; margin: 0 0 8px; }
  .blog-cta p { color: rgba(219, 234, 254, 0.85); margin: 0 0 16px; }
  .blog-cta a.btn { display: inline-flex; align-items: center; padding: 12px 22px; background: #fff; color: #0B1F3B; border-radius: 999px; font-weight: 700; text-decoration: none; }

  /* Listings */
  .blog-list-shell { background: #fff; color: #0F172A; padding: 80px 24px 96px; }
  .blog-list-inner { max-width: 1100px; margin: 0 auto; }
  .blog-list-header { text-align: center; margin: 0 0 48px; }
  .blog-list-header h1 { font-size: clamp(38px, 5vw, 56px); font-weight: 800; letter-spacing: -0.025em; line-height: 1.05; color: #0B1F3B; margin: 0 0 12px; }
  .blog-list-header p { font-size: 18px; color: #475569; max-width: 640px; margin: 0 auto; }
  .blog-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 28px; }
  .blog-card { display: flex; flex-direction: column; background: #fff; border: 1px solid #E2E8F0; border-radius: 16px; overflow: hidden; text-decoration: none; color: inherit; transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease; }
  .blog-card:hover { transform: translateY(-2px); box-shadow: 0 20px 50px -30px rgba(11, 31, 59, 0.25); border-color: #CBD5E1; }
  .blog-card .blog-card-thumb { aspect-ratio: 16 / 10; background: #EFF6FF; overflow: hidden; }
  .blog-card .blog-card-thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
  .blog-card-body { padding: 24px; display: flex; flex-direction: column; gap: 8px; flex: 1; }
  .blog-card-category { color: #2F80ED; text-transform: uppercase; font-size: 12px; letter-spacing: 0.06em; font-weight: 700; }
  .blog-card-title { font-size: 20px; font-weight: 700; line-height: 1.3; color: #0B1F3B; margin: 0; }
  .blog-card-desc { font-size: 15px; line-height: 1.55; color: #475569; margin: 0; flex: 1; }
  .blog-card-meta { font-size: 13px; color: #94A3B8; margin-top: 4px; }
  .blog-empty { text-align: center; color: #64748B; padding: 64px 0; font-size: 16px; }
</style>
"""


def _schema_jsonld_for(
    title: str,
    description: str,
    canonical: str,
    *,
    page_type: str = "WebPage",
    published: str | None = None,
    modified: str | None = None,
    hero_url: str | None = None,
) -> str:
    page_url = f"{SITE_URL}{canonical}"
    page_node: dict[str, object] = {
        "@type": page_type,
        "@id": f"{page_url}#webpage",
        "url": page_url,
        "name": title,
        "description": description,
        "inLanguage": "en-AU",
        "isPartOf": {"@id": f"{SITE_URL}/#website"},
        "publisher": {"@id": f"{SITE_URL}/#organization"},
    }
    if published:
        page_node["datePublished"] = published
    if modified:
        page_node["dateModified"] = modified
    if hero_url:
        page_node["primaryImageOfPage"] = hero_url
    graph: dict[str, object] = {
        "@context": "https://schema.org",
        "@graph": [
            page_node,
            {
                "@type": "WebSite",
                "@id": f"{SITE_URL}/#website",
                "url": SITE_URL,
                "name": "Finwell AI",
                "inLanguage": "en-AU",
                "publisher": {"@id": f"{SITE_URL}/#organization"},
            },
            {
                "@type": "Organization",
                "@id": f"{SITE_URL}/#organization",
                "name": "Finwell AI",
                "legalName": "Finwell AI",
                "url": SITE_URL,
                "logo": f"{SITE_URL}/assets/images/img-f5ef1fbf38.png",
                "email": "info@finwellai.com.au",
            },
        ],
    }
    return (
        '<script type="application/ld+json">\n'
        + json.dumps(graph, indent=2, ensure_ascii=False)
        + "\n</script>"
    )


def _extra_schema_block(extra_schema: list[dict]) -> str:
    if not extra_schema:
        return ""
    chunks: list[str] = []
    for node in extra_schema:
        chunks.append(
            '<script type="application/ld+json">\n'
            + json.dumps(node, indent=2, ensure_ascii=False)
            + "\n</script>"
        )
    return "\n".join(chunks)


def page_shell(
    *,
    title: str,
    description: str,
    canonical: str,
    body: str,
    extra_head: str = "",
    body_class: str = "blog-page",
    og_title: str | None = None,
    og_description: str | None = None,
) -> str:
    cookiebot_block = _COOKIEBOT_BLOCK_ENABLED if COOKIEBOT_ENABLED else _COOKIEBOT_BLOCK_DISABLED
    social_title = og_title or title
    social_description = og_description or description
    return f"""<!DOCTYPE html>
<html lang="en-AU">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>
<title>{html.escape(title, quote=False)}</title>
<meta name="description" content="{html.escape(description, quote=True)}"/>
<meta name="theme-color" content="#0B1F3B"/>
<link rel="canonical" href="{SITE_URL}{canonical}"/>
<link rel="icon" type="image/png" sizes="64x64" href="/assets/images/img-f5ef1fbf38.png"/>
<meta name="robots" content="index,follow"/>

<meta property="og:type" content="article"/>
<meta property="og:title" content="{html.escape(social_title, quote=True)}"/>
<meta property="og:description" content="{html.escape(social_description, quote=True)}"/>
<meta property="og:url" content="{SITE_URL}{canonical}"/>
<meta property="og:image" content="{SITE_URL}/assets/finwellai-og.jpeg"/>
<meta property="og:image:type" content="image/jpeg"/>
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="{html.escape(social_title, quote=True)}"/>
<meta name="twitter:description" content="{html.escape(social_description, quote=True)}"/>
<meta name="twitter:image" content="{SITE_URL}/assets/finwellai-og.jpeg"/>

{extra_head}

<link rel="preload" as="font" type="font/woff2" href="/assets/fonts/inter-var.woff2" crossorigin/>
<link rel="stylesheet" href="/assets/css/styles.css"/>
{cookiebot_block}
{_BLOG_STYLES}
</head>
<body data-page="{body_class}">
{URGENT_BANNER}

<header class="site-header dark" id="siteHeader">
<div class="header-inner">
<a class="logo" href="/" data-event="nav_click" data-cta-label="logo">
<div class="logo-mark"><div class="brand-fmark-img" role="img" aria-label="Finwell AI"></div></div>
<div class="logo-text">
<div class="logo-name">Finwell <span class="ai">AI</span></div>
<div class="logo-tag">Financial Wellness</div>
</div>
</a>
</div>
</header>

{body}

{SHARED_FOOTER}

{CHAT_FAB}

<script src="/assets/js/app.js" defer></script>
</body>
</html>
"""


# ---------------------------------------------------------------- article load
@dataclass
class ArticleMeta:
    slug: str
    title: str
    description: str
    og_title: str
    og_description: str
    published: str
    updated: str
    category: str
    hero_image: str
    hero_image_alt: str
    md_path: Path
    md_body: str


def _str_field(data: dict[str, object], key: str, default: str = "") -> str:
    value = data.get(key)
    if isinstance(value, str):
        return value
    return default


def _bool_field(data: dict[str, object], key: str, default: bool = False) -> bool:
    value = _str_field(data, key)
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y"}


def load_articles() -> list[ArticleMeta]:
    if not BLOG_DIR.is_dir():
        return []
    articles: list[ArticleMeta] = []
    for md_file in sorted(BLOG_DIR.glob("*.md")):
        raw = md_file.read_text(encoding="utf-8")
        data, body = parse_frontmatter(raw)
        if _bool_field(data, "draft"):
            continue
        slug = _str_field(data, "slug") or md_file.stem
        title = _str_field(data, "title") or slug
        description = _str_field(data, "description")
        og_title = _str_field(data, "og_title") or title
        og_description = _str_field(data, "og_description") or description
        published = _str_field(data, "published") or date.today().isoformat()
        updated = _str_field(data, "updated") or published
        category = _str_field(data, "category") or "insights"
        hero_image = _str_field(data, "hero_image") or DEFAULT_HERO
        hero_image_alt = _str_field(data, "hero_image_alt") or title
        articles.append(
            ArticleMeta(
                slug=slug,
                title=title,
                description=description,
                og_title=og_title,
                og_description=og_description,
                published=published,
                updated=updated,
                category=category,
                hero_image=hero_image,
                hero_image_alt=hero_image_alt,
                md_path=md_file,
                md_body=body,
            )
        )
    articles.sort(key=lambda a: a.published, reverse=True)
    return articles


# ---------------------------------------------------------------- listings
def _format_date(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    return d.strftime("%-d %B %Y") if hasattr(date, "strftime") else iso


def render_listings(articles: list[ArticleMeta]) -> str:
    if not articles:
        cards_html = '<div class="blog-empty">No articles published yet - check back soon.</div>'
    else:
        cards: list[str] = []
        for art in articles:
            thumb = _picture(
                art.hero_image,
                alt=art.title,
                width=1200,
                height=750,
                eager=False,
            )
            cards.append(
                f'<a class="blog-card" href="/blog/{art.slug}/" '
                f'data-event="nav_click" data-cta-label="blog_card_{art.slug}">'
                f'<div class="blog-card-thumb">{thumb}</div>'
                f'<div class="blog-card-body">'
                f'<div class="blog-card-category">{html.escape(art.category)}</div>'
                f'<h2 class="blog-card-title">{html.escape(art.title)}</h2>'
                f'<p class="blog-card-desc">{html.escape(art.description)}</p>'
                f'<div class="blog-card-meta">{_format_date(art.published)}</div>'
                f'</div>'
                f'</a>'
            )
        cards_html = '<div class="blog-grid">\n' + "\n".join(cards) + "\n</div>"

    body = f"""
<main class="blog-list-shell">
  <div class="blog-list-inner">
    <div class="blog-list-header">
      <h1>Insights</h1>
      <p>Plain-English tax, deduction, and finance guides for Australians. Researched against ATO sources, written for working people.</p>
    </div>
    {cards_html}
  </div>
</main>
"""
    schema = _schema_jsonld_for(
        title="Insights - Finwell AI",
        description="Plain-English tax, deduction, and finance guides for Australians.",
        canonical="/blog/",
        page_type="CollectionPage",
        modified=articles[0].updated if articles else None,
    )
    return page_shell(
        title="Insights - Finwell AI",
        description="Plain-English tax, deduction, and finance guides for Australians from Finwell AI.",
        canonical="/blog/",
        body=body,
        extra_head=schema,
        body_class="blog-listings",
    )


# ---------------------------------------------------------------- article page
def render_article(art: ArticleMeta) -> str:
    rendered = md_to_html(art.md_body)

    # The markdown's first H1 becomes the page hero title; suppress duplicate H1
    # in the rendered body so it doesn't print twice. Render hero separately.
    body_html = re.sub(r"^<h1>.*?</h1>\s*", "", rendered.body_html, count=1)
    clean_for_reading_time = re.sub(r"<!--.*?-->", "", art.md_body, flags=re.DOTALL)
    clean_for_reading_time = clean_for_reading_time.split("\n## Sources\n")[0]
    word_count = len(re.findall(r"\b[\w'$.-]+\b", clean_for_reading_time))
    reading_minutes = max(1, round(word_count / 220))

    hero = _picture(
        art.hero_image,
        alt=art.hero_image_alt,
        width=1200,
        height=675,
        eager=True,
    )

    footnotes_html = ""
    if rendered.footnotes:
        items = "\n".join(
            f'<li id="fn-{num}">{_render_inline(text)} '
            f'<a href="#fnref-{num}" aria-label="Back to text">&#8617;</a></li>'
            for num, text in rendered.footnotes
        )
        footnotes_html = (
            '<aside class="blog-footnotes" aria-label="Sources">'
            "<h2>Sources</h2>"
            f"<ol>{items}</ol>"
            "</aside>"
        )

    cta_html = """
<aside class="blog-cta">
  <h3>Founding 500 early access</h3>
  <p>Help shape Finwell AI before launch through one short survey.</p>
  <a class="btn" href="/survey.html" data-event="cta_click" data-cta-label="blog_article_bottom">Take the 2-minute survey. Founding 500 members get 6 months Premium free.</a>
</aside>
"""

    body = f"""
<main class="blog-shell">
  <div class="blog-inner">
    <a href="/blog/" class="blog-back">← All insights</a>
    <div class="blog-meta">
      <span>{html.escape(art.category)}</span>
      <span class="dot">•</span>
      <span>{_format_date(art.published)}{f' (updated {_format_date(art.updated)})' if art.updated != art.published else ''}</span>
      <span class="dot">•</span>
      <span>{reading_minutes} min read</span>
    </div>
    <h1>{html.escape(art.title)}</h1>
    <div class="blog-hero">{hero}</div>
    {body_html}
    {cta_html}
    {footnotes_html}
  </div>
</main>
"""

    canonical = f"/blog/{art.slug}/"
    hero_url = f"{SITE_URL}/assets/images/{art.hero_image}.jpg"
    schema_blocks = [
        _schema_jsonld_for(
            title=art.title,
            description=art.description,
            canonical=canonical,
            page_type="WebPage",
            published=art.published,
            modified=art.updated,
            hero_url=hero_url,
        ),
        _extra_schema_block(rendered.extra_schema),
    ]
    extra_head = "\n".join(filter(None, schema_blocks))

    return page_shell(
        title=art.title,
        description=art.description,
        canonical=canonical,
        body=body,
        extra_head=extra_head,
        body_class=f"blog-article-{art.slug}",
        og_title=art.og_title,
        og_description=art.og_description,
    )


# ---------------------------------------------------------------- sitemap
def render_blog_sitemap(articles: list[ArticleMeta]) -> str:
    """Emit a urlset for blog articles only.

    Referenced from the root `sitemap.xml` (a sitemapindex). Listings page
    `/blog/` lives in `sitemap-pages.xml`, not here, so search engines that
    fetch this file get a clean article-only view.
    """
    lines: list[str] = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for art in articles:
        loc = f"{SITE_URL}/blog/{art.slug}/"
        lines.append("  <url>")
        lines.append(f"    <loc>{loc}</loc>")
        lines.append(f"    <lastmod>{art.updated}</lastmod>")
        lines.append("    <changefreq>monthly</changefreq>")
        lines.append("    <priority>0.7</priority>")
        lines.append("  </url>")
    lines.append("</urlset>")
    lines.append("")  # trailing newline
    return "\n".join(lines)


# ---------------------------------------------------------------- main
def main() -> None:
    articles = load_articles()

    listings_path = BLOG_DIR / "index.html"
    listings_path.write_text(render_listings(articles), encoding="utf-8")
    print(f"  blog/index.html        {listings_path.stat().st_size:>9,} bytes "
          f"({len(articles)} article{'s' if len(articles) != 1 else ''})")

    for art in articles:
        article_dir = BLOG_DIR / art.slug
        article_dir.mkdir(exist_ok=True)
        out_path = article_dir / "index.html"
        out_path.write_text(render_article(art), encoding="utf-8")
        print(f"  blog/{art.slug}/index.html  {out_path.stat().st_size:>9,} bytes")

    sitemap_path = ROOT / "sitemap-blog.xml"
    sitemap_path.write_text(render_blog_sitemap(articles), encoding="utf-8")
    print(f"  sitemap-blog.xml       {sitemap_path.stat().st_size:>9,} bytes")


if __name__ == "__main__":
    main()
