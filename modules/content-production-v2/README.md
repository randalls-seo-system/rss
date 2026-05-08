# content-production-v2

**Version:** v2 (coexists with v1 `modules/content-production/`, which is frozen)

Article production pipeline rebuilt from scratch around the Article Spec.
The spec is data, each tool does one thing, the pipeline is composable,
and validation is spec-driven.

**Source of truth:** [`docs/article-spec.md`](../../docs/article-spec.md)
**Architecture map:** [`docs/v2-module-architecture.md`](../../docs/v2-module-architecture.md)

## Directory structure

```
content-production-v2/
├── README.md                          # This file
├── overlays/                          # Intent-specific structural templates (Spec Section 6.6)
│   ├── definition.yaml                #   "what is" / "explained" articles — bullets-dominant, no BLUF
│   ├── process.yaml                   #   "how to" / "step by step" articles — bullets-dominant, conditional BLUF
│   ├── decision.yaml                  #   "X vs Y" / "should I" articles — tables-dominant, BLUF included
│   ├── cost.yaml                      #   "how much" / "fee" / "rate" articles — tables-dominant, BLUF included
│   └── comparison.yaml                #   "best X" / "top X" / "ranked" articles — tables-dominant, no BLUF
├── prompts/                           # Slot-filler prompts (NOT monolithic intent prompts)
│   ├── atf-lede.md                    #   50-60 word answer-first opening paragraph
│   ├── atf-card.md                    #   Single quick-card (called 4x per article)
│   ├── atf-faq.md                     #   Single ATF FAQ Q&A pair (called 3x)
│   ├── bluf.md                        #   Optional BLUF section
│   ├── h2-section.md                  #   Single body H2 section (called 6-15x)
│   ├── closing-bottom-line.md         #   Closing recap section
│   └── btf-faq.md                     #   BTF FAQ section (5-12 items)
├── lib/                               # Shared Python utilities
│   ├── __init__.py                    #   Package init
│   ├── spec_assertions.py             #   Spec Section 18 as importable validation functions
│   ├── overlay_loader.py              #   Load + validate overlay YAMLs into typed dataclasses
│   ├── llm_client.py                  #   Unified Claude CLI / OpenAI dispatch with caching
│   ├── serp_adapter.py                #   Typed accessors over serp-research JSON output
│   └── anchor_pool.py                 #   Read linking-v2 anchor pool, apply competition rule
├── tools/                             # Standalone CLI tools (each does one thing)
│   ├── extract-subtopic-gaps.py       #   SERP → subtopic frequency map (high/medium/low coverage)
│   ├── compute-target-wc.py           #   SERP → body word count target (avg +/-15%)
│   ├── build-card.py                  #   Build single ATF quick-card (debugging unit)
│   ├── build-h2-section.py            #   Build single body H2 section (debugging unit)
│   ├── build-bluf.py                  #   Build BLUF section
│   ├── build-faqs.py                  #   Build ATF + BTF FAQ sections
│   ├── build-resources.py             #   Build Resources Used (hard-fails without SERP per Spec 15.6)
│   ├── inject-internal-links.py       #   Inject links from anchor pool into assembled HTML
│   ├── assemble-article.py            #   Orchestrator — full 22-step pipeline
│   ├── validate-article-v2.py         #   Spec-driven validator (replaces v1 validate-structure.py)
│   └── compare-to-baseline.py         #   Diff v2 output vs v1 baseline (manual review tool)
└── examples/                          # Populated as v2 articles are generated and approved
```

## Cross-module dependencies (read-only)

- `serp-research/tools/analyze-serp.py` — SERP data fetch
- `brand-voice/archetypes/{archetype}.md` — voice rules + callout typology
- `brand-voice/lib/voice_validator.py` — voice validation
- `rl-components/templates/{intent}.html` — reference templates
- `linking-v2/data/anchor-pool.csv` — link candidates
- `wp-deploy/tools/push-post-content.py` — WordPress deployment

v2 does NOT modify v1 `content-production/` or any other existing module.

## Current build status

| Component | Status | Notes |
|---|---|---|
| **overlays/** | stub | 5 intent YAMLs need schema implementation |
| **prompts/atf-lede.md** | stub | |
| **prompts/atf-card.md** | stub | |
| **prompts/atf-faq.md** | stub | |
| **prompts/bluf.md** | stub | |
| **prompts/h2-section.md** | stub | |
| **prompts/closing-bottom-line.md** | stub | |
| **prompts/btf-faq.md** | stub | |
| **lib/spec_assertions.py** | stub | |
| **lib/overlay_loader.py** | stub | |
| **lib/llm_client.py** | stub | |
| **lib/serp_adapter.py** | stub | |
| **lib/anchor_pool.py** | stub | |
| **tools/extract-subtopic-gaps.py** | stub | |
| **tools/compute-target-wc.py** | stub | |
| **tools/build-card.py** | stub | |
| **tools/build-h2-section.py** | stub | |
| **tools/build-bluf.py** | stub | |
| **tools/build-faqs.py** | stub | |
| **tools/build-resources.py** | stub | |
| **tools/inject-internal-links.py** | stub | |
| **tools/assemble-article.py** | stub | |
| **tools/validate-article-v2.py** | stub | |
| **tools/compare-to-baseline.py** | stub | |

## Migration path

When v2 has produced 5 LRG articles approved by Randall:
1. Move v1 to `modules/_archived/content-production-v1/`
2. Rename `content-production-v2/` to `content-production/`
3. Update top-level callers referencing v1's interface
4. Delete `_archived/` after 30 days if no rollback needed
