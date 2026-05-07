#!/usr/bin/env python3
"""Build production multi-page site from the single-file prototype.

Reads:  docs/finwellai_prototype_v5 (1).html
Writes: index.html, survey.html, thanks.html

For each output:
  * Shared <head> with per-page meta/OG/canonical, JSON-LD, GA4 placeholder,
    Cookiebot placeholder, preload, self-hosted Inter via styles.css.
  * Externalised CSS link.
  * Externalised JS link (deferred).
  * No inline base64 — all images point to /assets/images/img-*.{webp,png,jpg}.
  * Internal navigation rewritten from window.fwGoto() onclick to real hrefs.
  * Survey wrapped in a real Netlify <form> with honeypot + reCAPTCHA hidden.
  * Math captcha block removed; reCAPTCHA v3 token field added.
  * Welcome modal only on index.html.
  * Chat FAB on every page.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "finwellai_prototype_v5 (1).html"

DATA_URI_RE = re.compile(
    r"data:image/(?P<mime>png|jpeg|jpg|webp);base64,(?P<b64>[A-Za-z0-9+/=]+)"
)

# Build-time toggle for the Cookiebot consent banner.
# Set to True once a real `COOKIEBOT_CBID` is wired in Netlify env vars.
# When False, the consent banner does not load, GA4 + reCAPTCHA fire without
# explicit user opt-in, and the "Cookie preferences" footer link is hidden.
# This is acceptable for AU-only traffic under the Privacy Act 1988 (which
# requires disclosure, not opt-in, for non-sensitive cookies). Before any
# EU / UK / California traffic, flip this back to True and set the CBID.
COOKIEBOT_ENABLED = False

# -------------------------------------------------------------------- helpers
def replace_data_uris(html: str) -> str:
    """Swap inline base64 image data URIs for /assets/images/ paths (.webp)."""
    def repl(m: re.Match) -> str:
        digest = hashlib.sha1(m.group("b64").encode()).hexdigest()[:10]
        return f"/assets/images/img-{digest}.webp"
    return DATA_URI_RE.sub(repl, html)


# Set of digests where AVIF is *smaller* than WebP — the build script's
# AVIF generator drops AVIFs that don't beat WebP, so this reflects what
# is actually on disk. Anything in here gets a <source type="image/avif">
# in front of the WebP fallback.
AVIF_DIGESTS = {
    "289e15f2a1",
    "2980485374",
    "2cdc2770ac",
    "45547e3aac",
    "6f54687d6c",
    "f5ef1fbf38",
}

# Image classes that are above the fold on every page they appear on. They
# should NOT be lazy-loaded, and the LCP candidate among them gets
# fetchpriority="high".
ABOVE_FOLD_CLASSES = {"hero-phone-image"}
LCP_CLASSES = {"hero-phone-image"}

CONTENT_IMG_RE = re.compile(
    r'<img\b'
    r'(?P<pre>[^>]*?)'
    r'\bsrc="(?P<src>/assets/images/img-(?P<digest>[0-9a-f]+)\.webp)"'
    r'(?P<post>[^>]*?)'
    r'\s*/?>',
    re.DOTALL,
)


def _attr(attrs: str, name: str) -> str | None:
    m = re.search(rf'\b{name}="([^"]*)"', attrs)
    return m.group(1) if m else None


def wrap_imgs_in_picture(html: str) -> str:
    """Replace bare <img src="/assets/images/img-XXX.webp" ...> tags with a
    <picture> that prefers AVIF when available, plus loading="lazy" on
    below-fold images and fetchpriority="high" on the LCP image."""
    def repl(m: re.Match) -> str:
        digest = m.group("digest")
        src = m.group("src")
        attrs = (m.group("pre") or "") + (m.group("post") or "")
        attrs = re.sub(r"\s+", " ", attrs).strip()
        cls = _attr(attrs, "class") or ""
        cls_set = set(cls.split())
        is_above = bool(cls_set & ABOVE_FOLD_CLASSES)
        is_lcp = bool(cls_set & LCP_CLASSES)

        # Compose the <img>, normalising the loading + decoding attrs.
        # If the original already had `loading=`, respect it; else default.
        loading = _attr(attrs, "loading") or ("eager" if is_above else "lazy")
        decoding = _attr(attrs, "decoding") or "async"
        # Strip any existing loading/decoding attrs to avoid duplicates.
        attrs_clean = re.sub(r'\s*\bloading="[^"]*"', "", attrs)
        attrs_clean = re.sub(r'\s*\bdecoding="[^"]*"', "", attrs_clean)
        attrs_clean = re.sub(r'\s*\bsrc="[^"]*"', "", attrs_clean).strip()
        fetch_attr = ' fetchpriority="high"' if is_lcp else ""
        img_tag = (
            f'<img src="{src}" loading="{loading}" decoding="{decoding}"'
            f'{fetch_attr} {attrs_clean}/>'
        )

        if digest not in AVIF_DIGESTS:
            return img_tag
        avif_src = src.replace(".webp", ".avif")
        return (
            "<picture>"
            f'<source type="image/avif" srcset="{avif_src}"/>'
            f'<source type="image/webp" srcset="{src}"/>'
            f"{img_tag}"
            "</picture>"
        )

    return CONTENT_IMG_RE.sub(repl, html)


def strip_inline_styles_scripts(html: str) -> str:
    """Remove inline <style>...</style> and inline <script>...</script>."""
    html = re.sub(r"<style>.*?</style>", "", html, flags=re.DOTALL)
    html = re.sub(r"<script>.*?</script>", "", html, flags=re.DOTALL)
    return html


def slice_by_marker(src: str, start_pat: str, end_pat: str) -> str:
    """Return content between (and including) markers. Greedy-safe via DOTALL."""
    m = re.search(start_pat + r".*?" + end_pat, src, re.DOTALL)
    if not m:
        raise SystemExit(f"slice not found: {start_pat!r} → {end_pat!r}")
    return m.group(0)


def rewrite_nav(html: str) -> str:
    """Convert prototype's JS routing onclicks into real hrefs."""

    # 1. Banner CTA — converted button → anchor (must rewrite matching </button>)
    html = re.sub(
        r'<button\s+class="banner-cta"\s+onclick="window\.fwGoto\(\'survey\'\)">([\s\S]*?)</button>',
        r'<a class="banner-cta" href="/survey" data-event="cta_click" data-cta-label="urgent_banner">\1</a>',
        html,
    )

    # 2. Logo anchor — already an <a>, just swap onclick → href
    html = html.replace(
        '<a class="logo" onclick="window.fwGoto(\'home\'); return false;">',
        '<a class="logo" href="/" data-event="nav_click" data-cta-label="logo">',
    )

    # 3. Survey header back-to-home button → anchor (rewrite closing </button>)
    html = re.sub(
        r'<button\s+class="btn-back"\s+onclick="window\.fwGoto\(\'home\'\)">([\s\S]*?)</button>',
        r'<a class="btn-back" href="/" data-event="nav_click" data-cta-label="survey_back_home">\1</a>',
        html,
    )

    # 4. Header "Claim my spot" / hero "Join waitlist" CTAs in the home page —
    # buttons that route to /survey become real anchors so search engines and
    # right-click → open in new tab work.
    html = re.sub(
        r'<button\s+class="btn btn-primary btn-arrow"\s+onclick="window\.fwGoto\(\'survey\'\)">([\s\S]*?)</button>',
        lambda m: '<a class="btn btn-primary btn-arrow" href="/survey" data-event="cta_click" data-cta-label="primary_cta">' + m.group(1).strip() + '</a>',
        html,
    )

    # 5. "See how it works" hero secondary — fwGoto only kicks in if it routes;
    # in the prototype this scrolls to #how, so it's already a same-page link.
    # Nothing to do.

    # 6. Welcome modal primary CTA — fwTakeSurveyFromModal() in the prototype.
    # Replace with an anchor that closes the modal then navigates.
    html = re.sub(
        r'<button\s+class="btn btn-primary btn-arrow"\s+onclick="window\.fwTakeSurveyFromModal\(\)">([\s\S]*?)</button>',
        lambda m: (
            '<a class="btn btn-primary btn-arrow" href="/survey" '
            'onclick="if(window.fwCloseWelcome)window.fwCloseWelcome();" '
            'data-event="cta_click" data-cta-label="welcome_modal_primary">'
            + m.group(1).strip() + '</a>'
        ),
        html,
    )

    return html


_COOKIEBOT_BLOCK_ENABLED = """\
<!-- Cookiebot consent banner (CBID injected at deploy time) -->
<!-- TODO_COOKIEBOT_CBID: replace `__COOKIEBOT_CBID__` with the live ID when supplied -->
<script id="Cookiebot" src="https://consent.cookiebot.com/uc.js"
        data-cbid="__COOKIEBOT_CBID__"
        data-blockingmode="auto" type="text/javascript"></script>"""

_COOKIEBOT_BLOCK_DISABLED = """\
<!-- Cookiebot consent banner is currently DISABLED. To re-enable: set
     COOKIEBOT_ENABLED = True in scripts/build_pages.py and provide a real
     COOKIEBOT_CBID via Netlify env. -->"""

_GTAG_BLOCK_GATED = """\
<script>
  window.dataLayer = window.dataLayer || [];
  window.gtag = function gtag(){ window.dataLayer.push(arguments); };
  gtag('consent', 'default', {
    ad_storage: 'denied',
    analytics_storage: 'denied',
    ad_user_data: 'denied',
    ad_personalization: 'denied',
    wait_for_update: 500
  });
  gtag('js', new Date());
  // GA4 config fires only when Cookiebot reports statistics consent.
  window.addEventListener('CookiebotOnAccept', function () {
    if (window.Cookiebot && window.Cookiebot.consent && window.Cookiebot.consent.statistics) {
      gtag('consent', 'update', { analytics_storage: 'granted' });
      gtag('config', '__GA4_MEASUREMENT_ID__', { anonymize_ip: true });
    }
  });
</script>
<script async src="https://www.googletagmanager.com/gtag/js?id=__GA4_MEASUREMENT_ID__"
        data-cookieconsent="statistics"></script>"""

_GTAG_BLOCK_UNGATED = """\
<script>
  window.dataLayer = window.dataLayer || [];
  window.gtag = function gtag(){ window.dataLayer.push(arguments); };
  gtag('js', new Date());
  gtag('config', '__GA4_MEASUREMENT_ID__', { anonymize_ip: true });
</script>
<script async src="https://www.googletagmanager.com/gtag/js?id=__GA4_MEASUREMENT_ID__"></script>"""


def build_head(*, title: str, description: str, canonical: str,
               og_image_path: str = "/assets/og-image.png",
               extra_preloads: tuple[tuple[str, str], ...] = ()) -> str:
    """Shared <head> template. Variables substituted per page.

    `extra_preloads` is a tuple of (as_value, href) — e.g. ("image",
    "/assets/images/hero.webp") — for per-page LCP hints.
    """
    extra_preload_html = "\n".join(
        f'<link rel="preload" as="{as_}" href="{href}" fetchpriority="high"/>'
        for as_, href in extra_preloads
    )
    cookiebot_block = _COOKIEBOT_BLOCK_ENABLED if COOKIEBOT_ENABLED else _COOKIEBOT_BLOCK_DISABLED
    gtag_block = _GTAG_BLOCK_GATED if COOKIEBOT_ENABLED else _GTAG_BLOCK_UNGATED
    cookiebot_preconnect = (
        '<link rel="preconnect" href="https://consent.cookiebot.com" crossorigin/>'
        if COOKIEBOT_ENABLED else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en-AU">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"/>
<title>{title}</title>
<meta name="description" content="{description}"/>
<meta name="theme-color" content="#0B1F3B"/>
<link rel="canonical" href="https://finwellai.com.au{canonical}"/>

<!-- Favicon -->
<link rel="icon" type="image/png" sizes="64x64" href="/assets/images/img-f5ef1fbf38.png"/>
<link rel="apple-touch-icon" href="/assets/images/img-f5ef1fbf38.png"/>

<!-- Open Graph -->
<meta property="og:type" content="website"/>
<meta property="og:site_name" content="Finwell AI"/>
<meta property="og:title" content="{title}"/>
<meta property="og:description" content="{description}"/>
<meta property="og:url" content="https://finwellai.com.au{canonical}"/>
<meta property="og:image" content="https://finwellai.com.au{og_image_path}"/>
<meta property="og:image:width" content="1200"/>
<meta property="og:image:height" content="630"/>

<!-- Twitter -->
<meta name="twitter:card" content="summary_large_image"/>
<meta name="twitter:title" content="{title}"/>
<meta name="twitter:description" content="{description}"/>
<meta name="twitter:image" content="https://finwellai.com.au{og_image_path}"/>

<!-- JSON-LD Organization -->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "Finwell AI",
  "url": "https://finwellai.com.au",
  "logo": "https://finwellai.com.au/assets/images/img-f5ef1fbf38.png",
  "description": "Finwell AI is the bookkeeper in your pocket. AI-powered receipt capture and tax-time automation for Australian sole traders, PAYG earners and small business owners.",
  "sameAs": []
}}
</script>

<!-- Preconnect to third-party origins so DNS + TLS happens in parallel with
     our own assets. Each preconnect saves ~100-300ms on a cold connection.
     Cookiebot preconnect is conditional on COOKIEBOT_ENABLED. -->
<link rel="preconnect" href="https://www.googletagmanager.com" crossorigin/>
<link rel="preconnect" href="https://www.gstatic.com" crossorigin/>
{cookiebot_preconnect}
<link rel="dns-prefetch" href="https://www.google-analytics.com"/>

<!-- Preload critical assets. fetchpriority="high" tells the browser the
     hero F-mark logo is on the LCP path. -->
<link rel="preload" as="font" type="font/woff2" href="/assets/fonts/inter-var.woff2" crossorigin/>
<link rel="preload" as="image" href="/assets/images/img-f5ef1fbf38.png" fetchpriority="high"/>
{extra_preload_html}

<!-- Stylesheet — preload + onload swap so it doesn't block first paint
     on slow mobile connections. Browsers without JS still get the
     stylesheet via <noscript>. -->
<link rel="preload" as="style" href="/assets/css/styles.css" onload="this.onload=null;this.rel='stylesheet'"/>
<noscript><link rel="stylesheet" href="/assets/css/styles.css"/></noscript>

{cookiebot_block}

<!-- Google Analytics 4 -->
<!-- TODO_GA4: replace `__GA4_MEASUREMENT_ID__` with the live G-XXXXXXXXXX -->
{gtag_block}
</head>
"""


# ----------------------------------------------------------------- extraction
RAW = SRC.read_text(encoding="utf-8")

# 1. Strip inline CSS + JS (already externalised to assets/)
RAW = strip_inline_styles_scripts(RAW)

# 2. Swap data: URIs for file paths
RAW = replace_data_uris(RAW)

# 3. Rewrite onclick navigations
RAW = rewrite_nav(RAW)

# 4. Wrap content <img>s in <picture> with AVIF source + lazy-load below fold
RAW = wrap_imgs_in_picture(RAW)

# 4. Slice fragments
URGENT_BANNER = slice_by_marker(
    RAW,
    r'<div class="urgent-banner" id="urgentBanner">',
    r'</div>\s*<!-- ============================================================\s*HOME PAGE',
)
# Trim trailing comment from match
URGENT_BANNER = re.sub(r"<!-- ===.*$", "", URGENT_BANNER, flags=re.DOTALL).rstrip()
# The slice ended at end of urgent-banner div but contains a trailing div from outer markup.
# Re-slice cleanly: from <div class="urgent-banner"> through its matching </div>.
m = re.search(r'(<div class="urgent-banner"[\s\S]*?)\n<!-- =', RAW)
URGENT_BANNER = m.group(1).strip() if m else URGENT_BANNER

HOME_BLOCK = slice_by_marker(
    RAW,
    r'<div class="page active" data-page="home">',
    r'</div>\s*<!-- end home page -->|</div>\s*<!-- ============================================================\s*SURVEY',
)
# Strip any trailing comment
HOME_BLOCK = re.sub(r"<!-- ===.*$", "", HOME_BLOCK, flags=re.DOTALL).rstrip()
# The wrapper is <div class="page active" data-page="home">...</div>. We want
# the inner content. Strip outer wrapper.
m = re.match(r'<div class="page active" data-page="home">(.*)</div>\s*$', HOME_BLOCK, re.DOTALL)
HOME_INNER = m.group(1).strip() if m else HOME_BLOCK


def patch_home_inner(html: str) -> str:
    """Fix dead anchors and onclick handlers inside the home block."""
    # Privacy + Terms anchors in the footer were href-less <a>Privacy</a>.
    html = html.replace("<a>Privacy</a>", '<a href="/privacy">Privacy</a>')
    terms_replacement = '<a href="/terms">Terms</a>'
    if COOKIEBOT_ENABLED:
        terms_replacement += (
            '<a href="#" onclick="if(window.Cookiebot)Cookiebot.renew();return false;" '
            'data-event="nav_click" data-cta-label="footer_cookie_prefs">Cookie preferences</a>'
        )
    html = html.replace("<a>Terms</a>", terms_replacement)
    # Survey link in footer (the only fwGoto leftover here)
    html = html.replace(
        '<a onclick="window.fwGoto(\'survey\')">Take the survey</a>',
        '<a href="/survey" data-event="cta_click" data-cta-label="footer_survey">Take the survey</a>',
    )
    # Scroll-anchor onclick handlers — the home page still uses them locally,
    # so we leave the in-section nav intact and only replace any handlers that
    # would fail if fwGoto stops existing. Nothing else to patch here.
    return html


HOME_INNER = patch_home_inner(HOME_INNER)

SURVEY_BLOCK = slice_by_marker(
    RAW,
    r'<div class="page survey-page" data-page="survey">',
    r'<!-- end survey page -->',
)
m = re.match(
    r'<div class="page survey-page" data-page="survey">(.*?)</div>\s*<!-- end survey page -->',
    SURVEY_BLOCK,
    re.DOTALL,
)
SURVEY_INNER = m.group(1).strip() if m else SURVEY_BLOCK

CHAT_FAB = slice_by_marker(
    RAW,
    r'<button class="chat-fab" id="chatFab"',
    r'</div>\s*<!-- WELCOME POPUP MODAL',
)
# Trim any trailing comment line
CHAT_FAB = re.sub(r"<!-- WELCOME.*$", "", CHAT_FAB, flags=re.DOTALL).rstrip()

WELCOME_MODAL = slice_by_marker(
    RAW,
    r'<div class="welcome-modal-backdrop" id="welcomeModal"',
    r'</body>',
)
WELCOME_MODAL = re.sub(r"</body>\s*$", "", WELCOME_MODAL, flags=re.DOTALL).rstrip()


# ---------------------------------------------------------- survey form mods
def survey_to_form(html: str) -> str:
    """Wrap the survey content in a Netlify form, drop math captcha, add hidden fields."""
    # Replace fwSubmit onclick with form submit handler
    html = html.replace(
        '<button class="btn btn-primary btn-arrow" id="submitBtn" onclick="window.fwSubmit()" disabled>',
        '<button type="submit" class="btn btn-primary btn-arrow" id="submitBtn" disabled data-event="survey_completed">',
    )
    # Add name= attributes to inputs/buttons. Buttons that capture data-q values
    # write into hidden inputs we'll add via JS at submit time. The visible inputs
    # (name, email, consent) need name attributes directly.
    # maxlength caps prevent garbage submissions and align with the HubSpot-
    # side truncation in submission-created.mjs.
    html = html.replace(
        '<input type="text" id="name" placeholder="What should we call you?"/>',
        '<input type="text" id="name" name="name" maxlength="200" placeholder="What should we call you?"/>',
    )
    html = html.replace(
        '<input type="email" id="email" placeholder="you@example.com" required/>',
        '<input type="email" id="email" name="email" maxlength="254" placeholder="you@example.com" required/>',
    )
    html = html.replace(
        '<input type="checkbox" id="consent"/>',
        '<input type="checkbox" id="consent" name="consent" value="yes"/>',
    )

    # Remove the math captcha block entirely
    html = re.sub(
        r'<div class="q7-section-divider"><span>Quick check</span></div>\s*<div class="captcha-block">.*?</div>\s*</div>',
        '',
        html,
        count=1,
        flags=re.DOTALL,
    )

    # Continue handlers: rewrite Continue buttons to use data-event for analytics
    html = re.sub(
        r'<button class="btn btn-primary btn-arrow" onclick="window\.fwNext\(\)" disabled id="next(\d+)">',
        r'<button type="button" class="btn btn-primary btn-arrow" onclick="window.fwNext()" disabled id="next\1" data-event="survey_step_completed" data-step-number="\1">',
        html,
    )
    # Back buttons → button type=button so they don't submit the form
    html = re.sub(
        r'<button class="btn-back" onclick="window\.fwBack\(\)">',
        r'<button type="button" class="btn-back" onclick="window.fwBack()">',
        html,
    )

    # Fix duplicate id collisions between Q6 and Q7 (status7/count7 used twice).
    # Renumber Q6's instance to status6/count6.
    # The first occurrence is in step-pane data-step="6"; rename only that one.
    pat = re.compile(
        r'(<div class="step-pane" data-step="6">.*?)id="status7"(.*?id="count7")',
        re.DOTALL,
    )
    html = pat.sub(lambda m: m.group(1) + 'id="status6"' + m.group(2).replace('id="count7"', 'id="count6"'), html, count=1)

    # Wrap the entire <main class="survey-main"> ... </main> block in a real form.
    html = re.sub(
        r'<main class="survey-main">',
        (
            '<form name="finwellai-waitlist" method="POST" '
            'data-netlify="true" data-netlify-honeypot="bot-field" '
            'action="/thanks" id="surveyForm" novalidate>\n'
            '<input type="hidden" name="form-name" value="finwellai-waitlist"/>\n'
            '<input type="hidden" name="g-recaptcha-response" id="recaptchaToken"/>\n'
            '<p class="hp-field" hidden>\n'
            '  <label>Don’t fill this out: <input name="bot-field"/></label>\n'
            '</p>\n'
            '<!-- Hidden inputs populated by app.js from button data-q selections -->\n'
            '<input type="hidden" name="income_type"/>\n'
            '<input type="hidden" name="salary_range"/>\n'
            '<input type="hidden" name="lost_receipt"/>\n'
            '<input type="hidden" name="tax_stress"/>\n'
            '<input type="hidden" name="deduction_confidence"/>\n'
            '<input type="hidden" name="top_feature"/>\n'
            '<input type="hidden" name="trust_builder"/>\n'
            '<input type="hidden" name="fair_price"/>\n'
            '<input type="hidden" name="points_willingness"/>\n'
            '<main class="survey-main">'
        ),
        html,
        count=1,
    )
    # Close the form after </main>
    html = re.sub(r'</main>', '</main>\n</form>', html, count=1)

    return html


SURVEY_INNER = survey_to_form(SURVEY_INNER)


# ----------------------------------------------------------------- templates

_COOKIE_PREF_LINK = (
    '<a href="#" onclick="if(window.Cookiebot)Cookiebot.renew();return false;" '
    'data-event="nav_click" data-cta-label="footer_cookie_prefs">Cookie preferences</a>'
    if COOKIEBOT_ENABLED else ""
)

SHARED_FOOTER = f"""
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
"""


def page(
    title: str,
    description: str,
    canonical: str,
    body_inner: str,
    *,
    modal: bool = False,
    include_footer: bool = True,
    home_already_has_footer: bool = False,
    include_recaptcha: bool = False,
    extra_preloads: tuple[tuple[str, str], ...] = (),
) -> str:
    """Compose a full page from head + shared shell + body.

    `include_recaptcha` is True only on /survey — the form is the only page
    that needs the v3 token. Loading it elsewhere is ~370KB of wasted
    bandwidth and ~1.7s of unused JS per Lighthouse.

    `extra_preloads` are per-page LCP hints — e.g. the home page preloads
    the hero phone image, the survey preloads the survey card decoration.
    """
    head = build_head(
        title=title, description=description, canonical=canonical,
        extra_preloads=extra_preloads,
    )
    modal_html = WELCOME_MODAL if modal else ""
    footer_html = "" if home_already_has_footer or not include_footer else SHARED_FOOTER
    # On /survey, app.js lazy-loads the reCAPTCHA script on first form
    # interaction — saves ~370KB of unused JS on initial paint. See
    # loadRecaptchaIfNeeded() in app.js.
    recaptcha_script = (
        '<script>window.__RECAPTCHA_LAZY__ = true;</script>'
    ) if include_recaptcha else ""
    body = f"""<body data-page="{canonical.strip('/') or 'home'}">
{URGENT_BANNER}

{body_inner}

{footer_html}

{CHAT_FAB}

{modal_html}

<script src="/assets/js/app.js" defer></script>
{recaptcha_script}
</body>
</html>
"""
    return head + body


# ----------------------------------------------------------------- write index
INDEX_HTML = page(
    title="Finwell AI — Financial wellness, smarter future.",
    description="Finwell AI is the bookkeeper in your pocket. Tax time is around the corner — help us shape what we are building. Take the 2-minute survey and join the founding 500 for 6 months free Premium.",
    canonical="/",
    body_inner=HOME_INNER,
    modal=True,
    home_already_has_footer=True,
    # LCP candidate on the home page is the hero phone image. Preloading it
    # gets the browser fetching it before the CSS is parsed.
    extra_preloads=(
        ("image", "/assets/images/img-45547e3aac.webp"),
    ),
)
(ROOT / "index.html").write_text(INDEX_HTML, encoding="utf-8")

# ---------------------------------------------------------------- write survey
SURVEY_HTML = page(
    title="Take the 2-minute survey — Finwell AI",
    description="Help shape Finwell AI. Answer 8 quick questions and lock in 6 months free Premium at launch as a founding member.",
    canonical="/survey",
    body_inner=SURVEY_INNER,
    include_recaptcha=True,
)
(ROOT / "survey.html").write_text(SURVEY_HTML, encoding="utf-8")


# ---------------------------------------------------------------- write thanks
THANKS_INNER = """
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

<main class="thanks-page" style="min-height:70vh;display:flex;align-items:center;justify-content:center;background:#0B1F3B;color:#fff;padding:120px 24px 80px;text-align:center;">
  <div style="max-width:640px;">
    <div class="logo-mark" style="margin:0 auto 32px;width:96px;height:96px;"><div class="brand-fmark-img" role="img" aria-label="Finwell AI" style="width:100%;height:100%;"></div></div>
    <h1 style="font-size:clamp(36px,5vw,56px);font-weight:800;letter-spacing:-0.025em;line-height:1.05;margin:0 0 16px;">
      Thanks. <span style="color:#56CCF2;">You’re on the list.</span>
    </h1>
    <p style="font-size:18px;line-height:1.6;color:rgba(255,255,255,0.8);margin:0 0 36px;">
      We’ll be in touch when founding-member access opens. In the meantime, keep an eye on your inbox — that’s where we’ll send your invite.
    </p>
    <a href="/" class="btn btn-primary" data-event="nav_click" data-cta-label="thanks_back_home" style="display:inline-flex;align-items:center;gap:8px;">
      Back to home
    </a>
  </div>
</main>
"""

THANKS_HTML = page(
    title="Thanks — you’re on the list — Finwell AI",
    description="You’re on the Finwell AI waitlist. We’ll email you when founding-member access opens.",
    canonical="/thanks",
    body_inner=THANKS_INNER,
)
(ROOT / "thanks.html").write_text(THANKS_HTML, encoding="utf-8")


# ---------------------------------------------------------------- summary
for name in ("index.html", "survey.html", "thanks.html"):
    p = ROOT / name
    print(f"  {name:14s}  {p.stat().st_size:>9,} bytes")
