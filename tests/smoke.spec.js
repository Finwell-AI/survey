// Smoke tests — fast, no browser interaction, just HTTP checks.
// Verifies pages return 200, security + cache headers are correct, and the
// SEO support files (robots, sitemap, OG image) exist.
const { test, expect } = require('@playwright/test');

const PAGES = ['/', '/survey', '/thanks', '/privacy', '/terms'];

test.describe('smoke', () => {
  for (const path of PAGES) {
    test(`GET ${path} returns 200 with a Finwell AI title`, async ({ request }) => {
      const res = await request.get(path);
      expect(res.status(), `unexpected status for ${path}`).toBe(200);
      const html = await res.text();
      expect(html).toMatch(/<title>[^<]*Finwell AI[^<]*<\/title>/i);
    });
  }

  test('robots.txt is reachable and references the sitemap', async ({ request }) => {
    const r = await request.get('/robots.txt');
    expect(r.status()).toBe(200);
    expect(await r.text()).toMatch(/Sitemap:\s+https?:/i);
  });

  test('sitemap.xml is well-formed and includes the homepage', async ({ request }) => {
    const r = await request.get('/sitemap.xml');
    expect(r.status()).toBe(200);
    const xml = await r.text();
    expect(xml).toContain('<urlset');
    expect(xml).toContain('https://finwellai.com.au/');
  });

  test('security headers are set on HTML', async ({ request }) => {
    const r = await request.get('/');
    const h = r.headers();
    expect(h['x-frame-options']).toBe('DENY');
    expect(h['x-content-type-options']).toBe('nosniff');
    expect(h['referrer-policy']).toBe('strict-origin-when-cross-origin');
    expect(h['strict-transport-security']).toMatch(/max-age=\d+/);
  });

  test('CSS + JS use short cache; images + fonts are immutable', async ({ request }) => {
    const css = await request.get('/assets/css/styles.css');
    expect(css.status()).toBe(200);
    expect(css.headers()['cache-control']).toContain('must-revalidate');

    const js = await request.get('/assets/js/app.js');
    expect(js.status()).toBe(200);
    expect(js.headers()['cache-control']).toContain('must-revalidate');

    const img = await request.get('/assets/images/img-f5ef1fbf38.png');
    expect(img.status()).toBe(200);
    expect(img.headers()['cache-control']).toContain('immutable');

    const font = await request.get('/assets/fonts/inter-var.woff2');
    expect(font.status()).toBe(200);
    expect(font.headers()['cache-control']).toContain('immutable');
  });

  test('OG image is present and is an image', async ({ request }) => {
    const r = await request.get('/assets/finwellai-og.jpeg');
    expect(r.status()).toBe(200);
    expect(r.headers()['content-type']).toContain('image');
  });

  test('Inter font WOFF2 is preloaded', async ({ request }) => {
    const html = await (await request.get('/')).text();
    expect(html).toContain('rel="preload"');
    expect(html).toContain('inter-var.woff2');
    expect(html).toContain('as="font"');
  });

  test('JSON-LD Organization block is present and valid', async ({ request }) => {
    const html = await (await request.get('/')).text();
    const m = html.match(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/);
    expect(m, 'no JSON-LD block found').not.toBeNull();
    const data = JSON.parse(m[1]);
    expect(data['@type']).toBe('Organization');
    expect(data.name).toBe('Finwell AI');
    expect(data.url).toMatch(/finwellai\.com\.au/);
  });
});
