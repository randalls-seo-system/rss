
## Article spec is the source of truth

For ANY work in modules/content-production-v2/, read these first:
- docs/article-spec.md (the canonical Article Spec)
- docs/v2-module-architecture.md (file structure and module relationships)

When the spec and the code disagree, the spec wins. When the spec is unclear,
flag it for Randall — do not improvise.

## Frozen modules

The following modules are frozen during v2 build and MUST NOT be modified:
- modules/content-production/ (v1, kept as baseline)
- All mu-plugin modules (technical-seo, schema, redirects, linking, qa-gates, analytics)

If a v2 task seems to require modifying a frozen module, stop and ask.

## SERP credentials

SERP credentials live in ~/randalls-seo-system/.env (gitignored).
Structure:

    SERPER_API_KEY=...                primary Serper.dev key
    SERPER_API_KEY_FALLBACK=...       optional backup Serper account
    SERPAPI_KEY_PRIMARY=...           primary SerpAPI account
    SERPAPI_KEY_FALLBACK=...          backup SerpAPI account for quota fallback

Provider strategy: Serper.dev primary (cheaper, 2500 free/month).
SerpAPI used only for features Serper doesn't expose (e.g. Google AI Mode).
Multi-account fallback transparently retries on quota errors.

To rotate keys: edit .env directly with a text editor. Never paste keys
into chat or shell commands that echo values to scrollback. Verify with:

    awk -F= '{print $1": "length($2)" chars"}' ~/randalls-seo-system/.env

Future sessions: do NOT ask the user to enter keys via prompt or script.
Keys live in .env permanently.

## GSC API credentials

Service account JSON lives at `~/randalls-seo-system/.gsc-credentials.json` (gitignored).
Fallback: `~/valn-rewrite/.gsc-credentials.json`. Required packages: `google-api-python-client`, `google-auth`.

To grant a new site access: In Google Search Console → Settings → Users and permissions → Add `valn-125@igneous-trail-449919-r4.iam.gserviceaccount.com` as a Full user.

Each site's `GSC_PROPERTY` is set in `sites/<slug>.conf` (e.g., `GSC_PROPERTY="sc-domain:example.com"`).

## Article generation rules (do not violate)

- Article HTML must NOT include inline TOC. RSS TOC Manager renders TOC
  at WordPress render time. Adding inline TOC creates duplicate/conflicting
  rendering.
- Section builders must produce content with ZERO internal links. Link
  injection is single-pass via inject-internal-links.py only.
- Anchor pool excludes the current article from its own link candidates.
- H2s must be natural-language, not keyword-stuffed SEO-2012 patterns.
