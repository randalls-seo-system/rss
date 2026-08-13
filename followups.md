# Short Sales Vertical -- Follow-up Items

## 1. Yoast Meta Description Not Rendering on Category Archives (site-wide)

**Status:** Parked. Not specific to Short Sales.

**What was done:** `wpseo_taxonomy_meta` option created with
`category[76][wpseo_desc]` set to the approved SERP snippet. The option
was empty before this write (no category on the site had Yoast term meta).

**What renders:** `og:description` picks up `tt.description` (the hero
subhead string). No `<meta name="description">` tag appears on any
category archive, including Home Buying (247 posts), which has never had
one.

**Likely cause:** Two possibilities, not yet investigated:
1. Yoast SEO taxonomy meta output is disabled in Yoast settings
   (SEO > Search Appearance > Taxonomies > Categories > "Show Categories
   in search results"). If set to "No", Yoast suppresses the meta tag.
2. `rss-meta-header.php` or the Divi theme builder overrides Yoast's
   `<head>` output on archive templates. The mu-plugin is 70KB and
   handles post-level meta extensively; it may not hook into taxonomy
   archives.

**Impact:** Every category archive (28+ categories with posts) ships
without a meta description. Google auto-generates snippets from page
content. For most informational categories this is low-priority, but for
Short Sales specifically the auto-generated snippet will pull from the
first card's excerpt -- which is currently the Educational Notice
disclaimer text (see Task 3).

**Fix scope:** Site-wide Yoast config check + possible rss-meta-header.php
extension for taxonomy archives. Separate session.

## 2. Pill Bar Ordering -- Short Sales at Position 25 of 29

**Status:** Report only. No change made.

**Mechanism:** `lrg_cat_hero_get_pills()` in `lrg-category-hero.php`
calls `get_categories(orderby => count, order => DESC)`. No pinning,
no priority array, no filter hook.

**Cost to pin:** ~10 lines added to the function: a `$pinned` array of
slugs that get sorted to the front, remaining categories follow in count
order. Minimal risk, but it is a mu-plugin edit on prod.

**Decision:** Not urgent. Do not revisit until the category has enough
posts to place organically. Pinning a 6-post category above 24 larger
ones is a mu-plugin edit on prod to solve a problem that solves itself
if the article queue ships. Revisit at 15+ posts, or never.

## 3. Post 1516 vs 9765 Cannibalization (UNRESOLVED)

**Status:** Flagged in Task 4 article queue. Not settled.

Post 1516 ("Understanding Short Sales: A Guide for Homebuyers and
Sellers") and 9765 ("Your Options When You Can't Afford to Sell Your
Texas Home") both now sit in the Short Sales category. They compete for
short-sale explainer intent. 1516 was reported as having 46 internal
links pointing to it in the recon pass (SECONDARY -- single-source LIKE
query, not verified against a second method). The 46-link count must be
confirmed before it drives a redirect decision. GSC shows only 15
impressions over 90 days. Options: redirect 1516 to 9765 (transfers
link equity if the count holds), rewrite 1516 to narrow its scope to
buyer-side only, or leave both. Requires backlink audit + link count
verification before deciding.

## 4. TREC Advertising Compliance (site-wide)

**Status:** Report only. No change made.

CTA block generated at `assemble-article.py:2094-2095` from `CTA_TEXT`
config. No broker licensed name displayed near the CTA. 22 Tex. Admin.
Code §535.155(b)(1) requires the broker's name to be "readily
noticeable" in advertising. Fix is template-level, affects every article
on the site. Separate session.

## 5. Adversarial Review Open Items (staging articles)

**Article #4 (Austin Underwater):**
- ZIP code underwater rankings CUT (no primary source)
- 9.2% negative equity stat CUT
- VA 9.6% and FHA 5.7% rates CUT
- Austin DPA eligibility details CUT
- MLS-median price decline range CUT
- KEPT: Cotality 15% decline figure (verified, cited inline)
- Word count after cuts: 2920 (viable)

**Article #8 (Forgiven Debt Tax, DRAFT):**
- Held for Mayra with review-for-mayra-article-8.md
- Texas recourse misstatement is the critical finding
- 1099-C/deficiency distinction needs clarification
- DO NOT fix before Mayra reviews

**Article #9 (Short Sale Process):**
- TREC Form 45-2 hedged with "verify current form at trec.texas.gov"

**Remaining UNFETCHABLE (not actionable without primary sources):**
- Article #7 guarantor waiver rules (Moayedi case law) -- article does
  not cite the case, no fix needed
- Article #5 reinstatement right -- checked, no overstated claim found

## 6. Durable-Phrasing Rules Must Go in ALL 7 Prompt Files

**Status:** STANDING RULE for the pipeline.

Any durable-phrasing rule added to the pipeline must be placed in ALL
7 prompt files, not one:
- `h2-section.md` (body sections)
- `bluf.md` (Bottom Line Up Front)
- `atf-lede.md` (ATF lede paragraph)
- `atf-card.md` (ATF comparison/option cards)
- `atf-faq.md` (ATF FAQ block)
- `btf-faq.md` (BTF FAQ block)
- `closing-bottom-line.md` (closing paragraph)

Single-file rules are silently partial. Each section type is built by a
separate tool (`build-h2-section.py`, `build-bluf.py`, `build-card.py`,
`build-faqs.py`) that loads its own prompt. A rule in `h2-section.md`
does not reach BLUF, lede, cards, or FAQs.

Proven by: the deficiency auto-waiver rule was added to `h2-section.md`
only. Post 9671's BLUF generated the exact violation the rule was
designed to prevent. Fixed by propagating to all 7 files.

## 7. Archive Card Apostrophe Bug (template-level)

`lrg-category-hero.php:541` double-encodes `wptexturize()` output via
`esc_html()`. Affects all archive card titles with apostrophes,
ampersands, or special characters. DB values are clean. Requires
mu-plugin edit.
