# Contributor Article Checklist — LRG Realty

Every contributor article (freehand or pipeline) must pass every item below
before delivery. This checklist exists because the freehand path drops elements
that `assemble-article.py` automates. Priscilla Hollenbeck's Boerne article
required 12 post-publish fix rounds because these items were not checked at
build time.

**Rule: an article is not "done" until every applicable item is YES.**

Built from gaps found deploying the Boerne guide (2026-06-16/17). Each gap
required a post-publish fix that this list would have caught.

---

## ATF (Above the Fold)

| # | Element | Spec | Audit Check |
|---|---------|------|-------------|
| A1 | **Breadcrumb** | `rl-breadcrumb` nav: Home > Blog > Page Title | `rl-breadcrumb` present |
| A2 | **Eyebrow** | `rl-eyebrow`: category + topic type | `rl-eyebrow` present |
| A3 | **H1 title** | Inside `header.rl-card.rl-hero`. The ONLY H1 on the page. | Exactly 1 H1 in content |
| A4 | **50-70w AEO intro** | `rl-hero-lead` paragraph. Directly answers the query. Contributor voice. | `rl-hero-lead` present, 50-70 words |
| A5 | **CTA pair** | Connect: `/lrg-blog/connect-with-lrg/?ref={slug}`. Search: `/listings/homes-for-sale-{city}/`. NEVER Squarespace IDX (`/homes-for-sale-in-{city}/`), NEVER Ylopo, NEVER `search.lrgrealty.com`. Fall back to nearest metro `/listings/` page if no city page exists. | Both hrefs present, both resolve 200, no legacy URLs |
| A6 | **4 stat cards** | `nh-qstats` with 4 `nh-qs`: price range, population, commute, school district. | 4 `nh-qs` items |
| A7 | **4 quick-answer cards** | `rl-quick-grid` with 4 `rl-quick-card`: cost, schools, commute, lifestyle. Each: H3 + 3 bullets. | 4 `rl-quick-card` articles |
| A8 | **3 ATF FAQs** | `rl-faq` section after cards, before body. 3 `<details><summary>` toggles. Contributor voice answers. SEPARATE from bottom FAQs. | Section with ID, 3 details/summary |

## Score Section

| # | Element | Spec | Audit Check |
|---|---------|------|-------------|
| S1 | **Scorecard** | `nh-scorecard` with 4 `nh-sc-item`: entry price, commute, school rating, tax jurisdiction. | 4 scorecard items |
| S2 | **Score bars** | `nh-meters` with 4-5 `nh-meter` bars. Label + colored fill (green/gold/red) + numeric 1.0-10.0. ONLY sourceable metrics. Omit rather than fabricate. | 4-5 score bars with justified values |
| S3 | **Score callout** | `nh-callout gray` below bars. One bullet per score explaining the rating with source. | Callout present, bullets match bar count |

## Body Sections

| # | Element | Spec | Audit Check |
|---|---------|------|-------------|
| B1 | **Section structure** | `rl-section` or `nh-blk` with `id` for jump links. H2 heading. Prose + callout block. | All sections have IDs and H2s |
| B2 | **Visual rhythm** | Alternating white/tinted or `nh-blk alt`. Colored callouts (`nh-callout blue/gray/green/beige`). No wall of same-style text. | Alternation present |
| B3 | **Comparison table** | `table.rl-table`. CSS: `table-layout:fixed`, first col `width:25%`, data cols `white-space:normal`. Real/sourced data only. Qualitative where not sourceable. | Table present, correct class |
| B4 | **Mid-article author bio** | `nh-callout blue` with headshot (72px round), "Why trust this guide", 1-2 line credentials, link to author page. Placed at natural break mid-article. | Bio callout present, headshot resolves 200 |
| B5 | **Good Fit / Think Twice** | `nh-fit` with `nh-panel good` + `nh-panel warn`. 4 items each (dt/dd). Followed by `nh-verify` before-you-commit checklist. | Both panels + verify block present |
| B6 | **Mid-article CTA** | `rl-cta-mid` with `rl-cta-primary`. "Connect with LRG" link. White text on red (`color:#fff !important`). | CTA present, class = `rl-cta-primary` |

## Bottom Section

| # | Element | Spec | Audit Check |
|---|---------|------|-------------|
| F1 | **4-7 bottom FAQs** | `section.rl-faq` with `<details><summary>` toggles. NEVER flat `div.rl-faq-item` with `h3.rl-faq-q`. Toggle format mandatory. Different questions from ATF FAQs. | 4-7 details/summary, no flat divs |
| F2 | **FAQPage schema** | JSON-LD `@type:FAQPage` with `mainEntity` array. All visible FAQ Q&As in schema. Schema text matches visible text. On LRG: render-time via `lrg-neighborhood-styles.php` for `_lrg_neighborhood` posts, or inline for others. | FAQPage in served HTML, Q count matches |
| F3 | **Related/cluster links** | `bullet-section-gray` with 5-8 related guides. Must include: neighborhood guide for the city (interlink), listings page, 3-5 adjacent-area guides. All resolve 200. | Links present, all 200 |
| F4 | **Resources Used** | `footer.rl-resources` with `rl-callout.rl-disclosure`. External source per factual claim. Minimum: school district, county/city government, chamber of commerce. All resolve 200. | Footer present, links resolve |
| F5 | **End-of-article contributor bio** | `rl-contributor-bio` > `rl-bio-card`: headshot from `/wp-content/uploads/authors/`, name, TREC license, 2-3 line bio, social links. After Resources Used, before FAQ schema. | Bio block present, headshot resolves |

## Meta and WordPress

| # | Element | Spec | Audit Check |
|---|---------|------|-------------|
| M1 | **`_lrg_neighborhood` meta** | Set to `1` on creation. Enables `neighborhood-guide` body class, loads nh-CSS, disables wpautop. | Meta = 1 |
| M2 | **Author** | `post_author` = contributor WP user ID (NOT lrgrealtyblogs ID 1). User must have `rss_mh_avatar` = hosted headshot URL, `rss_mh_role` = "REALTOR", `rss_mh_profile_url` = author page URL. | post_author correct, avatar meta set |
| M3 | **Reviewer** | `_rss_reviewer_select` = `custom`. `_rss_reviewer_override` = Mayra Torres, Managing Broker, with her headshot and author page URL. Author and reviewer MUST differ. | Reviewer = Mayra, not author, not Editorial Team |
| M4 | **Byline toggle** | Article: `_rss_enable_block` = `1`. Author PAGE: `_rss_enable_block` = `0`. | Correct per post type |
| M5 | **Post excerpt** | Manual excerpt set. Clean sentence, no HTML. Used by blog grid and OG tags. | Excerpt present, no markup bleed |
| M6 | **Yoast meta** | `_yoast_wpseo_title` with year. `_yoast_wpseo_metadesc` clean sentence. | Both set |
| M7 | **Featured image** | GPT pipeline: `lrg-batch-generate.py`. Navy gradient + scene + headline + LRGREALTY.COM. QA passed. Set via `set_post_thumbnail`. | Thumbnail set, resolves 200 |

## Content Rules

| # | Rule | Audit Check |
|---|------|-------------|
| C1 | No em-dashes in body | 0 occurrences of `—` |
| C2 | No parentheses in body prose | 0 `(` in prose (OK in schema/HTML attrs) |
| C3 | Capitalize Veteran and Military | 0 lowercase `veteran` or `military` in prose |
| C4 | No H1 in post_content body | Only 1 H1 total (in header) |
| C5 | No fabricated statistics | Every number sourced or explicitly qualitative |
| C6 | Light Veteran-owned positioning | 1-2 mentions max |
| C7 | End on substance | Last section = value, not sales pitch |
| C8 | Contributor voice throughout | First-person local authority, natural |

## Author Entity (One-Time Per Contributor)

| # | Element | Spec |
|---|---------|------|
| E1 | **WP user** | `firstname.lastname`, role: author, display_name set |
| E2 | **Headshot** | PNG at `/wp-content/uploads/authors/{first}-{last}.png`, resolves 200 |
| E3 | **User meta** | `rss_mh_avatar` = headshot URL, `rss_mh_role` = REALTOR, `rss_mh_profile_url` = author page |
| E4 | **Author page** | Child of 5480 `/authors/`. `lrgAuthor` HTML + Person JSON-LD. `_lrg_neighborhood`=1, `_rss_enable_block`=0 |
| E5 | **Person schema** | name, jobTitle, url, image, worksFor (NFLO LLC dba LRG), hasCredential (TREC), knowsAbout, sameAs |
| E6 | **Article listing** | `laArticles` links updated when articles publish (currently static HTML) |

---

## CTA URL Reference

| City | Search CTA (`/listings/` page) |
|------|-------------------------------|
| Boerne | `/listings/homes-for-sale-boerne/` |
| San Antonio | `/listings/homes-for-sale-san-antonio/` |
| Austin | `/listings/homes-for-sale-austin/` |
| Killeen | `/listings/homes-for-sale-killeen/` |
| New Braunfels | `/listings/homes-for-sale-new-braunfels/` |
| Fair Oaks Ranch | `/listings/homes-for-sale-fair-oaks-ranch/` |

Connect CTA for ALL cities: `/lrg-blog/connect-with-lrg/?ref={slug}`

Verify the `/listings/` page returns 200 before using. If no city page exists,
fall back to nearest metro.

---

## Validation

Run the audit PHP against any post to check all items:

```bash
cat audit/lrg-contributor-audit.php | ssh lrgrealtyblog@... \
  'cat > /tmp/run.php && cd /nas/content/live/lrgrealtyblog && wp eval-file /tmp/run.php'
```

Output: per-item PASS/FAIL. An article passes when all applicable items show PASS.

The consistency-audit CSV (`audit/lrg-consistency-audit.csv`) checks the full
published corpus. The contributor audit checks a single article in depth.
