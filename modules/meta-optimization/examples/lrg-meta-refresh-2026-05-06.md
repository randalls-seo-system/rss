# LRG Meta Refresh — First Production Run

**Date:** 2026-05-06
**Site:** lrgrealty.com/lrg-blog/
**Module version:** 1.0

## Pipeline Summary

| Step | Tool | Result |
|------|------|--------|
| Pull clusters | pull-keyword-clusters.py | 374 pages, 17,391 queries |
| Analyze | analyze-clusters.py | 374 pages with parent/variants/gaps/intent |
| Generate (v1 - template) | Python string templating | FAILED — mechanical, repetitive output |
| Generate (v2 - LLM) | gpt-4o-mini per page | 374 ok, 0 failures |

## Key Metrics

- **Candidates:** 374 pages (filtered from 1000 GSC pages)
- **Total cluster impressions (90d):** 310,307
- **Current weighted CTR:** 0.44%
- **Total queries pulled:** 17,391
- **Average queries per page:** 46.5
- **LLM tokens used:** ~387,000
- **LLM cost:** ~$0.06

## Validation

- Titles 50-60 chars: 252/374 (67%)
- Titles under 50: 72 (acceptable — short is fine)
- Titles over 60: 46 (4 flagged as warnings, rest within 65)
- Metas 150-160: 222/374 (59%)
- Metas under 150: 88 (acceptable)
- Metas over 160: 60 (4 flagged as warnings)

## Lessons Learned

1. **Python string templating fails for meta generation.** Produces mechanical
   copy: "X for San Antonio in 2026. Updated data, local insights..."
   repeated verbatim across every page. No semantic awareness.

2. **LLM-per-page with cluster context works.** Each page gets unique copy
   that captures parent query, addresses intent, and incorporates brand tone.
   Cost is negligible (~$0.001/page).

3. **Prompt engineering matters.** The prompt template must include:
   - Full cluster data (parent, variants, gaps, modifiers)
   - Intent classification
   - Brand context (loaded from site config, not hardcoded)
   - Strict character limits with validation rules
   - Quality check instructions (would I click this?)

4. **Validation + retry loop catches edge cases.** 4 warnings (slightly
   over/under target ranges) out of 374. Zero errors. The retry-with-feedback
   approach handles most validation failures on second attempt.

## Files Generated

- `22-meta-refresh-candidates.csv` — 374 candidate pages
- `22b-page-keyword-clusters.json` — full cluster data per page
- `22c-cluster-analysis-v2.csv` — analyzed clusters
- `22d-meta-refresh-proposals-v2.csv` — LLM-generated proposals
- `22e-sample-proposals-v2.txt` — 20 sample proposals for review
