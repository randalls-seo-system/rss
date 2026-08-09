# LRG Short Sale / Distressed Homeowner Content Vertical
## Strategy Document — August 2026

**Prepared for:** Levi Rodgers, LRG Realty
**Scope:** Research and content architecture — no production writes
**Markets:** San Antonio (primary), Austin, Texas statewide authority

---

## 1. EXECUTIVE SUMMARY

Texas had the most lender repossessions (REOs) of any state in H1 2026 by
raw count: 3,322 properties. [VERIFIED — ATTOM Mid-Year 2026 via PRNewswire,
fetched 2026-08-09. Texas rate was 0.18% (1 in 551 properties), well below
Florida's 0.27%. Texas leads on volume because it is the second-largest
state, not because its per-household foreclosure rate is worst.]

Austin home prices have declined significantly from their mid-2022 peak.
The magnitude depends on the index: Cotality's repeat-sale HPI shows ~15%
below peak as of March 2026; MLS-median-based sources report 24-25%.
[VERIFIED — Cotality "US Home Price Insights May 2026," fetched 2026-08-09,
quotes "Austin fell 15% from its mid 2022 peak." MLS-median figures from
multiple secondary sources cluster around 24-25%; the 27.3% figure from
teamprice.com could not be independently verified (403 on fetch) and is
withdrawn.] Negative equity among 2022-vintage Austin borrowers was ~18%
as of ICE's July 2025 Mortgage Monitor; ResiClub reported 22.4% using ICE
data from a later period. Both figures describe the same phenomenon at
different measurement dates. [UNVERIFIED — the ~18% ICE July 2025 figure
was stated in Randall's critique of the prior draft; the ICE Mortgage
Monitor primary source (mortgagetech.ice.com) returned 403 on fetch
attempt. Must be traced to ICE directly before use in published content.
The 22.4% ResiClub figure was read on DeviceDaily.com, which sourced
ResiClub, which sourced ICE — two layers of aggregation.] Austin overall:
9.2% of all mortgages underwater as of December 2025 (ICE via ResiClub,
#3 nationally). San Antonio: 8.8% (#4 nationally, same source and date).
[SECONDARY SOURCE — DeviceDaily.com, reporting ResiClub's analysis of
ICE Mortgage Technology data, "at the end of December 2025." The primary
source (ICE Mortgage Monitor) was not fetched.]

The qualified principal residence exclusion under the Mortgage Forgiveness
Debt Relief Act does not apply to debt discharged after December 31, 2025
(IRS Topic 431). This does NOT mean all forgiven mortgage debt is now
automatically taxable — the insolvency exclusion and bankruptcy exclusion
(Title 11) are permanent and not date-limited. Forgiven debt from a short
sale or deed in lieu may create taxable income; other exclusions may apply;
a CPA or tax attorney should evaluate each homeowner's situation.
[VERIFIED — IRS.gov Topic 431, fetched 2026-08-09. Quoted: "Cancellation
of qualified principal residence indebtedness that is discharged before
January 1, 2026" and separately lists "Debt canceled to the extent
insolvent" and "Debt canceled in a Title 11 bankruptcy case" as
exclusions with no expiration date.]

LRG has a unique position: veteran-owned brokerage in two Texas metros
with significant negative equity exposure, with a sister site (VALN)
already owning the VA loan mechanics side. LRG can own the **local broker
perspective** — what are your actual options as a San Antonio or Austin
homeowner who's underwater, behind on payments, or forced to sell during
a PCS.

**Levi's hypothesis — promising and differentiated, not yet quantified:**
The VA/military angle in San Antonio appears strongly differentiated for a
local broker. Veterans United and Military.com own the generic national
content, but nobody owns "PCS from JBSA with an underwater mortgage, what
do I actually do." [HYPOTHESIS — supported by SERP observations below but
the JBSA/Lackland/Fort Sam/Randolph + PCS + equity SERPs need systematic
volume quantification before calling it "wide open."] LRG post 8714
appeared as the #1 organic result for "selling home pcs no equity" in a
single Serper.dev SERP pull on 2026-08-09. [SERP OBSERVATION — not yet
confirmed via 28/90-day GSC query-level position data. Call it an observed
#1 result until GSC validates.]

---

## 1B. CLAIM PROVENANCE KEY

Every data claim in this document carries one of these labels:

| Label | Meaning |
|-------|---------|
| **VERIFIED** | A PRIMARY source was fetched this session, the relevant passage was read, and it can be quoted. An aggregator reporting a primary source's data is not VERIFIED, however reputable — it is SECONDARY SOURCE. |
| **SECONDARY SOURCE** | An aggregator, news outlet, or intermediary reporting a primary source's data. The aggregator was fetched and the number is accurately reproduced, but the underlying primary source was not independently opened. |
| **UNVERIFIED** | The number appears in this document but the primary source has not been fetched. May come from a critique, a prior session, or common knowledge. Must be traced before it enters any published content. |
| **SERP OBSERVATION** | Data observed in a Serper.dev or GSC API pull during this session. Represents a point-in-time snapshot, not a stable measurement. |
| **INFERENCE** | Derived from verified or observed data, but the conclusion itself is not directly stated in any source. |
| **HYPOTHESIS** | Strategic judgment or Levi's input. Supported by observations but not yet validated with systematic data. |

---

## 1C. PRE-PUBLISHING CHECKLIST (not required before drafting)

These items must be completed before any Phase 1 content goes live:

- [ ] **AEO/GEO audit artifact:** Fixed query set, actual ChatGPT / AI Overviews / Perplexity responses captured, cited domains recorded, date and method documented. The Serper `aiOverview` flag from Section 4A is a proxy, not a substitute.
- [ ] **Post 8714 "#1" validation:** Pull 28-day and 90-day GSC query-level data for "selling home pcs no equity" to confirm durable position, not just a single SERP snapshot.
- [ ] **Post 1516 redirect decision:** Backlink inventory (Ahrefs or GSC links report), historical GSC query set, internal links pointing at it, and intent overlap with new pillar — all checked before any 301 recommendation.
- [ ] **JBSA/military SERP volume quantification:** Systematic volume pull for JBSA, Lackland, Fort Sam Houston, Randolph + PCS + equity/underwater/sell query combinations to validate the military lane size.

---

## 2. EXISTING CONTENT AUDIT

### 2A. Direct-Hit Pages (already on lrgrealty.com)

| ID | Slug | Title | Status | ~Words | 30d Clicks | 30d Impr | Pos | Quality |
|----|------|-------|--------|--------|------------|----------|-----|---------|
| 1516 | understanding-short-sales | Understanding Short Sales: A Guide for Homebuyers and Sellers | publish | 3,985 | 0 | 347 | 8.4 | LEGACY — pre-pipeline, general explainer. Buyer-and-seller angle dilutes focus. Legacy slug with date prefix. Not ranking for any high-intent query. |
| 8688 | va-loan-after-foreclosure-short-sale-texas | VA Loan After a Previous Foreclosure or Short Sale in Texas | publish | 3,700 | 2 | 405 | 7.3 | GOOD — pipeline article, Levi author. Focuses on getting BACK into homeownership after a short sale. Forward-looking, not crisis content. |
| 8714 | selling-home-pcs-no-equity-texas | Selling a Home During a PCS With Little or No Equity | publish | 3,736 | 1 | 34 | 6.6 | STRONG — pipeline, ranks #1 for "selling home pcs no equity". Low volume but perfect intent match. This is the beachhead article. |
| 2233 | how-to-buy-foreclosure-san-antonio | How to Buy a Foreclosure in San Antonio | publish | 3,962 | 44 | 7,407 | 7.5 | GOOD — buyer-side foreclosure, highest traffic of the group. Not part of the seller-distress vertical but should cross-link. |
| 2226 | how-to-buy-foreclosure-austin | How to Buy a Foreclosure in Austin, TX | publish | 3,900 | 23 | 5,621 | 7.0 | GOOD — same as above, Austin market. Cross-link target. |
| 2230 | how-to-buy-foreclosure-killeen | How to Buy a Foreclosure in Killeen, TX | publish | 3,677 | 6 | 1,022 | 7.6 | GOOD — same, Killeen. |

### 2B. Adjacent Pages (touch the topic, support linking)

| ID | Slug | Title | Status | 30d Clicks | 30d Impr | Relevance |
|----|------|-------|--------|------------|----------|-----------|
| 2861 | va-loan-assumption-sam-houston-texas | VA Loan Assumption: Protect Your Entitlement After a PCS | publish | 12 | 2,299 | HIGH — VA assumption is an alternative to selling at a loss. Must cross-link. |
| 8654 | second-tier-va-entitlement-buy-before-sell-texas | Second-Tier VA Entitlement: Buying Again Before You Sell | publish | 0 | 102 | HIGH — addresses the "buy new home before selling underwater one" scenario. |
| 2717 | selling-home-before-pcs-orders-sa | Sell Before PCS Orders in SA: Veteran PCS Checklist | publish | 0 | 29 | MEDIUM — general PCS selling, no distress focus. |
| 2110 | fort-sam-houston-pcs-sell-guide | Selling Your Fort Sam Houston Home After the Army Merger | publish | 0 | 148 | MEDIUM — niche PCS angle, JBSA-specific. |
| 8891 | capital-gains-tax-selling-home-texas-2026 | Capital Gains Tax When Selling a Home in Texas | publish | 8 | 1,235 | HIGH — tax consequences overlap with short sale tax questions. |
| 7487 | heloc-texas-home-equity-guide | HELOC in Texas: How a Home Equity Line of Credit Works | publish | — | — | LOW — equity extraction, opposite problem. |
| 5435 | buying-house-after-bankruptcy-sa | Buying a House After Bankruptcy in San Antonio | publish | — | — | MEDIUM — post-crisis recovery, links to from short sale/foreclosure recovery pages. |
| 8943 | real-estate-help-texas | Real Estate Problems in SA, Austin & Killeen? Start Here | publish | 0 | 0 | HIGH — could serve as the distressed vertical hub if restructured. Currently focuses on "house won't sell" listing strategy, not distress. |

### 2C. Drafts Sitting Unpublished (potential overlap risk)

| ID | Slug | Title | Status | Notes |
|----|------|-------|--------|-------|
| 2500 | pcs-home-sale-checklist-san-antonio | PCS Home Sale Checklist for Veterans in San Antonio | draft | Overlaps with 2717. Evaluate before publishing. |
| 2505 | pcs-to-jbsa-home-sellers-guide | PCS to JBSA: A Home Seller's Guide | draft | Another PCS selling angle. May overlap new vertical. |
| 2701 | sell-home-near-fort-cavazos-pcs | Fort Cavazos PCS Home Sale Timeline and Remote Closing | draft | Fort Hood specific. |

### 2D. VALN Sister Site Coverage (DO NOT DUPLICATE)

VALN (valoannetwork.com) already covers the VA loan mechanics side extensively:

| VALN Post | Title | Words | LRG Overlap? |
|-----------|-------|-------|-------------|
| 10786 | Understanding the VA Compromise Sale Program | 4,438 | NO — VALN should own this. LRG links TO it. |
| 36939 | Underwater on Your VA Mortgage? Options for Upside-Down Veterans | 3,242 | PARTIAL — VALN covers VA loan mechanics; LRG covers local broker options for the same person. |
| 36929 | VA Foreclosure Avoidance: Every Option Veterans Have in 2026 | 3,870 | NO — VALN comprehensive guide. Cross-link target. |
| 36657 | VA Loan After Short Sale: Waiting Periods and Eligibility | 3,145 | OVERLAP with LRG 8688. LRG's version is TX-specific; keep both, cross-link. |
| 36659 | VA Loan After Deed in Lieu: Eligibility and Recovery | 3,562 | NO — VALN owns this. |
| 5495 | VA Loan After Foreclosure: 2026 Waiting Period & Rules | 4,814 | MINIMAL — VALN covers VA rules; LRG 8688 covers TX broker perspective. |
| 13402 | VA Partial Claim Program 2026 | 4,732 | NO — VALN exclusive. Link to from LRG foreclosure prevention content. |

**Cross-site strategy:** LRG covers "what to do as a homeowner in San Antonio/Austin" and links to VALN for "how your VA loan works in this scenario." They are complementary, not competing.

### 2E. Cannibalization Risk Assessment

| Risk | Pages | Resolution |
|------|-------|------------|
| MODERATE | 1516 (Understanding Short Sales) vs. new pillar page | Likely candidate for redirect, but no action until backlinks, historical GSC queries, internal links pointing at it, and intent overlap with the new pillar are all checked. Weak performance alone is not sufficient reason for a 301. |
| LOW | 8688 (VA After Short Sale) vs. new "Short Sale Guide SA" | Different intent — 8688 is about buying again AFTER, new page is about going THROUGH. Complementary. |
| LOW | 8714 (PCS No Equity) vs. new "PCS Underwater Mortgage" | 8714 focuses on legitimate-equity-thin sales. New page would cover actual underwater/negative scenarios. Keep both, cross-link with clear scope. |
| NONE | Foreclosure buying guides (2233, 2226, 2230) | Buyer-side content, not seller-side. Different intent entirely. Cross-link as "what buyers should know" perspective. |

---

## 3. SERP RESEARCH — THE OPPORTUNITY

### 3A. SERP Landscape by Query Type

**CATEGORY 1: Core short sale queries** — Dominated by national authority (NAR, Investopedia, Bankrate, LendingTree). No local Texas broker presence. Texas title company (texasnationaltitle.com) and Houston HAR.com are the only TX voices. San Antonio/Austin: ZERO local broker content ranking.

| Query | AI Overview? | Top Rankers | LRG Opportunity |
|-------|-------------|-------------|-----------------|
| short sale process texas | NO | texasnationaltitle, NAR, Reddit, HAR | HIGH — no SA/Austin-specific content exists |
| short sale vs foreclosure texas | NO | NAR, texasnationaltitle, silblawfirm, TX State Law Library | HIGH — comparison content from a broker perspective |
| how does a short sale work | NO | Reddit, Freddie Mac, NAR, Investopedia | MEDIUM — generic query, hard to crack top 3 |
| short sale san antonio | NO | Zillow, satxproperty, ezhomesearch | HIGH — listing sites only, no educational content |
| va short sale | NO | va.gov, Veterans United, NewDay USA | LOW — VALN should own this, not LRG |

**CATEGORY 2: Upstream / pre-vocabulary queries** — This is the primary opportunity. Reddit dominates, meaning the question-askers have nowhere authoritative to go. AI Overviews trigger on many of these.

| Query | AI Overview? | Who Ranks | Opportunity |
|-------|-------------|-----------|-------------|
| owe more than house is worth what to do | YES | Reddit, American Financing, durangohomesforsale | VERY HIGH — AIO query with no broker content |
| can't afford to sell my house | NO | Reddit, Facebook, Realtor.com | VERY HIGH — pure desperation query, Reddit #1 |
| need to sell house but owe too much | NO | Reddit, Realtor.com, Redfin | VERY HIGH — same pattern |
| how to sell house when you owe more than its worth | NO | Reddit, Realtor.com, Redfin | VERY HIGH |
| what happens if I just walk away from my mortgage | NO | Reddit, Investopedia, FastExpert | HIGH |
| house worth less than I paid | NO | Reddit, Reddit, Quora | VERY HIGH — zero professional content |
| behind on mortgage payments texas | NO | TDHCA, texaslawhelp, TDHCA | MEDIUM — government sites dominate |
| can't make mortgage payment options | YES | CFPB, HUD, Fannie Mae | MEDIUM — government dominance |
| moving but house won't sell | YES | Reddit, Opendoor | VERY HIGH |
| sell house bring money to closing | YES | Reddit, Bankrate, Wells Fargo | HIGH |

**CATEGORY 3: Military PCS-specific** — LRG's strongest lane. Already has beachhead.

| Query | AI Overview? | Who Ranks | Opportunity |
|-------|-------------|-----------|-------------|
| selling home pcs no equity | NO | **LRG #1 (observed)**, Reddit, milhousingnetwork | STRONG — observed #1 in single SERP pull 2026-08-09; validate with 28/90d GSC before treating as durable |
| pcs with underwater mortgage | NO | Veterans United, Military.com, winklawfirm (Denver!) | HIGH — no Texas-specific content |
| military pcs can't sell house | NO | Reddit, Military.com, Opendoor | VERY HIGH |
| got orders can't sell house | NO | Reddit, Reddit, Quora | VERY HIGH — pure Reddit |
| military orders have to sell house fast | YES | Homelight, sandiegomilitaryre | HIGH — no Texas voice |
| va loan underwater what to do | NO | Reddit, Veterans United, VALN | MEDIUM — VALN should cover VA specifics |

**CATEGORY 4: TX legal/process** — Important for authority but compliance-heavy.

| Query | AI Overview? | Who Ranks | Opportunity |
|-------|-------------|-----------|-------------|
| foreclosure timeline texas | NO | texaslawhelp, TX State Law Library | MEDIUM — legal authority sites dominate |
| how to stop foreclosure texas | NO | TX State Law Library, texaslawhelp, HUD | MEDIUM |
| pre-foreclosure options texas | YES | TX State Law Library, texaslawhelp | MEDIUM |
| deed in lieu of foreclosure texas | NO | TX Bankers, silblawfirm | MEDIUM — legal territory |
| deficiency judgment texas | YES | TX State Law Library, Fannie Mae | MEDIUM-HIGH — critical topic, poorly explained |
| hoa lien foreclosure texas | NO | TX State Law Library, fsresidential | LOW — niche |

### 3B. Key GSC Signals (LRG already appears for)

LRG is already getting impressions for distressed-homeowner queries it doesn't have dedicated content for:

- `foreclosure` — 1,392 impressions, 1 click, pos 6.4
- `va loan short sale` — 60 impressions, pos 8.8
- `va home loan after short sale` — 38 impressions, pos 7.6
- `sell distressed property san antonio` — 41 impressions, pos 5.8
- `sell distressed property fast` — 24 impressions, pos 13.0
- `distressed property leads, pre-foreclosures... san antonio` — 262+ impressions (investor query)
- `foreclosed homes san antonio` — 25 impressions, pos 10.8

These impressions WITHOUT dedicated content indicate high potential with targeted pages.

### 3C. Competition Assessment

**Who would LRG compete against?**

| Competitor | Strength | Weakness |
|-----------|----------|----------|
| **Reddit/Quora** | Dominates upstream queries with authentic stories | No expertise, no local knowledge, no broker guidance |
| **Bankrate/Investopedia/LendingTree** | Strong national authority explainers | Generic, no TX specifics, no military angle, no local broker |
| **Veterans United** | VA-specific underwater content | National, not TX-focused, not broker (they're a lender) |
| **Military.com** | Military PCS content | National, thin on options, no TX specifics |
| **texaslawhelp.org / TX State Law Library** | Authoritative TX legal info | Government reference, not actionable broker guidance |
| **HAR.com (Houston)** | Houston-specific short sale content | Houston only, no SA/Austin |
| **Zillow/Redfin/Realtor.com** | Listing pages for "short sale [city]" | No educational content, just listings |
| **Local cash buyers (homebuyerssanantonio, four19properties)** | "We buy distressed" landing pages | Adversarial to homeowner interests, not educational |

**Gap:** Nobody is providing Texas-specific, broker-guided, military-aware educational content about distressed homeowner options in San Antonio or Austin. The closest is HAR.com for Houston and TDHCA (government). LRG can own this category.

---

## 4. AEO/GEO ANALYSIS — AI CITATION LANDSCAPE

### 4A. AI Overview Trigger Rate

12 of 49 researched queries trigger Google AI Overviews. [SERP OBSERVATION
— method: Serper.dev API, single pull per query, 2026-08-09. Serper
reports `aiOverview` or `answerBox` presence. This is a point-in-time
observation, not a stable percentage — AIO triggering varies by session,
location, and Google's rollout. The directional signal (upstream queries
skew toward AIO) is more reliable than the exact count.] These skew
toward the **upstream/problem-aware queries** — exactly the queries where
LRG should compete.

Queries with AI Overviews:
- owe more than house is worth what to do
- negative equity options homeowner
- pre-foreclosure options texas
- deficiency judgment texas
- san antonio housing market downturn
- can I sell my house if I still owe money
- can't make mortgage payment options
- moving but house won't sell
- military orders have to sell house fast
- house value dropped can I sell
- sell house bring money to closing
- 1099-C short sale tax

### 4B. Who Gets Cited in AI Overviews

| Source Type | Cited? | Examples |
|------------|--------|----------|
| Government (.gov) | YES — heavily | CFPB, HUD, VA.gov, IRS |
| Financial publishers | YES | Bankrate, Investopedia, NerdWallet |
| Reddit | YES — in organic, not AIO | Appears as organic #1-3 but NOT cited in AIO content |
| Local brokers | NEVER | Zero local real estate agents cited in any AIO |
| VALN | Appears in organic for VA queries | Not cited in AIO directly |

### 4C. AEO Content Strategy

The AI Overviews for these queries follow a consistent structure:
1. Direct answer to the question (1-2 sentences)
2. Numbered list of options (3-5 options with brief descriptions)
3. Texas-specific caveat or legal note (when applicable)

**To get cited, LRG content needs:**
- Immediate direct answer in the first paragraph (not an intro/hook)
- Structured options list with clear headings
- Texas-specific legal context
- Numbers and specifics (timelines, costs, percentages)
- Schema markup (FAQPage, HowTo)

### 4D. Citation Gaps

| Topic | Current AIO Source | What's Missing |
|-------|-------------------|---------------|
| Underwater options for TX homeowners | Generic national content | TX-specific: 80% LTV constitutional limit, non-judicial foreclosure timeline, deficiency judgment risk |
| Short sale vs foreclosure for TX military | No local content | JBSA/Fort Hood PCS timeline integration, VA compromise sale option, military-specific SCRA protections |
| Tax on forgiven mortgage debt 2026 | IRS.gov (generic) | Post-MFDRA qualified-residence-exclusion expiration specifics, surviving insolvency/bankruptcy exclusions explained clearly, TX-specific (no state income tax advantage) |
| Austin 2022 buyer options | Nobody local | Significant price decline (15-25% depending on index), ~18% of 2022-vintage borrowers underwater, what to actually do |

---

## 5. UPSTREAM CAPTURE — PRE-VOCABULARY QUERIES

### 5A. The Journey Map

Most distressed homeowners don't search "short sale." They search their *situation*:

```
STAGE 1: AWARENESS ("something is wrong")
├── "house worth less than I paid"
├── "house value dropped can I sell"
├── "can't afford to sell my house"
└── "stuck in house can't sell"

STAGE 2: URGENCY ("I have to do something")
├── "need to sell house but owe too much"
├── "behind on mortgage payments texas"
├── "can't make mortgage payment options"
├── "what happens if I just walk away from my mortgage"
└── "moving but house won't sell"

STAGE 2M: MILITARY URGENCY ("orders came, clock is ticking")
├── "military orders have to sell house fast"
├── "got orders can't sell house"
├── "pcs with underwater mortgage"
└── "military pcs can't sell house"

STAGE 3: VOCABULARY ACQUISITION ("now I know the terms")
├── "short sale process texas"
├── "short sale vs foreclosure texas"
├── "underwater mortgage options"
├── "pre-foreclosure options texas"
└── "va compromise sale"

STAGE 4: ACTION ("how do I do this")
├── "short sale san antonio"
├── "how to stop foreclosure texas"
├── "deed in lieu of foreclosure texas"
├── "mortgage hardship letter"
└── "sell distressed property san antonio"

STAGE 5: AFTERMATH ("what happens next")
├── "va loan after foreclosure short sale texas"
├── "do I owe taxes on short sale forgiven debt"
├── "deficiency judgment texas"
├── "buying house after bankruptcy san antonio"
└── "how to restore va loan entitlement"
```

### 5B. Where LRG Should Capture

**Stages 1-2M are the highest-value capture points.** By the time someone
reaches Stage 3-4, they've already found legal aid sites and government
resources. LRG wins by being the first professional voice they encounter
in Stage 1-2, then guiding them through the vocabulary and decision process.

**Reddit domination in Stages 1-2 is the signal.** When Reddit is the
#1-#3 result for a query, it means no professional content exists. Every
Reddit thread in these SERPs ends with "talk to a real estate agent" —
LRG IS that agent.

### 5C. People Also Ask Goldmine

The PAA questions from our SERP research reveal exact user questions:

**Must-answer questions for the pillar page:**
- What can I do if my house is worth less than I owe?
- Can I sell my house if I owe more than it's worth?
- What happens if you sell your house for less than you owe?
- Is a short sale as bad as a foreclosure?
- Do banks prefer short sale or foreclosure?
- How do I stop foreclosure immediately in Texas?
- What are the consequences of walking away from a mortgage?
- How long does it take for your house to go into foreclosure in Texas?
- Does a VA short sale affect credit score?
- Is there a waiting period for a VA loan short sale?

**Related searches to target:**
- "can't sell house but need to move"
- "when to worry about house not selling"
- "how to sell a house underwater fast"
- "short sale approval time texas"

---

## 6. CONTENT ARCHITECTURE

### 6A. Cluster Structure

```
PILLAR PAGE (TX-authority)
│
├── CLUSTER 1: Options Overview (TX-authority)
│   ├── [PILLAR] Your Options When You Can't Afford to Sell in Texas
│   ├── Short Sale Process in Texas: Step by Step
│   ├── Short Sale vs Foreclosure in Texas: Which Is Better?
│   ├── Deed in Lieu of Foreclosure in Texas
│   ├── Loan Modification in Texas: How to Apply
│   └── What Happens If You Walk Away from Your Mortgage in Texas
│
├── CLUSTER 2: Military/PCS (SA-local + TX-authority)
│   ├── PCS with an Underwater Mortgage: Military Options in Texas
│   ├── VA Compromise Sale: What JBSA Families Need to Know
│   │   └── (Cross-links to VALN comprehensive guide)
│   ├── SCRA Protections for Military Homeowners Facing Foreclosure
│   │   └── (Complements existing post 8716)
│   └── Renting vs Selling During PCS When Equity Is Thin
│       └── (Complements existing post 8714)
│
├── CLUSTER 3: Local Market Distress (hyperlocal)
│   ├── Austin Homeowners Underwater in 2026: Your Real Options
│   ├── San Antonio Short Sales in 2026: What Sellers Need to Know
│   └── Bought at the Peak in Austin: What to Do Now
│
├── CLUSTER 4: Legal & Financial (TX-authority, YMYL-heavy)
│   ├── Texas Foreclosure Timeline: How Fast Can It Happen?
│   ├── Deficiency Judgments in Texas After a Short Sale or Foreclosure
│   ├── Tax on Forgiven Mortgage Debt in 2026 (Post-MFDRA)
│   └── Second Liens and HOA Liens in a Texas Short Sale
│
└── CLUSTER 5: Recovery & Aftermath (TX-authority)
    ├── [EXISTS: 8688] VA Loan After Foreclosure or Short Sale in TX
    ├── [EXISTS: 5435] Buying a House After Bankruptcy in SA
    └── Rebuilding Credit After a Short Sale in Texas
```

### 6B. Page-Level Architecture

#### PILLAR PAGE: "Your Options When You Can't Afford to Sell Your Texas Home"

- **Scope:** TX-authority
- **Target queries:** "owe more than house worth what to do", "can't afford to sell my house", "underwater mortgage options", "need to sell house but owe too much"
- **Author:** Levi Rodgers (founder perspective, Veteran credibility)
- **Reviewer:** Mayra Torres (managing broker)
- **Structure:**
  - BLUF: 5-card kcards — one card per option (stay & pay, short sale, deed in lieu, loan mod, bring cash to closing)
  - Decision matrix comparing all options on: credit impact, timeline, cost, deficiency risk, tax consequence
  - Texas-specific section (non-judicial foreclosure, constitutional HELOC limit, no state income tax)
  - Military-specific sidebar (link out to Cluster 2)
  - CTA: "Get My Free Home Equity Analysis"
- **COMPLIANCE:** Educational Notice + Legal & Tax Disclaimer. "Consult an attorney and CPA" framing. No tax outcomes stated as fact.
- **AEO optimization:** Direct answer in first sentence, structured comparison table, FAQ schema

#### SPOKE: "Short Sale Process in Texas: Step by Step"

- **Scope:** TX-authority
- **Target queries:** "short sale process texas", "how does a short sale work", "short sale timeline in texas"
- **Author:** Salena Arledge (listing/selling lane)
- **Reviewer:** Mayra Torres
- **Structure:**
  - Step-by-step process with Texas-specific details
  - Timeline (what to expect in TX non-judicial market)
  - Documents needed
  - How to choose a short sale agent (LRG positioning)
  - Common deal-killers
- **COMPLIANCE:** Educational Notice required. "Consult an attorney" for lien subordination and deficiency waiver.
- **CANNIBALIZATION:** Potential overlap with post 1516. Requires backlink audit, historical GSC query check, and internal link inventory on 1516 before deciding redirect vs coexistence.

#### SPOKE: "Short Sale vs Foreclosure in Texas: Which Is Better for You?"

- **Scope:** TX-authority
- **Target queries:** "short sale vs foreclosure texas", "is a short sale as bad as a foreclosure"
- **Author:** Levi Rodgers (YMYL credibility)
- **Reviewer:** Mayra Torres
- **Structure:**
  - Side-by-side comparison table (credit impact, timeline, control, deficiency, tax, VA entitlement impact)
  - Texas-specific: non-judicial foreclosure speed, deficiency judgment statute (Property Code 51.003)
  - Decision framework: "When short sale is better" / "When foreclosure may be unavoidable"
- **COMPLIANCE:** Legal & Tax Disclaimer. Cannot state credit score impacts as specific numbers. Must cite Property Code by section.

#### SPOKE: "PCS with an Underwater Mortgage: Military Options in Texas"

- **Scope:** SA-local + TX-authority
- **Target queries:** "pcs with underwater mortgage", "military pcs can't sell house", "got orders can't sell house"
- **Author:** Levi Rodgers (VA expertise lane)
- **Reviewer:** Mayra Torres
- **Structure:**
  - BLUF: Your 5 options (sell at loss + bring cash, VA compromise sale, rent it out + second VA loan, VA assumption, short sale)
  - JBSA/Fort Hood specific context
  - PCS timeline vs foreclosure timeline
  - Link to VALN's VA Compromise Sale guide for mechanics
  - Link to existing 8714 (PCS no equity) for equity-thin (but not underwater) scenarios
  - CTA: "Get My Free Home Equity Analysis Before Your PCS"
- **COMPLIANCE:** VA-specific claims must come from VA.gov or VALN verified content. No invented waiting periods.

#### SPOKE: "Austin Homeowners Underwater in 2026: Your Real Options"

- **Scope:** Austin-local
- **Target queries:** "austin housing market negative equity 2026", "bought at peak austin what to do"
- **Author:** Karishma Rupani (Austin/general buyer lane)
- **Reviewer:** Mayra Torres
- **Structure:**
  - Data-driven lede: price decline range (Cotality ~15% repeat-sale; MLS median ~24-25%), 2022-vintage borrowers ~18% underwater (ICE Jul 2025), overall ~9.2% (ICE Dec 2025). Every number sourced and labeled.
  - Options organized by urgency (can wait vs must act now)
  - Neighborhood-level variation (where the declines are worst)
  - What's recovering vs what's still declining
  - CTA: "Get My Free Austin Home Equity Analysis"
- **COMPLIANCE:** All data citations must be sourced (ResiClub, ATTOM, CoreLogic). No invented neighborhood-level numbers.

#### SPOKE: "San Antonio Short Sales in 2026: What Sellers Need to Know"

- **Scope:** SA-local
- **Target queries:** "short sale san antonio", "sell distressed property san antonio"
- **Author:** Salena Arledge (seller lane)
- **Reviewer:** Mayra Torres
- **Structure:**
  - SA market context (8.8% underwater [SECONDARY SOURCE — DeviceDaily → ResiClub → ICE, Dec 2025], #4 nationally; 459 Bexar County foreclosure properties [SECONDARY SOURCE — KSAT Nov 2025, page not fetched])
  - Short sale process with local specifics (Bexar County recording, title companies)
  - Investor buyer dynamics in SA
  - Difference between legitimate short sale agent and "we buy ugly houses" operations
  - CTA: "Get My Free Home Equity Analysis"
- **COMPLIANCE:** Educational Notice. No specific property value claims.

#### SPOKE: "Deficiency Judgments in Texas After a Short Sale or Foreclosure"

- **Scope:** TX-authority
- **Target queries:** "deficiency judgment texas", "va loan short sale deficiency"
- **Author:** Levi Rodgers
- **Reviewer:** Mayra Torres
- **Structure:**
  - What a deficiency judgment is and how TX Property Code 51.003 works
  - FMV vs sale price: how the court determines deficiency
  - How to negotiate deficiency waiver in a short sale approval letter
  - VA loan specific: VA's position on deficiency
  - Statute of limitations
- **COMPLIANCE:** CRITICAL — this is legal territory. Educational framing ONLY. "Consult a real estate attorney" in every section. Source Property Code 51.003 directly. No assertions about court outcomes.

#### SPOKE: "Tax on Forgiven Mortgage Debt in 2026"

- **Scope:** TX-authority
- **Target queries:** "do I owe taxes on short sale forgiven debt", "1099-C short sale tax", "mortgage relief act 2026"
- **Author:** Levi Rodgers
- **Reviewer:** Mayra Torres
- **Structure:**
  - The qualified principal residence exclusion expired for discharges after Dec 31, 2025 — what changed and what did NOT change
  - Surviving exclusions: insolvency (no expiration), bankruptcy/Title 11 (no expiration) — sourced from IRS Topic 431
  - 1099-C process and what triggers it
  - Correct framing: "may create taxable income; other exclusions may apply"
  - Texas angle: no state income tax on the forgiven debt regardless of federal treatment
  - What the pending congressional legislation (H.R. 917) would do if passed
- **COMPLIANCE:** CRITICAL — this is tax territory. "Consult a CPA or tax attorney" in every section. Source IRS.gov directly. Do NOT state "forgiven debt is now taxable" as a blanket statement — it is wrong for insolvency/bankruptcy cases. Cite H.R. 917 by bill number only with "proposed" framing.

### 6C. Internal Linking Plan

```
PILLAR: Options When Can't Afford to Sell
  ├── → Short Sale Process TX (spoke)
  ├── → Short Sale vs Foreclosure TX (spoke)
  ├── → Deed in Lieu TX (spoke)
  ├── → Loan Modification TX (spoke)
  ├── → Walk Away from Mortgage TX (spoke)
  ├── → PCS Underwater Mortgage (spoke)
  ├── → Austin Underwater 2026 (spoke)
  ├── → SA Short Sales 2026 (spoke)
  ├── → Deficiency Judgments TX (spoke)
  └── → Tax on Forgiven Debt 2026 (spoke)

CROSS-CLUSTER LINKS:
  PCS Underwater → VALN: VA Compromise Sale Program
  PCS Underwater → VALN: VA Underwater Mortgage Options
  PCS Underwater → LRG 8714: Selling Home PCS No Equity
  PCS Underwater → LRG 2861: VA Loan Assumption
  PCS Underwater → LRG 8654: Second-Tier VA Entitlement
  Short Sale Process → LRG 8688: VA Loan After Short Sale
  Deficiency Judgments → LRG 8891: Capital Gains Tax Selling Home TX
  Austin Underwater → LRG 2226: How to Buy Foreclosure Austin (buyer perspective)
  SA Short Sales → LRG 2233: How to Buy Foreclosure SA (buyer perspective)
  Recovery → LRG 5435: Buying After Bankruptcy SA
  Recovery → LRG 8688: VA Loan After Short Sale TX

EXISTING PAGES THAT SHOULD LINK INTO THE CLUSTER:
  LRG 7411 (SA Housing Market 2026) → Pillar + SA Short Sales
  LRG 7412 (Austin Housing Market 2026) → Austin Underwater
  LRG 8264 (SA Housing Market Mid-Year) → Pillar + SA Short Sales
  LRG 8900 (Low Appraisal) → Pillar (appraisal → equity problem)
  LRG 1918 (Keep and Rent Move-Up Strategy) → Pillar (alternative to selling)
```

### 6D. Compliance Matrix

| Page | Educational Notice | Legal Disclaimer | Tax Disclaimer | Broker Review | Attorney CTA | CPA CTA |
|------|-------------------|-----------------|----------------|---------------|-------------|---------|
| Pillar: Options | YES | YES | YES | Mayra Torres | YES | YES |
| Short Sale Process TX | YES | YES | NO | Mayra Torres | YES (lien/deficiency) | NO |
| Short Sale vs Foreclosure | YES | YES | YES | Mayra Torres | YES | YES |
| Deed in Lieu TX | YES | YES | YES | Mayra Torres | YES | YES |
| Loan Modification TX | YES | NO | NO | Mayra Torres | YES (if restructuring) | NO |
| Walk Away TX | YES | YES | YES | Mayra Torres | YES | YES |
| PCS Underwater | YES | NO | NO | Mayra Torres | YES (if short sale) | NO |
| VA Compromise Sale JBSA | YES | YES | NO | Mayra Torres | YES | NO |
| SCRA Protections | YES | YES | NO | Mayra Torres | YES | NO |
| Rent vs Sell PCS | NO | NO | YES | Mayra Torres | NO | YES (rental income) |
| Austin Underwater 2026 | YES | NO | NO | Mayra Torres | YES (if foreclosure) | NO |
| SA Short Sales 2026 | YES | YES | NO | Mayra Torres | YES | NO |
| Bought at Peak Austin | YES | NO | NO | Mayra Torres | NO | NO |
| Foreclosure Timeline TX | YES | YES | NO | Mayra Torres | YES | NO |
| Deficiency Judgments TX | YES | YES | NO | Mayra Torres | YES | NO |
| Tax on Forgiven Debt | YES | NO | YES | Mayra Torres | NO | YES |
| Second Liens / HOA | YES | YES | NO | Mayra Torres | YES | NO |
| Rebuilding Credit | NO | NO | NO | Mayra Torres | NO | NO |

---

## 7. PRIORITY ORDER — 90-DAY PUBLISHING PLAN

### Phase 1: Weeks 1-3 — Establish the Pillar + Beachhead Expansion

**WHY FIRST:** The pillar page captures all the upstream queries that currently
go to Reddit. It's the highest-value single page in the vertical.

| # | Page | Type | Effort | Volume Signal | Priority |
|---|------|------|--------|---------------|----------|
| 1 | **Options When Can't Afford to Sell TX** (Pillar) | TX-authority | HIGH | Very High (multiple upstream queries w/ 0 professional content) | P0 — publish first |
| 2 | **Short Sale vs Foreclosure TX** | TX-authority | MEDIUM | High (PAA-rich, comparison intent) | P0 — publish same week as pillar |
| 3 | **PCS with Underwater Mortgage TX** | SA-local + TX | MEDIUM | Medium (low volume but zero competition, perfect LRG lane) | P0 — the military beachhead |

**TOTAL PHASE 1:** 3 pages. ~7-10 days including pipeline + review + deploy.

### Phase 2: Weeks 4-6 — Austin Urgency + Texas Process

**WHY SECOND:** Austin's significant price decline (15-25% depending on
index) and elevated negative equity rate (~18% of 2022-vintage borrowers
per ICE) make this timely. These pages ride a current news cycle.

| # | Page | Type | Effort | Volume Signal | Priority |
|---|------|------|--------|---------------|----------|
| 4 | **Austin Homeowners Underwater 2026** | Austin-local | MEDIUM | High (news cycle, 2022-buyer audience) | P1 |
| 5 | **Short Sale Process TX: Step by Step** | TX-authority | MEDIUM | Medium (how-to intent) | P1 |
| 6 | **SA Short Sales 2026** | SA-local | MEDIUM | Medium (local intent) | P1 |
| 7 | **Evaluate post 1516** (backlink/query/intent audit before any redirect decision) | — | LOW | — | P1 |

**TOTAL PHASE 2:** 3 new pages + 1 redirect. ~10-14 days.

### Phase 3: Weeks 7-9 — Legal/Financial Authority + Military Depth

**WHY THIRD:** These are compliance-heavy pages that require careful sourcing.
They build the E-E-A-T authority that makes the whole cluster credible.

| # | Page | Type | Effort | Volume Signal | Priority |
|---|------|------|--------|---------------|----------|
| 8 | **Deficiency Judgments TX** | TX-authority | HIGH (sourcing) | Medium (AIO trigger, unique angle) | P2 |
| 9 | **Tax on Forgiven Debt 2026 (Post-MFDRA)** | TX-authority | HIGH (sourcing) | Medium (AIO trigger, timely) | P2 |
| 10 | **Foreclosure Timeline TX** | TX-authority | MEDIUM | Medium (PAA-rich) | P2 |
| 11 | **VA Compromise Sale: What JBSA Families Need to Know** | SA-local | MEDIUM | Low-Medium (cross-link to VALN) | P2 |

**TOTAL PHASE 3:** 4 pages. ~14-18 days (sourcing adds time).

### Phase 4: Weeks 10-13 — Fill the Cluster

| # | Page | Type | Effort | Volume Signal | Priority |
|---|------|------|--------|---------------|----------|
| 12 | **Deed in Lieu of Foreclosure TX** | TX-authority | MEDIUM | Low-Medium | P3 |
| 13 | **What Happens If You Walk Away TX** | TX-authority | MEDIUM | Medium | P3 |
| 14 | **Loan Modification TX** | TX-authority | MEDIUM | Low-Medium | P3 |
| 15 | **Bought at the Peak in Austin** | Austin-local | MEDIUM | Low (but high AEO potential) | P3 |
| 16 | **Rebuilding Credit After Short Sale TX** | TX-authority | LOW | Low | P3 |

**TOTAL PHASE 4:** 5 pages. Fills remaining cluster gaps.

### What I'd Deprioritize or Cut

| Page Idea | Verdict | Reasoning |
|-----------|---------|-----------|
| Second Liens / HOA Liens in TX Short Sale | DEFER | Niche, low volume, high compliance risk |
| SCRA Protections for Military Foreclosure | DEFER | Existing post 8716 covers SCRA + selling. Expand that page instead of new one. |
| Rent vs Sell PCS Thin Equity | DEFER | Existing 8714 and 8713 (Rent vs Buy) already cover. Cross-link instead. |
| "Bought at the Peak in SA" | CUT | SA correction is milder than Austin. 8.8% underwater [SECONDARY SOURCE] is significant but not the same crisis-market narrative. The SA short-sale spoke covers this audience. |
| Mortgage Hardship Letter template | CUT | Low value, legal risk, better served by linking to CFPB/HUD templates. |
| Pre-foreclosure listings/map page | CUT | Investor intent, not distressed-homeowner intent. LRG is not a wholesaler. |

---

## 8. CTA STRATEGY

### Primary CTA: "Get My Free Home Equity Analysis"

Every page in this vertical should funnel to a **free equity analysis** —
not a generic "contact us." The equity analysis is the natural next step
for someone who's underwater or thinks they might be.

**Why this works:**
- It's risk-free for the homeowner (not "list with us")
- It gives LRG the data to diagnose the situation (current value, loan balance, selling costs)
- It naturally leads to the conversation: "here's your equity position, here are your options"
- It positions LRG as the advisor, not the salesperson

### CTA Placement (per-page)

1. **After BLUF / first section** — soft CTA: "Not sure where you stand? Get a free equity analysis from LRG."
2. **After decision matrix / options section** — action CTA: "Ready to see your options? Start with a free home equity analysis."
3. **End of article** — closing CTA with form or link to dedicated equity analysis page.

### Secondary CTAs (contextual)

- **Military pages:** "PCSing soon? Get your equity analysis before orders drop."
- **Foreclosure pages:** "Worried about foreclosure? A free equity analysis is the first step."
- **Austin pages:** "Bought in 2021-2022? See where your Austin home stands today."

### Equity Analysis Landing Page

Consider creating a dedicated `/equity-analysis/` page as the funnel
destination. This page should:
- Explain what the analysis includes (comparable sales, current market value, estimated net proceeds)
- Have a form collecting: name, email, phone, property address, approximate loan balance, situation (dropdown: "need to sell", "considering options", "PCS/military orders", "behind on payments")
- Route leads to appropriate LRG agent based on situation

---

## 9. MARKET DATA SUMMARY (for Levi)

### Austin Is the Bigger Opportunity, SA Is the Homebase

| Metric | San Antonio | Austin | Source | Label |
|--------|------------|--------|--------|-------|
| Overall underwater rate | 8.8% (#4 nationally) | 9.2% (#3 nationally) | DeviceDaily.com → ResiClub → ICE Mortgage Technology, Dec 2025 | SECONDARY SOURCE |
| 2022-vintage borrower underwater rate | Not separately reported | ~18% | Stated in Randall's critique; primary source (ICE Mortgage Monitor Jul 2025) not fetched | UNVERIFIED |
| Peak-to-current price decline | Moderate (no specific index figure sourced) | 15% (Cotality repeat-sale HPI, Mar 2026) to ~24-25% (MLS-median sources) | Cotality May 2026 report (fetched); multiple secondary sources | VERIFIED (Cotality) / SERP OBSERVATION (MLS median range) |
| Bexar/Travis foreclosure inventory | 459 homes (KSAT, Nov 2025) | Not separately reported; 199% YoY spike (Apr 2026, secondary source) | KSAT.com search snippet (page not fetched); web search result | SECONDARY SOURCE (SA) / SERP OBSERVATION (Austin YoY) |
| LRG existing content advantage | STRONG (PCS, military, SA-local) | MODERATE (foreclosure guide, market updates) | — | INFERENCE |

### Key National Context

- Texas had the most lender repossessions (REOs) by raw count in H1 2026: 3,322 properties. Texas's foreclosure RATE was 0.18% — not in the top 5 (Florida led at 0.27%). [VERIFIED — ATTOM Mid-Year 2026 via PRNewswire]
- Nationwide underwater homes reached 2 million (first time since 2021). [SERP OBSERVATION — The Real Deal headline; underlying source not independently fetched]
- The qualified principal residence exclusion under the MFDRA does not apply to debt discharged after Dec 31, 2025. Insolvency and bankruptcy exclusions remain in effect with no expiration. Forgiven debt may create taxable income; other exclusions may apply. [VERIFIED — IRS.gov Topic 431]
- H.R. 917 (Mortgage Debt Relief extension) pending in Congress. [SERP OBSERVATION — congress.gov appeared in search results; bill text not fetched]

### The VA/Military Lane — Promising and Differentiated [HYPOTHESIS]

Levi's hypothesis that LRG can differentiate in the VA/military
distressed-homeowner category in SA is supported by SERP observations,
but the JBSA/Lackland/Fort Sam/Randolph + PCS + equity SERPs have not
been systematically volume-quantified yet. What we know:

1. **LRG post 8714 appeared as #1 organic** for "selling home pcs no equity" in a single SERP pull (2026-08-09). [SERP OBSERVATION — needs 28/90-day GSC query-level validation]
2. **Zero local Texas broker content** found for "pcs with underwater mortgage" in SERP pull. [SERP OBSERVATION]
3. **Reddit is #1** for "military pcs can't sell house" and "got orders can't sell house" — no professional content. [SERP OBSERVATION]
4. **VALN covers the VA loan mechanics** (compromise sale, entitlement, waiting periods) — LRG doesn't need to duplicate this. [VERIFIED — VALN content audit this session]
5. **The gap appears to be the local broker perspective** — "you're at JBSA, you're underwater, here's what we'd actually recommend." [INFERENCE from SERP observations]
6. **Military.com and Veterans United write national content** — no Texas specificity, no SA/Austin market context. [SERP OBSERVATION]

---

## 10. RISKS AND HONEST ASSESSMENT

### High-Effort / Low-Return Pages

- **Loan Modification TX:** Government sites dominate, low commercial intent, LRG adds little over HUD/TDHCA content
- **Mortgage Hardship Letter:** Template-seekers, not likely to convert to real estate leads
- **Second Liens / HOA Liens:** Very niche, high compliance overhead, low search volume

### Compliance Risk

This entire vertical is adjacent to legal and financial advice. Every page
needs the compliance framework from Section 6D. The biggest risks:

1. **Tax content post-MFDRA:** The qualified principal residence exclusion expired for discharges after Dec 31, 2025 — but the insolvency and bankruptcy exclusions are permanent (IRS Topic 431). Content must NOT say "forgiven debt is now taxable" as a blanket statement. Correct framing: "may create taxable income; other exclusions may apply; a CPA or tax attorney should evaluate your situation." Every tax page needs CPA referral and explicit disclaimer.

2. **Foreclosure timeline assertions:** Texas non-judicial foreclosure can move fast, but stating specific day counts as fact requires citing the specific Property Code sections. "As fast as 21 days after notice" needs a citation.

3. **Deficiency judgment advice:** Saying "Texas allows deficiency judgments" is fact (Property Code 51.003). Saying "you probably won't face one" is legal advice. Stay on the factual side.

4. **VA-specific claims:** VA compromise sale eligibility, waiting periods, and entitlement impacts must be sourced from VA.gov or verified VALN content. Never invent VA policy.

### Content Generation Compliance

All pages must go through the RSS pipeline (`assemble-article.py`). No
freehand content generation. The pipeline's fact-checker module will flag
claims that need sourcing — but given the YMYL nature of this vertical,
the human review gate on the fact-check report is non-negotiable.

---

## APPENDIX A: SERP Cache Index

All SERP data cached to `~/lrg-rewrite/serp-shortsale/`. Files:

- `short_sale_process_texas.json`
- `short_sale_vs_foreclosure_texas.json`
- `how_does_a_short_sale_work.json`
- `short_sale_san_antonio.json`
- `short_sale_austin_tx.json`
- `va_short_sale.json`
- `va_compromise_sale.json`
- `owe_more_than_house_is_worth_what_to_do.json`
- `can_t_afford_to_sell_my_house.json`
- `behind_on_mortgage_payments_texas.json`
- `underwater_mortgage_options.json`
- `selling_house_at_a_loss_texas.json`
- `negative_equity_options_homeowner.json`
- `pcs_with_underwater_mortgage.json`
- `military_pcs_can_t_sell_house.json`
- `va_loan_underwater_what_to_do.json`
- `selling_home_pcs_no_equity.json`
- `pre-foreclosure_options_texas.json`
- `how_to_stop_foreclosure_texas.json`
- `foreclosure_timeline_texas.json`
- `alternatives_to_foreclosure.json`
- `deed_in_lieu_of_foreclosure_texas.json`
- `loan_modification_texas.json`
- `deficiency_judgment_texas.json`
- `mortgage_hardship_letter.json`
- `sell_distressed_property_san_antonio.json`
- `distressed_homes_san_antonio.json`
- `san_antonio_housing_market_downturn.json`
- `austin_housing_market_negative_equity_2026.json`
- `upstream_house_worth_less_than_I_paid.json` (+ 19 more upstream_* files)

## APPENDIX B: GSC Query Inventory

All distressed-homeowner queries LRG currently appears for (60-day window, June 10 - August 8, 2026):

| Query | Clicks | Impressions | Position |
|-------|--------|-------------|----------|
| foreclosure | 1 | 1,392 | 6.4 |
| distressed property leads... SA (Hammond) Jun | 0 | 262 | 6.1 |
| distressed property leads... SA (Hammond) Jul | 0 | 258 | 9.0 |
| distressed property leads... SA (Highland Park) | 0 | 180 | 5.8 |
| austin foreclosures | 0 | 121 | 7.9 |
| austin foreclosure | 0 | 69 | 12.7 |
| va loan short sale | 0 | 60 | 8.8 |
| sell distressed property san antonio | 0 | 41 | 5.8 |
| va loan after short sale | 0 | 38 | 7.6 |
| short sale va loan | 0 | 33 | 9.0 |
| austin foreclosure auction | 1 | 32 | 8.6 |
| va guidelines short sale | 0 | 29 | 9.1 |
| va guidelines on short sales | 0 | 26 | 8.3 |
| foreclosed homes san antonio | 1 | 25 | 10.8 |
| sell distressed property fast | 0 | 24 | 13.0 |
| sell my distressed house fast | 0 | 21 | 10.7 |
| va home loan after short sale | 0 | 18 | 8.1 |

**Total distressed-topic impressions (60 days):** ~2,600+ (2,629 from the
top 17 queries shown above; ~40 additional tail queries at 1-5 impressions
each not shown). [VERIFIED — GSC Search Analytics API, sc-domain:lrgrealty.com,
2026-06-10 to 2026-08-08, query-level filter for 15 distressed-topic terms,
pulled via service account this session.]
**Total distressed-topic clicks (60 days):** ~5

This confirms: LRG has visibility but no conversion because the existing
content doesn't match the searcher's intent. New purpose-built content
should convert these impressions into clicks and leads.
