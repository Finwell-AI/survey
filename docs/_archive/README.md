# Archive — superseded build artefacts

Frozen on 2026-05-07 when the site moved to direct-edit HTML pages. The
files in this directory were the original prototype-driven build pipeline.
They are kept for rollback and historical reference only — none of them are
read by the live build.

## What lives here

| File | What it was |
| --- | --- |
| `finwellai_prototype_v5 (1).html` | Single-file SPA prototype. Body content for home + survey was sliced out of this file by `build_pages.py`. |
| `build_pages.py` | Generated `index.html`, `survey.html`, `thanks.html` from the prototype + Python templates. Also held the shared `URGENT_BANNER`, `SHARED_FOOTER`, `CHAT_FAB` constants imported by `build_legal_pages.py`. |
| `extract_prototype.py` | One-shot script that did the initial split of inline CSS / JS / base64 images out of the prototype into `assets/`. Already run; reruns would clobber hand-edits. |
| `patch_css.py` | One-shot CSS patcher for the Inter `@font-face` block + image-path normalisation. Already run. |

## Why they were retired

The prototype-to-page pipeline was built for the SPA → multi-page conversion.
That conversion is done. The pipeline kept costing edits in two places (the
prototype + the published HTML or the build script) and the prototype itself
is 855 KB of stale SPA scaffolding that the build script then strips back
out. See the audit discussion in commit history.

## Current source of truth

| Page | Edit | Then run |
| --- | --- | --- |
| `/`, `/survey`, `/thanks` | the published `index.html` / `survey.html` / `thanks.html` directly | nothing |
| `/privacy`, `/terms` | `content/privacy.md` / `content/terms.md` | `python3 scripts/build_legal_pages.py` |
| Banner / footer copy | edit in all 4 places: `index.html`, `survey.html`, `thanks.html`, plus the `URGENT_BANNER` / `SHARED_FOOTER` constants in `scripts/build_legal_pages.py` | `python3 scripts/build_legal_pages.py` |
| Env-var placeholders (`__GA4_MEASUREMENT_ID__` etc.) | leave as-is; `scripts/inject_env.sh` substitutes at deploy time | `netlify build` |

## To roll back

If direct HTML editing turns out to be worse than the build pipeline:

1. `git mv docs/_archive/build_pages.py scripts/`
2. `git mv "docs/_archive/finwellai_prototype_v5 (1).html" docs/`
3. Restore `python3 scripts/build_pages.py &&` at the start of the
   `[build].command` in `netlify.toml`.
4. Revert the inline `URGENT_BANNER` / `SHARED_FOOTER` / `CHAT_FAB` /
   `COOKIEBOT_ENABLED` block in `scripts/build_legal_pages.py` and put
   the `from build_pages import (...)` line back.
5. Run `python3 scripts/build_pages.py` to regenerate the pages.
