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

**Impact:** Every category archive (27 categories with posts) ships
without a meta description. Google auto-generates snippets from page
content. For most informational categories this is low-priority, but for
Short Sales specifically the auto-generated snippet will pull from the
first card's excerpt -- which is currently the Educational Notice
disclaimer text (see Task 3).

**Note (2026-08-13):** Category base changed from `/lrg-blog/category/`
to `/lrg-blog/topics/`. Category archives now live at
`/lrg-blog/topics/<slug>/`. Old `/category/` paths 301 via regex in
`lrg-broken-link-redirects.php` v1.3.0. Category count is 27 non-empty
(down from 29 after junk terms "30" and "64" were deleted).

**Fix scope:** Site-wide Yoast config check + possible rss-meta-header.php
extension for taxonomy archives. Separate session.

## 2. Pill Bar Ordering -- Short Sales Sorts by Post Count

**Status:** Report only. No change made. Open against new `/topics/` base.

**Mechanism:** `lrg_cat_hero_get_pills()` in `lrg-category-hero.php`
calls `get_categories(orderby => count, order => DESC)`. No pinning,
no priority array, no filter hook. Short Sales position depends on its
post count relative to other categories. Category base is now
`/lrg-blog/topics/` (changed 2026-08-13). Pill bar links auto-updated
via `get_term_link()`.

**Cost to pin:** ~10 lines added to the function: a `$pinned` array of
slugs that get sorted to the front, remaining categories follow in count
order. Minimal risk, but it is a mu-plugin edit on prod.

**Decision:** Not urgent. Do not revisit until the category has enough
posts to place organically. Revisit at 15+ posts, or never.

## 3. Post 1516 Rebuild — Resolved, Not Yet Deployed

**Status:** RESOLVED. Rebuild complete on staging, NOT YET DEPLOYED.

Query analysis showed 1516 serves short-sale process intent and 9765
serves options-overview intent — no cannibalization. Decision: Option A,
rebuild 1516 at a clean slug.

Draft 9671 (`short-sale-process-guide-texas`) exists on staging. Post
1516 still live at the dated Squarespace slug
`2024-8-14-understanding-short-sales-a-guide-for-homebuyers-and-sellers`.

**Approach when resumed:** Update post 1516 in place with 9671's content
and the new slug. Generate a featured image. Add CF Worker redirect
entries for the old dated URL.

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

## 7. Sidebar CTA Reads "Connect with LRG" (template-level)

The sidebar sticky CTA is rendered by `rss-sticky-cta.php` mu-plugin,
not from post_content. The in-article CTAs were swapped to "Get My Free
Home Equity Analysis" but the sidebar CTA is template-driven. Fixing it
requires editing the mu-plugin or its config. Affects all articles
site-wide, not just the short-sale batch. Same session scope as TREC
advertising (#4 above).

## 8. Duplicate FAQ H2 in Jump Nav (pipeline bug)

The pipeline generates both ATF FAQs and BTF FAQs with identical H2
text ("Frequently Asked Questions"). The sidebar jump nav picks up both,
showing a duplicate entry. Fixed in this batch by renaming the BTF H2
to "More Questions". Affected 5 of 9 articles. The fix should be in
the BTF FAQ builder (`build-faqs.py --mode btf`) to use a distinct H2
by default.

## 9. Zeroed post_date_gmt on Pipeline-Created Posts

Posts created by `run-shortsale-batch.py`'s `create_staging_post()`
had `post_date_gmt = 0000-00-00 00:00:00`, causing the template to
render "Updated on January 1, 1970." Root cause: `wp_insert_post()`
via SSH/eval-file leaves GMT fields zeroed when creating drafts. Fixed
by backfilling with `get_gmt_from_date()`. The batch runner's
`create_staging_post()` should pass `post_date_gmt` explicitly.

## 10. Archive Card Apostrophe Bug (template-level)

`lrg-category-hero.php:541` double-encodes `wptexturize()` output via
`esc_html()`. Affects all archive card titles with apostrophes,
ampersands, or special characters. DB values are clean. Requires
mu-plugin edit. Open against new `/topics/` base.

## 11. Cloudflare Worker REDIRECTS Map — Stale /category/ Targets

**Status:** Open. Manual pass required.

The CF Worker REDIRECTS map (deployed via Cloudflare, not in the repo)
has entries whose targets point at `/lrg-blog/category/` paths. These
now chain through the WordPress 301 handler (`lrg-broken-link-redirects.php`
v1.3.0 regex: old `/category/*` → `/lrg-blog/topics/*`). The chains
work but add a hop. A manual pass of the Worker source is needed to
update targets to `/lrg-blog/topics/` directly.

The linker config files also need updating:
- `randalls-seo-system/sites/lrg/config.json` line 65: `excluded_destinations`
  contains `/lrg-blog/category/` — update to `/lrg-blog/topics/`
- `randalls-seo-system/sites/lrg-linker.json` line 36: same
- `rss-shortsale/sites/lrg/config.json` line 65: same

## 12. Post 1516 Rebuild — Pending Deploy

**Status:** Open. Draft 9671 on staging, never deployed.

Post 1516 ("Understanding Short Sales: A Guide for Homebuyers and
Sellers") still has the dated Squarespace slug
`2024-8-14-understanding-short-sales-a-guide-for-homebuyers-and-sellers`.
The rebuild (draft 9671) was created on staging but never shipped.

**Approach:** Update post 1516 in place with 9671's content and a new
clean slug. Generate a featured image. Add CF Worker entries for the
old dated URL. The `2024-8-31-understanding-san-antonio-home-price-trends`
Worker entry that points at the dated 1516 URL also needs updating to
the new slug once the rebuild deploys.
