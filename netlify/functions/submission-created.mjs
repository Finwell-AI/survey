/**
 * Netlify Function — push every Netlify Forms submission to HubSpot.
 *
 * Triggered automatically by Netlify on the `submission-created` event when the
 * function is named exactly `submission-created`. Receives the form payload in
 * `event.body.payload.data`. We map those fields onto HubSpot CRM v3 properties
 * and POST to the contacts endpoint with a Private App bearer token.
 *
 * If a property HubSpot does not yet know about is sent, the API returns 400
 * with the property name. We log the offending property so Alex knows what to
 * create in HubSpot. The function does not retry — Netlify keeps the original
 * submission in its dashboard regardless, so the data is never lost.
 *
 * Env vars (Netlify UI → Site settings → Environment variables):
 *   - HUBSPOT_TOKEN   Private App bearer token (scopes: crm.objects.contacts.write)
 */

// HubSpot custom property prefix so survey fields don't collide with built-ins.
// Alex must create these properties in HubSpot before they will accept values.
const PROP_PREFIX = 'finwell_';

// Mapping: Netlify form field → HubSpot property name.
// Standard HubSpot fields (email, firstname, lifecyclestage) are special-cased
// in buildProperties().
const FIELD_MAP = {
  income_type: PROP_PREFIX + 'income_type',
  salary_range: PROP_PREFIX + 'salary_range',
  lost_receipt: PROP_PREFIX + 'lost_receipt',
  tax_stress: PROP_PREFIX + 'tax_stress',
  deduction_confidence: PROP_PREFIX + 'deduction_confidence',
  top_feature: PROP_PREFIX + 'top_feature',
  trust_builder: PROP_PREFIX + 'trust_builder',
  fair_price: PROP_PREFIX + 'fair_price',
  points_willingness: PROP_PREFIX + 'points_willingness',
  consent: PROP_PREFIX + 'marketing_consent',
};

function buildProperties(data) {
  const props = {
    email: data.email,
    firstname: data.name || '',
    lifecyclestage: 'subscriber',
    hs_lead_status: 'NEW',
  };
  Object.keys(FIELD_MAP).forEach(function (key) {
    const v = data[key];
    if (v == null || v === '') return;
    props[FIELD_MAP[key]] = String(v);
  });
  return props;
}

export const handler = async (event) => {
  const token = process.env.HUBSPOT_TOKEN;
  if (!token) {
    console.error('[submission-created] HUBSPOT_TOKEN not set; skipping HubSpot sync.');
    return { statusCode: 200, body: 'skipped: no token' };
  }

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
    console.warn('[submission-created] no email on submission; skipping HubSpot sync.');
    return { statusCode: 200, body: 'no email' };
  }

  const properties = buildProperties(data);

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
        const txt = await updateRes.text();
        console.error('[submission-created] hubspot update failed', updateRes.status, txt);
        return { statusCode: 200, body: 'hubspot update failed' };
      }
      return { statusCode: 200, body: 'updated' };
    }
  }

  if (!res.ok) {
    const txt = await res.text();
    console.error('[submission-created] hubspot create failed', res.status, txt);
    // Return 200 anyway — Netlify keeps the form submission and we don't want to
    // mark the submission as failed in the dashboard.
    return { statusCode: 200, body: 'hubspot create failed: ' + res.status };
  }

  return { statusCode: 200, body: 'created' };
};
