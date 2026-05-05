# Linking v2: AI-Powered Anchor Pools

**Status:** Phase 1 complete (anchor pool generator built and tested)

## What This Does

Generates 15-25 high-quality anchor text variations per destination URL using AI. Replaces single-word anchor text (e.g., "duplex") with diverse, natural phrases (e.g., "buying a duplex with a VA loan", "VA loan duplex eligibility rules").

## Quick Start

```bash
# 1. Pull destination metadata from a site
./modules/linking-v2/tools/pull-destinations.sh sites/valn.conf

# 2. Generate anchor pools (full run or limited)
./modules/linking-v2/tools/generate-anchor-pool.sh sites/valn.conf --limit 20
./modules/linking-v2/tools/generate-anchor-pool.sh sites/valn.conf --ids "602,648,70"

# 3. Generate review CSV and summary
./modules/linking-v2/tools/review-pools.sh sites/valn.conf
```

## Configuration

In your site config (`sites/<site>.conf`):

```bash
AI_PROVIDER="openai"                    # openai or anthropic
AI_MODEL="gpt-4o-mini"                  # model name
AI_API_KEY_ENV_VAR="OPENAI_API_KEY"     # env var holding API key
AI_MAX_RETRIES="3"
AI_REQUEST_TIMEOUT="30"

LINKING_V2_ENABLED=true
ANCHOR_POOL_SIZE_MIN="15"
ANCHOR_POOL_SIZE_MAX="25"
ANCHOR_POOL_PATH="sites/valn-anchor-pools.json"
```

## Cost

GPT-4o-mini at current pricing ($0.15/1M input, $0.60/1M output):
- 20 destinations: ~$0.004
- 783 destinations (full VALN): ~$0.16 projected

## Output Format

`sites/<site>-anchor-pools.json` — JSON with per-destination anchor arrays, usage stats, and generation metadata.

`sites/<site>-anchor-pools-review-<date>.csv` — One row per destination, anchors in columns for spreadsheet review.

## Phase Roadmap

See `docs/architecture.md` for full roadmap.
