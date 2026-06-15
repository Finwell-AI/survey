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

  test('sitemap.xml is a sitemap index that resolves to the homepage', async ({ request }) => {
    const indexRes = await request.get('/sitemap.xml');
    expect(indexRes.status()).toBe(200);
    const indexXml = await indexRes.text();
    expect(indexXml).toContain('<sitemapindex');
    const childLocs = [...indexXml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
    expect(childLocs.length, 'sitemap index has no child <loc> entries').toBeGreaterThan(0);

    const pagesUrl = childLocs.find((u) => /sitemap-pages\.xml$/.test(u));
    expect(pagesUrl, 'sitemap-pages.xml not referenced by sitemap.xml').toBeTruthy();

    const pagesPath = new URL(pagesUrl).pathname;
    const pagesRes = await request.get(pagesPath);
    expect(pagesRes.status()).toBe(200);
    const pagesXml = await pagesRes.text();
    expect(pagesXml).toContain('<urlset');
    expect(pagesXml).toContain('https://finwellai.com.au/');
  });

  test('security headers are set on HTML', async ({ request }) => {
    const r = await request.get('/');
    const h = r.headers();
    expect(h['x-frame-options']).toBe('DENY');
    expect(h['x-content-type-options']).toBe('nosniff');
    expect(h['referrer-policy']).toBe('strict-origin-when-cross-origin');
    expect(h['strict-transport-security']).toMatch(/max-age=\d+/);
  });

  test('CSS, JS, images, and fonts are served with immutable long-lived cache', async ({ request }) => {
    // Production serves content-hashed CSS/JS (e.g. styles.eaa16483.css) with the
    // same 1y-immutable policy as images and fonts. Discover the deployed paths
    // from the homepage rather than hard-coding the hash.
    const homeHtml = await (await request.get('/')).text();
    const cssMatch = homeHtml.match(/\/assets\/css\/styles(?:\.[a-f0-9]+)?\.css/);
    const jsMatch = homeHtml.match(/\/assets\/js\/app(?:\.[a-f0-9]+)?\.js/);
    expect(cssMatch, 'no styles.css reference on homepage').not.toBeNull();
    expect(jsMatch, 'no app.js reference on homepage').not.toBeNull();

    const css = await request.get(cssMatch[0]);
    expect(css.status()).toBe(200);
    expect(css.headers()['cache-control']).toContain('immutable');

    const js = await request.get(jsMatch[0]);
    expect(js.status()).toBe(200);
    expect(js.headers()['cache-control']).toContain('immutable');

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

  test('survey is on v2: 12 questions, segment qualifier, VW currency block', async ({ request }) => {
    const html = await (await request.get('/survey')).text();
    expect(html).toContain('survey_version');
    expect(html).toMatch(/value="v2"/);
    expect(html).toContain('of 12');
    expect(html).toContain('data-q="segment"');
    expect(html).toContain('name="price_too_cheap"');
    expect(html).toContain('name="price_too_expensive"');
  });
});
