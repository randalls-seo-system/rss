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
