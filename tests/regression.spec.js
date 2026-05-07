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

test('survey page does not have duplicate id="status7" / id="count7"', async ({ page }) => {
  // Regression: the prototype reused the same IDs on Q6 and Q7. Multi-select
  // counter would update only one of the two, depending on which paint last.
  await page.goto('/survey');
  expect(await page.locator('#status7').count()).toBeLessThanOrEqual(1);
  expect(await page.locator('#count7').count()).toBeLessThanOrEqual(1);
  expect(await page.locator('#status6').count()).toBe(1);
  expect(await page.locator('#count6').count()).toBe(1);
});

test('contact email is alex@finwellai.com (NOT .com.au)', async ({ request }) => {
  // Regression: the brief said .com.au, but the founder uses .com. Privacy
  // and terms must match what's on file with Netlify and HubSpot.
  const html = await (await request.get('/privacy')).text();
  expect(html).toContain('alex@finwellai.com');
  expect(html).not.toContain('alex@finwellai.com.au');
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

test('Cookie preferences link is present in every footer', async ({ request }) => {
  // F-12: the privacy policy promises a footer link; it must exist.
  for (const path of ['/', '/survey', '/thanks', '/privacy', '/terms']) {
    const html = await (await request.get(path)).text();
    expect(html, `${path} missing Cookie preferences link`).toContain('Cookie preferences');
  }
});

test('Cookiebot is loaded on every page', async ({ request }) => {
  for (const path of ['/', '/survey', '/thanks', '/privacy', '/terms']) {
    const html = await (await request.get(path)).text();
    expect(html, `${path} missing Cookiebot`).toContain('consent.cookiebot.com');
  }
  // GA4 still uses the static data-cookieconsent attr because the gtag tag
  // is in <head>; reCAPTCHA's gating is done in JS instead.
  const home = await (await request.get('/')).text();
  expect(home, 'GA4 must be gated by Cookiebot statistics consent').toMatch(/data-cookieconsent="statistics"/);
});

test('consent default is "denied" before user opt-in', async ({ page }) => {
  await page.goto('/');
  // We push consent state into dataLayer with positional args: ['consent','default',{...}]
  const denied = await page.evaluate(() => {
    const entry = window.dataLayer.find(d => d['0'] === 'consent' && d['1'] === 'default');
    return entry && entry['2'] && entry['2'].analytics_storage === 'denied';
  });
  expect(denied).toBe(true);
});

test('all 5 routable pages return 200 (no broken multi-page split)', async ({ request }) => {
  for (const p of ['/', '/survey', '/thanks', '/privacy', '/terms']) {
    const res = await request.get(p);
    expect(res.status(), `${p} should be 200`).toBe(200);
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
