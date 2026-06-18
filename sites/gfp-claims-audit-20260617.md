# GFP Content Claims Audit — 2026-06-17

## Summary

| Metric | Count |
|--------|-------|
| Total published posts | 283 |
| Posts with unverifiable claims | 254 (90%) |
| HIGH risk (specific prices/hours/deals/times) | 250 |
| MEDIUM risk (delivery/catering/veteran claims) | 4 |
| Delivery page (1292) | Already trashed |

## Claim Categories (posts affected)

| Category | Posts | Risk | Examples |
|----------|-------|------|----------|
| price_specific | 241 | HIGH | $34.50, $35.99, $7.79, $24.75, $37.75 |
| deal_specific | 145 | HIGH | "$8 off weekday deal", "$75 Pizza Pack" |
| hours_specific | 101 | HIGH | "11am-9pm", "11am-10pm" |
| veteran_owned | 74 | MEDIUM | "Veteran-owned" |
| catering_claim | 32 | MEDIUM | "2+ hours notice", "catering minimum" |
| delivery_fee | 18 | HIGH | "modest delivery fee" |
| minimum_order | 18 | MEDIUM | "minimum order" |
| delivery_time | 11 | HIGH | "15-25 minutes", "30-45 minutes" |
| radius_claim | 11 | HIGH | "delivery radius", "X-mile" |
| year_claim | 4 | MEDIUM | "reopened in 2025" |

## Root Cause

The GFP AI generator (gfp-ai-generator plugin) and bulk CSV queue created
content with NO source-of-truth for business facts. The LLM invented
plausible-sounding specifics: exact prices ($34.50 for a large specialty),
specific deal structures ($8 off Monday/Wednesday), delivery time ranges,
and zone details. None of these are verified against actual business data.

## Immediate Risks

1. **Wrong prices:** 241 posts assert specific dollar amounts. If any are
   wrong, customers order expecting one price and get another.
2. **Wrong delivery zones:** 106 posts assert specific neighborhood delivery.
   If GFP doesn't actually deliver to a claimed area, that's a broken promise.
3. **Wrong hours:** 101 posts assert specific operating hours. Stale hours
   drive customers to show up when the store is closed.
4. **Fake deals:** 145 posts assert specific promotions. Customers showing up
   for a "$8 off Monday" deal that doesn't exist is a complaint generator.

## Remediation Plan

### Immediate (no team input needed)
- [x] Business-facts file created (`gfp-business-facts.md`)
- [x] Facts guard wired into RSS pipeline (`assemble-article.py`)
- [x] Facts guard wired into GFP AI generator plugin (agent_memory)
- [x] Delivery page (1292) already trashed

### Requires team input
- [ ] Team ratifies `gfp-business-facts.md` — confirms or corrects all VERIFY fields
- [ ] After ratification: batch price-scrub on 241 posts (replace specific prices
      with "check current menu" or confirmed prices)
- [ ] After ratification: batch hours-scrub on 101 posts
- [ ] Team confirms "veteran-owned" claim (74 posts)
- [ ] Team confirms delivery zone list

### Batch scrub approach (after team ratification)
For each published post:
1. Strip all specific dollar amounts not in the confirmed facts file
2. Replace with conditional language ("check our menu for current pricing")
3. Strip specific hours, replace with "check our hours page"
4. Keep confirmed facts (address, phone, order URL)
5. Verify sample of 5, then batch the rest

This is a SQL REPLACE batch similar to the LRG linker cleanup — not a
content regeneration. The articles themselves are fine; only the invented
business details need scrubbing.
