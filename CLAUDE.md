# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture in one paragraph

This is a static, multi-page Netlify site for the Finwell AI waitlist. `index.html`, `survey.html`, and `thanks.html` are **hand-edited source-of-truth** — edit them directly. Privacy and Terms render from `content/*.md` via `scripts/build_legal_pages.py` (a tiny inline markdown converter). Shared assets live in `assets/css/styles.css`, `assets/js/app.js`, `assets/images/img-*.{png,jpg,webp}`, `assets/fonts/inter-var.woff2`. Two Netlify Functions in `netlify/functions/` handle reCAPTCHA verification and HubSpot CRM sync. A `bash scripts/inject_env.sh` step substitutes `__VAR__` placeholders in HTML/JS with deploy-time env vars.

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

There are no tests, no linter, no formatter configured. Don't invent them.

## Edit which file?

| To change | Edit | Then run |
| --- | --- | --- |
| Hero copy, FAQs, features, sections on the home page | `index.html` | nothing |
| Survey questions, wording, hidden fields | `survey.html` | nothing |
| Thanks page copy | `thanks.html` | nothing |
| Title, meta description, OG, Twitter, JSON-LD, head schema (per page) | the `<head>` block of `index.html` / `survey.html` / `thanks.html` | nothing |
| Urgent banner copy or footer copy | edit in 4 places: `index.html`, `survey.html`, `thanks.html`, plus the `URGENT_BANNER` and `SHARED_FOOTER` constants in `scripts/build_legal_pages.py` | `python3 scripts/build_legal_pages.py` |
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

**Field names use semantic identifiers, not the brief's `q1_role`/`q2_business_type` placeholders.** The actual survey asks about `income_type`, `salary_range`, `lost_receipt`, `tax_stress`, `deduction_confidence`, `top_feature`, `trust_builder`, `fair_price`, `points_willingness`. HubSpot custom properties are prefixed `finwell_*`. The README's HubSpot table is the source of truth.

**Email contact is `alex@finwellai.com`** (not `.com.au`, despite the brief). Site URL is `finwellai.com.au` (the public domain). Don't conflate.

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
| `GA4_MEASUREMENT_ID` | `inject_env.sh` substitutes into `gtag/js?id=…` and `gtag('config', …)` |
| `COOKIEBOT_CBID` | `inject_env.sh` substitutes into `data-cbid` |

Set with `netlify env:set NAME 'value'` then redeploy.

## Required HubSpot setup

Run `HUBSPOT_TOKEN=… python3 scripts/hubspot_setup.py` once to create the `finwell_survey` property group + 10 custom properties (`finwell_income_type`, `finwell_salary_range`, `finwell_lost_receipt`, `finwell_tax_stress`, `finwell_deduction_confidence`, `finwell_top_feature`, `finwell_trust_builder`, `finwell_fair_price`, `finwell_points_willingness`, `finwell_marketing_consent`). The script is idempotent — safe to re-run.

If the function logs a 400 about an unknown property, add it in HubSpot and re-run the script.

## Live identifiers

- Netlify site ID: `cdb07751-3505-4c4d-a0ad-1211d71f9a06`
- Admin: https://app.netlify.com/projects/finwellai-survey
- Repo: https://github.com/Finwell-AI/survey
- Default deploy URL (use until DNS): https://finwellai-survey.netlify.app

## Outstanding

- Install Netlify GitHub App on Finwell-AI org → unlocks auto-deploy on push
- Real reCAPTCHA + Cookiebot keys → set env vars + redeploy
- HubSpot Private App token + run `hubspot_setup.py`
- Configure Form notification email in Netlify dashboard → Forms → finwellai-waitlist → Notifications → email to `alex@finwellai.com`
- DNS cutover for `finwellai.com.au`
- Replace placeholder logo + OG image once founder supplies the assets folder
- Legal review on `[REVIEW: …]` tags in `content/privacy.md` and `content/terms.md`
