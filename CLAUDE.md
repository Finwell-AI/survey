# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture in one paragraph

This is a static, multi-page Netlify site for the Finwell AI waitlist. `index.html`, `survey.html`, and `thanks.html` are **hand-edited source-of-truth** — edit them directly. Privacy and Terms render from `content/*.md` via `scripts/build_legal_pages.py` (a tiny inline markdown converter). Blog articles render from `blog/*.md` via `scripts/build_blog.py` into `blog/index.html` (listings) and `blog/{slug}/index.html` (article); both import `SHARED_FOOTER` / `URGENT_BANNER` from `build_legal_pages.py` so footer/banner edits propagate. Shared assets live in `assets/css/styles.css`, `assets/js/app.js`, `assets/images/img-*.{png,jpg,webp}`, `assets/fonts/inter-var.woff2`. Two Netlify Functions in `netlify/functions/` handle reCAPTCHA verification and HubSpot CRM sync. A `bash scripts/inject_env.sh` step substitutes `__VAR__` placeholders in HTML/JS with deploy-time env vars (now recurses into `blog/` subdirs).

The previous prototype-driven build pipeline (`docs/finwellai_prototype_v5 (1).html` + `scripts/build_pages.py`) was retired on 2026-05-07; see `docs/_archive/README.md` for rollback instructions.

## Commands

```sh
# Local preview (Netlify CLI handles redirects + functions + env vars)
netlify dev --offline           # serves on http://localhost:8888

# Stop the background server
pkill -f 'netlify dev'

# Manual production deploy (until GitHub App is installed for auto-deploys)
netlify build                                # injects site env vars + runs build command
netlify deploy --prod --dir . --message '…'  # uploads the built output

# Build steps (runs as part of `netlify build`)
python3 scripts/build_legal_pages.py  # privacy/terms from content/*.md
bash scripts/inject_env.sh            # sed-substitutes __VAR__ placeholders

# Index, survey, thanks: hand-edited HTML, no build step.

# One-off setup
python3 scripts/build_og_image.py     # placeholder OG card

# HubSpot CRM properties (idempotent)
HUBSPOT_TOKEN='pat-na1-…' python3 scripts/hubspot_setup.py
```

Tests: `npm test` runs Playwright (HTTP smoke + browser e2e). `npm run test:smoke` for the HTTP-only subset. Tests target `BASE_URL` (default `https://finwellai-survey.netlify.app`). Override with `BASE_URL=http://localhost:8888 npm test` to run against `netlify dev`. Some POST-to-`/thanks` tests in `form.spec.js` only pass against production (Netlify Forms intercepts the POST; netlify dev returns 405 — pre-existing limitation, not a regression).

## Edit which file?

| To change | Edit | Then run |
| --- | --- | --- |
| Hero copy, FAQs, features, sections on the home page | `index.html` | nothing |
| Survey questions, wording, hidden fields | `survey.html` | nothing |
| Thanks page copy | `thanks.html` | nothing |
| Title, meta description, OG, Twitter, JSON-LD, head schema (per page) | the `<head>` block of `index.html` / `survey.html` / `thanks.html` | nothing |
| Urgent banner copy or footer copy | edit in 4 places: `index.html`, `survey.html`, `thanks.html`, plus the `URGENT_BANNER` and `SHARED_FOOTER` constants in `scripts/build_legal_pages.py` (blog pages also import `SHARED_FOOTER` from that file, so updating it covers them too) | `python3 scripts/build_legal_pages.py && python3 scripts/build_blog.py` |
| Blog article body, frontmatter, or hero image | `blog/{slug}.md` (frontmatter `hero_image: img-XXXXXX` to override default) | `python3 scripts/build_blog.py` |
| Add a new blog article | create `blog/{new-slug}.md` with the existing frontmatter shape | `python3 scripts/build_blog.py` |
| Blog listings copy ("Insights" heading + tagline), styles, hero default | `scripts/build_blog.py` (`render_listings`, `_BLOG_STYLES`, `DEFAULT_HERO`) | `python3 scripts/build_blog.py` |
| Sitemap entries for static pages (home, survey, privacy, terms, /blog/) | `sitemap-pages.xml` (hand-edited) | nothing |
| Sitemap entries for blog articles | regenerated from `blog/*.md` frontmatter (`updated`) into `sitemap-blog.xml` | `python3 scripts/build_blog.py` |
| Privacy or Terms text | `content/privacy.md` or `content/terms.md` | `python3 scripts/build_legal_pages.py` |
| Privacy/Terms head template (title, meta, schema) | `scripts/build_legal_pages.py` `page()` function | `python3 scripts/build_legal_pages.py` |
| Behaviour, analytics, form-submit flow | `assets/js/app.js` (hand-edited) | nothing |
| Brand styles, fonts, colours | `assets/css/styles.css` (hand-edited) | nothing |
| Build/deploy substitutions | `scripts/inject_env.sh` + `[build].command` in `netlify.toml` | `netlify build` |
| HubSpot mapping | `netlify/functions/submission-created.mjs` | redeploy |
| Spam threshold | `netlify/functions/verify-recaptcha.mjs` (`SCORE_THRESHOLD`) | redeploy |
| Survey field names sent to HubSpot | `FIELD_MAP` in `submission-created.mjs` and the hidden `<input name="…"/>` fields in `survey.html` | redeploy + HubSpot property creation |

## Gotchas

**Banner and footer live in 4 files.** When you change `URGENT_BANNER` markup or `SHARED_FOOTER` markup, update `index.html`, `survey.html`, `thanks.html`, AND the `URGENT_BANNER` / `SHARED_FOOTER` constants in `scripts/build_legal_pages.py`. Privacy and Terms read from those constants and will drift otherwise. There is no automated cross-page check — visually verify after the change.

**`netlify deploy --build` does NOT inject site env vars.** Confirmed empirically — deployed with `--build` and got `MISSING_GA4_MEASUREMENT_ID` even with the env var set in the dashboard. Always use the two-step form: `netlify build && netlify deploy --prod --dir .`. The `netlify build` step is the one that pulls env vars from the dashboard into the local subprocess.

**`inject_env.sh` is destructive — preserve `__VAR__` placeholders.** The HTMLs and `assets/js/app.js` carry placeholders like `__GA4_MEASUREMENT_ID__`, `__COOKIEBOT_CBID__`, `__RECAPTCHA_SITE_KEY__`. `inject_env.sh` sed-substitutes them on every deploy from Netlify env vars (or to literal `MISSING_<NAME>` if unset). Once a placeholder is gone from the committed file, `inject_env.sh` has nothing to replace. **Never commit the substituted output** — keep the placeholders in the repo. If a placeholder accidentally got replaced (look for `MISSING_*` or a baked GA4 ID), restore it with a global find-and-replace.

**The retired prototype build pipeline lives in `docs/_archive/`.** Don't import from it. Don't restore it without reading `docs/_archive/README.md` first. The archive is for rollback and historical context only.

**Netlify Forms requires the form in the published HTML at deploy time.** That's why `survey.html` is statically built rather than rendered from JS. If a future change moves the form into a JS-rendered template, Netlify won't detect it. The current detection is verified — see `netlify api listSiteForms` returning `finwellai-waitlist` with 14 fields.

**Custom domain finwellai.com.au is configured on the Netlify site but DNS is not cut over yet.** Use `https://finwellai-survey.netlify.app` for testing until DNS points to Netlify.

**GitHub email privacy is on.** Commits to this repo must use `6508597+valentinceaprazaru@users.noreply.github.com` (already set as the project-local `git config user.email`). Don't change it. GitHub rejects pushes that would expose `valentin.c@codingheads.com`.

**Auto-deploy on push is NOT wired.** The Netlify GitHub App isn't installed on the `Finwell-AI` org yet. Until it is, every change requires a manual `netlify build && netlify deploy --prod --dir .` from this machine.

## Conventions

**Survey is on v2 schema (cutover 2026-05-10).** v2 fields: `segment` (Q1 qualifier), `lost_receipt`, `tax_stress`, `deduction_confidence` (semantic flipped — 1=fully claiming, 10=leaving money), `top_feature` (multi, max 3, AI ATO categorisation first), `price_too_cheap` / `price_bargain` / `price_expensive` / `price_too_expensive` (Van Westendorp 4-input block, integer AUD), `points_willingness`, `trust_builder` (multi, no cap). Hidden tracking fields: `survey_version=v2`, `launch_phase=pre_launch`. v1-only fields (`income_type`, `salary_range`, `fair_price`) stay mapped in `submission-created.mjs` for back-compat with archived submissions but are no longer collected — corresponding HubSpot properties are dormant. v1 archive tag: `survey-v1-archive` (10 submissions captured). Q4 confidence semantic flip is intentional — accept the noise on the 10 v1 responses (per spec override). HubSpot custom properties are prefixed `finwell_*`. **Founding 500 messaging is kept across the site** as a deliberate override of the v2 spec checklist (which said remove). README's HubSpot table is the source of truth.

**Email contact is `info@finwellai.com.au`.** Site URL is also `finwellai.com.au`. (Earlier convention was `alex@finwellai.com`; switched 2026-05-08.)

**No framework.** Vanilla HTML/CSS/JS. Don't rewrite to Next.js or any SPA — Netlify Forms requires the form in static HTML at build time, and a framework rewrite breaks that detection.

**No GTM, no Microsoft Clarity, no marketing pixels, no Slack webhook, no chat backend.** All deferred per founder. GA4 is installed directly via `gtag.js`, gated by Cookiebot consent. If a future task asks to add Clarity or pixels, install via the existing pattern (Cookiebot-gated `<script>` in the `<head>` of every page) — apply the change to `index.html`, `survey.html`, `thanks.html`, and the legal-pages `page()` head template in `scripts/build_legal_pages.py`.

**Self-hosted Inter (variable WOFF2).** Don't add a Google Fonts `<link>` — the `@font-face` is in `styles.css` and the WOFF2 is preloaded in `<head>`.

**Env var placeholders use `__VAR__` syntax.** Currently: `__GA4_MEASUREMENT_ID__`, `__COOKIEBOT_CBID__`, `__RECAPTCHA_SITE_KEY__`. Missing values become `MISSING_<NAME>` strings at substitution time so failures show up in the browser console rather than silently breaking.

## Required env vars on Netlify

| Variable | Used by |
| --- | --- |
| `RECAPTCHA_SITE_KEY` | injected into HTML+JS by `inject_env.sh` |
| `RECAPTCHA_SECRET` | `verify-recaptcha.mjs` (server-side siteverify call) |
| `HUBSPOT_TOKEN` | `submission-created.mjs` (Bearer auth to HubSpot CRM v3). Private App scopes: `crm.schemas.contacts.read/write`, `crm.objects.contacts.read/write` |
| `RESEND_API_KEY` | `submission-created.mjs` — Resend transactional welcome email. Fail-safe: missing key skips email, submission still completes. |
| `RESEND_FROM` | optional override of welcome-email sender. Default: `Finwell AI <hello@finwellai.com.au>`. Must be a verified Resend sending domain. |
| `RESEND_REPLY_TO` | optional override of Reply-To. Default: `info@finwellai.com.au`. |
| `GA4_MEASUREMENT_ID` | `inject_env.sh` substitutes into `gtag/js?id=…` and `gtag('config', …)` |
| `COOKIEBOT_CBID` | `inject_env.sh` substitutes into `data-cbid` |

Set with `netlify env:set NAME 'value'` then redeploy.

## Required HubSpot setup

Run `HUBSPOT_TOKEN=… python3 scripts/hubspot_setup.py` once to create the `finwell_survey` property group + the contact properties. v2 set: `finwell_marketing_consent`, `finwell_segment`, `finwell_lost_receipt`, `finwell_tax_stress`, `finwell_deduction_confidence`, `finwell_top_feature`, `finwell_trust_builder`, `finwell_points_willingness`, `finwell_price_too_cheap`, `finwell_price_bargain`, `finwell_price_expensive`, `finwell_price_too_expensive`, `finwell_survey_version`, `finwell_launch_phase`. v1 dormant (kept for archived submissions): `finwell_income_type`, `finwell_salary_range`, `finwell_fair_price`. The script is idempotent — safe to re-run; existing properties are skipped.

If the function logs a 400 about an unknown property, add it in HubSpot and re-run the script.

## Live identifiers

- Netlify site ID: `cdb07751-3505-4c4d-a0ad-1211d71f9a06`
- Admin: https://app.netlify.com/projects/finwellai-survey
- Repo: https://github.com/Finwell-AI/survey
- Default deploy URL (use until DNS): https://finwellai-survey.netlify.app

## Outstanding

- Install Netlify GitHub App on Finwell-AI org → unlocks auto-deploy on push
- Real reCAPTCHA + Cookiebot keys → set env vars + redeploy
- HubSpot Private App token + re-run `hubspot_setup.py` for v2 properties (segment, 4 price points, version, phase)
- Resend API key + verify `finwellai.com.au` sending domain → set `RESEND_API_KEY` env var
- Configure Form notification email in Netlify dashboard → Forms → finwellai-waitlist → Notifications → email to `info@finwellai.com.au`
- DNS cutover for `finwellai.com.au`
- Replace placeholder logo + OG image once founder supplies the assets folder
- Legal review on `[REVIEW: …]` tags in `content/privacy.md` and `content/terms.md` — v2 changed the data being collected (added 4 price points + segment, removed salary_range and fair_price). The privacy policy text mentions "annual income range" and "preferred monthly price tier" which are now misaligned with the v2 form. Update needed before launch.
