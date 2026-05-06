/**
 * Netlify Function — reCAPTCHA v3 verifier.
 *
 * Client posts { token } JSON. We call Google's siteverify with the secret
 * key from the RECAPTCHA_SECRET environment variable. We accept scores >= 0.5
 * per the brief.
 *
 * Response: 200 OK on pass, 403 on fail. Body is JSON with `score` for debug.
 *
 * Env vars (configure in Netlify UI → Site settings → Environment variables):
 *   - RECAPTCHA_SECRET   The secret key from https://www.google.com/recaptcha/admin
 */

const SCORE_THRESHOLD = 0.5;

export default async function handler(req) {
  if (req.method !== 'POST') {
    return new Response('Method Not Allowed', { status: 405 });
  }

  const secret = process.env.RECAPTCHA_SECRET;
  if (!secret) {
    // No secret configured — fail closed but log loudly.
    console.error('[verify-recaptcha] RECAPTCHA_SECRET env var is not set.');
    return new Response(JSON.stringify({ ok: false, error: 'server_misconfigured' }), {
      status: 500,
      headers: { 'content-type': 'application/json' },
    });
  }

  let token = '';
  try {
    const body = await req.json();
    token = (body && body.token) || '';
  } catch {
    return new Response(JSON.stringify({ ok: false, error: 'bad_body' }), {
      status: 400,
      headers: { 'content-type': 'application/json' },
    });
  }
  if (!token) {
    return new Response(JSON.stringify({ ok: false, error: 'missing_token' }), {
      status: 400,
      headers: { 'content-type': 'application/json' },
    });
  }

  const params = new URLSearchParams({ secret, response: token });
  const verifyRes = await fetch('https://www.google.com/recaptcha/api/siteverify', {
    method: 'POST',
    headers: { 'content-type': 'application/x-www-form-urlencoded' },
    body: params.toString(),
  });

  if (!verifyRes.ok) {
    return new Response(JSON.stringify({ ok: false, error: 'siteverify_unreachable' }), {
      status: 502,
      headers: { 'content-type': 'application/json' },
    });
  }

  const data = await verifyRes.json();
  const ok = data.success === true && (data.score ?? 0) >= SCORE_THRESHOLD;

  return new Response(
    JSON.stringify({ ok, score: data.score, action: data.action, errors: data['error-codes'] || [] }),
    {
      status: ok ? 200 : 403,
      headers: { 'content-type': 'application/json' },
    }
  );
}
