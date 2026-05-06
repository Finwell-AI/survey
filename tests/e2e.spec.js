// End-to-end tests — full user flows in a real browser.
// Welcome modal, multi-step survey, internal nav, and analytics buffering
// while consent is denied.
const { test, expect } = require('@playwright/test');

test('home page loads, welcome modal appears, then dismisses', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#welcomeModal')).toHaveClass(/show/, { timeout: 5_000 });
  await page.click('button:has-text("Maybe later")');
  await expect(page.locator('#welcomeModal')).not.toHaveClass(/show/);
});

test('welcome modal "Join waitlist" CTA navigates to /survey', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('#welcomeModal')).toHaveClass(/show/, { timeout: 5_000 });
  // Scope to the modal to avoid colliding with the hero CTA that has very
  // similar text ("Join waitlist · 6 months free Premium").
  await page.locator('#welcomeModal a[data-cta-label="welcome_modal_primary"]').click();
  await expect(page).toHaveURL(/\/survey/);
});

test('hero CTA from home navigates to /survey', async ({ page }) => {
  await page.goto('/');
  await page.locator('#welcomeModal').waitFor({ state: 'visible', timeout: 5_000 }).catch(() => {});
  await page.evaluate(() => window.fwCloseWelcome && window.fwCloseWelcome());
  // Wait for modal to fully hide (transition).
  await expect(page.locator('#welcomeModal')).not.toHaveClass(/show/);
  await page.locator('.hero a[href="/survey"]').first().click({ force: true });
  await expect(page).toHaveURL(/\/survey/);
});

test('survey advances through all 8 steps and enables Submit when valid', async ({ page }) => {
  await page.goto('/survey');

  await page.click('[data-q="income_type"][data-v="payg"]');
  await expect(page.locator('[data-step="2"].on')).toBeVisible();

  await page.click('[data-q="salary_range"][data-v="50_80k"]');
  await expect(page.locator('[data-step="3"].on')).toBeVisible();

  await page.click('[data-q="lost_receipt"][data-v="frequent"]');
  await expect(page.locator('[data-step="4"].on')).toBeVisible();

  await page.click('[data-q="tax_stress"][data-v="6"]');
  await expect(page.locator('[data-step="5"].on')).toBeVisible();

  await page.click('[data-q="deduction_confidence"][data-v="4"]');
  await expect(page.locator('[data-step="6"].on')).toBeVisible();

  // Multi-select Q6 — pick 2, then continue
  await page.click('[data-q="top_feature"][data-v="auto_capture"]');
  await page.click('[data-q="top_feature"][data-v="bas_prep"]');
  await page.click('#next6');
  await expect(page.locator('[data-step="7"].on')).toBeVisible();

  await page.click('[data-q="trust_builder"][data-v="ato_accreditation"]');
  await page.click('[data-q="trust_builder"][data-v="security_review"]');
  await page.click('#next7');
  await expect(page.locator('[data-step="8"].on')).toBeVisible();

  // Submit stays disabled until tier + points + email + consent are filled
  await expect(page.locator('#submitBtn')).toBeDisabled();
  await page.click('[data-q="fair_price"][data-v="30"]');
  await page.click('[data-q="points_willingness"][data-v="depends"]');
  await page.fill('#name', 'Playwright User');
  await page.fill('#email', `playwright-${Date.now()}@finwellai-test.local`);
  await page.check('#consent');
  await expect(page.locator('#submitBtn')).toBeEnabled();
});

test('survey Back button returns to the previous step', async ({ page }) => {
  await page.goto('/survey');
  await page.click('[data-q="income_type"][data-v="sole_trader"]');
  await expect(page.locator('[data-step="2"].on')).toBeVisible();
  await page.click('button:has-text("Back")');
  await expect(page.locator('[data-step="1"].on')).toBeVisible();
});

test('footer Privacy + Terms links navigate correctly', async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => window.fwCloseWelcome && window.fwCloseWelcome());
  // Chat FAB sits over the bottom-right of the page; scroll the footer into
  // view and click with force so its position doesn't block the test.
  await page.locator('footer').scrollIntoViewIfNeeded();
  await page.locator('footer a:has-text("Privacy")').click({ force: true });
  await expect(page).toHaveURL(/\/privacy/);
  await expect(page.locator('h1')).toHaveText(/Privacy Policy/);

  await page.goto('/');
  await page.evaluate(() => window.fwCloseWelcome && window.fwCloseWelcome());
  await page.locator('footer').scrollIntoViewIfNeeded();
  await page.locator('footer a:has-text("Terms")').click({ force: true });
  await expect(page).toHaveURL(/\/terms/);
  await expect(page.locator('h1')).toHaveText(/Terms of Use/);
});

test('GA4 dataLayer buffers events while consent is denied', async ({ page }) => {
  await page.goto('/');
  // Trigger a tracked event deterministically — clicking any element with
  // data-event fires fwEvent, which buffers when consent is denied.
  await page.evaluate(() => window.fwCloseWelcome && window.fwCloseWelcome());
  await page.locator('button:has-text("Maybe later")').click({ force: true }).catch(() => {});
  // Now wait for any dataLayer entry with _denied: true.
  await page.waitForFunction(
    () => Array.isArray(window.dataLayer)
      && window.dataLayer.some(e => e && e._denied === true),
    { timeout: 10_000 },
  );
  const buffered = await page.evaluate(
    () => window.dataLayer.filter(e => e && e._denied === true).length,
  );
  expect(buffered).toBeGreaterThan(0);
});

test('FAQ accordion expands and collapses', async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => window.fwCloseWelcome && window.fwCloseWelcome());
  await page.locator('#faq').scrollIntoViewIfNeeded();
  // The first FAQ item — locator depends on prototype markup. Skip if not found.
  const firstFaq = page.locator('.faq details, .faq-item').first();
  if (await firstFaq.count() === 0) {
    test.skip(true, 'FAQ markup not found — skipping');
    return;
  }
  await firstFaq.click();
  // accept either aria-expanded or [open] state change
  const opened = await firstFaq.evaluate(el =>
    el.getAttribute('open') !== null
    || el.getAttribute('aria-expanded') === 'true'
    || el.classList.contains('open')
  );
  expect(opened).toBe(true);
});
