// Regression tests — guard rails for bugs we've already fixed. Each test
// references the issue it's protecting against. These are the cheapest tests
// to keep because they run in milliseconds and stop a known failure mode
// from coming back.
const { test, expect } = require('@playwright/test');

test('GA4 measurement ID is wired (no MISSING placeholder)', async ({ request }) => {
  // Regression: env injection silently failed once when `netlify deploy --build`
  // was used without `netlify build` first. The placeholder string was left in
  // the deployed HTML.
  const html = await (await request.get('/')).text();
  expect(html).not.toContain('MISSING_GA4_MEASUREMENT_ID');
  expect(html).toMatch(/G-[A-Z0-9]{8,}/);
});

test('app.js has the reCAPTCHA hang-protection (3s timeout + once guard)', async ({ request }) => {
  // Regression: with the placeholder reCAPTCHA site key, grecaptcha.execute
  // threw synchronously inside grecaptcha.ready and the promise never settled,
  // freezing the form at "Submitting…".
  const js = await (await request.get('/assets/js/app.js')).text();
  expect(js, 'expected once() guard').toContain("once('')");
  expect(js, 'expected 3s hard timeout').toMatch(/setTimeout\(\s*function\s*\(\)\s*\{\s*once\(''\);\s*\},\s*3000\s*\)/);
  expect(js, 'expected MISSING_ early-out').toContain("siteKey.indexOf('MISSING_') === 0");
});

test('CSS + JS are not served with `immutable` (un-fingerprinted assets)', async ({ request }) => {
  // Regression: assets/* used to be `max-age=31536000, immutable` for everything.
  // Browsers refused to revalidate app.js after deploys. Split rules now apply
  // immutable only to fingerprinted images + fonts.
  const css = await request.get('/assets/css/styles.css');
  expect(css.headers()['cache-control']).not.toContain('immutable');
  const js = await request.get('/assets/js/app.js');
  expect(js.headers()['cache-control']).not.toContain('immutable');
});

test('survey HTML has no fwGoto leftovers (multi-page split is clean)', async ({ request }) => {
  // Regression: the prototype used a JS routing function `fwGoto`. After the
  // multi-page split, every onclick that referenced it should be replaced with
  // a real <a href>. A single missed conversion would break navigation.
  const html = await (await request.get('/survey')).text();
  expect(html).not.toContain('fwGoto');
});

test('survey multi-select status IDs are semantic (one per question, no v1 step-number collision)', async ({ page }) => {
  // Regression: the v1 prototype reused step-numbered IDs (#status6, #count6
  // for top_feature; #status7, #count7 for trust_builder). The duplicate
  // pattern broke the multi-select counter when panes shared an ID.
  // v2 uses semantic IDs derived from the question name, so each multi
  // pane has a distinct id pair and the original collision risk is gone.
  await page.goto('/survey');
  expect(await page.locator('#status_top_feature').count()).toBe(1);
  expect(await page.locator('#count_top_feature').count()).toBe(1);
  expect(await page.locator('#status_trust_builder').count()).toBe(1);
  expect(await page.locator('#count_trust_builder').count()).toBe(1);
  // v1 step-numbered IDs must be gone.
  expect(await page.locator('#status6').count()).toBe(0);
  expect(await page.locator('#count6').count()).toBe(0);
  expect(await page.locator('#status7').count()).toBe(0);
  expect(await page.locator('#count7').count()).toBe(0);
});

test('contact email is info@finwellai.com.au', async ({ request }) => {
  const html = await (await request.get('/privacy')).text();
  expect(html).toContain('info@finwellai.com.au');
  expect(html).not.toContain('alex@finwellai.com');
});

test('reCAPTCHA is set up to lazy-load, only on /survey', async ({ request }) => {
  // Performance: reCAPTCHA's gstatic.com payload is ~370KB. We only need it
  // on the form page, and only after first user interaction. The static
  // HTML must NOT contain a reCAPTCHA <script> tag — app.js injects it
  // on demand via loadRecaptchaIfNeeded().
  for (const path of ['/', '/thanks', '/privacy', '/terms']) {
    const html = await (await request.get(path)).text();
    expect(html, `unexpected reCAPTCHA on ${path}`).not.toContain('google.com/recaptcha/api.js');
    expect(html, `unexpected lazy flag on ${path}`).not.toContain('__RECAPTCHA_LAZY__');
  }
  // /survey arms the lazy loader by setting window.__RECAPTCHA_LAZY__.
  const survey = await (await request.get('/survey')).text();
  expect(survey).toContain('window.__RECAPTCHA_LAZY__');
  expect(survey, 'reCAPTCHA script must NOT be inline — app.js injects it').not.toContain('google.com/recaptcha/api.js');
});

test('reCAPTCHA loader respects Cookiebot security consent', async ({ request }) => {
  // The lazy loader must wait for Cookiebot's `security` consent before
  // injecting the reCAPTCHA script — otherwise we'd bypass user consent.
  const js = await (await request.get('/assets/js/app.js')).text();
  expect(js).toContain('Cookiebot.consent.security');
  expect(js).toContain('CookiebotOnAccept');
});

test('Content-Security-Policy is set on every HTML page', async ({ request }) => {
  // F-01: a CSP must be present on HTML responses to backstop any future XSS.
  for (const path of ['/', '/survey', '/thanks', '/privacy', '/terms']) {
    const res = await request.get(path);
    const csp = res.headers()['content-security-policy'];
    expect(csp, `${path} missing CSP`).toBeTruthy();
    // Critical directives that must always be present.
    expect(csp).toContain("object-src 'none'");
    expect(csp).toContain("base-uri 'self'");
    expect(csp).toContain("frame-ancestors 'none'");
  }
});

test('verify-recaptcha endpoint rejects requests without an Origin header set to ours', async ({ request }) => {
  // F-03: the function applies an Origin guard against drive-by floods.
  // An evil-origin request must be rejected before any siteverify call.
  const res = await request.post('/.netlify/functions/verify-recaptcha', {
    headers: {
      'origin': 'https://evil.example.com',
      'content-type': 'application/json',
    },
    data: JSON.stringify({ token: 'whatever' }),
  });
  expect(res.status()).toBe(403);
  const body = await res.json();
  expect(body.error).toBe('origin_not_allowed');
});

test('survey form has maxlength caps on name and email inputs', async ({ request }) => {
  // F-09: defends HubSpot from arbitrarily long values.
  const html = await (await request.get('/survey')).text();
  expect(html).toMatch(/<input[^>]+id="name"[^>]+maxlength="200"/);
  expect(html).toMatch(/<input[^>]+id="email"[^>]+maxlength="254"/);
});

test('privacy policy describes the survey in plain English (no q1_role / referral_source)', async ({ request }) => {
  // F-06/F-07/F-13: the policy must accurately enumerate the actual fields.
  const html = await (await request.get('/privacy')).text();
  expect(html).not.toContain('q1_role');
  expect(html).not.toContain('q2_business_type');
  expect(html).not.toContain('referral_source');
  expect(html).toContain('How you primarily earn your income');
  expect(html).toContain('annual income range');
  expect(html).toContain('preferred monthly price tier');
});

test('Cookie preferences link is hidden while Cookiebot is disabled', async ({ request }) => {
  // The link only makes sense when Cookiebot is loaded (it calls
  // Cookiebot.renew()). With Cookiebot disabled, the link must not render.
  for (const path of ['/', '/survey', '/thanks', '/privacy', '/terms']) {
    const html = await (await request.get(path)).text();
    expect(html, `${path} unexpectedly renders Cookie preferences link`).not.toContain('Cookie preferences');
  }
});

test('Cookiebot is currently disabled (build flag) — none of the pages ship the script', async ({ request }) => {
  // While COOKIEBOT_ENABLED = False in build_pages.py, no Cookiebot script
  // tag should reach the rendered HTML. Re-enable by flipping that flag and
  // setting COOKIEBOT_CBID; this test will then need to flip too.
  for (const path of ['/', '/survey', '/thanks', '/privacy', '/terms']) {
    const html = await (await request.get(path)).text();
    expect(html, `${path} unexpectedly ships Cookiebot`).not.toContain('consent.cookiebot.com');
    expect(html, `${path} unexpectedly references Cookiebot CBID placeholder`).not.toContain('data-cbid="__COOKIEBOT_CBID__"');
  }
  // GA4 still loads but without the data-cookieconsent="statistics" gate.
  const home = await (await request.get('/')).text();
  expect(home).toMatch(/googletagmanager\.com\/gtag\/js/);
  expect(home).not.toMatch(/data-cookieconsent="statistics"/);
});

test('GA4 fires unconditionally while Cookiebot is disabled', async ({ page }) => {
  // With Cookiebot disabled, no `consent` default-deny is set. gtag('config')
  // runs synchronously from the head <script>. dataLayer holds at least the
  // 'js' and 'config' entries by the time the page is interactive.
  await page.goto('/');
  await page.waitForFunction(() => Array.isArray(window.dataLayer) && window.dataLayer.length >= 2);
  const dl = await page.evaluate(() => window.dataLayer.map((d) => d['0']));
  expect(dl).toContain('js');
  expect(dl).toContain('config');
});

test('all 5 routable pages return 200 (no broken multi-page split)', async ({ request }) => {
  for (const p of ['/', '/survey', '/thanks', '/privacy', '/terms']) {
    const res = await request.get(p);
    expect(res.status(), `${p} should be 200`).toBe(200);
  }
});

test('all routable pages share the same urgent banner, footer, and chat FAB', async ({ request }) => {
  // Every public page should carry the same chrome — top urgent banner,
  // full site footer (brand + tagline + four-link nav), and chat FAB.
  // Privacy + Terms used to ship a slimmer footer; that's been unified.
  const required = ['urgent-banner', 'footer-brand', 'chat-fab'];
  for (const p of ['/', '/survey', '/thanks', '/privacy', '/terms']) {
    const html = await (await request.get(p)).text();
    for (const marker of required) {
      expect(html, `${p} missing ${marker}`).toContain(marker);
    }
    // Footer must include the eight-link nav + bottom strip.
    expect(html, `${p} footer missing tagline`).toContain('Financial Wellness. Smarter Future.');
    expect(html, `${p} footer missing bottom strip`).toContain('Made in Melbourne.');
  }
});

test('Inter is self-hosted (not loaded from fonts.googleapis.com at runtime)', async ({ request }) => {
  // Regression: a Google Fonts <link> would put a third-party request on
  // every page load and undo the self-hosting work.
  const html = await (await request.get('/')).text();
  expect(html).not.toMatch(/fonts\.googleapis\.com\/css/);
});

test('powered-by-ai uses image-as-section-background on tablet+ widths', async ({ page }) => {
  // Regression: the layout was reworked so the photo lives as the section's
  // own background-image at >=768px, with the inline .pba-visual block
  // hidden. A revert would break the design.
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto('/');
  const sec = page.locator('.powered-by-ai');
  const bg = await sec.evaluate(el => getComputedStyle(el).backgroundImage);
  expect(bg).toContain('img-289e15f2a1.webp');
  const visualDisplay = await page.locator('.pba-visual').evaluate(el => getComputedStyle(el).display);
  expect(visualDisplay).toBe('none');
});
