#!/usr/bin/env bash
# Run the Playwright test suite against a deployed URL.
#
# Default target is production (https://finwellai-survey.netlify.app).
# Override with BASE_URL=https://staging-... ./scripts/run-tests.sh
#
# Optional first argument filters to a single suite:
#   ./scripts/run-tests.sh smoke
#   ./scripts/run-tests.sh e2e
#   ./scripts/run-tests.sh form
#   ./scripts/run-tests.sh regression

set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d node_modules ] || [ ! -d node_modules/@playwright ]; then
  echo "→ Installing dependencies (first run only)…"
  npm install
fi

if [ ! -d "$HOME/Library/Caches/ms-playwright" ] && [ ! -d "$HOME/.cache/ms-playwright" ]; then
  echo "→ Installing Playwright browsers (first run only)…"
  npx playwright install chromium
fi

export BASE_URL="${BASE_URL:-https://finwellai-survey.netlify.app}"
echo "→ Target: $BASE_URL"

SUITE="${1:-}"
if [ -n "$SUITE" ]; then
  npx playwright test "tests/${SUITE}.spec.js"
else
  npx playwright test
fi
