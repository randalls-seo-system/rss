# LRG Short Sale / Distressed Content -- Production Recon
## 2026-08-12 | Read-Only Reconnaissance

**Install verified:** `https://lrgrealty.com` / `LRG Realty Blog`
**Method:** Direct database queries via wp eval-file. GSC API via service account. SERP via Serper.dev.
**Prior work:** Strategy doc (shortsale-strategy.md, Aug 9) + 49 cached SERP pulls. This recon extends that work with exhaustive term coverage, deep page profiles, and defect scanning.

---

## 1. EXHAUSTIVE TERM SEARCH RESULTS

**611 posts** matched at least one distressed term across post_title, post_content, post_excerpt, and post_name. Searched 43 terms independently across ALL post types (post, page) and ALL statuses (publish, draft, trash).

| Status | Count |
|--------|-------|
| publish | 473 |
| draft | 125 |
| trash | 13 |

Post types: 586 posts, 25 pages.

### 1A. Classification: GENUINE TOPICAL vs INCIDENTAL

Of 611 total matches, **22 are genuine topical pages** where the distressed homeowner problem space is the actual topic. The remaining ~589 are incidental mentions (the word "foreclosure" or "PCS" appears in context of another topic).

---

## 2. GENUINE TOPICAL PAGES -- FULL INVENTORY

### 2A. Phase 1 Pages (NEW -- published Aug 9-10, 2026)

| ID | Slug | Title | Status | Words | Author | Date |
|----|------|-------|--------|-------|--------|------|
| 9765 | options-cant-afford-sell-texas-home | Your Options When You Can't Afford to Sell Your Texas Home | publish | 4,664 | Levi Rodgers | 2026-08-09 |
| 9773 | pcs-underwater-mortgage-military-options-texas | PCS with an Underwater Mortgage: Military Options in Texas | publish | 4,080 | Levi Rodgers | 2026-08-09 |
| 9774 | short-sale-vs-foreclosure-texas | Short Sale vs Foreclosure in Texas: Which Is Better for You? | publish | 4,323 | Levi Rodgers | 2026-08-09 |

**ALL THREE ARE ORPHANS** -- zero internal links point to them from any other page on the site.

GSC: Zero impressions for all three (published 3 days ago; GSC lag normal).

### 2B. Existing Distressed-Topic Pages

| ID | Slug | Title | Status | Words | Author | 90d Clicks | 90d Impr | Avg Pos |
|----|------|-------|--------|-------|--------|------------|----------|---------|
| 8714 | selling-home-pcs-no-equity-texas | Selling a Home During a PCS With Little or No Equity | publish | 3,807 | Levi Rodgers | 0 | 5 | -- |
| 1516 | 2024-8-14-understanding-short-sales-a-guide-for-homebuyers-and-sellers | Understanding Short Sales: A Guide for Homebuyers and Sellers | publish | 3,951 | Levi Rodgers | 0 | 15 | -- |
| 8688 | va-loan-after-foreclosure-short-sale-texas | VA Loan After a Previous Foreclosure or Short Sale in Texas | publish | 3,790 | Levi Rodgers | 0 | 563 | 8.8 |
| 2233 | how-to-buy-foreclosure-san-antonio | How to Buy a Foreclosure in San Antonio | publish | 3,979 | Candice Witt | 25 | 2,175 | 6.2 |
| 2226 | how-to-buy-foreclosure-austin | How to Buy a Foreclosure in Austin, TX in 2026 | publish | 4,075 | Karishma Rupani | 4 | 625 | 8.0 |
| 2230 | how-to-buy-foreclosure-killeen | How to Buy a Foreclosure in Killeen, TX | publish | 3,420 | Candice Witt | 4 | 752 | 7.6 |
| 5435 | buying-house-after-bankruptcy-san-antonio | Buying a House After Bankruptcy in San Antonio | publish | 1,908 | Candice Witt | 0 | 0 | -- |
| 5433 | va-loan-bad-credit-san-antonio | VA Loan with Bad Credit in San Antonio | publish | 2,876 | Charles Clevenger | 0 | 0 | -- |
| 8891 | capital-gains-tax-selling-home-texas-2026 | Capital Gains Tax When Selling a Home in Texas | publish | 3,385 | Levi Rodgers | 0 | 337 | 8.2 |
| 8943 | real-estate-help-texas (under /tools/) | Real Estate Problems in SA, Austin & Killeen? Start Here | publish | 3,550 | Levi Rodgers | 0 | 0 | -- |
| 8716 | scra-protections-selling-lease-texas | SCRA Protections When Selling or Breaking a Lease in Texas | publish | 3,465 | Levi Rodgers | 0 | 4 | -- |

### 2C. Adjacent Pages (support linking, not primary distress topic)

| ID | Slug | Title | Status | 90d Impr | Relevance |
|----|------|-------|--------|----------|-----------|
| 2861 | va-loan-assumption-sam-houston-texas | VA Loan Assumption: Protect Your Entitlement After a Fort Sam Houston PCS | publish | 479 | HIGH -- alternative to selling at a loss |
| 8654 | second-tier-va-entitlement-buy-before-sell-texas | Second-Tier VA Entitlement: Buying Again Before You Sell | publish | -- | HIGH -- buy-before-sell for PCS |
| 2717 | selling-home-before-pcs-orders-san-antonio-veteran-checklist | Sell Before PCS Orders in San Antonio: Veteran PCS Checklist | publish | -- | MEDIUM -- general PCS selling |
| 2110 | fort-sam-houston-pcs-sell-guide-army-north-south | Selling Your Fort Sam Houston Home After the Army Merger | publish | -- | MEDIUM -- JBSA-specific |
| 2703 | sell-house-fast-san-antonio | How to Sell a House in San Antonio | publish | -- | LOW -- general selling |
| 7415 | sell-house-fast-austin-tx | How to Sell Your House Fast in Austin, Texas | publish | -- | LOW -- general selling |

### 2D. Drafts (potential overlap risk)

| ID | Slug | Title | Status | Author | Words | Notes |
|----|------|-------|--------|--------|-------|-------|
| 2500 | pcs-home-sale-checklist-san-antonio | PCS Home Sale Checklist for Veterans in San Antonio | draft | Levi Rodgers | 3,755 | Overlaps 2717 and 9773 |
| 2505 | pcs-to-jbsa-home-sellers-guide | PCS to JBSA: A Home Seller's Guide | draft | Charles Clevenger | 5,554 | Overlaps 9773. 1 Fort Cavazos hit. |
| 2701 | fort-cavazos-pcs-home-sale-timeline | Fort Cavazos PCS Home Sale Timeline and Remote Closing | draft | Pedro Solis | 4,443 | **45 Fort Cavazos instances.** Entire article uses wrong name. |

---

## 3. DEEP PROFILES -- DEFECT INVENTORY

### 3A. Disclaimer Coverage

| ID | Title | Educational Notice | Legal/Tax Disclaimer | Status |
|----|-------|--------------------|---------------------|--------|
| 9765 | Options When Can't Afford to Sell | YES | YES | OK |
| 9773 | PCS Underwater Mortgage | YES | YES | OK |
| 9774 | Short Sale vs Foreclosure | YES | YES | OK |
| 8714 | Selling Home PCS No Equity | **NO** | **NO** | DEFECT -- beachhead lacks both |
| 1516 | Understanding Short Sales | **NO** | **NO** | DEFECT |
| 8688 | VA Loan After Short Sale | YES | YES | OK |
| 2233 | Buy Foreclosure SA | YES | YES | OK |
| 2226 | Buy Foreclosure Austin | YES | YES | OK |
| 2230 | Buy Foreclosure Killeen | YES | YES | OK |
| 5435 | Buying After Bankruptcy SA | **NO** | **NO** | DEFECT |
| 5433 | VA Loan Bad Credit SA | **NO** | **NO** | DEFECT |
| 2861 | VA Loan Assumption | **NO** | **NO** | DEFECT |
| 8654 | Second-Tier VA Entitlement | **NO** | **NO** | DEFECT |
| 2717 | Sell Before PCS SA | **NO** | **NO** | DEFECT |
| 2110 | Fort Sam Houston PCS Sell | **NO** | **NO** | DEFECT |
| 8716 | SCRA Protections | **NO** | **NO** | DEFECT |
| 8891 | Capital Gains Tax TX | YES | YES | OK |
| 8943 | Real Estate Problems Hub | **NO** | **NO** | DEFECT |

**9 of 18 published topical pages lack both disclaimer blocks.** The three Phase 1 pages are compliant; the rest predate the disclaimer pipeline.

### 3B. Tax Language Defects

| ID | Location | Match | Context | Severity |
|----|----------|-------|---------|----------|
| 9765 | Line 214 | "creates taxable income" | "A deed in lieu carries legal and tax consequences that vary by loan type and lender terms." | MEDIUM -- missing "may" qualifier and "other exclusions may apply" |

No other tax language defects found in the 18 profiled pages. The correct framing ("may create taxable income; other exclusions may apply") appears in the Phase 1 pages' disclaimer sections but is contradicted by the deed-in-lieu body section in 9765.

### 3C. Fair Housing Scan

**Regex hits: 1**
| ID | Line | Match | Context |
|----|------|-------|---------|
| 9773 | 13 | "best for families" | "Works best for families who owe close to market value and can cover a small gap out of pocket at closing." |

**Semantic hits: 0 additional** beyond the regex hit.

The 9773 hit is in the BLUF card describing the "sell at a small loss" option. "Works best for families" is steering language in a Fair Housing context -- it implies the option is better for one familial status than another. Recommend rewording to "Works best when you owe close to market value."

### 3D. UPL (Unauthorized Practice of Law) Scan

Flagged sentences that state legal conclusions, tell readers what the law requires, or advise a specific legal course. These are flags, not confirmed violations -- most are borderline or properly hedged.

| ID | Line | Quote | Assessment |
|----|------|-------|------------|
| 9773 | 178 | "You must document that PCS orders prevent you from continuing mortgage payments" | BORDERLINE -- directive language. Could add "your servicer will require documentation" framing. |
| 9773 | 180 | "Texas Property Code 51.003 governs deficiency judgments" | OK -- factual citation of statute |
| 8714 | 97 | "Your home value dropped below your loan balance and you cannot bring cash to closing" | OK -- factual description of a scenario |
| 8891 | (2 hits) | Describing tax obligations | Review needed -- tax content should use "consult a CPA" framing |

No hard UPL violations found. The Phase 1 pages consistently use "consult an attorney" and "consult a CPA" framing.

### 3E. Fort Cavazos Defects

The base was renamed back to **Fort Hood** in 2025. Every instance of "Fort Cavazos" is a factual error.

| ID | Title | Instances | Status |
|----|-------|-----------|--------|
| 2230 | Buy Foreclosure Killeen | **6** | DEFECT -- all in FAQ JSON-LD |
| 2701 | Fort Cavazos PCS Timeline (draft) | **45** | DEFECT -- entire article |
| 2226 | Buy Foreclosure Austin | 1 | DEFECT |
| 2110 | Fort Sam Houston PCS Sell | 1 | DEFECT |
| 2505 | PCS to JBSA Seller's Guide (draft) | 1 | DEFECT |

**Total: 54 instances across 5 pages (3 published, 2 draft).**

Post 2230 is the most critical -- it's the Killeen foreclosure guide with 752 impressions/90d and has 6 "Fort Cavazos" instances in its FAQ schema, which is directly served to Google.

### 3F. Factual Sourcing Audit

| ID | Title | Sources Cited | Unverifiable? |
|----|-------|--------------|---------------|
| 9765 | Options Pillar | HUD, IRS, CFPB, ICE, Property Code, NAR | No -- institutional sources |
| 9773 | PCS Underwater | HUD, ICE, IRS, Property Code, NAR | No |
| 9774 | Short Sale vs Foreclosure | HUD, ICE, IRS, CFPB, Property Code, NAR | No |
| 8714 | Selling Home PCS No Equity | MLS, ICE, IRS, NAR | "MLS" is vague -- which MLS, what date? |
| 1516 | Understanding Short Sales | MLS, ICE, IRS, NAR, Freddie Mac | "MLS" is vague |
| 8688 | VA After Short Sale | FEMA, HUD, ICE, IRS, VA.gov, NAR, Fannie Mae | FEMA citation should be verified |
| 2233 | Buy Foreclosure SA | HUD, MLS, appraisal district, ICE, IRS, Property Code, NAR, Fannie Mae, Freddie Mac | "appraisal district" is vague |
| 2226 | Buy Foreclosure Austin | HUD, MLS, ICE, IRS, Fannie Mae, Freddie Mac | "MLS" vague |
| 2230 | Buy Foreclosure Killeen | HUD, appraisal district, ICE, IRS, Fannie Mae, Freddie Mac | "appraisal district" vague |
| 5435 | Buying After Bankruptcy SA | HUD, ICE, IRS, VA.gov, CFPB | OK |
| 5433 | VA Loan Bad Credit SA | HUD, ICE, IRS, VA.gov, NAR | OK |
| 8714 | Selling Home PCS No Equity | **NONE** | DEFECT -- beachhead cites zero sources |

**Post 8714 (beachhead) cites zero authoritative sources.** This is a significant gap for YMYL content.

### 3G. Meta Title / Meta Description

| ID | Meta Title | Meta Desc | Legal in Meta? |
|----|-----------|-----------|----------------|
| 9765 | (not set) | (not set) | N/A |
| 9773 | (not set) | (not set) | N/A |
| 9774 | (not set) | (not set) | N/A |
| 8714 | (not set) | (not set) | N/A |
| 1516 | (not set) | "Short sales explained for buyers and sellers..." | No |
| 8688 | (not set) | "Texas Veterans applying for a VA Loan after a foreclosure or short sale typically face a two-year waiting period..." | No |
| 2233 | "How to Buy Foreclosures in San Antonio (2026) \| LRG" | "Learn how to buy foreclosures..." | No |
| 2226 | "Buying Foreclosures in Austin, TX: A 2026 Guide \| LRG" | "Learn how to navigate..." | No |
| 2230 | "Foreclosed Homes in Killeen, TX: Buying Guide 2026 \| LRG" | "Learn how to buy foreclosures in Killeen..." | No |

**All three Phase 1 pages and the beachhead (8714) have no meta title or meta description set.** Yoast/Rank Math will auto-generate from post title and content, but these are YMYL pages where the meta description should be deliberately crafted. No legal conclusions found in any set meta descriptions.

### 3H. CTA Analysis

| ID | Equity Analysis CTA | Generic CTA | Assessment |
|----|--------------------|--------------|----|
| 9765 | NO | "Connect with LRG" | Should be "Get My Free Home Equity Analysis" per strategy |
| 9773 | NO | "Connect with LRG" | Should be equity analysis |
| 9774 | NO | "Connect with LRG" | Should be equity analysis |
| 8714 | NO | "Connect with LRG" | Should be equity analysis |
| All others | NO | Mixed | Generic CTAs across the board |

**Zero pages in the distressed vertical use the "Get My Free Home Equity Analysis" CTA** that the strategy document specified. All use the generic "Connect with LRG" CTA.

### 3I. Layout/Template Pattern

All Phase 1 pages and most existing topical pages use the `rl-page` template. Consistent patterns:
- H2 count: 9-14
- FAQ section (details/summary): Present on all
- Table present: All Phase 1 + most existing
- rl-kcards: None of the profiled pages use kcards

Outliers:
- **5435 (Bankruptcy SA):** No rl-page wrapper, only 1,908 words (below pipeline minimum)
- **5433 (VA Bad Credit SA):** No rl-page wrapper, 2,876 words
- **8943 (Real Estate Problems Hub):** rl-page but under /tools/ path, not /lrg-blog/

### 3J. Internal Links Analysis

**Orphan pages (zero links IN):**

| ID | Title | 90d Impressions | Priority |
|----|-------|----------------|----------|
| 9765 | Options Pillar (Phase 1) | 0 | CRITICAL -- pillar page with no links |
| 9773 | PCS Underwater (Phase 1) | 0 | CRITICAL |
| 9774 | Short Sale vs Foreclosure (Phase 1) | 0 | CRITICAL |
| 2233 | Buy Foreclosure SA | 2,175 | HIGH -- best-performing distressed page, zero links |
| 2226 | Buy Foreclosure Austin | 625 | HIGH |
| 2230 | Buy Foreclosure Killeen | 752 | HIGH |
| 8943 | Real Estate Problems Hub | 0 | MEDIUM |

**Well-linked pages:**

| ID | Title | Links IN |
|----|-------|----------|
| 1516 | Understanding Short Sales | 46 |
| 2110 | Fort Sam Houston PCS Sell | 43 |
| 2717 | Sell Before PCS SA | 21 |
| 5433 | VA Loan Bad Credit SA | 14 |
| 2861 | VA Loan Assumption | 10 |
| 5435 | Buying After Bankruptcy SA | 6 |

**Internal links OUT from Phase 1 pages:**

| ID | Links OUT | Target Pages |
|----|-----------|-------------|
| 9765 | 8 internal, 11 external | Links to HUD, IRS, CFPB, Property Code. Missing links to 9773, 9774, 8714. |
| 9773 | 12 internal, 9 external | Links to HUD, VA.gov. Missing links to 9765, 9774. |
| 9774 | 4 internal, 9 external | Fewest internal links of the three. Missing links to 9765, 9773. |

**The Phase 1 cluster has no internal cross-linking.** They don't link to each other and nothing links to them.

---

## 4. CANNIBALIZATION MAP

### 4A. Intent Clusters

**Cluster: "Options for underwater/distressed homeowner in Texas"**
- 9765 (pillar) -- TX-authority, comprehensive options
- 8943 -- "Real Estate Problems" hub, lighter version
- **Risk: LOW.** 8943 is under /tools/ and focuses on "house won't sell" listing strategy. 9765 is the YMYL deep dive. Different enough.

**Cluster: "Short sale process/mechanics"**
- 1516 -- General explainer, buyer-and-seller angle
- 9774 -- Short sale vs foreclosure comparison
- **Risk: MODERATE.** 1516 targets "understanding short sales" (informational). 9774 targets "short sale vs foreclosure texas" (comparison). Overlap exists in the process explanation sections. 1516 has 46 internal links; any redirect must be handled carefully.

**Cluster: "PCS/military + underwater/equity"**
- 9773 -- PCS with underwater mortgage (military-specific)
- 8714 -- Selling during PCS with low/no equity
- 2717 -- General PCS selling checklist
- 2110 -- Fort Sam Houston PCS selling
- 2500 (draft) -- PCS home sale checklist SA
- 2505 (draft) -- PCS to JBSA seller's guide
- 2701 (draft) -- Fort Cavazos PCS timeline
- **Risk: HIGH.** This is the most crowded cluster. 9773 and 8714 have scope overlap (both address "PCS + can't cover equity gap"). 2717 and 2110 are general PCS selling but touch the equity topic. Three drafts (2500, 2505, 2701) add further overlap risk. Publishing any draft without deduplication will cannibalize.

**Cluster: "Foreclosure buying guides (buyer-side)"**
- 2233 -- SA foreclosure buying
- 2226 -- Austin foreclosure buying
- 2230 -- Killeen foreclosure buying
- **Risk: NONE among themselves** (different geos). But they compete with each other on generic "foreclosure" queries -- GSC shows 2233 appearing for bare "foreclosure" at pos 6.2.

**Cluster: "VA loan recovery after credit event"**
- 8688 -- VA loan after foreclosure/short sale
- 5435 -- Buying after bankruptcy SA
- 5433 -- VA loan with bad credit SA
- **Risk: LOW.** Different intent angles (VA-specific vs general credit recovery vs bad-credit-specific).

### 4B. Cross-Reference: Phase 1 vs Existing Pages

| Phase 1 Page | Overlaps With | Resolution |
|-------------|---------------|-----------|
| 9765 (Options Pillar) | 1516 (Understanding Short Sales) | 1516 is buyer+seller generic; 9765 is seller-focused TX-specific. Coexist but 1516 redirect decision still open (per strategy doc pre-publishing checklist). |
| 9765 (Options Pillar) | 8943 (Real Estate Problems) | Different intent and location (/tools/ vs /lrg-blog/). Coexist. |
| 9773 (PCS Underwater) | 8714 (PCS No Equity) | Most significant overlap. 8714 covers "equity-thin but not underwater." 9773 covers "actually underwater." The line is blurry in practice -- a reader at 8714 might be underwater. Cross-link with clear scope differentiation. |
| 9774 (Short Sale vs Foreclosure) | 1516 (Understanding Short Sales) | 9774 is comparison-focused. 1516 is process-focused. Low overlap. |

---

## 5. POST 8714 -- BEACHHEAD PROFILE

**URL:** https://lrgrealty.com/lrg-blog/selling-home-pcs-no-equity-texas/
**Title:** Selling a Home During a PCS With Little or No Equity
**Status:** publish | **Author:** Levi Rodgers | **Words:** 3,807
**Published:** 2026-07-02 | **Modified:** 2026-07-28

### Current State Assessment

| Dimension | Finding | Status |
|-----------|---------|--------|
| GSC Performance | 5 impressions, 0 clicks over 90 days | WEAK -- not validated as durable #1 |
| Educational Notice | Missing | DEFECT |
| Legal/Tax Disclaimer | Missing | DEFECT |
| Equity Analysis CTA | Missing (uses generic "Connect with LRG") | GAP |
| Sources Cited | **Zero** | DEFECT -- YMYL page with no authoritative sources |
| Meta Title | Not set | GAP |
| Meta Description | Not set | GAP |
| Fort Cavazos | Clean | OK |
| Fair Housing | Clean | OK |
| Tax Language | Clean | OK |
| UPL | 3 flags, all OK on review | OK |
| Internal Links IN | 2 (from 2110 and 2756) | THIN |
| Internal Links OUT | 9 internal, 8 external | ADEQUATE |
| Template | rl-page, 10 H2s, FAQ details, table | CONSISTENT |
| rl-kcards | Not present | Per spec (not required) |

**Strategy doc claimed 8714 as "#1 organic for 'selling home pcs no equity'"** based on a single Serper.dev pull on Aug 9. GSC data (90-day window) shows only 5 total impressions for this page across all queries, none for "selling home pcs no equity" specifically. This does not confirm a durable #1 position. The pre-publishing checklist item "Post 8714 #1 validation" remains OPEN.

### Priority Fixes for 8714

1. Add both disclaimer blocks (Educational Notice + Legal/Tax Disclaimer)
2. Add authoritative source citations (currently zero)
3. Set meta title and meta description
4. Replace generic CTA with "Get My Free Home Equity Analysis Before Your PCS"
5. Cross-link to 9773 (PCS underwater) for readers who are actually underwater, not just equity-thin

---

## 6. VALN SISTER SITE COVERAGE

VALN has **7+ dedicated pages** covering VA-specific distressed mechanics. Confirmed via database query on valoannetwork.com:

| VALN ID | Title | Term Matches |
|---------|-------|-------------|
| 36659 | VA Loan After Deed in Lieu: Eligibility and Recovery | 9 terms |
| 36929 | VA Foreclosure Avoidance: Every Option Veterans Have in 2026 | 9 terms |
| 10786 | Understanding the VA Compromise Sale Program | 8 terms |
| 10931 | VA Foreclosure Moratorium | 8 terms |
| 36939 | Underwater on Your VA Mortgage? Options for Upside-Down Veterans | 7 terms |
| 36928 | VA Loan Modification: How It Works and When Veterans Qualify | 7 terms |
| 36657 | VA Loan After Short Sale: Waiting Periods and Eligibility | 6 terms |
| 5495 | VA Loan After Foreclosure: 2026 Waiting Period & Rules | 6 terms |
| 36735 | What Happens to a VA Loan When the Veteran Dies | 7 terms |
| 13402 | VA Partial Claim Program 2026 | -- |

**Cross-site division is clean.** VALN owns VA loan mechanics (compromise sale, entitlement, waiting periods, loan modification). LRG owns "what do I do as a Texas homeowner" (local options, broker perspective, TX-specific legal). No duplication needed.

**Cross-linking gap:** LRG Phase 1 pages should link to VALN 10786 (VA Compromise Sale) and 36939 (Underwater VA options) but this has not been verified in the current link-out data.

---

## 7. GSC PERFORMANCE DATA

**Source:** GSC Search Analytics API, sc-domain:lrgrealty.com, 2026-05-14 to 2026-08-12 (90 days)

### Top Distressed-Topic Queries (all pages)

| Query | Clicks | Impr | Pos | Page |
|-------|--------|------|-----|------|
| foreclosure | 1 | 1,203 | 6.2 | /how-to-buy-foreclosure-san-antonio/ |
| foreclosed homes san antonio | 2 | 292 | 10.6 | /how-to-buy-foreclosure-san-antonio/ |
| how to buy foreclosed homes in texas | 1 | 250 | 10.5 | /how-to-buy-foreclosure-san-antonio/ |
| austin foreclosures | 0 | 148 | 8.0 | /how-to-buy-foreclosure-austin/ |
| foreclosure (Killeen) | 0 | 143 | 5.8 | /how-to-buy-foreclosure-killeen/ |
| how to buy a foreclosed home in texas | 1 | 96 | 6.7 | /how-to-buy-foreclosure-san-antonio/ |
| va loan short sale | 0 | 60 | 8.8 | /va-loan-after-foreclosure-short-sale-texas/ |
| va short sale | 0 | 59 | 10.3 | /va-loan-after-foreclosure-short-sale-texas/ |
| bank foreclosures killeen tx | 1 | 55 | 9.0 | /how-to-buy-foreclosure-killeen/ |
| foreclosures san antonio | 1 | 53 | 10.7 | /how-to-buy-foreclosure-san-antonio/ |
| va foreclosure waiting period | 0 | 47 | 9.8 | /va-loan-after-foreclosure-short-sale-texas/ |
| va shortsale | 0 | 45 | 9.1 | /va-loan-after-foreclosure-short-sale-texas/ |

### Key Observations

- **Buyer-side foreclosure guides dominate traffic.** 2233 (SA) alone has 2,175 impressions. The buyer-side content outperforms seller-side distressed content by 100x.
- **Zero clicks on any seller-side distressed query.** Not a single click for short sale, underwater, or PCS + equity queries.
- **VA after short sale is the strongest seller-side signal:** 563 impressions on 8688, positions 7.6-10.3 for VA short sale variants.
- **Phase 1 pages show zero GSC data** -- expected at 3 days old.
- **8714 (beachhead) has only 5 impressions** over 90 days -- the "#1 ranking" from the Serper pull is not confirmed.

---

## 8. INCIDENTAL MENTION PAGES (useful for internal linking)

589 posts mention at least one distressed term in passing. The most link-worthy for the distressed cluster:

| ID | Title | Matched Terms | Link Value |
|----|-------|--------------|------------|
| 1586 | Trump's 50-Year Mortgage Plan | underwater, negative equity, low equity, no equity, owe more than | HIGH -- natural link to pillar |
| 7411 | SA Housing Market 2026 | foreclosure, distressed | HIGH -- market context links |
| 7412 | Austin Housing Market 2026 | foreclosure, distressed | HIGH -- Austin underwater links |
| 8264 | SA Housing Market Mid-Year | foreclosure | HIGH |
| 8900 | Low Appraisal Guide | negative equity, owe more than | MEDIUM |
| 1918 | Keep and Rent Move-Up Strategy | negative equity, PCS | MEDIUM |
| 2302 | JBSA PCS Housing 90-Day Plan | no equity, PCS, orders | MEDIUM |

---

## 9. PROTECTED POST IDs

Posts 2794, 2790, 2797, 2095 -- confirmed present, no staged changes against them. This session wrote nothing.
