# RSS Article Spec v0

**Status:** DRAFT v0 — pending Randall's review of unresolved questions in `valn-pattern-extraction.md`.

**Purpose:** This is the single source of truth for what an article is in Randall's SEO System. Every module references this document. Prompts cite it. Validators enforce it. Templates implement it. When two parts of the system disagree, this document wins.

**Scope:** Defines the structure, content rules, and validation logic for any rewrite or new article produced by the content-production module. Does NOT cover: hub/spoke organization (separate spec), site-level configuration (`sites/<slug>.conf`), brand voice (`brand-voice/archetypes/<archetype>.md`), CSS components (`rl-components/`).

---

## 1. INTENT TYPES (closed set)

Every article is classified into exactly one intent. Intent drives card labels, callout type defaults, table-vs-bullet defaults, and FAQ source priorities.

| Intent | Trigger keywords | Card-shape | Body-default | Callout defaults |
|---|---|---|---|---|
| `definition` | "what is", "explained", "guide to", "understanding" | 4 cards: definition, key facts, why it matters, common confusions | bullets-dominant | File Guidance, Scenario |
| `process` | "how to", "step by step", "guide to", "checklist" | 4 cards: prerequisites, what you need, timeline, costs | bullets-dominant | Deal Saver, Approval Watchpoint |
| `decision` | "X vs Y", "which", "should I", "is X worth" | 4 cards: option A subtopics, option B subtopics, who chooses A, who chooses B | tables-dominant | Deal Math, Lender Reality Check (or archetype equivalent) |
| `cost` | "how much", "cost of", "fee", "price", "rate" | 4 cards: rates by category, rates by scenario, exemptions/reductions, real-world dollar examples | tables-dominant | Deal Math, Lender Reality Check |
| `comparison` | "best X", "top X", "X ranked", "X reviews" | 4 cards: top pick, runner-up, best for X niche, how we scored | tables-dominant | Underwriter's Note, Deal Math |

**Rule 1.1:** Intent is detected by `detect-intent.py` from the target keyword + SERP signals. Override is supported via `--intent` flag.

**Rule 1.2:** Cost is a distinct intent from comparison. Currently the code conflates them. Spec change: split.

**Rule 1.3:** Tool-anchored articles (calculator embeds) are a future variant, not in v0 scope.

---

## 2. ARTICLE SKELETON (canonical structure)

The 14-section skeleton, in order. Required vs optional explicitly marked.

| # | Section | Required? | Validator check |
|---|---|---|---|
| 1 | Header prelude (breadcrumb, eyebrow, H1, byline, primary sources) | REQUIRED | All sub-elements present |
| 2 | Jump nav (5 anchor links, last is "FAQs") | REQUIRED | Exactly 5 links; last text == "FAQs"; first 4 anchors resolve to H2s |
| 3 | ATF lede (50-60 word answer-first paragraph) | REQUIRED | Word count 40-110; first sentence has no `?` |
| 4 | First CTA pill | REQUIRED | Link href matches `CTA_URL` from site config |
| 5 | ATF quick-card grid (4 cards) | REQUIRED | Exactly 4 cards; each has H3 and 4 bullets |
| 6 | ATF FAQs (3 items) | REQUIRED | Exactly 3 items; answers 35-60 words; no inline links |
| 7 | Tool embed | OPTIONAL | Skip in v0 |
| 8 | Bottom Line Up Front (BLUF) | OPTIONAL | Word counts: lead 50-70, body 70-100, capstone 5 bullets |
| 9 | Body H2 sections (6-15 H2s) | REQUIRED | H2 count 6-15; each has answer-first intro + ≥1 structural element |
| 10 | Mid-article CTA pill | REQUIRED | Same href as first CTA |
| 11 | Closing "The Bottom Line" section | REQUIRED | Word count 100-150; no bullets; no external links |
| 12 | BTF FAQs section | REQUIRED | 5-12 items; no overlap with ATF FAQs |
| 13 | Resources Used | REQUIRED | 5-8 items; ≥3 distinct domains; anchor format compliance |
| 14 | "In this Article" TOC | REQUIRED | Auto-generated from H2 inventory |

---

## 3. HEADER PRELUDE

### 3.1 Breadcrumb
```
Home → {Parent Category} → {Page Title}
```
- Parent category from site config: `BREADCRUMB_PARENT_LABEL` and `BREADCRUMB_PARENT_URL`.
- Page title is `<h1>` text, optionally truncated.

### 3.2 Eyebrow
**Format:** `{Topic} · {Subtitle enumerating subtopics}`

- Topic: 1-4 words. Capitalized. Often includes year.
- Subtitle: 4-10 words. Enumerates the article's main H2s in shortened form.

**Examples (from VALN gold standard):**
- "2026 VA Funding Fee · Rates, Exemptions, Refunds, and 2026 Updates"
- "2026 VA Loan Requirements · COE Basics, Credit Overlays, Funding Fees, And Occupancy Gotchas"

**Rule 3.2.1:** Eyebrow subtitle is built FROM the H2 inventory, not from a static intent tag. The current `atf-decision.md` prompt hardcodes "Comparison" — this is wrong.

### 3.3 H1
- One per page. Includes year for time-sensitive topics. 5-15 words.
- Mirrors target keyword but does not need to match exactly.

### 3.4 Byline
**Format:**
```
[Author photo] [Reviewer photo]

Written by: {Author name} · NMLS#{author NMLS, linked to nmlsconsumeraccess.org}
Reviewed by: {Reviewer name}, {Reviewer title} · NMLS#{reviewer NMLS, linked}
Updated on {Month Day, Year}
```

- All values from site config: `AUTHOR_NAME`, `AUTHOR_NMLS`, `AUTHOR_PHOTO_URL`, `REVIEWER_NAME`, `REVIEWER_TITLE`, `REVIEWER_NMLS`, `REVIEWER_PHOTO_URL`.
- Updated date: today's date when article is generated.

**Rule 3.4.1:** For sites without dual-credential bylines (e.g., LRG real estate), site config supports `BYLINE_MODE = single` to skip reviewer.

### 3.5 Primary sources
**Format:** `Primary sources: {link 1} · {link 2} · {link 3}`

- 3 external authoritative URLs.
- Sourced from SERP top organic results (filtered to .gov / authoritative non-competitor domains).
- Anchor text follows the **External Anchor Format** rule (Section 11.2).

**Rule 3.5.1:** This element is novel — not in current RSS prompts. Must be added.

---

## 4. JUMP NAV

**Format:** Exactly 5 anchor links, separated by line breaks or pipes:
```
Subtopic 1
Subtopic 2
Subtopic 3
Subtopic 4
FAQs
```

**Rule 4.1:** Last link is always "FAQs", anchored to BTF FAQ section.

**Rule 4.2:** First 4 link texts MUST match (in shortened form) the labels of:
- ATF quick-card #1 H3
- ATF quick-card #2 H3
- ATF quick-card #3 H3
- ATF quick-card #4 H3

This enforces the **jump-nav ↔ card-label ↔ H2-label triangle** that VALN articles use.

**Rule 4.3:** First 4 anchors resolve to H2s in the body. (Cards summarize body H2s, jump-nav points to body H2s.) The summary→detail relationship.

---

## 5. ATF LEDE

**Format:** Single paragraph (preferred) or two paragraphs (acceptable for complex topics).

**Word count:**
- Single-paragraph: 40-110 words. Target 50-60.
- Two-paragraph: 80-200 words combined. Each paragraph 40-100 words.

**Content rules:**
- 5.1 Sentence 1 states the conclusion / direct answer to the target query.
- 5.2 Sentence 2 introduces concrete numbers, ranges, or list size ("the three biggest pressure points").
- 5.3 Sentence 3 introduces a wrinkle, exception, or "the catch."
- 5.4 No inline links in the ATF lede.
- 5.5 No questions in the lede (declarative only).
- 5.6 Anti-pattern words/phrases banned: "discover", "explore", "vibrant", "dive into", "let's", "we'll cover".

---

## 6. ATF QUICK-CARD GRID

This is the section the current RSS gets most wrong. Spec replaces hardcoded labels with **structure-derived labels.**

### 6.1 Cardinality
Exactly 4 cards per article. Not 2 (current decision intent), not "2 if news else 4" (current validator). 4.

### 6.2 Card structure
```html
<article class="rl-quick-card">
  <h3>{Card title}</h3>
  <ul>
    <li><strong>{Bullet label 1}:</strong> {Bullet content, 14-30 words}</li>
    <li><strong>{Bullet label 2}:</strong> {Bullet content, 14-30 words}</li>
    <li><strong>{Bullet label 3}:</strong> {Bullet content, 14-30 words}</li>
    <li><strong>{Bullet label 4 — synthesis bullet}:</strong> {Synthesis content, often with concrete number, 18-35 words}</li>
  </ul>
</article>
```

### 6.3 Card title rules
**Card titles are SUBTOPIC NAMES, not generic labels.**

The 4 card titles are derived from one of two sources:
- (a) The article's H2 inventory's first 4 H2s (post-BLUF)
- (b) The intent overlay's named subtopic slots

**Rule 6.3.1:** Card titles must match jump-nav labels (Section 4) and the first 4 body H2 labels (Section 9).

**Rule 6.3.2:** Card titles do NOT use generic intent labels like "Best for" / "Key advantage" / "Watch out". These are bullet labels, not card titles. The current prompts confuse these levels.

### 6.4 Bullet label rules
- 6.4.1 Bullet labels describe the bullet's content, not the card's content. Examples: "Common exemptions:", "Alternative pay status counts:", "Retroactive refund path:", "Timing matters:".
- 6.4.2 Bullet labels are 1-4 words, end in colon, formatted with `<strong>`.
- 6.4.3 Bullet labels are unique within a card.
- 6.4.4 The 4th bullet is a "synthesis" bullet — usually contains the concrete number, threshold, or consequence-rule that ties the card together. Often labeled "Bottom line:", "Break-even:", "Main takeaway:", "Worth noting:" — synthesis-flavored.

### 6.5 Bullet content rules
- 6.5.1 Word count: bullets 1-3 are 14-30 words. Synthesis bullet is 18-35 words.
- 6.5.2 No links inside bullets. (Links go in body H2 sections.)
- 6.5.3 Concrete numbers preferred. "On a $300,000 purchase" > "On a typical purchase."
- 6.5.4 No filler verbs ("dive into", "explore"). No emojis. No em dashes.

### 6.6 Intent overlay reference
The actual labels for cards in v0 come from these intent overlays. These are STARTING POINTS. The LLM derives the article-specific labels from these slots + the SERP gap analysis.

```yaml
# overlays/definition.yaml
card_slots:
  - role: definition_card
    h3_pattern: "What Is {Term}?"
  - role: key_facts_card
    h3_pattern: "Key Facts About {Term}"
  - role: why_matters_card
    h3_pattern: "Why {Term} Matters"
  - role: common_confusions_card
    h3_pattern: "{Term} Misconceptions"
```

```yaml
# overlays/process.yaml
card_slots:
  - role: prerequisites_card
    h3_pattern: "Before You Start"
  - role: requirements_card
    h3_pattern: "What You Need"
  - role: timeline_card
    h3_pattern: "Process Timeline"
  - role: costs_card
    h3_pattern: "What It Costs"
```

```yaml
# overlays/cost.yaml
card_slots:
  - role: rates_by_category_card
    h3_pattern: "{Topic} Rates by Category"
  - role: rates_by_scenario_card
    h3_pattern: "{Topic} by Down Payment Tier"  # variable per topic
  - role: exemptions_card
    h3_pattern: "Exemptions and Reductions"
  - role: examples_card
    h3_pattern: "Real-World {Topic} Examples"
```

```yaml
# overlays/decision.yaml
card_slots:
  - role: option_a_card
    h3_pattern: "{Option A} at a Glance"
  - role: option_b_card
    h3_pattern: "{Option B} at a Glance"
  - role: who_picks_a_card
    h3_pattern: "When {Option A} Wins"
  - role: who_picks_b_card
    h3_pattern: "When {Option B} Wins"
```

```yaml
# overlays/comparison.yaml
card_slots:
  - role: top_pick_card
    h3_pattern: "Top Pick: {Winner}"
  - role: runner_up_card
    h3_pattern: "Runner-Up: {Second}"
  - role: niche_card
    h3_pattern: "Best for {Niche Use Case}"
  - role: methodology_card
    h3_pattern: "How We Scored"
```

**Rule 6.6.1:** Overlays are templates, not strict text. LLM substitutes `{Term}`, `{Topic}`, `{Option A}` from the target keyword + SERP context, AND may rewrite `h3_pattern` if a more natural article-specific label emerges from the SERP top results.

**Rule 6.6.2:** Each overlay file lives at `modules/content-production/overlays/{intent}.yaml`. The current `prompts/atf-{intent}.md` files are deprecated and replaced by overlay-driven generation.

### 6.6.3 Overlay variable vocabulary

Overlay `h3_pattern` and `bullet_label_hints` fields support these template variables, resolved by the assembler from the target keyword + SERP context:

- `{Topic}` — the article's noun-form topic (e.g., "VA Funding Fee")
- `{Term}` — for definition intent: the term being defined
- `{Year}` — the article's year, when time-sensitive
- `{Option A}` / `{Option B}` — for decision/comparison intents: parsed from the target keyword's "X vs Y" pattern
- `{Winner}` / `{Second}` / `{Niche}` — for comparison intent: derived from SERP top results' ordering or explicit overlay input
- `{Niche Use Case}` — for comparison intent: derived from the SERP's distinguishing-criteria signals

Variables are case-sensitive. Unknown variables in an overlay file are a hard error in the overlay loader.

---

## 7. ATF FAQs

### 7.1 Cardinality
Exactly 3 items.

### 7.2 Source priority
1. Top 3 PAA questions from SERP, filtered for relevance to target keyword
2. If PAA returns fewer than 3, fill from AI Overview's listed questions
3. If both sources empty, generate from intent overlay's "default ATF FAQ patterns" (each overlay has these as fallback)

### 7.3 Format
```html
<details>
  <summary>{Question, ending in ?}</summary>
  <p>{Answer, 35-60 words, 1-2 sentences}</p>
</details>
```

### 7.4 Content rules
- 7.4.1 No inline links in answers.
- 7.4.2 First FAQ should restate the article's central question (e.g., "What is the VA funding fee in 2026?" for an article on the VA funding fee).
- 7.4.3 Answer length: 35-60 words. Strict.
- 7.4.4 Answer should not require reading the body to understand. Self-contained.

---

## 7.5 EXPLORE-RESOURCES HUB BOX (cluster link box)

When the article belongs to a topic cluster with ≥3 sibling pages, include an
Explore-Resources hub box between the ATF section and the main body. This box
links the reader to related cluster articles and strengthens internal linking.

### 7.5.1 Format
```html
<aside class="rl-cluster-box">
  <h2>Explore {Topic} Resources</h2>
  <p>{1-2 sentence description of the cluster}</p>
  <ul>
    <li><a href="{url}">{Page title}</a> — {6-12 word description}</li>
    ...
  </ul>
</aside>
```

### 7.5.2 Rules
- 7.5.2.1 Include 5-7 links to sibling/child pages in the same cluster.
- 7.5.2.2 Links are sourced from the site's anchor pool cluster data. If cluster
  data is unavailable (new site, no cluster map), omit the hub box entirely.
- 7.5.2.3 Do NOT duplicate links that already appear in the body — the hub box
  is for cluster navigation, body links are for contextual reading.
- 7.5.2.4 The hub box is OPTIONAL. It is omitted when fewer than 3 cluster
  siblings exist or when cluster data is not yet populated.

---

## 8. BOTTOM LINE UP FRONT (BLUF)

### 8.1 When to include
INCLUDE for all intents. Every article benefits from a BLUF that sets the
reader's expectations. Overlay `bluf_default` controls per-intent behavior:
- Intent is `cost` → always include
- Intent is `decision` → always include
- Intent is `process` → always include
- Intent is `definition` → always include
- Intent is `comparison` → always include

### 8.2 Format
```html
<section class="rl-bluf">
  <h2>The Bottom Line Up Front</h2>
  <p><strong>{Lead paragraph: 50-70 words. States the central claim and identifies the friction point.}</strong></p>
  <p>{Body paragraph: 70-100 words. Concrete numbers, edge cases, named exceptions.}</p>
  <ul>
    <li>{Capstone bullet 1, 12-20 words}</li>
    <li>{Capstone bullet 2, 12-20 words}</li>
    <li>{Capstone bullet 3, 12-20 words}</li>
    <li>{Capstone bullet 4, 12-20 words}</li>
    <li>{Capstone bullet 5, 12-20 words}</li>
  </ul>
</section>
```

### 8.3 Content rules
- 8.3.1 Lead paragraph is bolded entirely. Other elements are not.
- 8.3.2 Lead paragraph CAN have 1-3 inline internal links.
- 8.3.3 Body paragraph CAN have 1-2 inline internal links.
- 8.3.4 Capstone bullets have NO inline links.
- 8.3.5 Exactly 5 capstone bullets. Not 4, not 6.

---

## 9. BODY H2 SECTIONS

### 9.1 Cardinality
6-15 H2 sections in the body (excluding BLUF, BTF FAQ, Bottom Line, Resources headings).

### 9.2 Question/statement mix
- 9.2.1 If SERP returns ≥4 PAA questions: at least 30% of body H2s should be in question form.
- 9.2.2 If SERP returns <4 PAA questions: any mix acceptable, including 0% question form.
- 9.2.3 NO HARD CEILING on question H2s. (Some articles are 50% question form. That's fine.)
- 9.2.4 The current RSS validator's "≥50% question H2s required" rule is REMOVED.

### 9.3 H2 internal structure
Each body H2 section has:
1. **Intro paragraph (REQUIRED)**: 50-70 words, answer-first, 1-3 inline internal links.
2. **Optional second paragraph**: 60-100 words, deeper detail. Can include 1-2 more inline links.
3. **ONE structural element (REQUIRED)** from this set:
   - `<table>` (3-7 columns × 3-12 rows)
   - `<ul>` with 3-7 bullets
   - `<div class="rl-callout rl-callout--{type}">` (see callout typology, Section 10)
4. **Optional closing paragraph**: 40-80 words, often a "scenario" or "deal math" application of the structural element.

### 9.4 Default structural element by intent
- `cost` and `decision`: tables-dominant. Half or more sections use tables.
  **Minimum 3 tables per article** for cost/decision intent. The gold-standard
  funding-fee page uses 4-5 tables.
- `process` and `definition`: bullets-dominant.
- `comparison`: tables-dominant. **Minimum 3 tables per article.**
- Override: any section can use any structural element. Defaults are starting points.

### 9.5 Word count
- 9.5.1 Per-section: 200-450 words (intro + body + optional closing, not counting structural element).
- 9.5.2 Article body total (sum of H2 sections): TARGET = SERP top-5 average word count, ±15%.
- 9.5.3 If SERP unavailable: target 1800-2400 words for body.
- 9.5.4 The current "min 1600" hardcoded floor is REPLACED by SERP-relative target.

### 9.6 Anti-patterns
- 9.6.1 No "In this section we'll cover..." opener.
- 9.6.2 No empty H2s with no structural element.
- 9.6.3 No more than ONE callout per H2 section.
- 9.6.4 No external links in H2 body content (except in callouts that explicitly reference a regulatory citation).

---

## 10. CALLOUT TYPOLOGY

### 10.1 Universal callout class
```html
<div class="rl-callout rl-callout--{type}">
  <strong>{Type Label}</strong>
  <p>{Callout content, 30-100 words}</p>
</div>
```

### 10.2 Per-archetype callout types

**Archetype: VA Lending (VALN)**
| Type label | Use when |
|---|---|
| Deal Math | Showing a concrete numerical example with consequence |
| File Guidance | Procedural advice about loan file documentation |
| Deal Saver | Action that prevents a deal from falling apart |
| Approval Watchpoint | Underwriting will flag this; borrower attention required |
| Lender Reality Check | Counterintuitive lending fact |
| Underwriter's Note | Direct authority-voice guidance |
| Scenario | Named borrower scenario with situational detail |

**Archetype: Real Estate (LRG)** *[draft, pending Randall confirmation]*
| Type label | Use when |
|---|---|
| Buyer Tip | Action a buyer should take |
| Seller Strategy | Action a seller should take |
| Inspection Watchpoint | Property condition issue likely to surface |
| Negotiation Move | Specific negotiation tactic |
| Market Reality Check | Counterintuitive market fact |
| Agent's Note | Direct authority-voice from listing agent |
| Scenario | Named buyer/seller scenario |

**Archetype: Local Business / Service (e.g. Godfather's Pizza)** *[future, not in v0]*

### 10.3 Visual variation
Each type gets a distinct color treatment via CSS variables:
- `--rl-callout-deal-math-border`: green family
- `--rl-callout-file-guidance-border`: blue family
- `--rl-callout-deal-saver-border`: orange/red family
- `--rl-callout-approval-watchpoint-border`: yellow family
- `--rl-callout-lender-reality-check-border`: purple family
- `--rl-callout-underwriters-note-border`: gray family
- `--rl-callout-scenario-border`: teal family

### 10.4 Callout density
- 10.4.1 Per article: 3-6 callouts total. The gold-standard funding-fee page uses
  6 callouts across 14 body H2s. For articles with ≥10 body H2s, target 5-6.
  For articles with 6-9 body H2s, target 3-4.
- 10.4.2 Per H2 section: at most 1 callout.
- 10.4.3 Callouts cluster in high-stakes sections (cost, exemptions, qualification gates).

### 10.5 Callout assignment rule
The intent overlay specifies preferred callout types per section role. The LLM chooses from those preferences based on the section's content theme.

### 10.5.1 Canonical archetype-neutral callout keys

Overlays reference callout slots using these 8 archetype-neutral keys. Archetype YAMLs map each key to an archetype-specific callout label (e.g., VA lending maps `numerical_proof` to "Deal Math"; real estate maps `numerical_proof` to "Cost Math").

- `numerical_proof` — concrete numerical example with consequence
- `reality_check` — counterintuitive fact that contradicts expectation
- `procedural_guidance` — process advice for documentation or steps
- `deal_preservation` — action that prevents the deal from falling apart
- `qualification_gate` — criterion the borrower/buyer must clear
- `authority_note` — direct authority-voice guidance
- `situational_example` — named scenario with situational detail
- `clarification_section` — clears up a definitional confusion

When writing an overlay, use ONLY these keys. New keys require spec amendment.

---

## 11. ANCHOR TEXT RULES

### 11.1 Internal link anchor format
**Anchor on the topical keyword.**
```
✓ "<a href='/va-loans/irrrl/'>IRRRLs</a>"
✓ "<a href='/va-loans/closing-costs/'>closing costs</a>"
✓ "<a href='/va-residual-income-chart/'>residual income</a>"
```
- 11.1.1 Anchor text 1-5 words.
- 11.1.2 Anchor text matches a topical keyword for the linked page.
- 11.1.3 Pulled from the linking module's anchor pool (when available) — diversifies across articles to prevent same-anchor repetition sitewide.

### 11.2 External link anchor format
**Anchor on the source identifier and document title, NOT the topical keyword.**

Format: `{Source/Authority Name} — {Specific Document Title}` or `{Source/Authority Name}: {Specific Document Title}`

```
✓ "<a href='va.gov/...'>VA.gov — VA Funding Fee and Loan Closing Costs</a>"
✓ "<a href='ecfr.gov/...'>38 CFR Part 36 — Loan Guaranty (eCFR)</a>"
✓ "<a href='benefits.va.gov/...'>VA Lender's Handbook (VA Pamphlet 26-7)</a>"
✗ "<a href='va.gov/...'>VA funding fees</a>"   (steals SEO equity from internal page)
✗ "<a href='va.gov/...'>learn more here</a>"  (no signal)
```

### 11.3 Anchor competition rule
External anchor text MUST NOT use the same topical keywords that internal anchors use sitewide.

This is enforceable: the linking module maintains a sitewide list of "internal anchor keywords." External link generation checks against this list. If an external link's natural anchor would collide with an internal anchor keyword, the system rewrites the external anchor to use the source-name format.

### 11.4 Internal link density
- 11.4.1 Per H2 section intro paragraph: 1-3 internal links. (Not zero — at least one when topic-relevant pages exist.)
- 11.4.2 Per H2 section body paragraphs: 0-2 additional internal links.
- 11.4.3 BLUF lead paragraph: 1-3 internal links.
- 11.4.4 Closing Bottom Line: 0 internal links.
- 11.4.5 ATF lede: 0 internal links.
- 11.4.6 Inside cards, inside ATF FAQs, inside BTF FAQs: 0 internal links.
- 11.4.7 **Article-level target** (enforced by link injector, not by section builders):
  Under 1,000 body words: 3-6 internal links.
  1,000-1,800 body words: 5-10 internal links.
  Over 1,800 body words: 8-15 internal links.
  The gold-standard funding-fee page (1,800+ words) has 7+ unique internal links.

### 11.5 Link injection bucketing
The linking module receives the article and the target topic. For each potential link injection point:
- If a topical match exists in the site's anchor pool: inject the link, log to "links injected" file.
- If no topical match exists: log to "links pending future creation" file with a note about which article needed it. This drives future content prioritization.

> Implementation note: anchor pool data lives at sites/{slug}-anchor-pools.json with structure { destinations: [{ url, primary_keyword, anchors: [string, ...] }] }. The anchor pool may be empty for new sites; in that case, link injection is a no-op and the validator's link-density warning is suppressed for that article.

---

## 12. CTA PILLS

### 12.1 Cardinality
2-3 CTA pills per article.

### 12.2 Placement
1. Immediately after ATF lede (REQUIRED).
2. Mid-article, after a content-heavy H2 section (REQUIRED).
3. Optional: third CTA in the body if article is >2500 words.

### 12.3 Format
```html
<p class="rl-cta-pill">
  <span class="rl-next-label">Next step:</span>
  <a class="rl-next-link" href="{CTA_URL}">{CTA_TEXT}</a>
</p>
```

### 12.4 CTA text
- 12.4.1 First CTA can be topic-specific (e.g., "Check Funding Fee Exemption" for funding fee article).
- 12.4.2 Subsequent CTAs use sitewide default from `CTA_TEXT` site config var.
- 12.4.3 CTA destination always = `CTA_URL` from site config.

---

## 13. CLOSING "THE BOTTOM LINE" SECTION

### 13.1 Format
```html
<h2>The Bottom Line</h2>
<p>{Recap content, 100-150 words across 1-3 paragraphs}</p>
```

### 13.2 Rules
- 13.2.1 Word count: 100-150. Hard.
- 13.2.2 No bullets.
- 13.2.3 No external links.
- 13.2.4 No new information not already in the body.
- 13.2.5 Distinguishable from BLUF: BLUF uses bullets and inline links; closing Bottom Line is prose-only.
- 13.2.6 Position: immediately before BTF FAQs.

---

## 14. BTF FAQs

### 14.1 Cardinality
5-12 items. Target 5-8 for most articles. Up to 12 for dense topics (cost, comprehensive guides).

### 14.2 Source mix
- 60% from PAA (after the 3 already used in ATF)
- 30% expert-added gap-fill questions (questions a domain expert would answer that aren't in PAA)
- 10% repeat-with-deeper-answer of an ATF FAQ if the topic warrants it (RARE, default no)

### 14.3 Content rules
- 14.3.1 No question text overlap with ATF FAQs.
- 14.3.2 Answer length: 50-110 words. Deeper than ATF answers.
- 14.3.3 BTF FAQ answers can mention forms by number, specific dollar amounts, edge cases.
- 14.3.4 No inline links in BTF FAQ answers.
- 14.3.5 No duplicate-topic FAQs (validator should flag two FAQs that effectively ask the same thing).

### 14.4 Heading
`<h2>Frequently Asked Questions</h2>` — same as ATF. Two H2s with the same heading is acceptable; positionally distinguished.

---

## 15. RESOURCES USED

### 15.1 Cardinality
5-8 items. Hard floor of 3.

### 15.2 Source diversity
Minimum 3 distinct authoritative domains. Examples:
- For VA lending: VA.gov, eCFR.gov, FHFA.gov, Benefits.va.gov, oversight.gov
- For real estate: HUD.gov, FreddieMac.com, Realtor.org, NAR.realtor, state real estate commissions

### 15.3 Source quality rules
- 15.3.1 Prefer .gov, .edu, recognized industry associations (.org), and primary regulatory sources.
- 15.3.2 Avoid: competitor commercial sites (Bankrate, NerdWallet, etc.), aggregator/listicle sites, Wikipedia (acceptable as supplement, not as sole source).
- 15.3.3 SERP top organic results are filtered by domain; acceptable domains pass to Resources.

### 15.4 Anchor format (see Section 11.2)
```
{Source/Authority Name} — {Specific Document Title}
```

### 15.5 Format
```html
<footer class="rl-resources">
  <h2>Resources Used</h2>
  <ul>
    <li><a href="{url}" target="_blank" rel="noopener noreferrer">{anchor in source-name format}</a></li>
    ...
  </ul>
</footer>
```

### 15.6 Forbidden fallback
**Hard ban: "Research data for {keyword} — compiled from public sources" or any equivalent placeholder.** If SERP unavailable AND no manually-supplied resource list, content production FAILS rather than ships placeholder. (This is the bug that produced v1 garbage.)

---

## 16. IN THIS ARTICLE TOC

Auto-generated from H2 inventory after article assembly. Lists 7-12 H2 anchor links. Deterministic transformation, not LLM-generated.

```html
<aside class="rl-toc">
  <h3>In this Article</h3>
  <ul>
    <li><a href="#{slug-of-h2}">{H2 text}</a></li>
    ...
  </ul>
</aside>
```

Includes only body H2s. Excludes: BLUF heading, BTF FAQ heading, Bottom Line heading, Resources Used heading.

---

## 17. SERP-DERIVED INPUTS (REQUIRED)

The content-production module MUST consume the following from `serp-research/analyze-serp.py` output BEFORE generating any content:

| Field | Source | Used for |
|---|---|---|
| `top_results` | SERP organic | Subtopic gap analysis, primary sources, target word count |
| `top_results[*].word_count` | SERP organic (computed) | Body word-count target (average ±15%) |
| `paa[*].question` | SERP PAA | ATF FAQs (top 3), BTF FAQs (4-9 more) |
| `ai_overview.text_blocks` | SERP AI Overview | ATF lede content, ATF cards' "synthesis" bullets |
| `ai_overview.references[]` | SERP AI Overview | Resources Used candidates (filtered by domain) |
| `related_searches[]` | SERP | Subtopic gap analysis |

### 17.1 Subtopic gap analysis logic
1. For each top-5 organic result: extract subtopic headers (H2/H3).
2. Aggregate subtopic frequency: which subtopics appear in 4+/5 results, 3/5, 2/5, 1/5.
3. Final article H2 inventory = (intent overlay's required slots) ∪ (subtopics in 3+/5 results) ∪ (gap-fill subtopics in <2/5 results that are domain-relevant).
4. The gap-fill items are the article's competitive moat — what competitors miss.

### 17.2 Target word count logic
- Compute average body word count from top-5 SERP results.
- Article body target = average ±15%.
- If SERP unavailable: fall back to default 1800-2400 words.
- Replaces the current hardcoded `--min-word-count 1600`.

> Implementation note: serp-research's current output does not include per-result word counts. Until that's added, compute-target-wc.py uses the fallback range (1800-2400) by default. When per-result word counts become available, the SERP-derived target takes precedence per the rule above.

### 17.3 SERP unavailable fallback
If SerpAPI/SerpDev BOTH return errors or no key configured:
- Log loudly. DO NOT proceed silently with degraded inputs.
- Generation can proceed only with `--allow-no-serp` flag explicitly set.
- In `--allow-no-serp` mode: Resources Used MUST come from manual config or generation fails (Section 15.6).

---

## 18. VALIDATION (machine-checkable)

Replaces the current `validate-structure.py` checks. New validator runs all of these on the assembled HTML.

### 18.1 Structural assertions
- 18.1.1 H1 present, exactly one.
- 18.1.2 Eyebrow present, format `{X} · {Y}`.
- 18.1.3 Byline present with author + (reviewer if `BYLINE_MODE != single`).
- 18.1.4 Primary sources line present with ≥3 external links.
- 18.1.5 Jump nav has exactly 5 links, last text == "FAQs".
- 18.1.6 Jump nav anchors 1-4 resolve to body H2 IDs.
- 18.1.7 Jump nav text 1-4 matches (substring or full match) ATF card H3 text 1-4.
- 18.1.8 ATF lede paragraph word count 40-110.
- 18.1.9 First CTA pill present, href == `CTA_URL`.
- 18.1.10 Exactly 4 ATF cards. Each has H3 + 4 bullets.
- 18.1.11 Exactly 3 ATF FAQs. Each answer 35-60 words. No links inside answers.
- 18.1.12 BLUF: if present, lead bold, body unboldsed, exactly 5 capstone bullets, all word counts in spec.
- 18.1.13 Body H2 count: 6-15 (excluding BLUF/BTF FAQ/Bottom Line/Resources headings).
- 18.1.14 Each body H2 has: intro paragraph + ≥1 structural element (table/ul/callout).
- 18.1.15 Mid-article CTA pill present.
- 18.1.16 Closing Bottom Line: present, word count 100-150, no `<ul>`, no external `<a>`.
- 18.1.17 BTF FAQ count: 5-12. No question text overlap with ATF FAQs.
- 18.1.18 Resources Used: 5-8 items, ≥3 distinct domains, anchor format check.

### 18.2 Anchor format assertions
- 18.2.1 External link anchors follow `{Source} — {Document Title}` pattern (regex match on em-dash or colon separator + capitalized source prefix).
- 18.2.2 External link anchor text does NOT match any keyword in the sitewide internal anchor pool. (Anchor competition check.)
- 18.2.3 Internal link anchor text is 1-5 words.

### 18.3 Word count assertions
- 18.3.1 Body word count is within ±15% of SERP-derived target (if SERP available).
- 18.3.2 Body word count is 1800-2400 if SERP unavailable.

### 18.4 Anti-pattern detection
Hard fail on:
- 18.4.1 Em dashes anywhere in the article body (existing `voice_validator` rule).
- 18.4.2 Banned filler phrases: "discover", "explore", "vibrant communities", "dive into", "let's", "we'll cover".
- 18.4.3 Resources Used contains the placeholder string "Research data for".
- 18.4.4 ATF lede contains a `?` (lede must be declarative).
- 18.4.5 Card title is a generic intent label ("Best for", "Key advantage", "Watch out") instead of a subtopic name.
- 18.4.6 Two H2 sections without a structural element between intro paragraph and the next H2.
- 18.4.7 More than one callout in a single H2 section.

### 18.5 Soft warnings (don't fail, but log)
- 18.5.1 H2 question/statement mix outside 30-70% range when ≥4 PAA questions available.
- 18.5.2 Internal link density <0.5 or >2.0 per H2 section.
- 18.5.3 Article body word count outside ±15% of SERP target (no fail, just log).
- 18.5.4 BTF FAQ duplicate-topic detected (two FAQs that effectively ask the same thing).

---

## 19. IMPLEMENTATION CHANGES TO EXISTING MODULES

This spec implies the following changes to the current RSS codebase. Listed for Step 3 implementation planning, not part of the spec itself.

### 19.1 `modules/content-production/`
- Replace `prompts/atf-{intent}.md` with `overlays/{intent}.yaml` per Section 6.6.
- Replace `prompts/main-content-{intent}.md` with thin slot-fillers that take overlay+SERP as input.
- Add new prompt: `prompts/bluf.md` (slot-filler for BLUF section).
- Add new prompt: `prompts/h2-section.md` (slot-filler for any body H2).
- Add new prompt: `prompts/closing-bottom-line.md`.
- Rewrite `tools/produce-article.py` to call `serp-research/analyze-serp.py` instead of inline SerpAPI.
- Rewrite `tools/generate-article.py` to drive from spec sections, not from monolithic intent prompts.
- Replace `tools/validate-structure.py` with spec-driven validator covering Section 18.

### 19.2 `modules/serp-research/`
- Add gap-analysis tool: `tools/extract-subtopic-gaps.py` (consumes `analyze-serp.py` output, produces subtopic frequency map).
- Add word-count target tool: `tools/compute-target-wc.py`.

### 19.3 `modules/linking/` and `modules/linking-v2/`
- Build the link injector that consumes the anchor pool. (Currently anchor pool exists; injector does not.)
- Add anchor-competition check: build sitewide internal anchor keyword list, expose to validator.

### 19.4 `modules/rl-components/`
- Add CSS variants for typed callouts: `rl-callout--deal-math`, `rl-callout--file-guidance`, etc.
- Add `rl-bluf` section class.
- Add `rl-cta-pill` class (or verify existing).

### 19.5 `modules/brand-voice/`
- Extend archetype files (`realtor.md`, future `va-lending.md`) to include the callout typology for that archetype.

### 19.6 `sites/<slug>.conf`
- Add config vars: `CTA_URL`, `CTA_TEXT`, `BYLINE_MODE`, `AUTHOR_NAME`, `AUTHOR_NMLS`, `AUTHOR_PHOTO_URL`, `REVIEWER_NAME`, `REVIEWER_TITLE`, `REVIEWER_NMLS`, `REVIEWER_PHOTO_URL`, `BREADCRUMB_PARENT_LABEL`, `BREADCRUMB_PARENT_URL`.

### 19.7 New top-level docs
- `docs/article-spec.md` — this file.
- `docs/intent-overlays.md` — overlay format reference.
- `docs/callout-typology.md` — per-archetype callout reference.
- `docs/anchor-rules.md` — internal vs external anchor rules + competition rule.

---

## 20. UNRESOLVED — PENDING RANDALL REVIEW

These items are flagged in the spec as my best read, but Randall's confirmation is needed before locking them in.

1. **BLUF inclusion logic** (Section 8.1): Currently auto-includes for `cost` intent, defaults yes for `decision`, judgment call elsewhere. Confirm or override.

2. **H2 question/statement mix** (Section 9.2): Currently 30% question form floor when PAA is rich, no ceiling, 0% acceptable when PAA is sparse. Removes the current "≥50% questions required" validator. Confirm.

3. **LRG callout typology** (Section 10.2): Drafted as Buyer Tip / Seller Strategy / Inspection Watchpoint / Negotiation Move / Market Reality Check / Agent's Note / Scenario. Want to confirm/refine before the spec locks.

4. **Tables-by-intent default** (Section 9.4): Cost/decision/comparison default to tables-dominant. Process/definition default to bullets. Confirm hard-default vs LLM-judgment.

5. **Two H2s with same "Frequently Asked Questions" heading** (Section 14.4): VALN does this. Acceptable per spec? Or change ATF heading to "Quick Answers" / "Top Questions"?

6. **Tool-anchored articles** (Section 7): Deferred from v0. Confirm.

7. **Required vs optional breakdown** (Section 2): My read of which sections are required. Confirm.

8. **CTA placement count** (Section 12.1): 2-3 per article. Article A has 3+. Confirm range.

9. **Forbidden fallback hard ban** (Section 15.6): Currently the system ships placeholder Resources when SERP unavailable. Spec hard-fails generation in this case. Confirm hard-fail vs warn-and-proceed.

10. **Anchor competition enforcement** (Section 11.3): Currently aspirational. Implementation requires sitewide internal anchor keyword list. Confirm priority for implementation in Step 3.
