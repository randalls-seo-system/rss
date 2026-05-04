# Sitewide Anchor & Link Quality Audit — 2026-05-03

## Executive Summary

Four distinct link quality problems identified. Combined scope: ~350 unique posts affected (roughly 45% of published content).

| Problem | Instances | Posts | Severity |
|---------|-----------|-------|----------|
| 1. Sub-word anchor splits | 171 | 132 | Critical |
| 2. Non-descriptive anchors | ~50 real | ~40 | Medium |
| 3. Same URL repeated 3+ times | 203 posts | 203 | Medium |
| 4. External links dominate internal | 214 posts | 214 | Medium |

---

## Problem 1: Sub-Word Anchor Splits

**171 instances across 132 posts.**

The link injector (`link-injector-v3.php`) wraps partial words in anchor tags because `stripos()` matches substrings without word boundary checks.

### Severity Tiers

**CRITICAL — Acronyms matched inside unrelated words (13 instances):**
- `"aus"` inside "because" → `bec<a>aus</a>e` — 9 posts
- `"mpr"` inside "comprehensive"/"improve" → `co<a>mpr</a>ehensive` — 3 posts
- `"income qualification"` + `"ication"` → `qualificationication` — 1 post
- `"occupancy requirements"` + `"ments"` → `requirementsments` — 1 post
- `"funding fee exemption"` + `"ion"` → `exemptionion` — 1 post

**HIGH — Suffix splits creating garbled text (28 instances):**
- `"VA closing costs"` → `costss` (6 posts)
- `"student loan DTI rules"` → `ruless` (4 posts)
- `"VA pre-approval"` → `pre-approvalal` (2 posts)
- `"rent"` → `<a>rent</a>al` (splitting "rental")
- `"closing time"` → `<a>closing time</a>lines` (splitting "timelines")
- `"mortgage plan"` → `<a>mortgage plan</a>ning` (splitting "planning")
- `"cash out"` → `<a>cash out</a>lay` (splitting "outlay")

**MEDIUM — Plural suffix splits (~100 instances):**
- Singular anchor matches plural text: `<a>closing cost</a>s`, `<a>property tax</a>es`, `<a>credit score</a>s`, `<a>disabled Veteran</a>s`, etc.

**MEDIUM — CTA markup corruption (11 instances):**
- Literal "n" chars instead of newlines in CTA markup. Different root cause (deployment encoding error).

**LOW — Trailing words caught (~8 instances):**
- Likely false positives from trailing spaces in anchor text entries.

### Root Cause

`link-injector-v3.php` line 61:
```php
$p = stripos($pi, $a);  // matches substring anywhere — no word boundary
```

Fix required: add `\b` word boundary regex or check chars before/after match position.

---

## Problem 2: Non-Descriptive Anchor Text

**~50 genuinely problematic instances** (excluding 90+ intentional breadcrumb "Home" links and ~12 fragments already counted in Problem 1).

| Type | Count | Examples |
|------|-------|---------|
| Short acronym anchors | ~30 | COE, DTI, AUS, BAH, PMI, LTV |
| Generic single words | ~10 | rent, roof, cash, lead, None |
| Other very short | ~10 | Data, MPRs, TRA, HDIP, PCS |

### Root Cause

`anchor-map.csv` contains bare acronym entries (e.g., `DTI` for /what-is-dti-ratio/, `COE` for /va-certificate-of-eligibility/). The injector uses these without expanding to descriptive phrases.

---

## Problem 3: Same URL Repeated 3+ Times Per Post

**203 posts have at least one URL linked 3 or more times.**

### Most-Repeated URLs (across all posts)

| URL | Posts with 3+ repeats | Max in single post |
|-----|----------------------|-------------------|
| `/compare-loan-offers/` (CTA) | 59 | 7x |
| VA.gov funding fee page | 17 | 8x |
| VA.gov home loans page | 8 | 3x |
| `/disabled-veterans-exempt-from-va-funding-fee/` | 7 | 3x |
| VA.gov benefits/warms | 6 | 5x |

### BAH Page (11040) — Specific Inventory

84 total links (61 internal, 23 external).

**External repeats on BAH page:**
- DTMO BAH Rate Lookup: **5x** (same URL, 4 with identical "BAH Rate Lookup" anchor)
- DTMO BAH Overview: **6x** (same URL, 4 identical "DTMO BAH Overview")
- JTR PDF: **4x** (alternating "Joint Travel Regulations (JTR)" and "JTR")
- DTMO BAH FAQ: **2x**

Total: 17 of 23 external links go to just 4 unique URLs.

### Pattern: Three-Touch Citation Structure

V6 articles cite each source in three places:
1. `vlnMeta` (ATF primary sources)
2. Inline body citations
3. `vlnDisclosure` (Resources Used)

This creates a structural minimum of 3x per source. Major sources (.gov) get additional inline mentions, pushing to 4-8x.

### Root Cause

Content generation prompt (CLAUDE.md rewrite spec) requires sources in ATF meta, body, and Resources Used — creating mandatory 3+ repetitions. No deduplication guidance exists in the spec.

---

## Problem 4: External Links Outnumber Internal Links

**214 posts** where external links exceed contextual internal links (excluding CTA).

### Sitewide Balance
- Internal-dominant: 558 posts
- External-dominant: 170 posts
- Balanced: 46 posts

### Worst Offenders (external gap)

| Post | Internal (contextual) | External | Gap |
|------|----------------------|----------|-----|
| 6220 mortgage-credit-scores-vs-credit-karma | 13 | 56 | +43 |
| 4211 best-va-rate-in-todays-market | 2 | 39 | +37 |
| 9726 va-pay-overview-benefits | 4 | 33 | +29 |
| 32096 best-places-veterans-live-2026 | 14 | 38 | +24 |
| 29121 va-lgy-25-4-2-coe-eligibility-api-update | 8 | 31 | +23 |
| 9671 guide-to-filing-va-disability-claim | 2 | 23 | +21 |
| 12296 refinance-va-loan-to-conventional | 8 | 29 | +21 |

### BAH Page Balance
- Internal: 61 (50 are state page links, 8 are BAH-cluster articles, 3 are injected — "mpr", "aus", "duplex")
- External: 23 (but 17 are repeats of 4 URLs)
- BAH is internal-dominant overall, but the external links get prominent, repeated, keyword-rich anchor text while internal injected links are broken fragments.

### Root Cause

Two compounding factors:
1. Content spec mandates .gov and authority citations throughout — each article gets 8-20+ external links by design
2. Internal links are added in a separate injection pass after content creation — they start from behind

The spec's "Primary sources" requirement in ATF, inline citations with descriptive anchor text, and Resources Used section all feed authority to external sources with strong keyword-rich anchors, while internal pages get contextual mentions added after the fact.

---

## Root Cause Summary — Answering Your Questions

### 1. Is the content auto-generated or human-written?
**Auto-generated by Claude Code rewrite pipeline.** The V6 content spec (`~/valn-rewrite/CLAUDE.md`) produces articles with mandatory three-touch citation structure. The 15 gap-fill articles from April also contributed.

### 2. Which prompt produced this style?
The **content spec's ATF template** requires `vlnMeta` primary sources + inline citations + `vlnDisclosure` Resources Used. The prompt instructs: "2-3 official .gov or industry-authority sources" and "Resources Used must be last section." No cap on total external link count per article.

### 3. The "duplexes" sub-word split — injector or manual?
**100% from link-injector-v3.php.** The anchor text "duplex" in anchor-map.csv was searched via `stripos()` inside "duplexes" without word boundary check. Same mechanism produced all 171 splits.

### 4. External link repetition — from citation pattern?
**Yes.** The three-touch citation pattern (ATF meta → body inline → Resources Used) forces each source to appear 3+ times. Articles with 4-5 primary sources easily hit 15-20 external links before any internal links are added.

---

## Prior Audit Gap

Work log entry 246 (April 27): "Sitewide anchor text audit" found and fixed only 28 instances on 22 pages. That audit:
- Only targeted weak single-word anchors
- Did NOT scan for the `</a>[a-z]+` sub-word split pattern
- Did NOT audit repeated URLs or external/internal balance
- Missed 85% of Problem 1 and 100% of Problems 3-4

---

## Detailed Data Files

- Split instances: `~/valn-rewrite/anchor-audit-2026-05-03.csv`
- Repeated URLs raw output: stored in Claude tool-results cache
- This report: `~/valn-rewrite/anchor-audit-expanded-2026-05-03.md`
