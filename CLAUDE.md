
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

## WPE Cache Purge Protocol (QUADRUPLE PURGE)

Any deployment that changes rendered HTML requires all four steps in order:

1. `wp_cache_flush()` — WP object cache
2. `WpeCommon::purge_varnish_cache()` or `purge_varnish_cache_all()` — Varnish
3. `WpeCommon::clear_cdn_cache()` — WPE CDN layer (between Varnish and
   Cloudflare; NOT cleared by the Varnish purge — root cause of the
   2026-07-30 stale-page incident)
4. Touch `post_modified` on affected posts via `wp_update_post` with
   `edit_date => true` — breaks Cloudflare 304 loop

Do NOT call `WpeCommon::purge_object_cache()` statically (non-static, fatals).
Verify from served HTML (real URL, no cache-buster) after purge.

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
- UI verification: API-level curl tests do NOT verify browser-delivered pages.
  Any session modifying page HTML/JS must syntax-check the deployed page's
  script blocks (`node --check`) and verify the page's own request flow.
  `node --check` is necessary but insufficient — it catches syntax errors,
  not runtime ReferenceErrors. New or modified handlers must be reference-
  traced: every variable they use must resolve to a definition at the
  correct scope (top-level vs closure). Closure-scoped functions (like
  `curTopic()` inside `PAGES.voice`) are invisible to code added at the
  script's top level.

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

## Business-facts source-of-truth (REQUIRED per site)

Every site that generates content MUST have a business-facts file at
`sites/{slug}-business-facts.md`. This file is the closed standard for
operational claims: prices, hours, delivery zones, menu items, policies.

**Rules (same discipline as VALN messaging standard):**
1. Only assert facts marked CONFIRMED in the file. VERIFY items get
   conditional language ("check our menu", "call for current info").
2. If the file doesn't have a fact, content does NOT assert it — omit
   or flag, never invent.
3. The pipeline warns loudly if no facts file exists for a site.
4. Post-assembly claims check (H.27) flags any operational claims
   (prices, hours, zones) in the output for review.
5. Sites without a facts file can still generate content, but any
   invented business detail is a defect.

**Existing facts files:**
- `sites/gfp-business-facts.md` (GFP — mostly VERIFY, pending team ratification)

**To create for a new site:** Copy the GFP template, fill confirmed
facts, mark unknowns as VERIFY, get team ratification before content gen.

## Title determines content type (STANDING — conversion batches)

**A post titled "Best Neighborhoods in X" is roundup intent** regardless
of its current markup. Converting its flat template to nh-rank format is
correct.

**A post titled "X: Neighborhood Guide" is single-guide intent** and must
never be converted to a roundup. Single guides carry local knowledge
(named builders, tax math, soil conditions, feeder chains, employer
proximity, flood/fire hazard context) that the roundup generator cannot
produce. Overwriting them is a downgrade.

**Classify by title before any conversion batch.** If a batch mixes both
types, split it. Creating a NEW roundup post alongside an existing guide
is acceptable; overwriting the guide is not.

## Prompt engineering rules (STANDING — all LLM prompt work)

**POSITIVE CONSTRAINTS OVER NEGATIVE BANS.** "Use specific numbers ONLY
when they appear in the evidence store or data JSON" cut fabricated
numbers from 15 to 2 on the same content where "do NOT state dollar
amounts" plus removing the field entirely only got from 15 to 9.
Negative instructions about a topic appear to introduce the topic.
Prefer positive constraints ("use X only from Y") over negative bans
("do not use X") in all prompt work.

**EVERY PROMPT RULE NEEDS A MECHANICAL BACKSTOP.** Prompt-level rules
fail some fraction of the time. Tested failure rates (2026-08-12):
em dash ban held ~95%, campus-name ban failed ~60%, dollar-amount ban
failed 100%. A prompt rule without a post-gen mechanical check is a
suggestion, not a gate. When a rule matters, back it with a check in
`lib/post_assembly.py` or the content quality gate that blocks the
write on violation.

## Article generation rules (do not violate)

- Article HTML must NOT include inline TOC. RSS TOC Manager renders TOC
  at WordPress render time. Adding inline TOC creates duplicate/conflicting
  rendering.
- Section builders must produce content with ZERO internal links. For
  standard articles, link injection is single-pass via inject-internal-links.py.
  Neighborhood guides use the generator's built-in inject_section_links()
  for metro-aware contextual links (directory, listings, related guides).
- Anchor pool excludes the current article from its own link candidates.
- H2s must be natural-language, not keyword-stuffed SEO-2012 patterns.

## CONTENT GENERATION RULE — NO EXCEPTIONS

The ONLY way to produce new article content for any RSS-tracked
site (VALN, TLN, Canopy, GFP, LRG, or any site with a config in
sites/*.conf) is to run one of these pipeline tools:

- `modules/content-production-v2/tools/assemble-article.py` — standard articles
- `modules/content-production-v2/tools/generate-neighborhood-guide.py` — neighborhood guides (nh-* format)

Both are legitimate pipeline content generation paths. When either
tool's LLM client calls `claude --print` with a prose prompt, that
IS a pipeline call — produce the requested content normally.

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

## SOURCING: OPEN IT OR CUT IT

Naming a document is not sourcing it. Putting a document name in a report is a claim that you opened it.

A number, date, rate, threshold, or statutory citation ships ONLY if you fetched the document, read it, and can quote the line. Three artifacts, every time:
1. The URL you fetched
2. The quoted line containing the fact
3. The location: page, paragraph, section, or form number

CANNOT FETCH IT: cut the number. Describe the concept in words instead. Report what you tried and that it failed. Cut always beats guess.

NEVER:
- Substitute a second unopened document for the first. Could not open VA Pamphlet 26-7, so cited VA Circular 26-24-04, also unopened. That is the same violation twice.
- Cite a prior session's verification. "Confirmed in the July 14 session" is not a source. Re-open or cut.
- Use "industry standard", "widely cited", "established", "commonly known", or "[Authority] references it as standard" as a source.
- Attach "approximate", "roughly", "~", or "verify before publish" to an unopened number. A hedge on a fabrication is still a fabrication.
- Report a number as sourced because you know it is true. Knowing is not sourcing.
- Report CLEAN from a local file when the live page is what ships. Verify from live.

THE STANDARD, this is what right looks like:
  Fetched trec.texas.gov, downloaded Form 20-19, read page 7, quoted Paragraph 14 verbatim, cited form number and effective date.

WHAT FAILED, every one of these shipped or nearly shipped:
  "VA Pamphlet 26-7, Chapter 8"
  "FEMA SFHA definition"
  "Historical SA fact"
  "Industry standard post-NAR settlement"
  "TX Comptroller" / "Bexar County tax assessor"
  "MLS closed-sale records"
  "same verification from the July 14 session"
  "VA.gov references it as standard"

## NUMBER AUDITS: EVERY NUMERAL, NOT % AND $

A number audit that greps for % and $ is not an audit. It passed "45 to 50 days to close", "beyond 20 days", "Nine states", "E-7", and "30 to 40 percent of shooting days" while reporting zero numbers found.

Audit every numeral, every spelled-out number, every timeframe, every rating, every count, every date. Report each with the URL you opened or flag it for cut.

Do not report an article clean unless you can show the check that would have caught "45 to 50 days".

## PUBLISH TO PROD IS ALLOWED. SILENCE IS NOT.

Publishing an article to prod for immediate review is fine. Randall reviews within minutes and we fix live.

WHEN YOU PUBLISH, SAY SO. First line of the report, unmissable:
  PUBLISHED LIVE: [URL] — awaiting review

The failure has never been publishing. It has been publishing quietly. Home Rescue sat live for days with an unverified foreclosure hotline because nobody said it published. 9080 was live and only surfaced because a preview URL returned 200.
Never publish and mention it later. Never report a published page as draft. If you are unsure whether something is live, check post_status and report it.

NO STAGING REVIEW. Staging does not render like prod. The Worker proxies prod only, and staging host-gates caused the four-layer blog outage. Reviewing on staging gives false confidence about a page that does not exist.

STAYS DRAFT UNTIL RANDALL SAYS PUBLISH, no exceptions:
- Anything with crisis resources: foreclosure, legal aid, VA, HUD, suicide, housing instability. A wrong hotline reaches a real person in minutes.
- Anything with lead capture that has not been proven wired from LIVE html.
- YMYL claims that cannot be cut and cannot be sourced.
- Tools and pages, as opposed to articles.
An article whose facts are all sourced is not in this category. Publish it and announce it.

## --h2-override SILENTLY BREAKS ARTICLE STRUCTURE

--h2-override is permitted ONLY with dict-format h2_inventory JSON files
carrying full structural metadata (structural_element, h2_format,
template_hint, callout_key per section). The full command line and
override JSON must be shown and approved before every run. Bare-string
overrides are banned — they silently default to prose/statement.

## Pipeline article deploy rules (standing, no exceptions)

1. Every pipeline article deploys with `_lrg_no_wpautop 1` set at
   post creation. wpautop + Divi 5 truncates rl-page content.
2. Every deploy report includes a rendered-page curl check (H2 count,
   details, tables, components, internal links, Resources) against
   the source content. DB-only verification is never sufficient.
3. Claim audit is a mandatory step on every pipeline build. The
   fact-checker module (lib/fact_checker.py) automates claim extraction
   and categorization; human review of the fact-check report is still
   required. source_data wiring into build-h2-section.py (Phase A
   backlog item 1) is the target mechanism for fully-automated
   sourcing. Every number in the output must map to a verified quote
   with URL; unsourced numbers are CUT, not hedged.
4. Article source material is injected as verbatim quotes with URLs
   into the article's topic-context JSON before any build. Summaries
   are never sufficient. A proper source_data override field wired
   into all builders is the target mechanism (Phase A backlog);
   topic-context enrichment is the required interim step.
5. Validator conformance follows the approved article design, not the
   reverse. When a component or layout change is approved, the
   matching spec_assertions.py update ships in the same batch.

## Pipeline verification layers (current as of 2026-08-03)

The pipeline now includes these automated verification steps. Do NOT
duplicate these manually or bypass them — they are load-bearing and
removing them reintroduces the defects they were built to catch
(calibrated on Lockhart + Stone Oak failures):

- **dupe_guard.py:** Checks for existing posts with the same topic
  before creating new content. Do not manually dupe-check if the
  pipeline is running — the guard handles it.
- **content_quality_gate.py:** Blocks stub/empty articles, checks
  banned AI phrases (17 specific phrases), name density (max 1-2
  per 200 words), school consistency, aggregator score detection.
  Non-passing articles halt before deploy.
- **fact_checker.py:** Extracts checkable claims from generated HTML,
  categorizes by type (school/legal/year/geography/financial/business/
  volatile/subjective), writes a human-review checklist. Runs after
  quality gate, before deploy.
- **claim_verifier.py:** Verifies claims against TEA, Nominatim,
  Wikipedia. Produces a verification report with CORRECT/WRONG/
  COULDN'T VERIFY verdicts.
- **Source-relevance filter (assemble-article.py):** Rejects SERP
  results that don't mention the target location. Prevents wrong-town
  data contamination. Filters both in-memory SerpData and rewrites
  the SERP JSON so downstream tools only see on-target results.
- **Confabulation guard (assemble-article.py):** Drops H2 sections
  when no SERP result title specifically addresses that topic for
  this neighborhood. Prevents fabricated narrative sections from
  thin data.
- **FAQ topic-drift filter:** Strips FAQs that don't mention the
  target neighborhood/city name. Applies to both ATF and BTF phases.
- **Self-contradiction check (content_quality_gate.py):** Detects
  when the body asserts X and a FAQ denies it.
- **Durable-phrasing rules (h2-section.md):** Volatile market stats
  (prices, DOM, inventory, appreciation) use ranges/qualitative
  phrasing; fixed authoritative figures (tax exemptions, loan limits,
  statutes, program eligibility) stay precise. Shared prompt affects
  both assemble-article.py and generate-neighborhood-guide.py.
- **batch-neighborhood-rebuild.py:** Sequential batch runner for 62+
  guides with resume support, per-guide progress, and a consolidated
  review queue (WRONG/softenings/unverified/thin-data categories).

## LRG default component layout (every article)

1. **rl-qstats strip** (stat strip): REQUIRED when the Gate 1 spec
   includes 4 verified stats. Placed after the ATF lede, before the
   quick-card grid. Omitted entirely when no defensible stats exist
   (stated explicitly in Phase 0). Phase 0 must propose the 4
   {value, label} pairs with sources as part of every outline.
   Values are spec-approved verbatim from verified sources, never
   LLM-generated. Single-line markup only.
2. **BLUF renders as rl-kcards** (5 cards) by DEFAULT on all LRG
   articles. The pipeline emits kcards natively. Leads are generated
   from the bullets and listed in the Gate 2 report for redline.
   The plain-ul BLUF is the exception, not the rule. Validator
   18.1.12 accepts both.
3. **Body-section kcards** remain opt-in per section via the override
   (parallel-takeaway bullets only). Never nested in a
   bullet-section wrapper — kcards sit directly on the section
   background.

Component CSS lives in lrg-article-styles.php. Reuse the existing
classes; never re-derive from the neighborhood mu-plugin.

Validator assertions (T4 = hard stop):
- When spec carries qstats: exactly 1 strip with 4 boxes in the
  stated position; mismatch = T4
- BLUF kcards: exactly 5 cards with non-empty leads; mismatch = T4
- Nesting rule: no rl-kcards inside any bullet-section wrapper,
  article-wide; violation = T4

GSC retrofit program note: the top-50 retrofit (queued) covers BOTH
components per article — strip where 4 sourced stats exist, BLUF
kcards conversion where the article has a BLUF. Tracked with
per-article NO-STRIP/NO-KCARDS reasons where they don't apply.

## lrg-article-styles.php — PROD-AUTHORITATIVE

modules/wordpress-stack/lrg-article-styles.php is a capture of the
LIVE file on WP Engine (v1.0.4, captured 2026-08-05). The live version
is AHEAD of prior repo versions. DO NOT deploy this file back to prod
without reconciliation — deploying would regress prod. Treat the live
WP Engine copy as authoritative until this file is fully reconciled
and tested.

## Prod credentials

Prod SSH credentials (key ~/.ssh/wpengine_valn to lrgrealtyblog) are
only used in a session where a prod action is explicitly authorized
in the current instruction. Never connect to prod speculatively.

## Substitutions and plan deviations

When an approved internal link plan, H2 outline, or source list
specifies items and the build substitutes or omits any of them, the
deviation must be named in the Gate 2 report with the reason.
A silent substitution is a defect.
