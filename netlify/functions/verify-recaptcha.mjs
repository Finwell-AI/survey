/**
 * Netlify Function — reCAPTCHA v3 verifier.
 *
 * Client posts { token } JSON. We call Google's siteverify with the secret
 * key from the RECAPTCHA_SECRET environment variable. We accept scores >= 0.5,
 * action === 'submit' (matches grecaptcha.execute(..., { action: 'submit' })
 * in app.js), and a hostname from the allow-list.
 *
 * The Origin header must also be one of our domains — a cheap drive-by
 * guard against browser-based floods of this endpoint while we're on the
 * Netlify free plan. Server-side attackers bypass this trivially, so it is
 * a quota guard rather than a real security control.
 *
 * Response: 200 OK on pass, 403 on fail. Body is JSON with `score` only —
 * we do not echo Google's `error-codes` to public callers because it helps
 * spammers iterate. Errors are still logged server-side.
 *
 * Env vars (Netlify UI → Site settings → Environment variables):
 *   - RECAPTCHA_SECRET   secret key from https://www.google.com/recaptcha/admin
 */

const SCORE_THRESHOLD = 0.5;
const EXPECTED_ACTION = 'submit';
const ALLOWED_HOSTNAMES = new Set([
  'finwellai.com.au',
  'finwellai-survey.netlify.app',
  'localhost',
]);
const ALLOWED_ORIGINS = new Set([
  'https://finwellai.com.au',
  'https://finwellai-survey.netlify.app',
  'http://localhost:8888',
  'http://localhost:3000',
]);

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json', 'cache-control': 'no-store' },
  });
}

export default async function handler(req) {
  if (req.method !== 'POST') {
    return new Response('Method Not Allowed', { status: 405 });
  }

  // Origin guard — rejects browser-based floods. Server-side attackers
  // bypass this trivially. Empty Origin (server-to-server, curl) is allowed
  // through to siteverify so manual debugging stays possible.
  const origin = req.headers.get('origin') || '';
  if (origin && !ALLOWED_ORIGINS.has(origin)) {
    return jsonResponse(403, { ok: false, error: 'origin_not_allowed' });
  }

  const secret = process.env.RECAPTCHA_SECRET;
  if (!secret) {
    console.error('[verify-recaptcha] RECAPTCHA_SECRET env var is not set.');
    return jsonResponse(500, { ok: false, error: 'server_misconfigured' });
  }

  let token = '';
  try {
    const body = await req.json();
    token = (body && body.token) || '';
  } catch {
    return jsonResponse(400, { ok: false, error: 'bad_body' });
  }
  if (!token) {
    return jsonResponse(400, { ok: false, error: 'missing_token' });
  }
  // Defensive cap — reCAPTCHA tokens are ~600 chars; reject anything wild.
  if (token.length > 4096) {
    return jsonResponse(400, { ok: false, error: 'token_too_large' });
  }

  const params = new URLSearchParams({ secret, response: token });
  const verifyRes = await fetch('https://www.google.com/recaptcha/api/siteverify', {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: params.toString(),
  });

  if (!verifyRes.ok) {
    return jsonResponse(502, { ok: false, error: 'siteverify_unreachable' });
  }

  const data = await verifyRes.json();
  const score = typeof data.score === 'number' ? data.score : 0;
  const ok =
    data.success === true &&
    score >= SCORE_THRESHOLD &&
    data.action === EXPECTED_ACTION &&
    ALLOWED_HOSTNAMES.has(data.hostname);

  if (!ok) {
    console.warn('[verify-recaptcha] rejected', {
      success: data.success,
      score,
      action: data.action,
      hostname: data.hostname,
      errors: data['error-codes'] || [],
    });
  }

  return jsonResponse(ok ? 200 : 403, { ok, score });
}
