# Finwell AI — production website

Marketing site and waitlist survey for [finwellai.com.au](https://finwellai.com.au).

Static HTML/CSS/JS hosted on Netlify. Form submissions captured by Netlify Forms, verified by reCAPTCHA v3, and synced to HubSpot via a Netlify Function.

---

## Stack

| Layer | Choice |
| --- | --- |
| Hosting | Netlify (`main` branch auto-deploys to production) |
| Source | Vanilla HTML/CSS/JS — no framework |
| Form backend | Netlify Forms |
| Spam protection | Google reCAPTCHA v3 + Netlify honeypot |
| CRM | HubSpot CRM v3 (via Netlify Function on `submission-created`) |
| Analytics | Google Analytics 4 via `gtag.js`, gated by Cookiebot consent |
| Cookie consent | Cookiebot |
| Fonts | Inter (variable WOFF2, self-hosted at `/assets/fonts/inter-var.woff2`) |
| Build | `bash scripts/inject_env.sh` substitutes deploy-time placeholders into HTML/JS |

Microsoft Clarity, marketing pixels, Slack notifications, and the chat FAB are deferred and intentionally not wired.

---

## Repo layout

```
.
├── index.html              # home (built from prototype + footer + modal)
├── survey.html             # 8-step waitlist survey wrapped in a Netlify form
├── thanks.html             # post-submit confirmation page
├── privacy.html            # rendered from content/privacy.md
├── terms.html              # rendered from content/terms.md
├── robots.txt
├── sitemap.xml
├── netlify.toml            # build, redirects, headers
├── assets/
│   ├── css/styles.css      # extracted from prototype + Inter @font-face
│   ├── js/app.js           # behaviour, analytics, form handling
│   ├── fonts/inter-var.woff2
│   ├── images/             # extracted PNG/JPG + WebP variants
│   └── og-image.png        # placeholder OG card — replace pre-launch
├── content/
│   ├── privacy.md          # source of truth for /privacy
│   └── terms.md            # source of truth for /terms
├── netlify/functions/
│   ├── verify-recaptcha.mjs # POST endpoint — token → siteverify → 200/403
│   └── submission-created.mjs # event handler — pushes form payload to HubSpot
├── scripts/
│   ├── build_legal_pages.py   # markdown → HTML for privacy/terms
│   ├── build_og_image.py      # generate placeholder OG card
│   ├── hubspot_setup.py       # idempotent HubSpot custom-property creator
│   ├── subset_inter.py        # one-off: subset Inter variable WOFF2
│   └── inject_env.sh          # Netlify build step — replace tokens in HTML/JS
├── docs/
│   └── _archive/              # retired prototype build pipeline (rollback only)
└── content/                   # markdown source for /privacy and /terms
```

`index.html`, `survey.html`, and `thanks.html` are **hand-edited** source-of-truth — there is no build step that regenerates them.

---

## Environment variables

Set these in Netlify → **Site settings → Environment variables**. They are also referenced in `.env.example` for local development.

| Variable | Purpose | Source |
| --- | --- | --- |
| `RECAPTCHA_SITE_KEY` | Public key, injected into HTML/JS at build time | https://www.google.com/recaptcha/admin |
| `RECAPTCHA_SECRET` | Server-side secret, used by `verify-recaptcha` function | same place — separate value |
| `HUBSPOT_TOKEN` | Bearer token for HubSpot CRM v3, used by `submission-created` function | HubSpot → Settings → Integrations → Private Apps. Required scopes: `crm.objects.contacts.read`, `crm.objects.contacts.write` |
| `GA4_MEASUREMENT_ID` | `G-XXXXXXXXXX` | GA4 → Admin → Data Streams |
| `COOKIEBOT_CBID` | The Cookiebot data-cbid UUID | Cookiebot dashboard → script settings |

Missing variables become the literal string `MISSING_<NAME>` in the deployed page so the failure shows up in the browser console rather than producing a working tag with bogus credentials.

---

## How to deploy a change

1. Edit files locally (or on a feature branch).
2. Commit and push to GitHub.
3. Push to `main` → Netlify auto-deploys to production.
4. Push to `staging` → Netlify creates a deploy preview at the staging URL.

For a quick visual preview:

```sh
python3 -m http.server 8000
# open http://localhost:8000/
```

The preview will not have GA4, Cookiebot, reCAPTCHA, or HubSpot wired (the env-injection step only runs on Netlify). Form submissions on localhost will not be captured.

To preview functions locally, install Netlify CLI:

```sh
npm install -g netlify-cli
netlify dev   # starts dev server with functions + env vars from .env
```

---

## Form submission flow

1. User completes the 8-step survey on `/survey`.
2. App.js validates required fields and the consent checkbox.
3. On submit:
   - All `data-q` answers are written into the form's hidden inputs.
   - reCAPTCHA v3 generates a token (action `submit`).
   - Token is POSTed to `/.netlify/functions/verify-recaptcha`.
   - On HTTP 200, the form is submitted natively (`form.submit()`).
4. Netlify intercepts the POST, validates honeypot, stores submission, sends notification email, and fires the `submission-created` event.
5. `submission-created.mjs` builds a HubSpot contact payload and POSTs to CRM v3.
6. Browser is redirected to `/thanks`.
7. GA4 `survey_completed` event fires (if statistics consent granted).

### HubSpot custom properties

The submission function maps survey fields onto HubSpot properties prefixed with `finwell_`. **These properties must exist in HubSpot before submissions will accept them.** Create them in HubSpot → Settings → Properties → Contact Properties.

| Form field | HubSpot property | Type |
| --- | --- | --- |
| `email` | `email` (built-in) | single-line text |
| `name` | `firstname` (built-in) | single-line text |
| `consent` | `finwell_marketing_consent` | single-checkbox |
| `income_type` | `finwell_income_type` | single-line text |
| `salary_range` | `finwell_salary_range` | single-line text |
| `lost_receipt` | `finwell_lost_receipt` | single-line text |
| `tax_stress` | `finwell_tax_stress` | number |
| `deduction_confidence` | `finwell_deduction_confidence` | number |
| `top_feature` | `finwell_top_feature` | multi-line text (comma-joined values) |
| `trust_builder` | `finwell_trust_builder` | multi-line text (comma-joined values) |
| `fair_price` | `finwell_fair_price` | number |
| `points_willingness` | `finwell_points_willingness` | single-line text |

If HubSpot returns 400 with an unknown-property error, the function logs the property name to the Netlify function log. Add the property in HubSpot, no redeploy needed.

### Retrieving submissions if Netlify is decommissioned

1. Netlify → Forms → `finwellai-waitlist` → **Export CSV**. Free tier retains the last 30 days.
2. HubSpot → Contacts → filter by lifecycle stage `subscriber` and source `Finwell AI Waitlist 2026` for the long-term record.
3. If both are gone, submission notification emails to alex@finwellai.com are the final fallback.

---

## Tracked GA4 events

All tracked events require user consent (`statistics` category in Cookiebot). Until consent is granted, events are pushed to `dataLayer` with `_denied: true` and not sent to GA4.

| Event | Trigger | Parameters |
| --- | --- | --- |
| `page_view` | Every page load (GA4 Enhanced Measurement) | — |
| `scroll_depth` | 25%, 50%, 75%, 100% (GA4 Enhanced Measurement) | — |
| `cta_click` | Click on any element with `data-event="cta_click"` | `cta_label` |
| `nav_click` | Click on internal nav link | `cta_label` |
| `modal_opened` | Welcome modal first appearance | `reason` |
| `modal_dismissed` | Welcome modal closed | — |
| `chat_opened` | Chat FAB clicked | — |
| `faq_opened` | FAQ accordion item expanded | `faq_question` |
| `survey_started` | First time user advances past Q1 | — |
| `survey_step_completed` | Every Continue click on survey | `step_number` |
| `survey_completed` | Form submitted, before redirect | — |

### Adding a new tracked event without redeploying

You can't — events fire from `assets/js/app.js`, which is part of the deploy. To change events:

1. Edit `assets/js/app.js` (or add a new `data-event="my_event"` attribute on an element).
2. Push. Netlify redeploys.

If you wanted no-redeploy event changes, the brief originally suggested Google Tag Manager. We deferred GTM because Microsoft Clarity and marketing pixels are out of scope right now. To re-enable: install the standard GTM snippet in `<head>` (gated by Cookiebot), move `gtag` calls to GTM tags, and remove the inline GA4 config.

---

## Build and rebuild

The published HTMLs are hand-edited. Only the legal pages have a build step:

```sh
python3 scripts/build_legal_pages.py   # privacy.md / terms.md → privacy.html / terms.html
bash scripts/inject_env.sh             # substitute __VAR__ placeholders (deploy step)
```

When you change the urgent banner or footer markup, update **all four** files together: `index.html`, `survey.html`, `thanks.html`, and the `URGENT_BANNER` / `SHARED_FOOTER` constants in `scripts/build_legal_pages.py`. The legal pages read from those constants and will drift otherwise.

The original prototype-driven build pipeline (`scripts/build_pages.py` + `docs/finwellai_prototype_v5 (1).html`) was retired on 2026-05-07. The retired files live in `docs/_archive/`; see the README in that directory for rollback instructions.

---

## Pre-launch QA checklist

Run these against the staging URL before requesting production sign-off:

- [ ] Homepage loads, no console errors
- [ ] Internal nav scrolls to correct sections
- [ ] All four CTAs (sticky banner, header, hero, welcome modal) navigate to `/survey`
- [ ] Survey advances through all 8 questions
- [ ] Survey Back button works on every step
- [ ] reCAPTCHA token is fetched on submit
- [ ] Form submits and redirects to `/thanks`
- [ ] Submission appears in Netlify dashboard, in HubSpot, and in alex@finwellai.com inbox within 60 seconds
- [ ] Honeypot test: edit form, fill `bot-field`, submit — Netlify rejects as spam
- [ ] Welcome modal appears once per session and respects dismissal
- [ ] FAQ accordion expand/collapse
- [ ] Cookie banner appears, Accept/Reject behave correctly
- [ ] Network tab confirms GA4 + reCAPTCHA scripts only load after consent
- [ ] HTTPS enforced, HSTS header present
- [ ] Lighthouse mobile ≥ 90, desktop ≥ 95
- [ ] Lighthouse Accessibility ≥ 95
- [ ] Cross-browser: Chrome, Safari, Firefox, Edge
- [ ] Mobile: iOS Safari + Android Chrome

---

## Outstanding items (deferred or pending input from Alex)

- [ ] Final logo files (master/512/64 PNG, wordmark light/dark) — placeholders in `/assets/images/img-*.png` to be replaced when assets folder supplied
- [ ] Final OG image — `/assets/og-image.png` is a programmatic placeholder
- [ ] Microsoft Clarity tag (deferred)
- [ ] Slack notification webhook (deferred)
- [ ] Marketing pixels — Meta, LinkedIn, Google Ads (deferred until paid spend confirmed)
- [ ] Chat FAB backend (currently shows the panel + canned responses only)
- [ ] Privacy and Terms text — current copy is a v1 draft. `[REVIEW: …]` tags inside `content/privacy.md` and `content/terms.md` mark spots needing legal review (registered business name, ABN, governing-state nomination, APP 8 reasonable-steps language)

---

## Stabilisation period

Two weeks of bug-fix support post-launch is included. After that, further work is on a maintenance retainer — terms agreed separately. Reach me at the email recorded in the project handover note.
