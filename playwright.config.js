// Playwright configuration. Run via `npm test` (or filter to `npm run test:smoke` etc.).
// BASE_URL env var overrides the default target. CI=true switches to retries +
// HTML reporter so failures are captured for inspection.
const { defineConfig, devices } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'https://finwellai-survey.netlify.app';
const isCI = !!process.env.CI;

module.exports = defineConfig({
  testDir: './tests',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 1 : 0,
  workers: isCI ? 2 : undefined,
  reporter: isCI ? [['list'], ['html', { open: 'never' }]] : [['list']],
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: isCI ? 'retain-on-failure' : 'off',
    extraHTTPHeaders: { 'x-finwellai-qa': 'playwright' },
    // Block service worker registration in tests so a SW from a previous
    // test run can't intercept fetches and serve stale assets. Real users
    // benefit from the SW; tests don't.
    serviceWorkers: 'block',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
