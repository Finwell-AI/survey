#!/usr/bin/env python3
"""Render content/privacy.md and content/terms.md into branded HTML pages.

Minimal Markdown converter (no third-party deps). Handles only the subset our
two documents use: H1, H2, paragraphs, ordered/unordered lists, bold (**...**),
italic (*...*), inline code, links, horizontal rules, and the inline
[REVIEW: ...] tags which we render as styled inline notes for Alex.

Banner + footer + Cookiebot state live as inline constants in this module.
The home/survey/thanks pages are now hand-edited HTML — when their banner or
footer changes, also update the constants here so the legal pages stay in
sync. Four files to touch, no shared template module.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"

# ----------------------------------------------------------------- shared shell
# Cookiebot consent banner is currently disabled. Flip to True and supply a
# real CBID via Netlify env once the consent flow is wired. When False the
# Cookiebot <script> is omitted entirely and the "Cookie preferences" footer
# link is hidden.
COOKIEBOT_ENABLED = False

# Chat FAB is disabled per founder 2026-05-07. Empty string keeps the page
# template valid; flip to the FAB markup string to re-enable.
CHAT_FAB = ""

# Urgent banner — must match the markup in index.html / survey.html /
# thanks.html. When changing the copy, links, or styling, update all four
# files together.
URGENT_BANNER = '''<div class="urgent-banner" id="urgentBanner">
<div class="urgent-banner-inner">
<span class="pulse-dot"></span>
<span><strong>Tax time is just around the corner.</strong> Be a founding member, join the waitlist, get 6 months free Premium.</span>
<a class="banner-cta" href="/survey" data-event="cta_click" data-cta-label="urgent_banner">Claim my spot</a>
</div>
<button class="dismiss" onclick="window.fwDismissBanner()" aria-label="Dismiss banner">
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
</button>
</div>'''

# Shared footer — must match the markup in index.html / survey.html /
# thanks.html. The Cookie preferences link is added only when Cookiebot is
# enabled.
_COOKIE_PREF_LINK = (
    '<a href="#" onclick="if(window.Cookiebot)Cookiebot.renew();return false;" '
    'data-event="nav_click" data-cta-label="footer_cookie_prefs">Cookie preferences</a>'
    if COOKIEBOT_ENABLED else ""
)

SHARED_FOOTER = f'''
<footer class="site-footer">
<div class="footer-inner">
<div class="footer-brand">
<a class="logo" href="/" data-event="nav_click" data-cta-label="footer_logo">
<div class="logo-mark"><div class="brand-fmark-img" role="img" aria-label="Finwell AI"></div></div>
<div class="logo-text">
<div class="logo-name" style="color: white;">Finwell <span class="ai">AI</span></div>
<div class="logo-tag" style="color: rgba(219, 234, 254, 0.7);">Financial Wellness</div>
</div>
</a>
<p class="tagline">Financial Wellness. Smarter Future. Built in Melbourne for Australians dealing with the financial pressure of today.</p>
</div>
<div class="footer-links">
<a href="/#what">What it does</a>
<a href="/#how">How it works</a>
<a href="/#tax">Tax automation</a>
<a href="/#trust">Trust</a>
<a href="/survey" data-event="cta_click" data-cta-label="footer_survey">Take the survey</a>
<a href="/#faq">FAQ</a>
<a href="/blog" data-event="nav_click" data-cta-label="footer_insights">Insights</a>
<a href="/privacy">Privacy</a>
<a href="/terms">Terms</a>
{_COOKIE_PREF_LINK}
</div>
</div>
<div class="footer-bottom">
<span>&copy; 2026 Finwell AI Pty Ltd. ABN pending. Made in Melbourne.</span>
<span>ATO DSP accreditation in progress.</span>
</div>
</footer>
'''


# ---------------------------------------------------------------- markdown
INLINE_RULES = [
    # Bold + italic + code (order matters: code first to avoid backtick clashes)
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
    (re.compile(r"\*\*([^*]+)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)"), r"<em>\1</em>"),
    # Markdown links [text](url)
    (re.compile(r"\[([^\]]+)\]\((https?://[^)]+|mailto:[^)]+|/[^)]*)\)"),
     r'<a href="\2">\1</a>'),
    # [REVIEW: ...] → styled inline note
    (re.compile(r"\[REVIEW:\s*([^\]]+)\]"),
     r'<span class="legal-review-note" title="Needs Alex / lawyer review">[REVIEW: \1]</span>'),
]


def render_inline(text: str) -> str:
    for pat, repl in INLINE_RULES:
        text = pat.sub(repl, text)
    return text


def md_to_html(md: str) -> str:
    out: list[str] = []
    in_ul = False
    in_p_buf: list[str] = []

    def flush_paragraph():
        if in_p_buf:
            out.append("<p>" + render_inline(" ".join(in_p_buf)) + "</p>")
            in_p_buf.clear()

    def close_list():
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    for raw_line in md.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            flush_paragraph()
            close_list()
            continue
        if line.startswith("# "):
            flush_paragraph(); close_list()
            out.append("<h1>" + render_inline(html.escape(line[2:].strip(), quote=False).replace("&lt;", "<").replace("&gt;", ">")) + "</h1>")
            continue
        if line.startswith("## "):
            flush_paragraph(); close_list()
            out.append("<h2>" + render_inline(line[3:].strip()) + "</h2>")
            continue
        if line.startswith("### "):
            flush_paragraph(); close_list()
            out.append("<h3>" + render_inline(line[4:].strip()) + "</h3>")
            continue
        if line.strip() == "---":
            flush_paragraph(); close_list()
            out.append("<hr/>")
            continue
        if line.lstrip().startswith("- "):
            flush_paragraph()
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append("<li>" + render_inline(line.lstrip()[2:]) + "</li>")
            continue
        # default: accumulate into paragraph buffer (joined with spaces)
        if in_ul:
            close_list()
        in_p_buf.append(line.strip())

    flush_paragraph(); close_list()
    return "\n".join(out)


_COOKIEBOT_BLOCK_ENABLED = """\
<!-- Cookiebot: legal pages still need the consent banner so a user who
     lands here directly gets the same opt-in flow as the rest of the site. -->
<script id="Cookiebot" src="https://consent.cookiebot.com/uc.js"
        data-cbid="__COOKIEBOT_CBID__"
        data-blockingmode="auto" type="text/javascript"></script>"""

_COOKIEBOT_BLOCK_DISABLED = (
    "<!-- Cookiebot disabled — see build_pages.py COOKIEBOT_ENABLED flag. -->"
)


# ---------------------------------------------------------------- page shell
def _schema_jsonld(title: str, description: str, canonical: str, last_modified: str) -> str:
    """Return a JSON-LD <script> block with WebPage + Organization + WebSite.

    Pre-launch: legalName uses "ABN pending" rather than a fake ACN/ABN. Once
    Finwell AI is registered, swap legalName to the registered entity name and
    add an `identifier` property with the ABN.
    """
    page_url = f"https://finwellai.com.au{canonical}"
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebPage",
                "@id": f"{page_url}#webpage",
                "url": page_url,
                "name": title,
                "description": description,
                "inLanguage": "en-AU",
                "datePublished": "2026-05-06",
                "dateModified": last_modified,
                "isPartOf": {"@id": "https://finwellai.com.au/#website"},
                "publisher": {"@id": "https://finwellai.com.au/#organization"},
            },
            {
                "@type": "WebSite",
                "@id": "https://finwellai.com.au/#website",
                "url": "https://finwellai.com.au",
                "name": "Finwell AI",
                "inLanguage": "en-AU",
                "publisher": {"@id": "https://finwellai.com.au/#organization"},
            },
            {
                "@type": "Organization",
                "@id": "https://finwellai.com.au/#organization",
                "name": "Finwell AI",
                "legalName": "Finwell AI (ABN pending)",
                "url": "https://finwellai.com.au",
                "logo": "https://finwellai.com.au/assets/images/img-f5ef1fbf38.png",
                "email": "info@finwellai.com.au",
                "areaServed": {"@type": "Country", "name": "Australia"},
                "foundingLocation": {
                    "@type": "Place",
                    "address": {
                        "@type": "PostalAddress",
                        "addressLocality": "Melbourne",
                        "addressRegion": "VIC",
                        "addressCountry": "AU",
                    },
                },
            },
        ],
    }
    return (
        '<script type="application/ld+json">\n'
        + json.dumps(graph, indent=2, ensure_ascii=False)
        + "\n</script>"
    )


def page(title: str, description: str, canonical: str, body: str, last_modified: str) -> str:
    cookiebot_block = _COOKIEBOT_BLOCK_ENABLED if COOKIEBOT_ENABLED else _COOKIEBOT_BLOCK_DISABLED
    schema_block = _schema_jsonld(title, description, canonical, last_modified)
    return f"""<!DOCTYPE html>
<html lang="en-AU">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>
<title>{title}</title>
<meta name="description" content="{description}"/>
<meta name="theme-color" content="#0B1F3B"/>
<link rel="canonical" href="https://finwellai.com.au{canonical}"/>
<link rel="icon" type="image/png" sizes="64x64" href="/assets/images/img-f5ef1fbf38.png"/>
<meta name="robots" content="index,follow"/>

<meta property="og:type" content="article"/>
<meta property="og:title" content="{title}"/>
<meta property="og:description" content="{description}"/>
<meta property="og:url" content="https://finwellai.com.au{canonical}"/>
<meta property="og:image" content="https://finwellai.com.au/assets/finwellai-og.jpeg"/>
<meta property="og:image:type" content="image/jpeg"/>

{schema_block}

<link rel="preload" as="font" type="font/woff2" href="/assets/fonts/inter-var.woff2" crossorigin/>
<link rel="stylesheet" href="/assets/css/styles.css"/>
{cookiebot_block}
<style>
  /* Legal-page typography overrides — keeps the brand without competing with it. */
  .legal-shell {{ background: #fff; color: #0F172A; padding: 80px 24px 80px; }}
  .legal-inner {{ max-width: 760px; margin: 0 auto; }}
  .legal-inner h1 {{ font-size: clamp(36px, 5vw, 56px); font-weight: 800; letter-spacing: -0.025em; line-height: 1.05; color: #0B1F3B; margin: 0 0 16px; }}
  .legal-inner h2 {{ font-size: clamp(22px, 2.4vw, 28px); font-weight: 800; letter-spacing: -0.015em; color: #0B1F3B; margin: 56px 0 16px; }}
  .legal-inner h3 {{ font-size: 18px; font-weight: 700; color: #0B1F3B; margin: 32px 0 12px; }}
  .legal-inner p {{ font-size: 16px; line-height: 1.6; color: #0F172A; margin: 0 0 16px; }}
  .legal-inner ul {{ font-size: 16px; line-height: 1.6; color: #0F172A; padding-left: 24px; margin: 0 0 16px; }}
  .legal-inner li {{ margin: 0 0 6px; }}
  .legal-inner a {{ color: #2F80ED; text-decoration: underline; }}
  .legal-inner hr {{ border: 0; border-top: 1px solid #E2E8F0; margin: 40px 0; }}
  .legal-inner code {{ background: #F1F5F9; padding: 2px 6px; border-radius: 6px; font-size: 0.9em; }}
  .legal-review-note {{ background: #FEF3C7; color: #78350F; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; }}
  .legal-meta {{ color: #64748B; font-size: 14px; margin: 0 0 32px; }}
  .legal-back {{ display: inline-flex; align-items: center; gap: 6px; color: #2F80ED; text-decoration: none; font-weight: 600; margin: 0 0 32px; }}
</style>
</head>
<body data-page="{canonical.strip('/')}">
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

<main class="legal-shell">
  <div class="legal-inner">
    <a href="/" class="legal-back">← Back to home</a>
    {body}
  </div>
</main>

{SHARED_FOOTER}

{CHAT_FAB}

<script src="/assets/js/app.js" defer></script>
</body>
</html>
"""


def main() -> None:
    privacy_md = (CONTENT / "privacy.md").read_text(encoding="utf-8")
    terms_md = (CONTENT / "terms.md").read_text(encoding="utf-8")

    # No field-name substitution — privacy.md must describe the survey in
    # plain English that matches the actual form, without mentioning the
    # internal field identifiers. The previous substitution corrupted the
    # surrounding prose and was the cause of audit findings F-06 and F-07.
    privacy_html = md_to_html(privacy_md)
    terms_html = md_to_html(terms_md)

    last_modified = "2026-05-07"

    (ROOT / "privacy.html").write_text(
        page(
            title="Privacy Policy — Finwell AI",
            description="How Finwell AI collects, stores, and uses your personal information under the Australian Privacy Act 1988 and Privacy Principles.",
            canonical="/privacy",
            body=privacy_html,
            last_modified=last_modified,
        ),
        encoding="utf-8",
    )
    (ROOT / "terms.html").write_text(
        page(
            title="Terms of Use — Finwell AI",
            description="Terms of use for finwellai.com.au — Finwell AI's pre-launch waitlist for AI-powered bookkeeping in Australia. Governed by NSW law.",
            canonical="/terms",
            body=terms_html,
            last_modified=last_modified,
        ),
        encoding="utf-8",
    )

    for n in ("privacy.html", "terms.html"):
        p = ROOT / n
        print(f"  {n:14s}  {p.stat().st_size:>9,} bytes")


if __name__ == "__main__":
    main()
