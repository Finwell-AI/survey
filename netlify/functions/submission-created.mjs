/**
 * Netlify Function — push every Netlify Forms submission to HubSpot and send a
 * customer welcome email via Resend.
 *
 * Triggered automatically by Netlify on the `submission-created` event when the
 * function is named exactly `submission-created`. Receives the form payload in
 * `event.body.payload.data`. We map those fields onto HubSpot CRM v3 properties
 * and POST to the contacts endpoint with a Private App bearer token, then fire
 * a transactional welcome email through Resend.
 *
 * Both integrations fail-open: missing env vars cause the relevant step to be
 * skipped (logged to function output) but the submission is never marked as
 * failed in the Netlify dashboard. Netlify keeps the original submission
 * regardless, so data is never lost even if HubSpot or Resend is down.
 *
 * Env vars (Netlify UI → Site settings → Environment variables):
 *   - HUBSPOT_TOKEN      Private App bearer token (scopes: crm.objects.contacts.write)
 *   - RESEND_API_KEY     Resend API key (https://resend.com)
 *   - RESEND_FROM        Override sender; default 'Finwell AI <hello@finwellai.com.au>'
 *   - RESEND_REPLY_TO    Override Reply-To; default 'info@finwellai.com.au'
 */

// HubSpot custom property prefix so survey fields don't collide with built-ins.
// Alex must create these properties in HubSpot before they will accept values.
const PROP_PREFIX = 'finwell_';

// Mapping: Netlify form field → HubSpot property name.
// Standard HubSpot fields (email, firstname, lifecyclestage) are special-cased
// in buildProperties().
const FIELD_MAP = {
  // v2 fields
  segment: PROP_PREFIX + 'segment',
  lost_receipt: PROP_PREFIX + 'lost_receipt',
  tax_stress: PROP_PREFIX + 'tax_stress',
  deduction_confidence: PROP_PREFIX + 'deduction_confidence',
  top_feature: PROP_PREFIX + 'top_feature',
  price_too_cheap: PROP_PREFIX + 'price_too_cheap',
  price_bargain: PROP_PREFIX + 'price_bargain',
  price_expensive: PROP_PREFIX + 'price_expensive',
  price_too_expensive: PROP_PREFIX + 'price_too_expensive',
  points_willingness: PROP_PREFIX + 'points_willingness',
  trust_builder: PROP_PREFIX + 'trust_builder',
  survey_version: PROP_PREFIX + 'survey_version',
  launch_phase: PROP_PREFIX + 'launch_phase',
  consent: PROP_PREFIX + 'marketing_consent',
  // v1 legacy fields (still mapped so any in-flight v1 submissions land cleanly)
  income_type: PROP_PREFIX + 'income_type',
  salary_range: PROP_PREFIX + 'salary_range',
  fair_price: PROP_PREFIX + 'fair_price',
};

// Per-field length caps before sending to HubSpot. Defends against junk
// submissions that bypass the honeypot but ship arbitrarily long strings,
// and avoids paying a HubSpot API call to learn HubSpot's own limits.
const EMAIL_MAX = 254;     // RFC 5321
const NAME_MAX = 200;
const TEXT_MAX = 500;      // generic single-line answers
const TEXTAREA_MAX = 2000; // multi-select joined values

const FIELD_LIMITS = {
  segment: TEXT_MAX,
  lost_receipt: TEXT_MAX,
  tax_stress: TEXT_MAX,
  deduction_confidence: TEXT_MAX,
  top_feature: TEXTAREA_MAX,
  price_too_cheap: TEXT_MAX,
  price_bargain: TEXT_MAX,
  price_expensive: TEXT_MAX,
  price_too_expensive: TEXT_MAX,
  points_willingness: TEXT_MAX,
  trust_builder: TEXTAREA_MAX,
  survey_version: TEXT_MAX,
  launch_phase: TEXT_MAX,
  consent: TEXT_MAX,
  income_type: TEXT_MAX,
  salary_range: TEXT_MAX,
  fair_price: TEXT_MAX,
};

const PRICE_FIELDS = [
  'price_too_cheap',
  'price_bargain',
  'price_expensive',
  'price_too_expensive',
];

const RESEND_FROM_DEFAULT = 'Finwell AI <hello@finwellai.com.au>';
const RESEND_REPLY_TO_DEFAULT = 'info@finwellai.com.au';

function clamp(value, max) {
  if (value == null) return '';
  return String(value).slice(0, max);
}

function buildProperties(data) {
  const props = {
    email: clamp(data.email, EMAIL_MAX),
    firstname: clamp(data.name, NAME_MAX),
    lifecyclestage: 'subscriber',
    hs_lead_status: 'NEW',
  };
  Object.keys(FIELD_MAP).forEach(function (key) {
    const v = data[key];
    if (v == null || v === '') return;
    props[FIELD_MAP[key]] = clamp(v, FIELD_LIMITS[key] || TEXT_MAX);
  });
  // Strip non-digit characters from VW currency inputs so HubSpot's number
  // property accepts them. Users sometimes type "$30" or "30/mo".
  PRICE_FIELDS.forEach(function (key) {
    const propName = FIELD_MAP[key];
    if (props[propName] == null) return;
    const digits = String(props[propName]).replace(/[^0-9]/g, '');
    if (digits === '') {
      delete props[propName];
    } else {
      props[propName] = digits;
    }
  });
  // HubSpot's `finwell_marketing_consent` is an enum with options `Yes`/`No`
  // (titlecase). The form posts `consent=yes` (lowercase). Normalize so
  // HubSpot accepts it.
  if (props[FIELD_MAP.consent]) {
    const c = String(props[FIELD_MAP.consent]).toLowerCase();
    props[FIELD_MAP.consent] = (c === 'yes' || c === 'on' || c === 'true') ? 'Yes' : 'No';
  }
  return props;
}

function escapeHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function welcomeEmailContent(firstname) {
  const greeting = firstname ? `Hi ${escapeHtml(firstname)},` : 'Hi there,';
  const subject = 'You are in. Your early access spot is locked in.';
  const text = [
    greeting,
    '',
    'Thanks for taking the Finwell AI survey. Your early access spot is locked in.',
    '',
    'Beta access opens in the coming weeks. We will be in touch with details and updates as we build.',
    '',
    'If you ever need to reach us, just reply to this email.',
    '',
    'Finwell AI — Built in Melbourne for Australians who hate tax time.',
  ].join('\n');
  const html = `<!doctype html><html><body style="margin:0;padding:24px;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Roboto,sans-serif;color:#0B1F3B;background:#F8FAFC;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;margin:0 auto;background:#FFFFFF;border-radius:12px;border:1px solid #E2E8F0;">
      <tr><td style="padding:32px 32px 8px;">
        <p style="margin:0 0 16px;font-size:14px;color:#64748B;letter-spacing:0.04em;text-transform:uppercase;">Finwell AI</p>
        <h1 style="margin:0 0 16px;font-size:24px;line-height:1.3;color:#0B1F3B;">You are in. Your early access spot is locked in.</h1>
        <p style="margin:0 0 16px;font-size:16px;line-height:1.55;">${greeting}</p>
        <p style="margin:0 0 16px;font-size:16px;line-height:1.55;">Thanks for taking the survey. Your answers go straight into what we build first.</p>
        <p style="margin:0 0 16px;font-size:16px;line-height:1.55;">Beta access opens in the coming weeks. We will be in touch with details and updates as we build.</p>
        <p style="margin:0 0 24px;font-size:16px;line-height:1.55;">If you ever need to reach us, just reply to this email.</p>
        <p style="margin:0;font-size:14px;color:#64748B;line-height:1.55;">Finwell AI &mdash; Built in Melbourne for Australians who hate tax time.</p>
      </td></tr>
    </table>
  </body></html>`;
  return { subject, text, html };
}

async function sendWelcomeEmail(toEmail, firstname) {
  const apiKey = process.env.RESEND_API_KEY;
  if (!apiKey) {
    console.log('[submission-created] RESEND_API_KEY not set; skipping welcome email.');
    return;
  }
  const from = process.env.RESEND_FROM || RESEND_FROM_DEFAULT;
  const replyTo = process.env.RESEND_REPLY_TO || RESEND_REPLY_TO_DEFAULT;
  const { subject, text, html } = welcomeEmailContent(firstname);
  try {
    const res = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'authorization': `Bearer ${apiKey}`,
        'content-type': 'application/json',
      },
      body: JSON.stringify({
        from,
        to: [toEmail],
        reply_to: replyTo,
        subject,
        text,
        html,
      }),
    });
    if (!res.ok) {
      console.error('[submission-created] resend send failed', res.status);
    }
  } catch (e) {
    // Best-effort send. A failed welcome email never fails the submission.
    console.error('[submission-created] resend threw', e && e.message);
  }
}

export const handler = async (event) => {
  let payload;
  try {
    const parsed = JSON.parse(event.body || '{}');
    payload = parsed.payload || {};
  } catch (e) {
    console.error('[submission-created] failed to parse event body', e);
    return { statusCode: 400, body: 'bad event body' };
  }

  const data = payload.data || {};
  if (data['bot-field']) {
    // Honeypot tripped — ignore.
    return { statusCode: 200, body: 'honeypot' };
  }
  if (!data.email) {
    console.warn('[submission-created] no email on submission; skipping CRM + email.');
    return { statusCode: 200, body: 'no email' };
  }

  const properties = buildProperties(data);
  const firstname = clamp(data.name, NAME_MAX);

  const token = process.env.HUBSPOT_TOKEN;
  if (token) {
    const res = await fetch('https://api.hubapi.com/crm/v3/objects/contacts', {
      method: 'POST',
      headers: {
        'authorization': `Bearer ${token}`,
        'content-type': 'application/json',
      },
      body: JSON.stringify({ properties }),
    });

    // 409 = contact already exists. Update it instead.
    if (res.status === 409) {
      const idLookup = await fetch(
        'https://api.hubapi.com/crm/v3/objects/contacts/' + encodeURIComponent(data.email) + '?idProperty=email',
        { headers: { authorization: `Bearer ${token}` } }
      );
      if (idLookup.ok) {
        const found = await idLookup.json();
        const updateRes = await fetch(
          'https://api.hubapi.com/crm/v3/objects/contacts/' + found.id,
          {
            method: 'PATCH',
            headers: {
              authorization: `Bearer ${token}`,
              'content-type': 'application/json',
            },
            body: JSON.stringify({ properties }),
          }
        );
        if (!updateRes.ok) {
          // Log status only — HubSpot's response body can echo property values
          // that came from user input.
          console.error('[submission-created] hubspot update failed', updateRes.status);
        }
      }
    } else if (!res.ok) {
      console.error('[submission-created] hubspot create failed', res.status);
    }
  } else {
    console.log('[submission-created] HUBSPOT_TOKEN not set; skipping HubSpot sync.');
  }

  // Welcome email is best-effort and runs regardless of HubSpot outcome —
  // the customer experience should not depend on CRM availability.
  await sendWelcomeEmail(data.email, firstname);

  return { statusCode: 200, body: 'ok' };
};
