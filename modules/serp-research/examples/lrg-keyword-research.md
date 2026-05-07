# LRG Keyword Research — Canonical Example

First production use of serp-research module on LRG keywords.

## Test Keywords (3 intent types)

### 1. Decision: "best neighborhoods in austin"

```bash
python3 modules/serp-research/tools/analyze-serp.py \
    --keyword "best neighborhoods in austin" --site lrg --provider serpapi
```

**Results:**
- Provider: serpapi
- Top results: 9 organic
- PAA: 4 questions (e.g., "What is the nicest neighborhood in Austin?")
- AI Overview: YES — paragraph about Zilker, East Austin, Hyde Park, Mueller
- AI Overview references: 14 sources
- Featured snippet: no
- Knowledge panel: no
- Local pack: no

### 2. Comparison: "cost of living san antonio vs austin"

```bash
python3 modules/serp-research/tools/analyze-serp.py \
    --keyword "cost of living san antonio vs austin" --site lrg --provider serpapi
```

**Results:**
- Provider: serpapi
- Top results: 8 organic
- PAA: 4 questions
- AI Overview: NO (comparison queries often lack AI Overview)
- Featured snippet: no

### 3. Definition: "what is the good neighbor next door program"

```bash
python3 modules/serp-research/tools/analyze-serp.py \
    --keyword "what is the good neighbor next door program" --site lrg --provider serpapi
```

**Results:**
- Provider: serpapi
- Top results: 9 organic
- PAA: 4 questions
- AI Overview: YES — describes HUD program for teachers, law enforcement, firefighters
- Featured snippet: no

## Cost

3 SerpAPI calls used. SerpDev not available (key not configured).

## Cache Behavior

All 3 results cached to `~/lrg-rewrite/serp/cache/` with 7-day TTL.
Subsequent runs with same keywords hit cache (0 API calls).
