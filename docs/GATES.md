# Gate Ledger

Every incident caught in review or by ground-truth checking ends its session
as a named assertion in `lib/gate_library.py` with a shown red run and a
`GATES.md` entry. No fix without a gate.

## Universal Gates (lib/gate_library.py)

These run on EVERY content write path — push-post-content, deploy_draft,
refresher, batch-inject-links, style-pass, and all LRG generators.

| Date | Incident | Assertion | Paths Protected |
|------|----------|-----------|-----------------|
| 2026-08-10 | `[FLAG FOR MAYRA]` shipped live in article body | `no_editorial_markup` | all write paths |
| 2026-08-10 | 23 duplicate slugs created across batch runs | `slug_unique` | push-post-content --create |
| 2026-08-10 | Fabricated methodology claims ("according to our analysis of MLS data") | `no_fabricated_sourcing` | all write paths |
| 2026-08-10 | `[REFRESH pending]` prefix leaked into live title | `title_integrity` | all write paths |
| 2026-08-10 | Fragment `<li>` items (2-word bullets, leading punctuation) shipped | `no_fragment_list_items` | all write paths |
| 2026-08-10 | Foreign CSS classes from wrong site config rendered broken | `no_undefined_classes` | all write paths |
| 2026-08-10 | Banned AI phrases ("dream home", "hassle-free") in published content | `no_banned_phrases` | all write paths |
| 2026-08-10 | Empty/stub articles deployed to production | `body_not_empty` | all write paths |
| 2026-08-10 | Content with no headline structure deployed | `headline_present` | all write paths |
| 2026-08-10 | Articles with 2 H2 sections passed as complete | `min_sections` | all write paths |
| 2026-08-10 | Wrong-but-plausible domain claims passing all gates | adversarial review stage | pipeline Stage E2 (bounded, evidence-verified) |

## Article-Pipeline Gates (spec_assertions.py)

These run inside the article pipeline (Stage D: Emit Gates) and refresher
approval. They are article-specific — the universal gates above cover all
content types.

| Date | Incident | Assertion | Spec Ref |
|------|----------|-----------|----------|
| 2026-08-09 | Fragment `<li>` items shipped in TLN refresh drafts | `assert_no_fragment_list_items` | 18.4.12 |
| 2026-08-09 | ATF elements rendered out of order (BLUF after cards) | `assert_atf_document_order` | 18.4.13 |
| 2026-08-09 | Title truncated/mismatched after pipeline | `assert_title_integrity` | 18.4.14 |
| 2026-08-09 | Editorial markers in body (`[FLAG`, `[TODO`) | `no_editorial_markup` (fd99cb8) | universal |
| 2026-08-06 | Mortgage vertical assertions (overuse, symmetrical AI, keyword stuffing) | multiple 18.4/18.5 | 3a5dd14 |
| 2026-08-05 | Pipeline gates not enforcing (soft-only) | 5 gates made hard | 2d12571 |
| 2026-08-03 | 13 stub/boilerplate guides deployed as real content | `content_quality_gate.py` | f64b43f |
| 2026-08-03 | Duplicate posts created across batch events | `dupe_guard.py` | 338ee68 |
| 2026-08-03 | Wrong-town data contamination from off-target SERP results | source-relevance filter | fd37a23 |
| 2026-08-03 | Confabulated H2 sections from thin SERP data | confabulation guard | ac2a928 |
| 2026-08-03 | FAQ topic drift (questions not naming target location) | FAQ topic-drift filter | ac2a928 |
| 2026-08-03 | Body/FAQ self-contradiction (asserts X, FAQ denies X) | self-contradiction check | ac2a928 |
| 2026-08-03 | Unsourced claims shipped in article body | fact_checker + claim_verifier | c38989e, eb7405f |
| 2026-07-31 | Fort Cavazos (now Fort Hood) in content | Cavazos hard-fail | bd220c9 |
| 2026-07-28 | In-body jump nav duplicating sidebar TOC | `assert_jump_nav_structure` | c3f6748 |
| 2026-07-28 | BLUF containing quick-card classes | BLUF negative assertion | c3f6748 |
| 2026-07-28 | Resources section with <3 items passing | Resources 3-8 threshold | 68eaf41 |
| 2026-06-22 | Publish without featured image | LRG publish gate | d53e138 |
| 2026-06-17 | Business claims without facts file | claims gate | f807139 |

## Community-Guide Gates (spec_assertions.py 18.CG.*)

| Date | Incident | Assertion | Spec Ref |
|------|----------|-----------|----------|
| 2026-08-03 | Builder comparison table missing required columns | `assert_cg_builder_comparison` | 18.CG.1 |
| 2026-08-03 | Cost section missing MUD/PID address | `assert_cg_cost_strip` | 18.CG.2 |
| 2026-08-03 | Prices in HTML not in manifest volatile_data | `assert_cg_zero_unsourced_prices` | 18.CG.3 |
| 2026-08-03 | School section with placeholder text | `assert_cg_schools_section` | 18.CG.4 |
| 2026-08-03 | Restaurant/venue lexicon in residential guide | `assert_cg_no_venue_lexicon` | 18.CG.5 |
| 2026-08-03 | Wrong geography for named community | `assert_cg_no_wrong_geography` | 18.CG.6 |
