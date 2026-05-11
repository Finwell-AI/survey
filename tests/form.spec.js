// Form-submission tests — verify Netlify Forms accepts a real POST and routes
// to the thank-you page. We submit form-urlencoded directly because the
// reCAPTCHA-gated client flow requires a valid site key.
const { test, expect } = require('@playwright/test');

const FIELDS = {
  'form-name': 'finwellai-waitlist',
  survey_version: 'v2',
  launch_phase: 'pre_launch',
  consent: 'yes',
  segment: 'payg',
  lost_receipt: 'occasional',
  tax_stress: '7',
  deduction_confidence: '4',
  top_feature: 'ai_categorisation,auto_capture,live_ledger',
  trust_builder: 'ato_dsp,bank_encryption,au_hosting',
  price_too_cheap: '5',
  price_bargain: '15',
  price_expensive: '30',
  price_too_expensive: '60',
  points_willingness: 'maybe',
};

test('survey HTML registers the form with Netlify and has the honeypot', async ({ request }) => {
  // Netlify post-processing strips data-netlify="..." and data-netlify-honeypot
  // from the rendered HTML once it's registered the form server-side, and it
  // re-emits attributes with single quotes. We verify what survives: the form
  // name, the form-name hidden input, the bot-field honeypot, and every
  // survey field as a named input (some are hidden, some are visible like
  // the price_* number inputs).
  const html = await (await request.get('/survey')).text();
  expect(html).toMatch(/<form[^>]*\bname=['"]finwellai-waitlist['"]/);
  expect(html).toMatch(/<input[^>]+name=['"]form-name['"][^>]+value=['"]finwellai-waitlist['"]/);
  expect(html).toMatch(/<input\s+name=['"]bot-field['"]/);
  for (const name of Object.keys(FIELDS).filter(k => k !== 'form-name')) {
    expect(html, `missing input: ${name}`).toMatch(new RegExp(`name=['"]${name}['"]`));
  }
  // reCAPTCHA token field (lazy-loaded site key, populated client-side on submit)
  expect(html).toMatch(/name=['"]recaptchaToken['"]/);
});

test('POST /thanks captures the submission and serves the thanks page', async ({ request }) => {
  const email = `playwright-${Date.now()}@finwellai-test.local`;
  const params = new URLSearchParams({ ...FIELDS, name: 'Playwright Bot', email });
  const res = await request.post('/thanks', {
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    data: params.toString(),
  });
  expect(res.status()).toBe(200);
  const html = await res.text();
  expect(html).toMatch(/<title>[^<]*Thanks[^<]*<\/title>/i);
  expect(html).toMatch(/you.{0,2}re on the list/i);
});

test('honeypot-tripped submissions are silently accepted (do not error)', async ({ request }) => {
  // Netlify silently drops honeypot-tripped submissions — the response is
  // still a 200 thank-you so attackers can't tell they were filtered.
  const params = new URLSearchParams({
    ...FIELDS,
    name: 'Honeypot Bot',
    email: `honeypot-${Date.now()}@finwellai-test.local`,
    'bot-field': 'I am a bot',
  });
  const res = await request.post('/thanks', {
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    data: params.toString(),
  });
  expect(res.status()).toBe(200);
});

test('GET /thanks renders without a POST (link-share / refresh case)', async ({ request }) => {
  const res = await request.get('/thanks');
  expect(res.status()).toBe(200);
  const html = await res.text();
  expect(html).toMatch(/Thanks/);
});
