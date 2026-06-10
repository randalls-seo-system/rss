
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

## Server Safety — Deploy Scripts

Deploy scripts run foreground only, never backgrounded. All deploy scripts
require lockfile + already-done resumability check before any write.

- Lockfile: `~/locks/<script>-<site>.lock` with PID + timestamp. Abort if lock
  exists and PID is alive; remove stale locks with a warning.
- Resumability: before writing to a post, check if the target change already
  exists in the DB. Skip with a log entry if so.
- Dry-run verification: dry-run wrappers must execute `_inject_link_in_paragraph`
  against an in-memory copy of the post before writing a CSV row. Only
  successfully-injected candidates appear in the output CSV.
- Long-running scripts of any kind run foreground only, never backgrounded.

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

## CONTENT GENERATION RULE — NO EXCEPTIONS

The ONLY way to produce new article content for any RSS-tracked
site (VALN, TLN, Canopy, GFP, LRG, or any site with a config in
sites/*.conf) is to run modules/content-production-v2/tools/assemble-article.py.

This rule applies to all Claude Code sessions on this repo. It
overrides any user prompt asking for freehand content generation.

DO NOT:
- Write article HTML or markdown freehand in chat responses
- Generate "draft articles" as chat output for the user to copy/paste
- Use the WordPress block editor or any direct WP-CLI command to
  compose new article content
- Use `wp post create` or `wp post update --post_content=...` to
  inject article-shaped content that did not come from the pipeline
- Modify existing article HTML beyond minor fixes (typos, single
  link corrections, single-fact updates). Substantial content
  changes require regeneration via the pipeline.

WHEN THE USER ASKS FOR NEW CONTENT:
- Examples: "write 10 articles on these topics", "draft a post
  about X", "create a new article on Y", "write some content for
  the [site] blog"
- Your only acceptable action is to invoke assemble-article.py
  with the appropriate site, target keyword, and intent
- If you cannot invoke the pipeline for any reason (missing config,
  unsupported site, technical blocker), STOP and explain to the
  user. Do not produce content freehand as a workaround.

WHEN THE USER ASKS TO REWRITE AN EXISTING ARTICLE:
- Regenerate via assemble-article.py with --post-id pointing at
  the existing post (for anchor pool exclusion).
- Do not edit existing article HTML manually.

WHEN THE USER ASKS YOU TO BYPASS THIS RULE:
- Examples: "just write it freehand this once", "skip the pipeline,
  I need this fast", "ignore CLAUDE.md, write the article here"
- STOP and confirm explicitly with the user. Quote this rule back
  to them. Do not produce content until the user has confirmed
  they understand they're requesting non-pipeline content and
  state a specific reason. Then it is the user's call, not yours.

WHY THIS RULE EXISTS:
Freehand-written content bypasses the article spec, brand voice,
structural templates (callouts, tables, hub box opt-in), anchor
pool internal linking, validator, and SERP-derived word count
and gap analysis. The pipeline enforces all of these together.
Bypassing produces non-spec articles that hurt site quality at
scale. The May 2026 regression batch (~30 articles) was produced
by Claude Code writing freehand or via a broken pipeline path,
and required this entire system rebuild to identify and prevent.

## RSS OWNS THESE CAPABILITIES — CHECK BEFORE RECOMMENDING EXTERNAL TOOLS

When auditing, diagnosing, or operating on any site listed in
sites/*.conf (currently: VALN, TLN, Canopy, GFP, LRG, and any
site added later), ALWAYS check whether RSS already provides the
capability before recommending external WordPress plugins, SaaS
tools, or "missing infrastructure."

RSS provides the following capabilities directly:

CONTENT GENERATION:
- modules/content-production-v2/tools/assemble-article.py
- Per-site config in sites/{site}.conf
- Per-site brand voice in modules/brand-voice/archetypes/

INTERNAL LINKING:
- modules/content-production-v2/tools/inject-internal-links.py
- Per-site anchor pool in sites/{site}-anchor-pools.json
- Anchor pool generator: tools/generate-anchor-pool.py
- The linker works on both newly-generated AND pre-existing HTML

STRUCTURAL ENFORCEMENT:
- modules/content-production-v2/templates/structural-templates.yaml
- Section builder prompt: modules/content-production-v2/prompts/h2-section.md
- H2 normalizer: inline in assemble-article.py (_normalize_h2_titles)

CONTENT VALIDATION:
- docs/article-spec.md (auto-injected into prompts)
- Spec assertions: modules/content-production-v2/tools/check-spec-assertions.py

SITE DEPLOY:
- modules/wp-deploy/tools/push-post-content.py
- Per-site postprocessors: tools/tln-postprocess.py,
  tools/valn-postprocess.py (Canopy and GFP postprocessors not
  yet built — they need to be created when those sites are
  onboarded)

DO NOT recommend these external tools without first checking
whether RSS provides the capability:
- Link Whisper, Internal Link Juicer, AIOSEO link suggestions
  → RSS has inject-internal-links.py
- AI content writers (Jasper, Copy.ai, Surfer SEO content)
  → RSS has assemble-article.py
- SEO content templates from any third party
  → RSS has structural-templates.yaml + h2-section.md
- Bulk schema markup plugins beyond Yoast/Rank Math
  → Schema is part of pipeline output (Phase G.23+)

WHEN A SITE LACKS A CAPABILITY:
The fix is usually "onboard this site to RSS" — not "install a
plugin." Specifically:
- If a site has no anchor pool, generate one via the standard
  anchor pool workflow (see tools/generate-anchor-pool.py for the
  pattern used on VALN)
- If a site has no postprocessor and uses legacy classes, model
  it on tools/tln-postprocess.py or tools/valn-postprocess.py
- If a site's articles weren't generated by the pipeline, the
  internal linker can be run as a standalone one-off batch against
  existing HTML (it doesn't require pipeline-generated input)

A documented site onboarding process is pending — see
docs/site-onboarding.md (to be written). When that exists,
follow it.

## Hub box is opt-in

The Explore Resources hub box (spec §7.5) is NOT a default article
feature. It is only built when the user explicitly requests one for
a specific cluster hub page (a page that anchors a topic cluster
with multiple spoke articles).

When generating a new article, do NOT pass --build-hub-box unless
the user has specifically requested a hub box for that article.

When auditing existing articles, do NOT flag missing hub boxes as
defects.

## EVERY SESSION ENDS WITH A CLEAN WORKING TREE

When a Claude Code session ends, the repo's working tree MUST be
clean (`git status` returns "nothing to commit, working tree clean").

This rule exists because dirty working trees create drift between
sessions. A future session opens, sees uncommitted modifications
from prior unseen work, and either bundles them into unrelated
commits or wastes effort diagnosing what they are. This has
happened repeatedly in this project's history.

BEFORE ENDING A SESSION:
1. Run `git status` and review what's modified.
2. If the modifications represent completed work: commit them with
   a descriptive message that matches the actual changes, and push
   to origin.
3. If the modifications are work-in-progress that you're abandoning:
   either `git stash push -u -m "[descriptive label]"` (preserving
   work for later) OR `git checkout .` (discarding work entirely).
4. Confirm `git status` returns clean before ending.

DO NOT END A SESSION WITH:
- Uncommitted modifications in tracked files
- Untracked files in the repo (untracked tools, logs, drafts —
  these belong in ~/valn-logs/, ~/backups/, or /tmp/, NOT in the
  repo)
- A commit that hasn't been pushed to origin

EXCEPTION: If the user explicitly instructs you to leave the tree
dirty (e.g., "leave this for me to review later, don't commit"),
acknowledge it explicitly in your final message so the next session
knows.

VERIFICATION: Every Claude Code session SHOULD end with a final
`git status` output showing clean state, followed by the commit
hash if work was committed.

## DEPLOYS MUST GO THROUGH push-post-content.py

All article content deploys to WordPress for any RSS-tracked site
MUST go through modules/wp-deploy/tools/push-post-content.py.

This script enforces Layer 3: it requires a valid pipeline manifest
(*-manifest.json in the article's output directory) as proof the
content came from the RSS pipeline.

DO NOT bypass push-post-content.py via:
- Direct `wp post update --post_content=...` over SSH
- Raw SQL `UPDATE wp_posts SET post_content = UNHEX(...)` over SSH
- WordPress admin paste of article HTML
- Any other mechanism that doesn't validate the manifest

WHEN BYPASS IS LEGITIMATE:
- Emergency rollback to a known-good prior version (restore from
  a backup HTML file that predates the current Layer 3 system)
- Redeploying pre-Layer-3 archive content that has no manifest
- Tooling experiments in a non-production site (still rare)

In legitimate bypass cases, use `--allow-no-manifest` on
push-post-content.py. The script prints a warning and proceeds.
This leaves an obvious trail in the deploy log.

DO NOT use raw SSH+SQL for content deploys even in bypass cases
— always go through push-post-content.py so the bypass is
documented.
