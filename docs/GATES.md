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
| 2026-08-18 | assemble-article.py never called run_universal_gates(). 65 GFP articles generated ungated — every manifest records `validation.ran: false`. Any editorial marker, foreign class, banned phrase, or stub article passed generation unchecked. | `run_universal_gates` wired into assemble-article.py between phase_polish and phase_i as hard failure. Generation-time config uses GENERATION_CSS_PREFIX ("rl-") instead of site deploy prefix. | assemble-article.py main() — all article generation |
| 2026-08-18 | `bullet-section-*` classes (emitted by html_sanitizer.py, added by VALN/LRG postprocessors) are foreign to no_undefined_classes at both generation and deploy lifecycle stages for all sites. Latent deploy blocker for any article with bare `<ul>` in body sections. | `bullet-section-` added to framework prefix tuple in `_get_css_allowlist` | all write paths (generation + deploy) |

## Deploy Artifact Resolution (lib/artifact_resolver.py)

These gates enforce that every deploy path resolves the certified artifact
by exact post_id and filename — no candidate lists, no globs, no fallbacks.

| Date | Incident | Assertion | Paths Protected |
|------|----------|-----------|-----------------|
| 2026-08-12 | Job 20260805-201409-d9dd5002 had `post_id: null`. `job.get("post_id", 0)` returned None (key exists with null value). cli_review fell through candidate list to glob and reviewed pre-postprocessor assembly (`1501-assembled-raw.html`) instead of certified `1501-deploy.html`. | `resolve_deploy_artifact` — requires `{post_id}-deploy.html` to exist; no candidate list, no glob, no fallback | adversarial_review cli_review (site #1), approve_refresh deploy gate (site #7) |
| 2026-08-12 | Same incident. `job.get("post_id", 0)` returns None for null keys. Bool (`isinstance(True, int)` is True), float (`int(3.7)` silently truncates), zero, and negative values all pass `int()`. | `validate_post_id` — rejects None, bool, float, empty string, zero, negative. Returns validated int. | rss Stage E2 post_id + reviewed-artifact name (sites #2, #3), adversarial_review post_id + reviewed-artifact name (sites #4, #5) |
| 2026-08-12 | approve_refresh had no deploy-artifact gate. Readiness check uses `refresh.original_post_id`; top-level `post_id` (used by resolver) was unchecked. Null post_id slipped to SSH call. | `resolve_deploy_artifact` + `run_universal_gates` on deploy artifact in approve_refresh | approve_refresh (site #7, additive alongside existing raw-article gate) |
| 2026-08-12 | Posts 1501/383/1740 received unstyled content (Aug 10). `run_postprocess` passthrough branch copied source to deploy unchanged when css_prefix was `rl-`. For non-rl- sites, postprocessor could pass through without converting classes and no gate caught it. | `assert_deploy_class_migration` — deploy artifact for non-rl- site must contain zero rl-* classes AND must not be byte-identical to source article | create_pending_draft (refresh path only, not universal) |

## Refresh Lifecycle Gates

| Date | Incident | Assertion | Paths Protected |
|------|----------|-----------|-----------------|
| 2026-08-18 | `start_refresh_job()` created jobs with `post_id: null`. `create_job()` defaults to None; refresh never overwrote it. All three August TLN refresh jobs (1501, 383, 1740) carry null. `approve_refresh` calls `resolve_deploy_artifact(job, jdir)` which calls `validate_post_id(job)` — raises on null, blocking every refresh approval after the resolver landed (2026-08-12). | `TestRefreshJobCarriesPostId` — `start_refresh_job` must set `job["post_id"]` to a valid positive integer, same value as `refresh.original_post_id`. | start_refresh_job (producer), approve_refresh + adversarial review + run_assemble (consumers via resolver/guard) |
| 2026-08-18 | `create_pending_draft()` line 360 references `site_slug` — never defined in function scope. Every call would `NameError` before reaching the universal gate check. Latent since initial implementation, never hit because `create_pending_draft` was only called in manual sessions that apparently never reached the gate path. | Fix: `site_slug` → `job.get("site", "")`. Test: `create_pending_draft` function is called through `rss refresh-draft` CLI. | create_pending_draft (refresh path) |
| 2026-08-18 | `run_assemble()` passed `str(None)` as `--post-id` to `assemble-article.py` when `job["post_id"]` was null. `argparse int()` raised `invalid int value: 'None'` — a subprocess `RuntimeError` with no mention of `post_id`, masking the root cause. | `TestRunAssembleRejectsNullPostId` — guard raises `ValueError` naming `post_id` before subprocess launch. | run_assemble (consumer-side guard) |
| 2026-08-18 | `create_pending_draft` had no CLI command. The refresh lifecycle required manual Python calls between `rss refresh` and `rss refresh-approve`. | `TestRefreshDraftCliRegistered` — `cmd_refresh_draft` function, `"refresh-draft"` subcommand, and dispatcher entry must all exist in `rss` CLI. | rss CLI dispatcher |

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

## Vertical Rules Coverage (test_vertical_rules_coverage.py)

Structural tests ensuring every prose-generating builder injects vertical
rules when the site declares a vertical.

| Date | Incident | Assertion | Paths Protected |
|------|----------|-----------|-----------------|
| 2026-08-18 | A durable-phrasing rule was added to h2-section.md forbidding short-sale deficiency language. The next generation produced the exact forbidden text — because the lede, cards, and closing never saw vertical rules. build-card.py (4 calls/article), `_build_atf_lede`, and `_build_closing` constructed prompts without `{{VERTICAL_RULES}}`. | `test_template_gate` — every prompt template with `{{INJECT_BRAND_VOICE}}` must also have `{{VERTICAL_RULES}}`. `test_builder_code_gate` — every `render_prompt()` call whose template has `{{VERTICAL_RULES}}` must pass the value (per-call granularity). `test_orchestrator_loads_vertical_rules` — `assemble-article.py` must assign `state.vertical_rules` from `load_vertical_rules_block()`. | build-card.py, `_build_atf_lede`, `_build_closing`, and any future builder using `render_prompt` with a prose template |

Known gaps:
- **build-hub-box.py**: Inline LLM prompts, no template, no render_prompt. Needs condensed vertical block (backlog L12).
- **generate-neighborhood-guide.py**: Loads vertical rules and injects via f-string, but uses no template/render_prompt pattern. The builder gate does not cover it; regression would not fire the test.
- **L14: canopy BLUF zone unprotected on post-processed content.** `canopy-postprocess.py` renames `rl-bluf` to `cnpHeroLead` (not `cnpBluf`). The linker zone check computes `prefix + suffix` = `"cnp" + "bluf"` = `"cnpbluf"`, which does not substring-match `"cnpherolead"`. The BLUF zone is unprotected on post-processed canopy content. Pre-existing postprocessor naming issue, not a config value problem. Do not fix here.

## Community-Guide Gates (spec_assertions.py 18.CG.*)

| Date | Incident | Assertion | Spec Ref |
|------|----------|-----------|----------|
| 2026-08-03 | Builder comparison table missing required columns | `assert_cg_builder_comparison` | 18.CG.1 |
| 2026-08-03 | Cost section missing MUD/PID address | `assert_cg_cost_strip` | 18.CG.2 |
| 2026-08-03 | Prices in HTML not in manifest volatile_data | `assert_cg_zero_unsourced_prices` | 18.CG.3 |
| 2026-08-03 | School section with placeholder text | `assert_cg_schools_section` | 18.CG.4 |
| 2026-08-03 | Restaurant/venue lexicon in residential guide | `assert_cg_no_venue_lexicon` | 18.CG.5 |
| 2026-08-03 | Wrong geography for named community | `assert_cg_no_wrong_geography` | 18.CG.6 |

## Config Migration Gates (tests/test_config_migration.py)

Structural tests ensuring the .conf → config.json migration does not silently
drop configuration. Two layers:

| Date | Incident | Assertion | Paths Protected |
|------|----------|-----------|-----------------|
| 2026-08-18 | GFP brand guardrails (PRICE_POLICY, FORBIDDEN_TERMS, etc.) exist only in .conf — invisible to every gate (which reads config.json). A generated article could name competitors and pass all gates. Canopy config.json has `article_min_words: "TODO-verify"` (string), crashing orchestrator.py on `int >= str`. TLN SSH_KEY_PATH and WP_PATH disagree between files. | `TestNoConfReadsForMigratedSites` — monkeypatches `builtins.open` to block any `.conf` read for migrated sites. Catches all 4 existing parsers + any future parser structurally. `TestFlattenParity` — for each migrated site, parses `.conf` directly and compares every non-empty key against `_flatten_json_config()` output. Missing or mismatched keys fail naming the key. | site_config.py, ssh_session.py, render-prompt.py, build-css-bundle.py, verify-css-rendered.py, gate_library._load_site_conf() |
| 2026-08-18 | Canopy config.json: 5 fields with `"TODO-verify"` string where int or list required. `article_min_words` (string) crashes `run_gates` on `int >= str` (TypeError). `zone_suffixes` (string) iterates characters, producing `"cnpT","cnpO",...` as blocked classes — silently protects nothing. `skip_slugs` (string) same pattern — silently skips nothing. `do_not_touch_pages` (string) crashes `refresher.py` on `char["post_id"]` (TypeError). `SITE_PREFIX` mapped from `site_id` ("canopy") instead of CSS prefix ("cnp") — AHN passed parity by coincidence. 6 `.conf` keys (SITE_DOMAIN, AI_API_KEY_ENV_VAR, AI_MAX_RETRIES, AI_REQUEST_TIMEOUT, ANCHOR_POOL_SIZE_MIN, ANCHOR_POOL_SIZE_MAX) had no `_flatten_json_config` source. | `TestMigratedConfigTypes`: `test_zone_suffixes_is_list_in_json`, `test_skip_slugs_is_list_in_json`, `test_do_not_touch_pages_is_list_in_json`, `test_article_max_words_is_int_in_json`, `test_prefix_is_explicit_field` — standing, site-agnostic, runs for EVERY migrated site. `TestFlattenParity` catches the 6 missing keys. | all config readers for all migrated sites |
