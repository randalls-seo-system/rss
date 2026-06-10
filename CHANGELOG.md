# Changelog

Historical record of completed work across all sites. Most recent first.

## VALN

### 2026-06-05 -- GSC whitespace gap analysis (read-only)
- **Scope:** 438,995 query+page rows, 180,861 unique queries, 13,951 with >=100 impressions
- **Core lane whitespace:** 353 queries (>=200 impr, not well-served, VA loan core lane)
- **Cannibalization:** 7,108 query-level conflicts (2+ VALN pages ranking for same query)
- **Top 15 plan:** 3 true new pages, 3 tool builds/embeds, 5 strengthen, 2 rewrites, 2 consolidates
- **True new pages:** VA Loan Affordability Calculator (8,665 impr), VA Loan Costs to Seller (3,287), VA Loan Underwriting Timeline (2,029)
- **Total addressable impressions:** 80,181 across 15 clusters
- **Deliverables:** `~/Downloads/gsc-whitespace-gap-plan.csv`, `~/Downloads/gsc-whitespace-all.csv`, `~/Downloads/gsc-cannibalization.csv`
- **Key finding:** Most "gaps" are existing pages ranking pos 10-20, not missing pages. Biggest ROI is V6 rewrites on manufactured homes (9,793 impr), PMI (9,201), and cash-out refi (6,041).

### 2026-06-05 -- Google snippet leak fixes + comments disabled sitewide (production)
- **Fix A:** Added `data-nosnippet` to `#valnGlobalSticky` review bar in `valn-sitebar.php` (line 356). Covers ~812 pages. Initial edit landed on disk but served HTML lagged due to PHP OPcache (CLI `opcache_reset` doesn't clear web-SAPI cache). Resolved by touching the file + Varnish purge. **Verified via curl**: `data-nosnippet` confirmed in served HTML on /military-base-pay/, /bad-credit-va-loan/, and /va-loans/.
- **Fix B:** Added `<meta name="robots" content="noindex,nofollow">` to all 9 standalone tool HTML files in `/wp-content/uploads/` (credit-router, military-pay-lookup, prequal, paydate, mpr, funding-fee, residual, bah, proptax). Prevents tool step text from appearing in search snippets.
- **Fix C:** Wrapped iframe embeds with `data-nosnippet` on posts 949 and 11783 (belt-and-suspenders with Fix B).
- **Fix D:** Post 931 meta description flagged for rewrite queue (current meta is adequate but Google is ignoring it).
- **Comments:** Closed comments + pings on 369 published pages (was open). All 814 now closed.
- **Backup:** `backups/valn-sitebar-20260605-*.php`

### 2026-06-05 -- Military Pay Lookup tool deployed on post 11783 (production)
- **Tool:** `/wp-content/uploads/military-pay-lookup/military-pay-lookup.html` (21,712 bytes)
- **Data:** PAY_CONFIG populated with all 550 cells (25 grades x 22 YOS columns) from verified chart tables. 485 numeric + 65 null. Zero pending states.
- **Embed:** iframe after BLUF paragraph, before enlisted H2. postMessage height auto-resize. Matches credit-eligibility-router visual pattern.
- **Spot checks (Playwright):** E-5/Over-8=$4,300, E-9/Over-20=$8,105, W-5/Over-20=$10,170, O-10/Over-20=$19,523. All match chart.
- **Screenshot verified:** Tool renders with navy header, two dropdowns, gold result display. NOT the homepage.
- **Backup:** `/nas/content/live/valoannetwork/backups/post-11783-pre-tool-embed-20260605-163450.html`

### 2026-06-05 -- Pay chart render fix: CSS + iframe on post 11783 (production)
- **Page:** /military-base-pay/ (post 11783)
- **Defect 1 (tables):** 22-column pay tables character-stacked (one digit per line). Root cause: Divi strips inline `<style>` from `et_pb_text` modules; appending to `vln-ui.css` hit a CSS parse cutoff in the browser. Fix: mu-plugin `valn-paychart-css.php` injects CSS via `wp_head` (priority 99, page 11783 only) with `overflow-x:auto`, `white-space:nowrap`, `min-width:1500px`, sticky grade column, dark sticky header.
- **Defect 2 (iframe):** Prequal-tool iframe loaded homepage on staging (file absent). Removed iframe section from content. Note: `/wp-content/uploads/military-pay-lookup/military-pay-lookup.html` does not exist -- tool needs to be built separately.
- **Verified:** Playwright rendered screenshots confirm single-line figures, horizontal scroll, sticky grade column at desktop (1400px) and mobile (375px).
- **Files:** `mu-plugins/valn-paychart-css.php` (new, 2,064 bytes), post 11783 content updated (removed inline style + iframe section).

### 2026-06-05 -- Full 2026 military pay chart rebuild on post 11783 (production)
- **Page:** /military-base-pay/ (post 11783)
- **Before:** Abbreviated sample tables (4 enlisted + 3 officer grades, 3 YOS columns, zero warrant officers). H1 "2026 Military Pay Raise Guide". Stale Yoast meta citing 2025 E-1 ($1,949) and O-10 ($16,974).
- **After:** Complete DFAS-sourced reference chart -- 10 enlisted grades (E-1 <4mo through E-9) + 5 warrant grades (W-1 through W-5) + 10 officer grades (O-1 through O-10), all with 22 YOS columns (2-or-less through Over 40). H1 reset to "2026 Military Pay Chart: All Grades and Years of Service".
- **Source:** 2026 DFAS pay table PDF (3.8% raise effective January 1, 2026). Cross-verified against navycs.com and our published page 32857.
- **Yoast title:** "2026 Military Pay Chart: All Grades and Years of Service" (was "2026 Military Pay Chart by Rank and Years of Service")
- **Yoast meta:** Updated with correct 2026 figures -- E-1 ($2,407) to E-9 ($10,729), W-1 ($4,057) to W-5 ($13,308), O-1 ($4,150) to O-10 ($19,523).
- **Cannibalization control:** Intent split confirmed -- 11783 targets "pay chart" (reference), 32857 targets "pay raise" (comparison). No cross-canonical needed.
- **Hub 11775:** Stale `/2025-military-base-pay/` link not present on production (already correct).
- **Backup:** `/nas/content/live/valoannetwork/backups/post-11783-pre-chart-rebuild-20260605-152751.html`
- **Verification:** All 6 spot checks PASS, all 6 n/a cell counts match DFAS structure, 3 tables (23 cols x 10/5/10 rows).

### 2026-06-04 -- Meta title + description rewrites for 12 tool pages (production)
- **Scope:** 12 posts from VALN_meta_rewrites_32.xlsx "Meta Rewrites" sheet, bucket 1.
- **Post IDs:** 11584, 949, 19681, 18895, 12804, 14177, 6273, 16604, 13751, 18887, 36666, 36934.
- **Changes:** Updated `_yoast_wpseo_title` and `_yoast_wpseo_metadesc` on all 12. Added tool-hook words (Checker, Lookup, Calculator) to titles; rewrote descriptions with action language.
- **Post 36934 fix:** Replaced broken Yoast title (`Purple Heart VA Funding Fee Exemption | 2026 Guide`) with `Purple Heart VA Funding Fee Exemption 2026: $0 Fee`.
- **Cache:** WP object cache flushed + WPE edge cache purged for all 12 URLs via `WpeCommon::purge_varnish_cache()`.
- **Verification:** All 12 title+desc values verified character-for-character in DB after write. Render verification shows 2/3 samples serving new titles immediately; 1 (post 949) lagging behind Varnish TTL.

### 2026-06-04 -- Post 12977 retired pricing replaced (prod-direct, register-sanctioned)
- **Page:** /va-home-loan-with-580-credit-score/ (post 12977)
- **Deviation:** Applied directly to production; all figures from per-page register, no invented numbers.
- **6 regions replaced:** H2 opening paragraph (740->640+ cutoff), rate table (5-row retired -> 2-row qualitative 640+/below-640), post-table paragraph (no derived $96; states $24/1/8pt and 1/8-1/2pt range), Deal Math callout ($350K/$214->$300K/$24-per-1/8pt), ATF FAQ (0.75%-1.5%->1/8-1/2 point), lower FAQ (same + $350K->$300K).
- **Retired figures removed:** 740/740+, 0.75%, 1.0%, 1.5%, $350,000, $175, 6.25%, 7.25%, $214, $150-$300, 20-point. Zero remain.
- **Register figures used:** 640+ top-tier, LLPAs below 640, 1/8-1/2 point spread, $24/mo per 1/8 point on $300,000, no PMI.
- **Backup:** `/nas/content/live/valoannetwork/backups/post-12977-pre-edit-20260604-162846.html`

### 2026-06-03 -- Post 6273 manual-UW fixes (prod-direct, Matt-stated)
- **Page:** /manual-underwriting-va-loan/ (post 6273)
- **Deviation:** Applied directly to production per Matt's explicit instructions from annotation set.
- **Lede:** Replaced generic BLUF with Matt's "VA manual underwriting occurs when your file fails the automated underwriting system..." paragraph.
- **Keys paragraph:** Inserted Matt's "The most important aspect to getting an approval on a manually underwritten file..." after lede.
- **ATF QuickCard + body Timeline bullets:** Both replaced with canon "Done properly, a manual underwrite should not add any time to the processing of your loan."
- **Lower FAQ:** "How long does VA manual underwriting take?" answer -> "Manual underwrites should not take any longer than automated approvals to close."
- **Fake-Matt deletion:** Removed AI-generated first-person sentence ("On manual underwrite files I work, the process is slower but not a dead end.") per voice rule.
- **Section kill:** Removed entire "How Long Does Manual Underwriting Take" H2 section + Process Watchpoint callout per Matt's kill instruction ("Everything else below can stay").
- **Q2 gap resolved:** The 2026-06-01 changelog claimed FAQ Q2 answer shipped, but live DB still had old copy. Corrected.
- **Backup:** `/nas/content/live/valoannetwork/backups/post-6273-pre-edit-20260603-181657.html`

### 2026-06-03 -- Messaging Standard replaced with Closed Standard v2
- **Replacement:** Entire Messaging Standard section replaced with Closed Standard.
- **Key changes:** Voice rule locked as authoritative; global canon vs per-page register split; conflict register added for Matt-stated internal conflicts; YMYL guardrail formalized; closed-standard rule prevents gap-filling with inferred claims.
- **Unapplied-edits queue:** Separate transient working file created at `~/valn-rewrite/valn-unapplied-edits-queue.md`. Contains page-specific edit items for 12977, 931, 6273, 949, 16527 pending execution.
- **Google Doc sync:** MCP lacks update-in-place; full content output for manual paste into doc `11Q-bqB-uiQO_nH3HEWRygvVIcAhJuO1TjNcVLiJsT_c`.

### 2026-06-02 -- Status corrections: fub-drip dashboard + Top 100 rebuild locks
- **Edit A -- fub-drip status:** Rewrote Disabled Subsystems intro. The `/fub-drip/` directory powers the LIVE Command Center dashboard (annotations, work log, leads). Only `valn_drip_cron_hook` and `valn_reactivation_enroll` crons remain dormant. Added note: UI shows legacy "fub drip" labels (cosmetic, rename incomplete).
- **Edit B -- Top 100 rebuild locks removed:** Deleted two Do Not Touch lines (IN_PROGRESS master log, active rebuild list). Rebuild is complete; locks no longer apply.
- **Google Doc sync:** MCP lacks update-in-place; full content output for manual paste into doc `11Q-bqB-uiQO_nH3HEWRygvVIcAhJuO1TjNcVLiJsT_c`.

### 2026-06-02 -- VALN Messaging Standard & Matt Voice Reference added
- **Source:** `/Users/esv211/Downloads/matt-voice-reference.md`, built from Matt's annotation history across 5 credit/underwriting pages + 56-record AUS annotation set.
- **Placement:** New Messaging Standard section inserted before Changelog.
- **Google Doc sync:** Content synced to canonical doc via manual copy.
- **Pending:** Validation against `valn_annotations_aus.json` not yet performed.

### 2026-06-01 -- Post 12977 content edits (prod-direct, Matt-requested)
- **Page:** /va-home-loan-with-580-credit-score/ (post 12977)
- **Deviation:** Applied directly to production without staging-first per Matt's explicit request.
- **Edit 1 -- AUS and Approval Path:** Replaced 4 bullets with Matt's updated copy (AUS findings, Timeline Impact, Approval odds with low credit, Credit/Income/Assets). Heading unchanged.
- **Edit 2 -- Credit Scores and rates:** Renamed heading from "Rate Pricing at 580". Replaced 4 bullets (Cost premium, Rate Differential, Monthly Impact, No PMI).
- **Edit 3 -- AUS comparison table:** Column header "At 620" -> "At 640". Interest rate row: At 580 -> "Typically 0.5% higher than 640+", At 640 -> "No LLPAs". Processing timeline row: both cells -> "3-4 weeks depending on lender".
- **Backup:** `~/backups/post-12977-pre-edit-20260601-*.html`

### 2026-06-01 -- Post 931 content edits (prod-direct, Matt-requested)
- **Page:** /va-loans/minimum-credit-score-needed-for-va-loans/ (post 931)
- **Deviation:** Applied directly to production without staging-first per Matt's explicit request.
- **Edit 1 -- Score Band Reality:** Replaced "Below 620" bullet with two new bullets (600-619 scores, Sub 600 scores). Section now 5 bullets.
- **Edit 2 -- Rate and Cost Impact:** Replaced first 3 bullets (Pricing bands, Pricing Gap, Cost Differential). Kept 4th bullet (No PMI) unchanged.
- **Edit 3 -- FAQ (both instances):** Replaced both occurrences of "What credit score do most VA lenders require in 2026?" with "What scores does your network of lenders lend down to?" and new answer about 580 minimum.
- **Backup:** `~/backups/post-931-pre-edit-20260601-*.html`

### 2026-06-01 -- Post 6273 table removal (prod-direct, Matt-requested)
- **Page:** /manual-underwriting-va-loan/ (post 6273)
- **Deviation:** Applied directly to production without staging-first per Matt's explicit request.
- **Edit:** Removed Milestone/Automated/Manual Underwriting timeline comparison table (4 data rows + thead). Kept H2 "How Long Does Manual Underwriting Take", intro paragraph, and "Process Watchpoint" callout intact.
- **Backup:** `~/backups/post-6273-pre-edit-20260601-*.html`

### 2026-06-01 -- Post 931 audit + 2 new edits (prod-direct, Matt-requested)
- **Page:** /va-loans/minimum-credit-score-needed-for-va-loans/ (post 931)
- **Deviation:** Applied directly to production without staging-first per Matt's explicit request.
- **Audit:** Prior edits A (Score Band Reality), B (Rate and Cost Impact), C (FAQ swap) all PASS. No remediation needed.
- **Edit A -- FAQ answer:** Replaced answer for "Does your credit score affect your VA loan interest rate?" with 640+/LLPA language. Question unchanged.
- **Edit B -- Lender table:** Inserted Cross Country Mortgage as first data row (580 / Yes / Specializes in low credit VA and manual underwriting). All existing rows unchanged.
- **Backup:** `~/backups/post-931-pre-edit2-20260601-*.html`

### 2026-06-01 -- Post 949 LLM contamination cleanup (prod-direct, Matt-requested)
- **Page:** /va-loans/bad-credit-va-loan/ (post 949)
- **Deviation:** Applied directly to production without staging-first per Matt's explicit request.
- **Issue:** LLM meta-commentary phrase injected into 9 locations across the page -- body copy, FAQ answers, a `<summary>` tag, and callouts.
- **Fix:** Surgical excision of the contamination string at all 9 insertion points. Each fix reconnects "manual underwriting" to its original sentence continuation. Content reduced from 27,768 to 25,284 chars.
- **Backup:** `~/backups/post-949-pre-cleanup-20260601-*.html`

### 2026-06-01 -- Post 6273 upper FAQ answer edits (prod-direct, Matt-requested)
- **Page:** /manual-underwriting-va-loan/ (post 6273)
- **Deviation:** Applied directly to production without staging-first per Matt's explicit request.
- **Edit Q2:** "How long does manual underwriting take?" -- replaced timeline answer with "When done properly manual underwriting doesn't take any longer to close than an automated approval."
- **Edit Q3:** "Do all VA lenders offer manual underwriting?" -- replaced broker/specialty answer with network experience language. Lower FAQ block untouched.
- **Backup:** `~/backups/post-6273-pre-faq-edit-20260601-*.html`

### 2026-06-01 -- Post 949 T1/T2/T4 edits (prod-direct, Matt-requested)
- **Page:** /va-loans/bad-credit-va-loan/ (post 949)
- **Deviation:** Applied directly to production without staging-first per Matt's explicit request.
- **T1 -- BLUF intro:** Replaced summary with Matt's single paragraph about credit score flexibility, lender minimums, and credit report composition.
- **T2 -- Score band box:** Replaced 4 bullets with 6 granular bands (680+/640-679/600-639/580-599/Below 580/No VA min). Heading "Approval Path by Score Band" unchanged.
- **T4 -- Table removed:** Deleted "VA Loan Approval Path by Credit Score Band (2026)" table (3 data rows). Kept H2 "What Lenders See When Your Credit Is Below 620", intro paragraphs, and post-table content.
- **T3 (FAQ):** Deferred -- awaiting Matt's replacement copy.
- **Backup:** `~/backups/post-949-pre-t1t2t4-20260601-*.html`
