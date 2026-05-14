#!/usr/bin/env bash
# Minify + content-hash CSS/JS, then rewrite HTML references.
# Runs as the last Netlify build step (see [build].command in netlify.toml).
#
# Idempotent: if styles.css / app.js are already renamed to hashed variants
# (i.e. the un-hashed path no longer exists), the script exits cleanly so a
# second run during local debugging does not blow up.
#
# Tools (installed via package.json devDependencies, NOT npx --yes downloads):
#   - esbuild           -> CSS + JS minification (one tool, both jobs)
#
# Cache strategy after this script: filenames carry the content hash, so the
# matching headers rule in netlify.toml can set 1y immutable safely. A new
# deploy mints a new hash -> new URL -> bypasses any cached copy.

set -euo pipefail

CSS_SRC="assets/css/styles.css"
JS_SRC="assets/js/app.js"

if [[ ! -f "$CSS_SRC" && ! -f "$JS_SRC" ]]; then
  echo "optimize_assets: nothing to do (both source files already missing)."
  exit 0
fi

hash_first8() {
  # macOS: shasum is BSD. Linux/Netlify: shasum exists too (Perl-based).
  /usr/bin/shasum -a 1 "$1" | /usr/bin/awk '{print substr($1,1,8)}'
}

# --- CSS ---------------------------------------------------------------------
if [[ -f "$CSS_SRC" ]]; then
  echo "Minifying $CSS_SRC ..."
  TMP_CSS="$(/usr/bin/mktemp).css"
  npx --no-install esbuild --minify --loader:.css=css "$CSS_SRC" --outfile="$TMP_CSS" --allow-overwrite
  /bin/mv "$TMP_CSS" "$CSS_SRC"

  CSS_HASH="$(hash_first8 "$CSS_SRC")"
  CSS_DEST="assets/css/styles.${CSS_HASH}.css"
  /bin/mv "$CSS_SRC" "$CSS_DEST"
  echo "  -> $CSS_DEST ($(wc -c < "$CSS_DEST" | tr -d ' ') bytes)"
else
  echo "optimize_assets: $CSS_SRC missing — assuming pre-hashed."
  CSS_HASH=""
fi

# --- JS ----------------------------------------------------------------------
if [[ -f "$JS_SRC" ]]; then
  echo "Minifying $JS_SRC ..."
  TMP_JS="$(/usr/bin/mktemp)"
  npx --no-install esbuild --minify --target=es2019 "$JS_SRC" --outfile="$TMP_JS" --allow-overwrite
  /bin/mv "$TMP_JS" "$JS_SRC"

  JS_HASH="$(hash_first8 "$JS_SRC")"
  JS_DEST="assets/js/app.${JS_HASH}.js"
  /bin/mv "$JS_SRC" "$JS_DEST"
  echo "  -> $JS_DEST ($(wc -c < "$JS_DEST" | tr -d ' ') bytes)"
else
  echo "optimize_assets: $JS_SRC missing — assuming pre-hashed."
  JS_HASH=""
fi

# --- Rewrite HTML references ------------------------------------------------
# sed -i works differently on macOS vs Linux; the -i.bak form is portable.
# Recurse into subdirs so blog/**/*.html also gets the hashed asset paths.
# Exclude node_modules, the retired prototype archive, and tests.
while IFS= read -r -d '' f; do
  if [[ -n "${CSS_HASH:-}" ]]; then
    /usr/bin/sed -i.bak "s|/assets/css/styles\.css|/assets/css/styles.${CSS_HASH}.css|g" "$f"
  fi
  if [[ -n "${JS_HASH:-}" ]]; then
    /usr/bin/sed -i.bak "s|/assets/js/app\.js|/assets/js/app.${JS_HASH}.js|g" "$f"
  fi
  /bin/rm -f "${f}.bak"
done < <(/usr/bin/find . -type f -name '*.html' \
  -not -path './node_modules/*' \
  -not -path './docs/_archive/*' \
  -not -path './tests/*' \
  -not -path './.netlify/*' \
  -print0)

echo "optimize_assets: complete."
