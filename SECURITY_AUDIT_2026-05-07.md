# Finwell AI Security Audit — 2026-05-07

**Auditor:** Claude Code (Security Auditor role)
**Scope:** `/Users/Herd/finwellai.com.au` — full codebase review prior to wiring live credentials and running paid traffic.

---

## 1. Executive Summary

The codebase is well-structured for a pre-launch static site and exhibits several security-aware design decisions: no secrets are committed, DOM manipulation consistently uses `textContent` rather than `innerHTML`, the honeypot and reCAPTCHA v3 are wired correctly at a code level, and the HSTS / X-Frame / X-Content-Type headers are in place.

Three issues warrant immediate attention before real credentials are inserted:

1. There is no Content-Security-Policy header.
2. The `verify-recaptcha` function neither validates the reCAPTCHA `action` field nor imposes any rate limit (making it trivial to probe cheaply).
3. The deployed HTML files contain the GA4 Measurement ID `G-FEXPCZFS0M` baked in by an earlier local build, instead of the `__GA4_MEASUREMENT_ID__` placeholder. GA4 IDs are not secret, but this is a process-hygiene issue that breaks the env-injection contract.

The privacy policy is materially inaccurate after a build-time `field_map` substitution corrupted the field descriptions. This must be fixed before paid traffic begins, regardless of credentials.

---

## 2. Findings

| # | Severity | Category | Location | Description |
|---|----------|----------|----------|-------------|
| F-01 | High | HTTP Security Headers | `netlify.toml` (all `[[headers]]`) | No Content-Security-Policy on any page. |
| F-02 | High | Netlify Function — reCAPTCHA | `netlify/functions/verify-recaptcha.mjs:63` | `action` from siteverify is never asserted server-side. A token from any other action passes. |
| F-03 | High | Netlify Function — rate limiting | `netlify/functions/verify-recaptcha.mjs` | No rate limiting. Trivial to flood. |
| F-04 | Medium | Build pipeline | `index.html:70,86,90` (and survey/thanks) | GA4 Measurement ID `G-FEXPCZFS0M` hardcoded in committed HTML rather than the `__GA4_MEASUREMENT_ID__` placeholder. |
| F-05 | Medium | Build pipeline — shell injection | `scripts/inject_env.sh:29-31,46` | Env vars interpolated bare into `sed` replacements. A `\|` or newline in a value would corrupt the build. |
| F-06 | Medium | Privacy compliance | `privacy.html:79-86` | After `field_map` substitution, surrounding English description text no longer matches the field codes (e.g. "Your business type (salary_range)"). |
| F-07 | Medium | Privacy compliance | `content/privacy.md:29-36` | Source uses `q1_role`/`q2_business_type` placeholder labels in prose; only the codes get substituted, leaving descriptions wrong. |
| F-08 | Medium | HTTP Security Headers | `netlify.toml` | `Cross-Origin-Embedder-Policy` and `Cross-Origin-Resource-Policy` absent. Low urgency for this threat model. |
| F-09 | Medium | Netlify Function — input validation | `netlify/functions/submission-created.mjs:38-50`, `survey.html:367,371` | No length caps on `name`, `email`. No `maxlength` on inputs. |
| F-10 | Medium | Netlify Function — reCAPTCHA | `netlify/functions/verify-recaptcha.mjs:63` | `hostname` from siteverify is not checked. |
| F-11 | Low | Local artefacts | `.netlify/db/` | PostgreSQL dev DB present locally. Correctly gitignored; cleanup hygiene only. |
| F-12 | Low | Privacy compliance | `privacy.html:110`, footer HTML | Privacy promises a "cookie settings link in the footer" that does not exist. |
| F-13 | Low | Privacy compliance | `content/privacy.md:36` | Privacy discloses a `referral_source` field that the form does not collect. |
| F-14 | Low | Form — replay protection | `assets/js/app.js:447-463` | Tiny race window between verify and form submit. Acceptable. |
| F-15 | Low | Third-party scripts — SRI | `survey.html:65-91`, `index.html:65-91` | No SRI on Cookiebot/GA4/reCAPTCHA. Not feasible for these CDNs; addressed by CSP (F-01). |
| F-16 | Low | Proxy routes not wired | `netlify.toml:53-65` vs page templates | `/_proxy/gtag.js` and `/_proxy/cookiebot/uc.js` rewrites exist but pages still load from third-party CDNs directly. |
| F-17 | Info | Public repo exposure | committed HTML | GA4 ID visible in repo. GA4 IDs are public; not a secret. |
| F-18 | Info | `node_modules` present locally | working tree | Correctly gitignored; not tracked. |

---

## 3. Detailed Findings

### F-01 — No Content-Security-Policy

**Severity:** High
**Location:** `netlify.toml` `[[headers]]` blocks for `/*.html` and `/`.

Every HTML page is served without CSP. No XSS vector currently exists in this code (all DOM writes use `textContent`), but CSP is the browser-enforced backstop for any future regression. Cookiebot's `data-blockingmode="auto"` dynamically toggles `<script>` tags via `data-cookieconsent`, so a future inline-script change could open a vector with no CSP to catch it.

**Remediation.** Start with the trivially-safe directives (no refactor needed):

```toml
Content-Security-Policy = "default-src 'self'; script-src 'self' 'unsafe-inline' https://consent.cookiebot.com https://www.googletagmanager.com https://www.gstatic.com https://www.google.com; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; font-src 'self'; connect-src 'self' https://www.google-analytics.com https://api.hubapi.com https://www.google.com; frame-src https://www.google.com; object-src 'none'; base-uri 'self'; form-action 'self';"
```

`object-src 'none'` and `base-uri 'self'` block the most severe vectors and can ship today. Tightening `script-src` to drop `'unsafe-inline'` requires moving the Cookiebot init and GA4 consent snippet from the page `<head>` into `app.js` first.

**Verification.** `curl -I https://finwellai-survey.netlify.app/survey | grep content-security`.

---

### F-02 — reCAPTCHA `action` not validated

**Severity:** High
**Location:** `netlify/functions/verify-recaptcha.mjs:63`

Google's siteverify response includes the `action` string the token was generated with. Our function returns `data.action` to the client but never asserts it equals `'submit'`. A token generated for any other action under the same site key passes verification.

**Remediation.** One-line addition:

```js
const EXPECTED_ACTION = 'submit';
const ok = data.success === true
  && (data.score ?? 0) >= SCORE_THRESHOLD
  && data.action === EXPECTED_ACTION;
```

---

### F-03 — No rate limiting on `/.netlify/functions/verify-recaptcha`

**Severity:** High
**Location:** `netlify/functions/verify-recaptcha.mjs`

Endpoint accepts unlimited POSTs. Free Netlify plan allows 125,000 function invocations/month; a 2-minute flood burns 1.6%.

**Remediation, in order of effort:**

1. **Origin/Referer guard (10 minutes, no infrastructure):**
   ```js
   const origin = req.headers.get('origin') || '';
   const allowed = ['https://finwellai.com.au', 'https://finwellai-survey.netlify.app'];
   if (!allowed.includes(origin)) return new Response('Forbidden', { status: 403 });
   ```
   Stops drive-by browser-based floods. Trivial to bypass server-side.

2. **Netlify Edge Function with Blobs-based token bucket (~1 hour):** the proper long-term fix. Free tier supports it.

3. **Accept the risk pre-launch.** Reasonable given the function does no harmful computation and the founder will see invocation metrics in the dashboard before any abuse becomes expensive.

---

### F-04 — GA4 Measurement ID hardcoded in committed HTML

**Severity:** Medium
**Location:** `index.html:70,86,90`, `survey.html:70,86,90`, `thanks.html:70,86,90`

The build pipeline emits `__GA4_MEASUREMENT_ID__` as a placeholder and substitutes it at deploy time via `scripts/inject_env.sh`. However, an earlier local `netlify deploy --build` run substituted the placeholder in-place and the substituted result was committed (the auto-commit "update website content" cycle). The committed HTML now contains the literal `G-FEXPCZFS0M`.

GA4 IDs are public values, so this is not a secret leak. It is a process hygiene issue: subsequent runs of `inject_env.sh` find no `__GA4_MEASUREMENT_ID__` to replace, so the deployed HTML always uses whatever was last committed, regardless of the Netlify env var.

**Remediation.** Re-run `python3 scripts/build_pages.py` to regenerate the placeholders, then commit. Going forward, add a pre-commit hook that fails if `G-` IDs appear literally in HTML files (only `__GA4_MEASUREMENT_ID__` should appear in committed HTML).

---

### F-05 — `inject_env.sh` interpolates env vars bare into `sed`

**Severity:** Medium
**Location:** `scripts/inject_env.sh:29-31, 46`

Lines:

```bash
sed -i.bak \
  -e "s|__GA4_MEASUREMENT_ID__|${GA4}|g" \
  -e "s|__COOKIEBOT_CBID__|${CBID}|g" \
  -e "s|__RECAPTCHA_SITE_KEY__|${RECAPTCHA_KEY}|g" \
  "$f"
```

If a Netlify env var contains `|`, `&`, or a newline, the sed expression breaks. Realistic input (G-, UUID, pat-na1-…) does not contain these characters, so the actual exploitability is nil. Adding the escape is cheap insurance.

**Remediation.**

```bash
escape_sed() { printf '%s' "$1" | sed 's/[|\\&]/\\&/g'; }
GA4=$(escape_sed "${GA4_MEASUREMENT_ID:-MISSING_GA4_MEASUREMENT_ID}")
CBID=$(escape_sed "${COOKIEBOT_CBID:-MISSING_COOKIEBOT_CBID}")
RECAPTCHA_KEY=$(escape_sed "${RECAPTCHA_SITE_KEY:-MISSING_RECAPTCHA_SITE_KEY}")
```

Also on the line that prepends to `app.js`, single-quote the value and escape any embedded single quotes, or switch to `printf '%s\n'` to avoid word splitting.

---

### F-06, F-07 — Privacy policy field descriptions wrong after substitution

**Severity:** Medium (compliance)
**Location:** `content/privacy.md:29-36`, `privacy.html:79-86`, `scripts/build_legal_pages.py:173-180`

The build's `field_map` substitution swaps the technical codes (`q1_role` → `income_type`, etc.) but leaves the surrounding English description unchanged. Rendered output reads:

- "Your role or job title (income_type)" — but `income_type` is "how you earn your income," not a job title.
- "Your business type (salary_range)" — but `salary_range` is annual income, not business type.
- "The tools you currently use for bookkeeping (tax_stress)" — `tax_stress` is a 1-10 stress scale.
- "How interested you are in using the product at launch (points_willingness)" — `points_willingness` is willingness to pay for rewards.

`deduction_confidence` and `trust_builder` are collected and sent to HubSpot but not disclosed at all.

Under APP 3.3, the privacy policy must accurately describe what is collected.

**Remediation.** Rewrite `content/privacy.md` lines 29-36 with accurate descriptions and remove the `field_map` substitution from `build_legal_pages.py`:

```
- How you primarily earn your income (sole trader, PAYG, etc.)
- Your approximate annual income range
- Whether you have lost tax receipts in the past 12 months
- Your level of stress preparing tax or BAS (rated 1–10)
- Your confidence that you claim every available deduction (rated 1–10)
- Product features most important to you (multiple-choice)
- What would build your trust in a platform that connects to spending data (multiple-choice)
- Your preferred monthly price tier
- Whether you would pay more to earn points or rewards
```

---

### F-08 — COEP / CORP absent

**Severity:** Medium (low urgency)

`Cross-Origin-Opener-Policy: same-origin` is set; `Cross-Origin-Embedder-Policy` and `Cross-Origin-Resource-Policy` are not. For a static marketing site with no `SharedArrayBuffer`, this is academic.

**Remediation.** Optional, for completeness:

```toml
Cross-Origin-Embedder-Policy = "unsafe-none"
Cross-Origin-Resource-Policy = "same-origin"
```

Use `unsafe-none` for COEP — `require-corp` would break Cookiebot/reCAPTCHA iframes which don't send CORP headers.

---

### F-09 — No input length caps before HubSpot

**Severity:** Medium
**Location:** `survey.html:367,371`, `netlify/functions/submission-created.mjs:38-50`

Inputs lack `maxlength`. Submission function passes unbounded `name`/`email` to HubSpot. If HubSpot rejects with a 400, the response body (which may echo user input) is logged via `console.error`.

**Remediation.**

1. `survey.html` — add `maxlength="200"` to `#name`, `maxlength="254"` to `#email`.
2. `submission-created.mjs:buildProperties()` — truncate:
   ```js
   email: (data.email || '').slice(0, 254),
   firstname: (data.name || '').slice(0, 200),
   ```
3. On error logs (lines 111, 120), log only the status code, not the response body that may contain user input.

---

### F-10 — reCAPTCHA `hostname` not validated

**Severity:** Medium (low exploitability with single site key)
**Location:** `netlify/functions/verify-recaptcha.mjs:63`

**Remediation.** Add to the `ok` check:

```js
const EXPECTED_HOSTNAME = 'finwellai.com.au';
const ok = data.success === true
  && (data.score ?? 0) >= SCORE_THRESHOLD
  && data.action === 'submit'
  && (data.hostname === EXPECTED_HOSTNAME
      || data.hostname === 'finwellai-survey.netlify.app'
      || data.hostname === 'localhost');
```

---

### F-11 — `.netlify/db/` PostgreSQL data directory locally

**Severity:** Low

`.gitignore` correctly excludes `.netlify/`. The dev DB itself uses trust auth (standard for ephemeral dev). The concern is non-git distribution (zip, archive). Clean up after dev sessions.

---

### F-12 — Cookie preferences link missing from footer

**Severity:** Low
**Location:** `content/privacy.md:70`, footer in all rendered HTML

Policy says preferences can be updated via a footer link. The footer has no such link. Cookiebot's floating widget is not a footer link.

**Remediation.** Add to `scripts/build_pages.py:SHARED_FOOTER` and the footer in `build_legal_pages.py`:

```html
<a href="javascript:void(0)" onclick="window.Cookiebot && Cookiebot.renew()">Cookie preferences</a>
```

---

### F-13 — Privacy discloses non-existent `referral_source`

**Severity:** Low
**Location:** `content/privacy.md:36`

The form doesn't collect this. Remove the line and the corresponding mapping in `build_legal_pages.py:180`.

---

### F-14 — Token replay window

**Severity:** Low / Accepted

Window between verify-success and native form submit is sub-100ms. Google marks tokens as used after one verify. Acceptable.

---

### F-15 — No SRI on third-party scripts

**Severity:** Low / Not feasible

CDN scripts are dynamic; hashes would be stale immediately. CSP `script-src` (F-01) is the equivalent protection.

---

### F-16 — Edge proxy routes are dead code

**Severity:** Low
**Location:** `netlify.toml:53-65` vs HTML `<script src=...>`

Either wire the proxy routes into `build_pages.py` (and tighten CSP to `script-src 'self'`) or delete the rules. Don't leave them unused.

---

## 4. Compliance Posture — Australian Privacy Act 1988

| APP | Status | Notes |
|-----|--------|-------|
| APP 1 (transparency) | Partial | `[REVIEW:]` items in `content/privacy.md` for ABN, registered address still open. |
| APP 3 (collection) | **Inaccurate** | Field descriptions wrong (F-06, F-07); `referral_source` listed but not collected (F-13). |
| APP 5 (notification) | Partial | Cookie settings mechanism described in policy doesn't exist in footer (F-12). |
| APP 8 (cross-border) | Partial | Recipients (Netlify, HubSpot, Google, Cookiebot) disclosed; `[REVIEW:]` on "reasonable steps" language. |
| APP 11 (security) | Partial | Rate-limiting (F-03) and CSP (F-01) gaps relevant here. |
| APP 12 / 13 (access / correction) | Met | Email + 30-day response process documented. OAIC referenced. |
| SPAM Act 2003 | Partial | Opt-in checkbox correct. Unsubscribe mechanism still to be implemented in launch email platform. |

---

## 5. Recommended Action Order

**Before inserting real credentials (now):**

1. **F-02 + F-10** — add `action` and `hostname` validation to `verify-recaptcha.mjs` (one-line each).
2. **F-06 + F-07 + F-13** — rewrite `content/privacy.md` collection section with accurate descriptions; drop `field_map` from `build_legal_pages.py`. Compliance fix.
3. **F-04** — re-run `build_pages.py`, commit clean placeholders.
4. **F-12** — add Cookie preferences link to shared footer.

**Before paid traffic (within first week):**

5. **F-01** — add CSP. Start with `object-src 'none'; base-uri 'self'`, then expand.
6. **F-09** — input `maxlength` + truncate before HubSpot.
7. **F-05** — escape sed inputs.

**After launch:**

8. **F-03** — Edge Function rate limiting.
9. **F-16** — wire or remove proxy routes.
10. **APP 1 / APP 8** `[REVIEW:]` items — needs lawyer.

---

## 6. What's Already Strong (Do Not Break)

- **DOM writes use `textContent` everywhere.** No `innerHTML`, no `document.write`. The single biggest XSS mitigation in vanilla JS.
- **Chat module is safe.** `chatAddMsg` uses `textContent` for both user and bot messages.
- **Secrets not committed.** `.env` empty, `.env.example` clean, `.gitignore` correct.
- **reCAPTCHA correctly lazy-loaded** with Cookiebot consent gating in `app.js:loadRecaptchaIfNeeded`.
- **GA4 consent gating correct.** Default-denied; only `update` to granted inside `CookiebotOnAccept`.
- **Honeypot wired in two places.** HTML form + server-side check in `submission-created.mjs:70`.
- **HSTS at maximum.** `max-age=31536000; includeSubDomains; preload`.
- **Service worker scope is narrow.** Caches only same-origin `/assets/*`. Third-party cannot poison cache.
- **HubSpot token never logged.** Used only in `Authorization` header.
- **Build scripts use safe path handling.** All paths anchored to project root via `pathlib`.
