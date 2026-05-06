#!/usr/bin/env bash
# Replace deploy-time placeholders in HTML files with values from env vars.
# Runs as the Netlify build step (see [build] command in netlify.toml).
#
# Required env vars (configure in Netlify UI → Site settings → Environment variables):
#   GA4_MEASUREMENT_ID    G-XXXXXXXXXX
#   COOKIEBOT_CBID        UUID from Cookiebot dashboard
#   RECAPTCHA_SITE_KEY    Public key from reCAPTCHA admin
#
# A missing var becomes the literal string "MISSING_<name>" so failures show up
# in browser console instead of producing a working tag with bogus credentials.

set -euo pipefail

GA4="${GA4_MEASUREMENT_ID:-MISSING_GA4_MEASUREMENT_ID}"
CBID="${COOKIEBOT_CBID:-MISSING_COOKIEBOT_CBID}"
RECAPTCHA_KEY="${RECAPTCHA_SITE_KEY:-MISSING_RECAPTCHA_SITE_KEY}"

echo "Injecting env into HTML files…"
echo "  GA4_MEASUREMENT_ID = ${GA4}"
echo "  COOKIEBOT_CBID     = ${CBID}"
echo "  RECAPTCHA_SITE_KEY = ${RECAPTCHA_KEY}"

# macOS sed and GNU sed differ; this form works on both.
for f in *.html; do
  [ -f "$f" ] || continue
  # Use a delimiter unlikely to appear in tokens.
  sed -i.bak \
    -e "s|__GA4_MEASUREMENT_ID__|${GA4}|g" \
    -e "s|__COOKIEBOT_CBID__|${CBID}|g" \
    -e "s|__RECAPTCHA_SITE_KEY__|${RECAPTCHA_KEY}|g" \
    "$f"
  rm -f "${f}.bak"
done

# Inject site key into app.js too — it reads window.__RECAPTCHA_SITE_KEY__.
APP_JS="assets/js/app.js"
if [ -f "$APP_JS" ]; then
  # Prepend a single-line set so we don't disturb the rest of the file.
  TMP="$(mktemp)"
  echo "window.__RECAPTCHA_SITE_KEY__ = '${RECAPTCHA_KEY}';" > "$TMP"
  cat "$APP_JS" >> "$TMP"
  mv "$TMP" "$APP_JS"
fi

echo "Env injection complete."
