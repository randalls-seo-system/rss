# Short Sale / Distressed Vertical -- Recon Summary
## For Levi | 2026-08-12

---

## What Exists

Phase 1 shipped. Three pages published Aug 9-10:

1. **Pillar:** "Your Options When You Can't Afford to Sell Your Texas Home" (post 9765)
2. **Military:** "PCS with an Underwater Mortgage: Military Options in Texas" (post 9773)
3. **Comparison:** "Short Sale vs Foreclosure in Texas: Which Is Better for You?" (post 9774)

Plus 6 existing pages that touch the distressed space directly (8714 beachhead, 1516 legacy short sale guide, 8688 VA after short sale, and 3 foreclosure buying guides), and 6 adjacent pages (VA assumption, second-tier entitlement, PCS checklists, SCRA).

VALN covers the VA mechanics side with 7+ dedicated pages. Cross-site division is clean -- no duplication needed.

---

## What's Defective

**9 items that need fixing before more content ships:**

1. **All 3 Phase 1 pages are orphans.** Zero internal links point to them from anywhere on the site. No other page knows they exist. This must be fixed before they can rank -- crawl discovery, link equity, and user navigation all depend on internal links.

2. **Post 8714 (beachhead) has no disclaimers, no sources, no meta tags.** This is YMYL content about selling a home with negative equity. It cites zero authoritative sources. It lacks both the Educational Notice and Legal/Tax Disclaimer. Meta title and description are not set. For the page positioned as the military distressed beachhead, this is a significant compliance gap.

3. **Tax language defect in the pillar (9765).** Line 214 says deed-in-lieu "creates taxable income." Hard rule: must say "may create taxable income; other exclusions may apply." The correct framing appears in the disclaimer section but is contradicted in the body.

4. **54 "Fort Cavazos" instances across 5 pages.** Post 2230 (Killeen foreclosure buying guide, 752 impressions) has 6 instances in its FAQ schema -- directly served to Google. Post 2701 (draft) has 45. Posts 2226, 2110, 2505 have 1 each. Fort Hood was renamed back in 2025.

5. **Fair Housing flag on 9773.** "Works best for families" in the BLUF card. Steering language -- implies the option is better for one familial status than another. Simple fix: "Works best when you owe close to market value."

6. **9 of 18 topical pages lack both disclaimer blocks.** All pre-pipeline pages (8714, 1516, 5435, 5433, 2717, 2110, 2861, 8654, 8716, 8943) are missing both the Educational Notice and Legal/Tax Disclaimer.

7. **No meta titles or descriptions on Phase 1 pages or 8714.** These are YMYL pages where the meta description should be deliberately crafted, not auto-generated.

8. **Zero pages use the equity analysis CTA.** Strategy specified "Get My Free Home Equity Analysis" as the primary CTA for every distressed page. All pages currently use generic "Connect with LRG."

9. **Foreclosure buying guides (2233, 2226, 2230) are orphans** despite being the highest-traffic distressed-topic pages (3,552 combined impressions). Zero internal links point to them.

---

## What the SERP Says

**61 queries researched across 5 bands.** Core finding unchanged from Aug 9:

- **Reddit owns upstream queries.** 11 of 13 pre-vocabulary queries have Reddit as #1. "House worth less than I paid" -- Reddit #1, Reddit #2, Quora #3. Zero professional content.
- **No local Texas broker ranks** for any core short sale or distressed query. The only local voices: Alexander Realty (SA, #3 for "short sale realtor san antonio"), Cain Realty (Austin, #2 for "short sale realtor austin"), and two military-niche competitors.
- **Two military-niche competitors found.** veteranrealestatesa.com ranks #1 for "JBSA PCS can't sell house." sharprealtygrouptx.com ranks #1 for "Lackland AFB PCS sell house fast." These are in LRG's lane.
- **AI Overviews fire on 14 of 61 queries,** skewing to upstream + legal queries. No local broker has ever been cited in an AIO for these topics.
- **Government sites own "help" queries** (.gov / TDHCA / texaslawhelp). LRG should link to these, not compete with them.

---

## What the Recon Changes About the Phase 1 Plan

Three things:

**1. Internal linking is the immediate blocker, not more content.**
The Phase 1 pages are live but invisible. They have zero internal links pointing to them. Before publishing any Phase 2 content, the existing pages need to be wired into the site's link graph. The pillar (9765) should receive links from at least: 7411 (SA market), 7412 (Austin market), 8264 (SA mid-year), 1586 (50-year mortgage), 8900 (low appraisal), 1918 (keep and rent), and every PCS page. The foreclosure buying guides (2233, 2226, 2230) should also be linked from their respective market pages.

**2. Post 8714's "#1 ranking" is not confirmed.**
The strategy doc positioned 8714 as the beachhead based on a single Serper pull showing #1 for "selling home pcs no equity." GSC shows 5 total impressions over 90 days. This doesn't disprove the ranking (the query might have very low volume), but it does mean we can't rely on 8714 as evidence that the military lane is proven. It's still the right strategic bet -- the SERP gap is real -- but the proof-of-concept is not yet established.

**3. The PCS cluster has cannibalization risk.**
Posts 9773 (PCS underwater), 8714 (PCS no equity), 2717 (PCS checklist), 2110 (Fort Sam PCS), plus 3 drafts (2500, 2505, 2701) all target PCS + selling queries. Without clear scope differentiation and cross-linking, they'll compete. The Phase 2 plan should not add any more PCS pages until the existing cluster is internally linked with clear intent boundaries.

---

## Decisions for Levi

1. **Post 1516 (Understanding Short Sales, 46 internal links) -- redirect to 9765 pillar, or keep?**
   The strategy doc flagged this for backlink/query/intent audit before decision. 1516 has 46 internal links (most in the cluster) but only 15 GSC impressions. The pillar (9765) is the better page. Redirecting 1516 to 9765 would transfer 46 internal links to the pillar -- significant crawl benefit. But 1516's slug is `2024-8-14-understanding-short-sales-a-guide-for-homebuyers-and-sellers` (ugly, date-prefixed) and it targets buyer+seller, while 9765 is seller-only. External backlink check needed before deciding.

2. **Fort Cavazos remediation scope -- batch fix all 54 instances, or page-by-page?**
   2230 (6 hits in live FAQ schema) is the priority since it's serving wrong facts to Google. 2701 (45 hits, draft) could just stay unpublished. 2226 and 2110 (1 hit each) are quick fixes. Recommend: fix 2230 and 2226 now, leave 2701 draft until needed.

3. **Disclaimer retrofit on pre-pipeline pages -- scope?**
   9 pages need both disclaimer blocks. The pipeline auto-injects them for new content but these predate it. Options: (a) batch inject via SQL REPLACE, (b) retrofit one-by-one via pipeline regeneration, (c) accept the gap and only fix the YMYL-heavy ones (8714, 5435, 2861). Recommend option (c) for now -- 8714 is the priority.
