# content-production-v2 — Architecture Map

**Status:** Spec for the v2 rebuild. Maps Article Spec v0 sections to file structure.
**Coexists with:** v1 `modules/content-production/` (frozen, kept as baseline).
**Reads:** `docs/article-spec.md` as the source of truth for behavior rules.

---

## Design principles

1. **The spec is data, not code.** Overlays, callout typology, anchor rules — all in YAML or referenced from YAML. Code reads these. Code does not contain spec rules inline.

2. **Each tool does one thing.** v1's `generate-article.py` is 445 lines that pulls SERP, renders prompts, calls LLM, validates voice, expands content, computes word counts, builds resources, assembles HTML, writes manifest. v2 splits these into named tools that can be called independently or composed.

3. **Pipeline is composable.** The orchestrator is thin. Each step can be run alone (debug a single card, regenerate one H2 section, re-run the validator without regenerating).

4. **No cross-module reach-arounds.** v1 inlined SerpAPI. v2 calls `serp-research/analyze-serp.py`. v1 inlined link generation. v2 calls `linking-v2/`. Module boundaries are real.

5. **Validation is spec-driven.** Validator imports the spec assertions from a single file. No more "validator says 4 cards, prompt says 2."

---

## Directory structure

```
modules/content-production-v2/
├── README.md
├── overlays/                          # Section 6.6 of spec
│   ├── definition.yaml
│   ├── process.yaml
│   ├── decision.yaml
│   ├── cost.yaml
│   └── comparison.yaml
├── prompts/                           # Slot-fillers, NOT monolithic
│   ├── atf-lede.md
│   ├── atf-card.md
│   ├── atf-faq.md
│   ├── bluf.md
│   ├── h2-section.md
│   ├── closing-bottom-line.md
│   └── btf-faq.md
├── lib/
│   ├── __init__.py
│   ├── spec_assertions.py             # Section 18 as importable functions
│   ├── overlay_loader.py              # Load + validate overlay YAMLs
│   ├── llm_client.py                  # Unified Claude CLI / OpenAI dispatch
│   ├── serp_adapter.py                # Reads serp-research output, exposes typed accessors
│   └── anchor_pool.py                 # Reads linking-v2 anchor pool, applies competition rule
├── tools/
│   ├── extract-subtopic-gaps.py       # SERP → gap analysis
│   ├── compute-target-wc.py           # SERP → word count target
│   ├── build-card.py                  # Single card builder (debugging unit)
│   ├── build-h2-section.py            # Single H2 section builder (debugging unit)
│   ├── build-bluf.py                  # BLUF builder (debugging unit)
│   ├── build-faqs.py                  # ATF + BTF FAQ builder
│   ├── build-resources.py             # Resources Used builder (hard-fails per spec 15.6)
│   ├── inject-internal-links.py       # Link injection from anchor pool
│   ├── assemble-article.py            # Orchestrator — replaces v1's produce + generate
│   ├── validate-article-v2.py         # Spec-driven validator
│   └── compare-to-baseline.py         # Diff v2 output against v1 baseline (optional)
└── examples/
    └── (populated as v2 articles are generated and approved)
```

---

## File-by-file specifications

### overlays/{intent}.yaml

**Purpose:** The structural template for an article of this intent type. Defines card slots, default callout types per section, default structural element preferences (table vs bullets), default BLUF inclusion, and default ATF FAQ patterns when SERP PAA is empty.

**Schema (same across all 5 overlays):**
```yaml
intent: cost                          # Matches filename
display_name: "Cost Article"
spec_reference: "docs/article-spec.md Section 1, Section 6.6"

# When to include BLUF (Section 8.1)
bluf_default: include                  # include | omit | conditional

# Body structural element preference (Section 9.4)
body_default: tables_dominant          # tables_dominant | bullets_dominant | mixed

# Card slot definitions (Section 6.6)
card_slots:
  - role: rates_by_category_card
    h3_pattern: "{Topic} Rates by Category"
    bullet_label_hints: ["Category A:", "Category B:", "Category C:", "Bottom line:"]
  - role: rates_by_scenario_card
    h3_pattern: "{Topic} by Scenario"
    bullet_label_hints: ["Scenario 1:", "Scenario 2:", "Scenario 3:", "Break-even:"]
  - role: exemptions_card
    h3_pattern: "Exemptions and Reductions"
    bullet_label_hints: ["Common exemptions:", "Edge cases:", "Documentation:", "Timing matters:"]
  - role: examples_card
    h3_pattern: "Real-World {Topic} Examples"
    bullet_label_hints: ["Example 1:", "Example 2:", "Example 3:", "Worth noting:"]

# Callout type preferences per section role (Section 10.5)
callout_preferences:
  high_stakes_section: ["Deal Math", "Lender Reality Check"]
  procedural_section: ["File Guidance", "Deal Saver"]
  qualification_section: ["Approval Watchpoint"]
  scenario_section: ["Scenario"]

# Default ATF FAQ patterns when SERP PAA is empty (Section 7.2 fallback)
default_atf_faq_patterns:
  - "What is the {topic} in {year}?"
  - "How does {topic} work?"
  - "What are the {topic} exemptions?"

# Default H2 question/statement mix when SERP PAA is sparse (Section 9.2.2)
question_h2_floor_when_paa_sparse: 0   # 0 means any mix acceptable
question_h2_floor_when_paa_rich: 30    # 30% floor when ≥4 PAA available
```

**Per-intent variations:**
- `cost.yaml`: bluf_default = include, body_default = tables_dominant
- `decision.yaml`: bluf_default = include, body_default = tables_dominant
- `process.yaml`: bluf_default = conditional, body_default = bullets_dominant
- `definition.yaml`: bluf_default = omit, body_default = bullets_dominant
- `comparison.yaml`: bluf_default = omit, body_default = tables_dominant

**Callout preferences are populated per the archetype**, not per intent. The overlay specifies preferences in archetype-neutral terms ("high_stakes_section" → "use a high-impact callout"); the archetype YAML maps that to actual callout type names ("Deal Math" for VA lending, "Buyer Tip" for real estate).

---

### prompts/atf-lede.md

**Purpose:** Generate the 50-60 word ATF lede paragraph. Slot-filler.

**Inputs (rendered into prompt):**
- `{TARGET_KEYWORD}`
- `{TOPIC_NOUN}` (the H1 subject in noun form)
- `{SERP_TOP_RESULT_LEDES}` (1-2 sentence summaries of top 3 SERP results' opening paragraphs)
- `{AI_OVERVIEW_TEXT}` (if present)
- `{INJECT_BRAND_VOICE}` (from archetype)

**Output:** Raw HTML — `<p>...</p>` (single paragraph) or two `<p>` elements (for complex topics).

**Constraints (in prompt):**
- 40-110 words total.
- First sentence states the conclusion directly. No question.
- Sentence 2 introduces concrete numbers.
- Sentence 3 introduces the wrinkle/exception.
- No links.
- No banned phrases (see brand-voice rules).

---

### prompts/atf-card.md

**Purpose:** Generate ONE quick-card. Called 4 times per article (once per card slot).

**Inputs:**
- `{CARD_ROLE}` (from overlay's card_slots[N].role)
- `{H3_PATTERN}` (from overlay)
- `{BULLET_LABEL_HINTS}` (from overlay, comma-separated)
- `{TARGET_KEYWORD}`
- `{TOPIC_CONTEXT}` (relevant subset of SERP top results for THIS card's subtopic)
- `{INJECT_BRAND_VOICE}`

**Output:** `<article class="rl-quick-card"><h3>...</h3><ul><li>...</li>×4</ul></article>`

**Constraints:**
- H3 substitutes overlay variables, may be rewritten if a more natural article-specific label emerges from SERP.
- Exactly 4 bullets.
- Bullets 1-3: 14-30 words each, label-prefixed with `<strong>`.
- Bullet 4 is the synthesis bullet: 18-35 words, often with a concrete number.
- Bullet labels are unique within the card.
- No links inside bullets.

---

### prompts/atf-faq.md

**Purpose:** Generate ONE ATF FAQ Q&A pair. Called 3 times.

**Inputs:**
- `{QUESTION}` (a PAA question, or fallback pattern from overlay)
- `{TARGET_KEYWORD}`
- `{TOPIC_CONTEXT}` (concise context for the answer)
- `{INJECT_BRAND_VOICE}`

**Output:** `<details><summary>Q</summary><p>A</p></details>`

**Constraints:**
- Answer 35-60 words. Strict.
- 1-2 sentences.
- No links.
- Self-contained (doesn't require body context).

---

### prompts/bluf.md

**Purpose:** Generate the optional BLUF section.

**Inputs:**
- `{TARGET_KEYWORD}`
- `{TOPIC_CONTEXT}` (top-level facts about the topic)
- `{FRICTION_POINT}` (the central "watch out" — derived from SERP gap analysis or explicitly passed)
- `{ANCHOR_POOL_CANDIDATES}` (1-3 internal links eligible for inline use)
- `{INJECT_BRAND_VOICE}`

**Output:** Full BLUF section HTML per spec Section 8.2.

**Constraints:**
- Lead paragraph: 50-70 words, fully bolded.
- Body paragraph: 70-100 words.
- Exactly 5 capstone bullets, 12-20 words each.
- Lead and body can have inline links from `{ANCHOR_POOL_CANDIDATES}`.
- Capstone bullets have no links.

---

### prompts/h2-section.md

**Purpose:** Generate ONE body H2 section. Called 6-15 times per article.

**Inputs:**
- `{H2_TITLE}` (from gap-analysis or overlay)
- `{SECTION_ROLE}` (e.g., "exemptions section", "cost comparison section")
- `{STRUCTURAL_ELEMENT_PREFERENCE}` (table | bullets | callout, from overlay default + per-section override)
- `{CALLOUT_TYPE}` (if structural element is callout, the specific type)
- `{TARGET_WORD_COUNT}` (per-section, derived from total body target / section count)
- `{TOPIC_CONTEXT}` (SERP-derived context for this specific subtopic)
- `{ANCHOR_POOL_CANDIDATES}` (3-7 internal links eligible for this section)
- `{INJECT_BRAND_VOICE}`

**Output:** `<section><h2>...</h2>{intro p}{optional body p}{structural element}{optional closing p}</section>`

**Constraints:**
- Intro paragraph 50-70 words, answer-first, contains 1-3 inline links from candidates.
- Optional body paragraph 60-100 words.
- ONE structural element per spec rule 9.3.
- Optional closing paragraph 40-80 words.
- Section total 200-450 words.
- No "In this section we'll cover..." opener.

---

### prompts/closing-bottom-line.md

**Purpose:** Generate the closing "The Bottom Line" recap.

**Inputs:**
- `{TARGET_KEYWORD}`
- `{ARTICLE_SUMMARY}` (compact summary of body H2s — built from H2 titles + intro paragraphs)
- `{INJECT_BRAND_VOICE}`

**Output:** `<h2>The Bottom Line</h2><p>...</p>` (1-3 paragraphs)

**Constraints:**
- 100-150 words. Hard.
- No bullets.
- No external links.
- No new information.
- Distinguishable from BLUF in tone (BLUF is "here's what's coming"; closing is "here's the recap").

---

### prompts/btf-faq.md

**Purpose:** Generate the BTF FAQ section.

**Inputs:**
- `{QUESTIONS_LIST}` (5-12 questions: PAA after first 3 + gap-fill + expert-added)
- `{TARGET_KEYWORD}`
- `{TOPIC_CONTEXT}`
- `{INJECT_BRAND_VOICE}`

**Output:** `<section class="rl-faq"><h2>Frequently Asked Questions</h2>{<details>×N}</section>`

**Constraints:**
- 5-12 items.
- Each answer 50-110 words. Deeper than ATF answers.
- No inline links.
- No question text overlap with the 3 ATF FAQs (passed in as exclusion list).

---

### lib/spec_assertions.py

**Purpose:** Section 18 of the spec, as importable Python functions. Single source of truth for what passes validation.

**Public API:**
```python
from .spec_assertions import (
    assert_h1_present,
    assert_eyebrow_format,
    assert_byline_present,
    assert_primary_sources_present,
    assert_jump_nav_structure,
    assert_atf_lede_word_count,
    assert_first_cta_present,
    assert_atf_card_count_and_structure,
    assert_atf_faq_count_and_structure,
    assert_bluf_structure_if_present,
    assert_body_h2_count,
    assert_each_h2_has_structural_element,
    assert_mid_article_cta_present,
    assert_closing_bottom_line_format,
    assert_btf_faq_count_and_no_overlap,
    assert_resources_format_and_diversity,
    assert_external_anchor_format,
    assert_external_anchor_no_competition,
    assert_internal_anchor_word_count,
    assert_body_word_count_in_serp_range,
    assert_no_em_dashes,
    assert_no_banned_phrases,
    assert_no_resources_placeholder,
    assert_no_card_label_as_h3,
    # ... etc.
)

# Each function takes (soup, context) where:
# - soup is a BeautifulSoup of the assembled article
# - context is a dict with site config, SERP data, anchor pool, exclusion lists
# Each returns AssertionResult(passed: bool, detail: str | None)
```

**Used by:**
- `validate-article-v2.py` (runs all assertions)
- `assemble-article.py` (runs key assertions inline during assembly to fail fast)
- Future tests (each assertion is unit-testable in isolation)

---

### lib/overlay_loader.py

**Purpose:** Load + validate the YAML overlays. Catch typos and schema errors before they reach the LLM prompts.

**Public API:**
```python
load_overlay(intent: str) -> OverlayConfig
list_overlays() -> list[str]
```

`OverlayConfig` is a typed dataclass with fields matching the YAML schema. Validation fails loudly if a required field is missing or a card_slot is malformed.

---

### lib/llm_client.py

**Purpose:** Unified dispatch for Claude CLI vs OpenAI. Replaces v1's inline `call_claude_cli` and `call_openai`. Adds retry logic, caching of identical prompts, and structured error handling.

**Public API:**
```python
class LLMClient:
    def __init__(self, provider: str, model: str | None = None)
    def call(self, prompt: str, system_msg: str | None = None,
             max_tokens: int = 4096, cache_key: str | None = None) -> LLMResponse
```

`LLMResponse` includes: `text`, `input_tokens`, `output_tokens`, `cost_estimate`, `cached: bool`.

`cache_key` enables per-section caching during iteration: if you regenerate one card, the other 3 don't re-call the LLM.

---

### lib/serp_adapter.py

**Purpose:** Read `serp-research/analyze-serp.py` output JSON and expose typed accessors. Replaces v1's inline JSON spelunking.

**Public API:**
```python
class SerpData:
    def __init__(self, json_path: Path)

    # Accessors used by assembler
    @property
    def top_results(self) -> list[OrganicResult]
    @property
    def paa_questions(self) -> list[str]
    @property
    def ai_overview_text(self) -> str | None
    @property
    def ai_overview_references(self) -> list[Reference]
    @property
    def related_searches(self) -> list[str]

    # Computed accessors
    def average_word_count_top_5(self) -> int
    def subtopic_gap_analysis(self) -> dict[str, list[int]]  # subtopic -> [result_indices that cover it]
    def primary_sources(self, max: int = 3) -> list[Reference]  # filtered for .gov/edu/auth
```

---

### lib/anchor_pool.py

**Purpose:** Read `linking-v2/` anchor pool. Apply anchor competition rule. Provide candidate links per section.

**Public API:**
```python
class AnchorPool:
    def __init__(self, site_slug: str)

    # Internal link candidates for a topic
    def candidates_for_topic(self, topic: str, max: int = 5) -> list[AnchorCandidate]

    # Anchor competition check (Section 11.3)
    def is_internal_anchor_keyword(self, anchor_text: str) -> bool
    def get_internal_keywords_set(self) -> set[str]
```

`AnchorCandidate` has: `url`, `anchor_text`, `topic_match_score`, `usage_count_sitewide`.

If anchor pool is empty (linking-v2 hasn't been seeded yet), return empty lists. Don't crash. Article will generate without internal links — validator will warn but not fail.

---

### tools/extract-subtopic-gaps.py

**Purpose:** Take SERP data, return subtopic frequency map.

**Usage:**
```
python3 extract-subtopic-gaps.py --serp-json /path/to/serp.json --output /path/to/gaps.json
```

**Output:**
```json
{
  "high_coverage": [
    {"subtopic": "VA Funding Fee Rates", "appears_in": [0, 1, 2, 3, 4]},
    ...
  ],
  "medium_coverage": [
    {"subtopic": "First-time vs Subsequent Use", "appears_in": [0, 2, 4]},
    ...
  ],
  "low_coverage_gaps": [
    {"subtopic": "Funding Fee on Loan Assumptions", "appears_in": [3]},
    ...
  ]
}
```

The "low_coverage_gaps" feeds the article's competitive moat — subtopics 1-2 competitors mentioned that 3+ missed.

---

### tools/compute-target-wc.py

**Purpose:** Compute target body word count from SERP top 5 average.

**Usage:**
```
python3 compute-target-wc.py --serp-json /path/to/serp.json
```

**Output:** Single JSON object `{"target": 2400, "min": 2040, "max": 2760, "source": "serp_avg ±15%"}` or fallback `{"target": 2100, "min": 1800, "max": 2400, "source": "fallback_default"}`.

---

### tools/build-card.py

**Purpose:** Build a single quick-card. Useful for debugging — regenerate one card without redoing the whole article.

**Usage:**
```
python3 build-card.py \
    --site lrg \
    --target-keyword "best san antonio neighborhoods for veterans" \
    --intent decision \
    --card-slot option_a_card \
    --serp-json /path/to/serp.json \
    --output /path/to/card.html
```

Calls `prompts/atf-card.md` with the resolved inputs, returns the card HTML.

---

### tools/build-h2-section.py

**Purpose:** Build a single body H2 section. Same debugging-unit pattern.

**Usage:**
```
python3 build-h2-section.py \
    --site lrg \
    --h2-title "Who Is Exempt From The VA Funding Fee" \
    --section-role exemptions_section \
    --structural-element bullets \
    --target-word-count 280 \
    --serp-json /path/to/serp.json \
    --output /path/to/section.html
```

---

### tools/build-bluf.py, build-faqs.py, build-resources.py

Same single-section-builder pattern. Each callable independently for iteration.

`build-resources.py` enforces the spec 15.6 hard fail: if SERP unavailable AND no manual `--resources-list` provided, exits non-zero with a loud error. No placeholder garbage.

---

### tools/inject-internal-links.py

**Purpose:** Take an article HTML, inject internal links from the anchor pool, apply competition rule.

**Usage:**
```
python3 inject-internal-links.py \
    --site lrg \
    --html-input /path/to/article.html \
    --html-output /path/to/article-with-links.html \
    --pending-links-output /path/to/pending-links.json
```

For each H2 section's intro paragraph: identifies link injection points, fetches candidates from anchor pool, picks 1-3 per section.

For potential links where no anchor pool match exists: writes to `pending-links.json` for future content prioritization (this is your "links pending future creation" requirement).

---

### tools/assemble-article.py

**Purpose:** The orchestrator. Replaces v1's `produce-article.py` + `generate-article.py`.

**Usage:**
```
python3 assemble-article.py \
    --site lrg \
    --post-id 2662 \
    --target-keyword "best san antonio neighborhoods for veterans" \
    --status draft \
    --output-dir ~/lrg-rewrite/articles-v2/
```

**Pipeline:**
1. Load site config, branding, archetype, voice rules
2. Load intent overlay (auto-detect or `--intent` override)
3. Run `serp-research/analyze-serp.py` (or use cached if fresh)
4. Run `extract-subtopic-gaps.py` → gaps.json
5. Run `compute-target-wc.py` → target word count
6. Build H2 inventory: overlay required slots ∪ high-coverage SERP subtopics ∪ gap-fill picks
7. Build header prelude (deterministic from site config)
8. Build jump nav (deterministic from H2 inventory's first 4)
9. Build ATF lede (calls `prompts/atf-lede.md`)
10. Build 4 ATF cards in parallel (4× `build-card.py` calls)
11. Build 3 ATF FAQs from PAA[:3]
12. Conditionally build BLUF (per overlay default + intent)
13. Build N body H2 sections (N× `build-h2-section.py` calls)
14. Build closing Bottom Line
15. Build BTF FAQs from PAA[3:] + gap-fill questions
16. Build Resources Used (or hard-fail if no SERP and no manual list)
17. Auto-generate "In this Article" TOC from H2 inventory
18. Assemble all into final HTML
19. Run `inject-internal-links.py` over assembled HTML
20. Run `validate-article-v2.py` — if fails, log violations, write HTML, exit non-zero
21. Optionally deploy via `wp-deploy/tools/push-post-content.py`
22. Write manifest JSON next to HTML

---

### tools/validate-article-v2.py

**Purpose:** Run all spec assertions against an assembled article. Replaces v1's `validate-structure.py`.

**Usage:**
```
python3 validate-article-v2.py \
    --html-file /path/to/article.html \
    --intent cost \
    --serp-json /path/to/serp.json \
    --site lrg \
    --output-format text|json|markdown
```

Outputs a per-assertion pass/fail report. Uses `lib/spec_assertions.py` exclusively — no inline rules. Exits non-zero if any hard assertion fails. Soft warnings logged but don't affect exit code unless `--strict` flag set.

---

### tools/compare-to-baseline.py

**Purpose:** Side-by-side diff of v2 output vs v1 baseline article. Useful for "is v2 actually better than v1 on this same input."

**Usage:**
```
python3 compare-to-baseline.py \
    --v1-html /path/to/v1-article.html \
    --v2-html /path/to/v2-article.html \
    --output /path/to/comparison.md
```

Outputs a markdown diff showing: word counts, link counts, callout counts, validator pass rates side-by-side. Not run as part of the pipeline — manual tool for our review during the LRG iteration.

---

## Cross-module dependencies

v2 reads from these existing modules (does not modify them):

- **serp-research/tools/analyze-serp.py** — SERP data fetch
- **brand-voice/lib/voice_validator.py** — voice validation (still used)
- **brand-voice/archetypes/{archetype}.md** — voice rules + callout typology
- **rl-components/templates/{intent}.html** — reference templates (informational)
- **linking-v2/data/anchor-pool.csv** (or wherever the pool lives) — link candidates
- **wp-deploy/tools/push-post-content.py** — WordPress deployment

v2 does NOT modify:
- v1 `content-production/` (frozen)
- Any mu-plugin module (technical-seo, schema, redirects, qa-gates, analytics, linking v1)
- Audit module
- CSS deployment

---

## Migration checklist

When v2 has produced 5 LRG articles approved by Randall, this is the cutover:

1. Move v1 to `modules/_archived/content-production-v1/`
2. Rename `content-production-v2/` → `content-production/`
3. Update `tools/new-client.sh` and any other top-level callers if they reference v1's interface
4. Delete `_archived/` after 30 days if no rollback needed
5. Update top-level README's module list

---

## What this architecture deliberately does NOT do

- **Does not solve hub/spoke clustering.** That's a separate module (`hub-and-spoke/`) for a separate phase.
- **Does not handle tool-anchored articles** (calculator embeds, etc.). Deferred to v2.1.
- **Does not validate qualitative quality** (is the writing actually good?). The spec validator catches structural compliance. Qualitative review is still you reading the article.
- **Does not auto-iterate the spec.** When you flag issues in a generated article, you decide whether the fix is to the prompt, the overlay, the spec, or all three. v2 doesn't propose its own spec changes.
