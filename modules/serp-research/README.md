# SERP Research Module

Multi-provider SERP data extraction for keyword research and content planning.

## Provider Strategy

| Provider | Role | AI Overview | Cost | Credits |
|----------|------|-------------|------|---------|
| **SerpDev** | Default | No | Cheap | 5,000 |
| **SerpAPI** | Fallback | Yes | Higher | Per-plan |

The router tries SerpDev first for all features. If a feature isn't
supported (e.g., AI Overview), it falls back to SerpAPI automatically.

## Setup

```bash
export SERPAPI_KEY="your-serpapi-key"
export SERPDEV_API_KEY="your-serpdev-key"  # optional, enables SerpDev as primary
```

## Quick Start

```bash
# Analyze a keyword (auto-selects best provider):
python3 modules/serp-research/tools/analyze-serp.py \
    --keyword "best neighborhoods in austin" --site lrg

# Batch analysis:
python3 modules/serp-research/tools/analyze-serp.py \
    --keywords-csv keywords.csv --site lrg --output-dir serp/

# Extract PAA for FAQ generation:
python3 modules/serp-research/tools/extract-paa.py \
    --serp-json serp/best-neighborhoods.json --output-csv paa.csv

# Compare providers:
python3 modules/serp-research/tools/compare-providers.py \
    --keyword "va loan requirements" --output-md comparison.md
```

## Tools

| Tool | Purpose |
|------|---------|
| analyze-serp.py | Master analyzer — consolidated JSON with all features |
| pull-serp.py | Raw response fetcher (saves unprocessed provider JSON) |
| extract-paa.py | People Also Ask → CSV |
| extract-ai-overview.py | AI Overview → markdown |
| extract-top-results.py | Top 10 organic results → CSV |
| compare-providers.py | Side-by-side provider comparison |

## Output Format (analyze-serp.py)

```json
{
  "keyword": "best neighborhoods in austin",
  "queried_at": "2026-05-06T22:30:00Z",
  "providers_used": ["serpapi"],
  "intent_signals": {
    "has_local_pack": false,
    "has_ai_overview": true,
    "has_paa": true,
    "has_featured_snippet": false,
    "has_knowledge_panel": false
  },
  "top_results": [...],
  "paa": [...],
  "ai_overview": {"text_blocks": [...], "references": [...]},
  "related_searches": [...]
}
```

## Cache

Results are cached to `~/<site>-rewrite/serp/cache/` with 7-day TTL.
Use `--skip-cache` to force fresh API calls.

## Adding a New Provider

1. Create `lib/<provider>_client.py` implementing `SerpProvider`
2. Map the provider's response fields to the abstract methods
3. Add to the provider list in `tools/analyze-serp.py:get_providers()`
4. Run `tests/test_provider_router.py` to verify routing

## File Structure

```
modules/serp-research/
├── README.md
├── lib/
│   ├── provider.py          Abstract base + router
│   ├── serpapi_client.py     SerpAPI implementation
│   ├── serpdev_client.py     SerpDev implementation (stub)
│   ├── cache.py              Disk cache with TTL
│   └── rate_limiter.py       Per-provider rate limiting
├── tools/
│   ├── analyze-serp.py       Master analyzer
│   ├── pull-serp.py          Raw fetcher
│   ├── extract-paa.py        PAA extractor
│   ├── extract-ai-overview.py AI Overview extractor
│   ├── extract-top-results.py Top results extractor
│   └── compare-providers.py  Provider comparison
├── tests/
│   └── test_provider_router.py
└── examples/
    └── lrg-keyword-research.md
```
