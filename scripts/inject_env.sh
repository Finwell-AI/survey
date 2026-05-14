#!/usr/bin/env bash
# Replace deploy-time placeholders in HTML files with values from env vars.
# Runs as the Netlify build step (see [build] command in netlify.toml).
#
# Required env vars (Netlify UI → Site settings → Environment variables):
#   GA4_MEASUREMENT_ID    G-XXXXXXXXXX
#   COOKIEBOT_CBID        UUID from Cookiebot dashboard
#   RECAPTCHA_SITE_KEY    public key from reCAPTCHA admin
#
# A missing var becomes the literal string "MISSING_<name>" so the failure
# shows up in the browser console instead of producing a working tag with
# bogus credentials.
#
# All values are passed through escape_sed before interpolation so that a
# value containing a sed delimiter (`|`) or escape (`\`) or replacement
# special (`&`) cannot break the substitution or inject extra commands.

set -euo pipefail

# Escape characters that are special in a sed `s|FROM|TO|` REPLACEMENT.
# Order matters: escape backslashes first so we don't double-escape ours.
escape_sed() {
  printf '%s' "$1" | /usr/bin/sed -e 's/\\/\\\\/g' -e 's/|/\\|/g' -e 's/&/\\\&/g'
}

# Escape for embedding inside a JS single-quoted string literal: backslash
# becomes \\ and single-quote becomes \'. Strip CR/LF defensively in case an
# env var came from a Windows clipboard.
escape_js_squote() {
  printf '%s' "$1" \
    | /usr/bin/tr -d '\r\n' \
    | /usr/bin/sed -e 's/\\/\\\\/g' -e "s/'/\\\\'/g"
}

GA4_RAW="${GA4_MEASUREMENT_ID:-MISSING_GA4_MEASUREMENT_ID}"
CBID_RAW="${COOKIEBOT_CBID:-MISSING_COOKIEBOT_CBID}"
RECAPTCHA_KEY_RAW="${RECAPTCHA_SITE_KEY:-MISSING_RECAPTCHA_SITE_KEY}"

GA4=$(escape_sed "$GA4_RAW")
CBID=$(escape_sed "$CBID_RAW")
RECAPTCHA_KEY=$(escape_sed "$RECAPTCHA_KEY_RAW")
RECAPTCHA_KEY_JS=$(escape_js_squote "$RECAPTCHA_KEY_RAW")

echo "Injecting env into HTML files…"
echo "  GA4_MEASUREMENT_ID = ${GA4_RAW}"
echo "  COOKIEBOT_CBID     = ${CBID_RAW}"
echo "  RECAPTCHA_SITE_KEY = ${RECAPTCHA_KEY_RAW}"

# macOS sed and GNU sed differ on -i; the `-i.bak` form works on both.
# Scan root + blog/** so generated blog pages also get __VAR__ substitutions.
# Exclude node_modules, the retired prototype archive, and tests.
while IFS= read -r -d '' f; do
  /usr/bin/sed -i.bak \
    -e "s|__GA4_MEASUREMENT_ID__|${GA4}|g" \
    -e "s|__COOKIEBOT_CBID__|${CBID}|g" \
    -e "s|__RECAPTCHA_SITE_KEY__|${RECAPTCHA_KEY}|g" \
    "$f"
  /bin/rm -f "${f}.bak"
done < <(/usr/bin/find . -type f -name '*.html' \
  -not -path './node_modules/*' \
  -not -path './docs/_archive/*' \
  -not -path './tests/*' \
  -not -path './.netlify/*' \
  -print0)

# Inject site key into app.js too — it reads window.__RECAPTCHA_SITE_KEY__.
# Idempotent: if a previous run already prepended a key line, replace it
# rather than stacking another one on top.
APP_JS="assets/js/app.js"
if [[ -f "$APP_JS" ]]; then
  if /usr/bin/head -1 "$APP_JS" | /usr/bin/grep -q '^window\.__RECAPTCHA_SITE_KEY__ = '; then
    # The sed replacement contains a JS-quoted value; that value must ALSO
    # have any sed-special chars (|, \, &) escaped before interpolation.
    RECAPTCHA_LINE="window.__RECAPTCHA_SITE_KEY__ = '${RECAPTCHA_KEY_JS}';"
    RECAPTCHA_LINE_ESC=$(escape_sed "$RECAPTCHA_LINE")
    /usr/bin/sed -i.bak \
      "1s|^window\\.__RECAPTCHA_SITE_KEY__ = .*|${RECAPTCHA_LINE_ESC}|" \
      "$APP_JS"
    /bin/rm -f "${APP_JS}.bak"
  else
    TMP="$(/usr/bin/mktemp)"
    /usr/bin/printf "window.__RECAPTCHA_SITE_KEY__ = '%s';\n" "$RECAPTCHA_KEY_JS" > "$TMP"
    /bin/cat "$APP_JS" >> "$TMP"
    /bin/mv "$TMP" "$APP_JS"
  fi
fi

echo "Env injection complete."
