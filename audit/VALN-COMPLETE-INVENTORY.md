# VALN Infrastructure Inventory — Complete Audit

**Date:** 2026-05-04
**Audited by:** Claude Code (Opus 4.6)
**Scope:** Production site (valoannetwork.com) + local ~/valn-rewrite/
**Purpose:** Catalog all VALN infrastructure for RSS v2.0 expansion planning

---

## What's Already in RSS v1.0

### MU-Plugins Migrated (6)
| Plugin | Lines | Purpose |
|--------|-------|---------|
| valn-ai-crawler-log.php | 278 | Logs AI crawler hits (GPTBot, ClaudeBot, etc.) |
| valn-dashboard-ai-crawlers.php | 232 | WP Admin page for AI crawler activity |
| valn-llms-config.php | 157 | Shared config for AI retrieval — curated page list |
| valn-llms-full-txt.php | 172 | Single-file markdown export at /llms-full.txt |
| valn-llms-txt.php | 112 | Dynamic llms.txt at /llms.txt |
| valn-markdown-variants.php | 279 | ?format=md endpoint for AI crawler ingestion |

### QA Audit Checks Migrated (4)
| Audit | Purpose |
|-------|---------|
| anchor-splits.php | Detect same anchor text pointing to different URLs |
| generic-anchors.php | Detect "click here", "learn more", bare acronyms |
| link-balance.php | Internal vs external link ratio enforcement |
| repeated-urls.php | Detect same URL linked 3+ times per page |

### Other RSS v1.0 Assets
- Templates: anchor-map-template.csv, content-spec-template.md, first-30-days-template.md, intake-form-template.md, site-config-template.conf
- Tools: audit-runner.sh, deploy-to-site.sh, new-client.sh
- Module structure: onboarding/, qa-gates/, technical-seo/

---

## What's NOT in RSS v1.0 — Gap Inventory

### A. MU-Plugins Not Migrated (51 custom plugins)

#### A1. Schema Infrastructure (5 plugins, 1,006 lines)

| Plugin | Lines | Purpose | Templatability |
|--------|-------|---------|----------------|
| valn-faq-schema.php | 174 | FAQPage JSON-LD from vlnFaq details/summary blocks. Deduplicates questions appearing on 3+ pages. | HIGH — any site with FAQ markup needs this |
| valn-schema-cleaner.php | 93 | Removes inline FAQPage/HowTo JSON-LD scripts from rendered content (prevents Divi double-schema) | HIGH — any Divi/builder site |
| valn-schema-extended.php | 639 | Emits VideoObject, MortgageLoan, DefinedTerm, Service, HowTo, SoftwareApplication, Speakable. Hooks wp_head after Yoast. | MEDIUM — schema types are niche-specific |
| valn-org-id.php | 12 | Forces Yoast Organization @id to canonical URL form | HIGH — trivial, universal |
| valn-profile-fix.php | 88 | Patches Person schema for non-primary authors (Levi, Kenneth, editorial) | LOW — VALN-specific author set |

#### A2. Interactive Mortgage Tools (17 plugins, ~4,200 lines + assets)

**Shadow DOM Tool Framework:**
| Plugin | Lines | Tools Included |
|--------|-------|----------------|
| valn-tools.php | 135 | [valn_tool] shortcode system — loads per-tool CSS/JS from assets/ |
| valn-tools-new.php | 1,878 | 12 tools: condo-lookup, jumbo, entitlement, construction, low-appraisal, tax-savings, occupancy, second-va, recovery, assumption, joint, fee-audit |
| valn-tools-api.php | 354 | REST endpoint /wp-json/valn/v1/tool-lead → FUB lead capture |

**Page-Native Rebuilt Tools:**
| Plugin | Lines | Tools Included |
|--------|-------|----------------|
| valn-tools-funding-fee.php | 505 | Funding fee calculator (rebuilt from Shadow DOM) |
| valn-tools-page-native-batch2.php | 338 | County loan limit, residual income, prequalification, VA assumption |
| valn-tools-page-native-batch3.php | 335 | Funding fee refund, student-loan IBR, job-change impact, construction readiness |
| valn-tools-page-native-batch4.php | 331 | Home-improvement, manufactured-home, seller-concessions, cash-out-vs-heloc |
| valn-tools-page-native-batch5.php | 92 | Inspection-checklist, rates-compare, rov-packet, timing-planner |
| valn-tools-page-native-batch6.php | 91 | Appraisal-fee, calvet-compare, community-property-debt, vlb-compare |
| valn-tools-page-native-batch7.php | 91 | Credit-improvement, recast-alternative, usaa-pay-date, navy-federal-pay-date |
| valn-tools-page-native-batch8.php | 89 | MPR-checklist, complex-router, hub-router |

**Standalone Calculators:**
| Plugin | Lines | Purpose |
|--------|-------|---------|
| valn-va-calculators.php | 746 | [va_calc_service] shortcode + legacy auto-replace |
| valn-affordability-calc.php | 109 | VA home affordability calc with DTI, residual income, funding fee |
| valn-credit-simulator.php | 140 | Credit score simulator + AJAX → FUB lead pipeline |
| valn-prequal-tool.php | 38 | Pre-qualification tool embed |
| valn-prequal-api.php | 152 | REST endpoint for prequal leads → FUB + backup email |
| valn-iframe-calc.php | 150 | Standalone embeddable calculator (no header/footer) |

**Tool asset directory:** `/wp-content/mu-plugins/valn-tools/assets/` contains per-tool .html/.css/.js triads for: appraisal-fees, closing-costs, funding-fee-chart, loan-limits, residual-income, va-income-requirements, va-loan-assumption, va-mpr

#### A3. Lead/CRM Pipeline (8 plugins, 1,498 lines)

| Plugin | Lines | Purpose | Client Relevance |
|--------|-------|---------|------------------|
| valn-fub-webhook.php | 199 | Two-step FUB integration for GF Form 9 — transforms entry into FUB /v1/events format | HIGH — any CRM webhook |
| valn-form-tracker.php | 528 | Form session lifecycle tracking: start → page changes → submit/abandon | HIGH — universal conversion tracking |
| valn-form-tracker-addon.php | 382 | Abandon recovery — contact capture on page change, email + FUB notification | HIGH — conversion recovery |
| valn-form-submit-guard.php | 85 | Error handling + retry UI + client-side UUID dedup for form submissions | HIGH — prevents double-submits |
| valn-dropoff-report-cron.php | 184 | Scheduled drop-off summary emails | MEDIUM — reporting |
| portal-auto-enroll.php | 268 | Creates client portal account when GF lead captured | LOW — VALN-specific |
| valn-agent-portal-routes.php | 7 | Agent login via /portal/?agent=XXXXXX | LOW — VALN-specific |
| vln-gf-lead-reports-loader.php | 22 | Safe production-only loader for GF lead reports | LOW |

#### A4. UI/Conversion Components (7 plugins, 889 lines)

| Plugin | Lines | Purpose | Client Relevance |
|--------|-------|---------|------------------|
| valn-sitebar.php | 541 | Sticky review ticker + CTA bar (after scroll). Apply page shows disclosure-only. | HIGH — sticky CTA pattern |
| valn-mobile-trust-mini.php | 181 | Mobile-only sticky mini trust strip (phone + veteran owned) | HIGH — mobile trust signals |
| valn-components-v2.php | 18 | vlnPage design components loader (CTA bars, tables, stat highlights, process steps) | HIGH — design system core |
| valn-denied-page-css.php | 25 | Extracted CSS for specific pages | LOW |
| valn-focus-fix.php | 25 | Removes ugly click focus outline, preserves keyboard focus-visible | HIGH — accessibility fix |
| valn-autofill-primer.php | 66 | Hidden name/email/phone fields for mobile browser autofill priming | HIGH — conversion optimization |
| valn-va-loans-page.php | 33 | Page-specific CSS/JS for /va-loans/ interactive tools | LOW |

#### A5. SEO/Redirect Infrastructure (7 plugins, 593 lines)

| Plugin | Lines | Purpose | Client Relevance |
|--------|-------|---------|------------------|
| valn-redirect-engine.php | 324 | Unified 301 handler for cannibalization merges, P1 fixes, broken-link patterns | HIGH — every site needs redirects |
| base-purge-410.php | 60 | Returns HTTP 410 Gone for retired content paths | HIGH — content lifecycle |
| force-enable-indexing.php | 50 | Forces blog_public=1 and prevents changes | HIGH — safety net |
| valn-cache-headers.php | 53 | Sane Cache-Control: private no-store for logged-in/admin | MEDIUM |
| valn-sitemap-redirects.php | 26 | Legacy paginated sitemap → canonical sitemap redirect | MEDIUM — migration artifact |
| valn-news-cleanup-redirects.php | 36 | 301 redirects for trashed news/event pages | LOW — VALN-specific |
| vlg-city-301-non-tx.php | 44 | City-level 301 redirects for non-Texas states | LOW — VALN-specific |

#### A6. Analytics (2 plugins, 175 lines)

| Plugin | Lines | Purpose | Client Relevance |
|--------|-------|---------|------------------|
| valn-analytics-head.php | 136 | Consolidated GTM + FB Pixel + Clarity injection, excludes logged-in users | HIGH — every client |
| valn-clarity.php | 39 | Microsoft Clarity (production-only, excludes logged-in) | MEDIUM |

#### A7. Content/Admin Tools (3 plugins, 694 lines)

| Plugin | Lines | Purpose | Client Relevance |
|--------|-------|---------|------------------|
| valn-ai-summary.php | 130 | AI article-summary button CSS/JS sitewide | LOW — experimental |
| valn-cron-schedule.php | 78 | WP-Cron scheduling for drip + reactivation | LOW — VALN-specific |
| valn-work-log-dashboard.php | 486 | Admin page for grouped activity log (wp_valn_work_log) | MEDIUM — operational tracking |

---

### B. WPCode Snippets Not in RSS (62 total, 2 active)

**Active snippets (2):**
| ID | Name | Purpose |
|----|------|---------|
| 36649 | Force 301 /author/mschwartz/ → /about-matt-schwartz/ | Author URL redirect |
| 36648 | Author link override (Matt → About page) | Author archive redirect |

**Inactive but architecturally significant (key 10):**
| ID | Name | Chars | RSS Relevance |
|----|------|-------|---------------|
| 30852 | Consolidated Yoast schema normalizer | 21,642 | HIGH — schema cleanup, templatize |
| 29965 | Site-wide schema normalizer | 5,335 | HIGH — schema normalization |
| 16158 | CTA popup and sticky bar | 10,488 | MEDIUM — conversion pattern |
| 16278 | Author box for posts/pages (1000+ words) | 1,654 | HIGH — EEAT signal |
| 29990 | Published-on date addon for posts | 2,209 | HIGH — freshness signal |
| 12382 | Display Last Updated Date | 481 | HIGH — freshness signal |
| 16435 | Last updated in meta | 1,515 | HIGH — Yoast meta freshness |
| 29963 | Default reviewer assignment rules | 1,566 | MEDIUM — reviewer workflow |
| 29932 | Auto reviewer rules on save | 1,262 | MEDIUM — reviewer workflow |
| 16165 | Turn FAQ questions into h3 | 3,378 | MEDIUM — FAQ processing |

**Remaining 50 inactive snippets:** Legacy/superseded by mu-plugins. Categories: social icons, image sizes, TOC management, OpenAI integration, margin fixes, comment disabling, lead source tracking, BAH rate functions, search modification, Divi CSS purging, military page styling.

---

### C. Linking Infrastructure

#### C1. Anchor Map
- **File:** `~/valn-rewrite/anchor-map.csv`
- **Size:** 9,672 rows (841 KB)
- **Format:** `source_id, source_slug, target_url, anchor_text`
- **Backup:** `anchor-map-pre-expansion-2026-05-03.csv` (839 KB)
- **RSS template exists:** `anchor-map-template.csv` (empty scaffold)

#### C2. Link Injector
- **File:** `~/valn-rewrite/link-injector-v3.php`
- **Size:** 4,319 bytes
- **Features:** Streaming output, restricted zone awareness (bullet-section, vlnCallout, vlnTable, vlnFaq, details, headings), word-boundary matching
- **Invocation:** Takes base64-encoded plan, runs via `wp eval-file`
- **Dependencies:** PHP on WP Engine, $wpdb access

#### C3. Supporting Scripts
- link-injector-v2.php (7,040 bytes) — earlier version
- batch-inject.php, inject-link.php, inject-one.php — various injection helpers
- inject-tier2-links.py, inject-tier3-links.py — Python injection orchestrators
- build-injection-plan.py — generates injection plans from anchor map

#### C4. Link Auditing
- link-audit-full.csv (260 KB) — complete internal link audit
- internal-link-audit.csv (553 KB) — detailed audit
- link-counts-2026-04-14.csv (35 KB) — per-page link counts
- orphaned-pages-*.csv — orphan page tracking
- link-injection-tier2-log.csv, tier3-log.csv — injection results

---

### D. Schema Infrastructure

#### D1. Server-Side Schema (mu-plugins)
- **valn-faq-schema.php** — Auto-generates FAQPage JSON-LD from vlnFaq HTML blocks. Deduplicates questions appearing on 3+ pages sitewide. Priority for RSS: HIGH.
- **valn-schema-extended.php** — Extended schema types Yoast doesn't generate. Needs per-niche schema mapping. Priority: MEDIUM.
- **valn-schema-cleaner.php** — Removes duplicate/orphan schema scripts from rendered HTML. Priority: HIGH.
- **valn-org-id.php** — Yoast Organization @id canonicalizer. 12 lines. Priority: HIGH (trivial).

#### D2. WPCode Schema (inactive but preserved)
- Consolidated Yoast schema normalizer (ID 30852, 21K chars) — Most complex. Normalizes all Yoast schema output.
- Site-wide schema normalizer (ID 29965, 5K chars) — Earlier version.
- Extended Levi schema addon (ID 16281, 2K chars) — Person schema for specific author.
- Address/area served (ID 14382, 1K chars) — LocalBusiness enhancement.

#### D3. Author/Reviewer Schema
- valn-profile-fix.php — Patches Person schema for non-Matt authors
- WPCode 29963 — Default reviewer assignment
- WPCode 29932 — Auto reviewer on save
- WPCode 29966 — "Founder and Ret. Green Beret" suffix
- Simple Author Box plugin (active) — UI rendering

---

### E. Content Production System

#### E1. Voice Guide
- **matt-forward-compact-v1.4.txt** (6,382 bytes)
- Operator voice, not article-writer. Mortgage broker who has handled real files.
- Specific rules: answer-first, no blog tone, no theatrical language, approved callout titles
- RSS template exists: `content-spec-template.md` (includes voice reference)

#### E2. Article Structure Specs
- **CLAUDE.md** (~33K, 500+ lines) — Complete article pipeline rules: ATF spec, main content spec, component system, gap-fill rules, internal linking rules, CSS class reference
- **content-spec.md** (11K) — V6 canonical pattern, content invariants, capitalization rules, URL protection, external link citation framework
- **V6-PATTERN-CANONICAL.md** — Locked v6 content pattern (referenced but not read in this audit)
- **internal-linking-policy.md** (5K) — Cluster map, tier structure, per-page constraints, restricted zones, anchor text rules

#### E3. Templates
- **template.txt** — Full page HTML scaffold: ATF hero + main content body with placeholders
- **atf-reference-template.html** (7.7K) — ATF section reference
- **golden-template.html** (30K) — "Golden" reference page
- **bah-template.html** (31K) — BAH page template

#### E4. QA System
- **qa-checklist.txt** — 80+ pass/fail checks organized in sections: page structure, output format, opening structure, content specs, voice, forbidden language, data-first, linking, components, FAQ, closing sections
- **regex-cleanup.txt** — Regex patterns for common errors (broken CTAs, forbidden phrasing, stray links)

#### E5. Content Indexes
- **content-index.csv** (100K) — Master content index
- **content-to-create-queue.csv** (5K) — Planned content queue
- **completed-rewrites.csv** (11K) — Rewrite tracking
- **all-slugs.csv** (29K) — Complete slug list
- **page-rewrite-queue-top50.csv** (5K) — Priority rewrite queue
- **legacy-rewrite-queue.csv** (26K) — Legacy format pages needing upgrade

#### E6. Competitive Analysis
- **competitor-gap-analysis-2026-04-12.md** (53K) — Detailed competitive gaps
- **deep-content-gap-analysis.md** (166K) — Comprehensive gap research
- Various gap matrices per topic (closing costs, bankruptcy, PMI, credit score, etc.)

---

### F. Interactive Tools Detail

**Total tools identified: 29+ (across Shadow DOM + page-native patterns)**

| Batch | Tools | Pattern | On Production |
|-------|-------|---------|---------------|
| valn-tools (Shadow DOM) | 8 original: appraisal-fees, closing-costs, funding-fee-chart, loan-limits, residual-income, va-income-requirements, va-loan-assumption, va-mpr | Shadow DOM via [valn_tool] shortcode | Yes |
| valn-tools-new | 12: condo-lookup, jumbo, entitlement, construction, low-appraisal, tax-savings, occupancy, second-va, recovery, assumption, joint, fee-audit | Shadow DOM merged | Yes |
| Page-native batch 2 | 4: county-limit, residual-income, prequalification, assumption-redesign | Page-native PHP | Staging |
| Page-native batch 3 | 4: funding-fee-refund, student-loan-IBR, job-change-impact, construction-readiness | Page-native PHP | Staging |
| Page-native batch 4 | 4: home-improvement, manufactured-home, seller-concessions, cash-out-vs-heloc | Page-native PHP | Staging |
| Page-native batch 5 | 4: inspection-checklist, rates-compare, rov-packet, timing-planner | Page-native PHP | Staging |
| Page-native batch 6 | 4: appraisal-fee, calvet-compare, community-property-debt, vlb-compare | Page-native PHP | Staging |
| Page-native batch 7 | 4: credit-improvement, recast-alternative, usaa-pay-date, navy-federal-pay-date | Page-native PHP | Staging |
| Page-native batch 8 | 3: mpr-checklist, complex-router, hub-router | Page-native PHP | Staging |
| Standalone | funding-fee (rebuilt), affordability, credit-simulator, prequal-tool, iframe-calc, va-calculators | Mixed | Yes |

**Migration complexity:** Tools are niche-specific (mortgage). The *framework* (shortcode system, Shadow DOM pattern, lead API, asset loader) is reusable. Individual tool logic/formulas are not.

---

### G. Theme/Design Infrastructure

#### G1. Child Theme (Divi-child)
- **functions.php** (1,802 bytes): Loads parent CSS, enqueues vln-ui.css + vln-ui.js, fixes viewport meta (removes Divi's user-scalable=0), defers non-critical scripts
- **assets/vln-ui.css** — Global UI stylesheet (full vlnPage component system: hero, cards, tables, callouts, FAQ, pills, breadcrumbs, grids, etc.)
- **assets/vln-ui.min.css** — Minified version
- **style.css** — Minimal child theme declaration (59 bytes)

#### G2. CSS Component System (vlnPage)
The vln-ui.css file powers the entire content design system:
- **ATF:** vlnHero, vlnCard, vlnBreadcrumb, vlnEyebrow, vlnPills, vlnHeroLead, vlnQuickGrid, vlnQuickCard, vlnMeta, vlnSkip
- **Body:** bullet-section-* (blue/gray/green/yellow/red), vlnCallout variants, vlnTable + vlnTableScroll, vlnFaq, vlnGrid2/3, vlnNextPill CTA
- **Trust:** Mobile trust strip, sticky CTA bar, review ticker

---

### H. Active Plugin Stack (50+ plugins)

**Lead Pipeline:**
- Gravity Forms v2.9.23 + Webhooks + Zapier — Core form/lead infrastructure
- valn-gf-session-capture — Session tracking for GF
- vln-gf-lead-reports — Lead reporting
- vln-va-readiness-leads — Readiness assessment leads
- valn-custom-gf-form — Custom form rendering

**Content/SEO:**
- Yoast SEO + Premium v27.5 — Core SEO plugin
- IndexNow — Instant indexation pings
- YARPP — Related posts
- valn-toc-manager v1.12.0 — Table of contents
- valn-meta-header-classic v9.6.4 — Custom meta headers
- Simple Author Box — Author bio rendering
- valn-auto-bullet-section-wrapper — Auto-wrapping content sections

**Conversion/UI:**
- valn-loan-compare-2025-v5.1-pro — Loan comparison tool
- valn-bah-calculator — BAH calculator (plugin, not mu-plugin)
- va-entitlement-calculator — Entitlement calculator
- vln-interactive-pages v1.7.8.1 — Interactive page features
- Monarch — Social sharing (Elegant Themes)

**Media/Performance:**
- valn-media-offload-suite — CDN media offload
- valn-cdn-logo-rewriter-fixed — CDN URL rewriting for logos
- Force Regenerate Thumbnails
- Media Cleaner

**Infrastructure:**
- Google Site Kit — Analytics connection
- WP Mail SMTP — Email delivery
- WP Crontrol — Cron management
- WP File Manager — File management UI
- wp-sheet-editor-premium — Bulk edit posts
- auto-relink-broken-externals — Fix broken external links

---

### I. Yoast Configuration Baseline

**Title/Meta Patterns:**
- Author metadesc: `Read articles written by %%name%%, a contributor at VA Loan Network specializing in VA home loans, Veteran benefits, and homeownership advice.`
- Post/page metadesc: Empty (custom per page)
- Home metadesc: Empty (custom)

**Indexing:**
- noindex: archive, author-noposts, et_tb_item_type
- Indexed: pages, posts, attachments, authors (with posts), all Divi layouts

**Social:**
- OpenGraph: enabled, default image set
- Twitter: summary_large_image
- Facebook: @valoannet
- Twitter: @valoannet

---

### J. Other Infrastructure Found

#### J1. GSC API Integration
- Credentials at `~/valn-rewrite/.gsc-credentials.json`
- Multiple Python scripts for GSC data pulls: gsc-seo-audit.py, gsc-opportunities.py, gsc-cannibal-deep.py, etc.
- Cannibalization detection, striking distance, device split, declining pages analysis

#### J2. Google Drive Sync
- `gdrive-sync.py` — Syncs operational docs to Google Drive
- OAuth credentials at `.gdrive-oauth-client.json` / `.gdrive-token.json`

#### J3. Playwright Visual QA
- `~/valn-rewrite/visual-qa/` — Playwright-based visual regression
- `~/valn-rewrite/staging-qa/` — Staging QA automation

#### J4. FUB Drip System (disabled)
- Full drip messaging system at `/nas/content/live/valoannetwork/fub-drip/`
- Cron, SQLite queue, auto-enrollment — all intentionally disabled
- Not a candidate for RSS (too VALN-specific)

#### J5. Decision Router
- `decision-router-routes.json` (25K) — Decision tree routing for complex VA loan scenarios
- `decision-router-build/` — Build scripts

---

## Migration Priority Recommendations

### Tier 1 — v1.1 (Blocks First Paying Client)

| Item | Category | Build Size | Reusability |
|------|----------|------------|-------------|
| FAQ Schema (valn-faq-schema.php) | Schema | SMALL | HIGH — any site with FAQ markup |
| Schema Cleaner (valn-schema-cleaner.php) | Schema | SMALL | HIGH — any builder site |
| Org ID Canonicalizer (valn-org-id.php) | Schema | SMALL | HIGH — trivial, universal |
| Force Indexing (force-enable-indexing.php) | SEO | SMALL | HIGH — safety net |
| 410 Handler (base-purge-410.php) | SEO | SMALL | HIGH — content lifecycle |
| Redirect Engine (valn-redirect-engine.php) | SEO | MEDIUM | HIGH — every site |
| Analytics Head (valn-analytics-head.php) | Analytics | SMALL | HIGH — GTM/Pixel pattern |
| Form Submit Guard (valn-form-submit-guard.php) | Lead | SMALL | HIGH — any form site |
| Content Spec Template | Content | SMALL | HIGH — already partially templated |
| QA Checklist Template | Content | SMALL | HIGH — adapt from qa-checklist.txt |
| Internal Linking Policy Template | Content | SMALL | HIGH — cluster structure is universal |
| Anchor Map + Injector v3 | Linking | MEDIUM | HIGH — core RSS differentiator |
| Voice Guide Template | Content | SMALL | HIGH — adapt framework, swap voice |
| Last Updated Meta (WPCode 16435/12382 patterns) | SEO | SMALL | HIGH — freshness signals |
| Author Box / EEAT patterns | Schema | MEDIUM | HIGH — EEAT is universal |

**Estimated build: 2-3 sessions**

### Tier 2 — v1.2 (Enhanced Client Value)

| Item | Category | Build Size | Reusability |
|------|----------|------------|-------------|
| Sticky CTA Bar (valn-sitebar.php) | UI | MEDIUM | HIGH — templatize triggers/content |
| Mobile Trust Strip (valn-mobile-trust-mini.php) | UI | SMALL | HIGH — universal trust signal |
| Form Tracker + Abandon Recovery | Lead | LARGE | HIGH — major conversion feature |
| Autofill Primer (valn-autofill-primer.php) | Lead | SMALL | HIGH — mobile conversion |
| Cache Headers (valn-cache-headers.php) | Performance | SMALL | HIGH — universal |
| Focus Fix (valn-focus-fix.php) | Accessibility | SMALL | HIGH — universal |
| Schema Extended (templatized) | Schema | LARGE | MEDIUM — niche-specific schema |
| Yoast Config Baseline Export | SEO | MEDIUM | HIGH — config as code |
| CSS Component System (vln-ui.css) | Design | LARGE | MEDIUM — needs per-brand theming |

**Estimated build: 3-4 sessions**

### Tier 3 — v2.0 (Full Platform)

| Item | Category | Build Size | Reusability |
|------|----------|------------|-------------|
| Interactive Tool Framework | Tools | LARGE | HIGH — shortcode + asset + lead API pattern |
| Tool Lead API pattern | Lead | MEDIUM | HIGH — CRM-agnostic |
| Drop-off Reporting | Reporting | MEDIUM | MEDIUM |
| Playwright Visual QA | QA | LARGE | HIGH — regression testing |
| GSC API Integration | Analytics | MEDIUM | HIGH — data-driven decisions |
| Work Log Dashboard | Admin | MEDIUM | MEDIUM — operational tracking |
| Content production prompts/CLAUDE.md | Content | MEDIUM | HIGH — adapt per niche |

**Estimated build: 5+ sessions**

### NOT for RSS (VALN-specific, no migration)

- Portal auto-enroll, agent routes
- FUB drip system
- City-level 301s
- News cleanup redirects
- BAH calculator
- Specific tool formulas (mortgage math)
- valn-va-loans-page.php, valn-denied-page-css.php
- WPCode snippets that are superseded by mu-plugins
- Legacy calculator auto-replace logic

---

## Summary Statistics

| Category | Items Found | In RSS v1.0 | Gap |
|----------|------------|-------------|-----|
| MU-plugins (custom) | 51 | 6 | 45 |
| WPCode snippets | 62 | 0 | 62 (10 architecturally significant) |
| QA audit checks | 4+ needed | 4 | ~8 more from qa-checklist.txt |
| Content spec docs | 7 | 1 (partial template) | 6 |
| Linking infrastructure | 4 components | 0 (template only) | 4 |
| Schema systems | 5 plugins + 4 snippets | 0 | 9 |
| Interactive tools | 29+ | 0 | Framework + niche examples |
| Active plugins | 50+ | 0 | Config-as-code baseline |
| CSS component system | 1 (vln-ui.css) | 0 | 1 |
| Child theme | 1 | 0 | 1 (functions.php pattern) |

**Total gap items: ~140+ discrete pieces of infrastructure**
**Architecturally significant gaps: ~25 items**
**RSS v1.0 captured approximately 8% of VALN's total infrastructure**
