# Redirect Strategy Decision Rules

When analyzing URLs from GSC or site audits, apply these rules to decide
whether a URL should be redirected, deleted, or left alone.

## Decision Matrix

### REDIRECT (301) when:

1. **Date-path URLs** — Squarespace-style `/blog/2024/10/19/slug`
   - Target: clean slug under current path prefix
   - Example: `/lrg-blog/2024/10/19/best-neighborhoods/` → `/lrg-blog/best-neighborhoods/`
   - Priority: high (GSC has indexed the date-path version)

2. **Hash suffix URLs** — Squarespace artifact `/slug-abc123xyz789`
   - Target: slug without the hash
   - Example: `/lrg-blog/staging-tips-ihij7o8e6zqmhsqp` → `/lrg-blog/staging-tips/`
   - Priority: medium

3. **Combined date-path + hash** — Both issues present
   - Strip date path AND hash suffix
   - Priority: high

4. **Domain migration** — Old domain → new domain
   - All paths from old domain redirect to matching path on new domain
   - Requires server-level or DNS-level redirect
   - Priority: critical

5. **Slug changes** — Deliberate slug rename for SEO
   - Only when the old slug has GSC impressions/clicks
   - Example: `/va-loan-funding-fee-2025/` → `/va-funding-fee/`
   - Priority: depends on traffic

### LEAVE ALONE when:

1. **No GSC data** — URL has 0 impressions AND 0 clicks
   - No redirect equity to preserve
   - Exception: if the URL is linked from external sites (check backlinks)

2. **Already 404** — Source URL returns 404 and has no traffic
   - Nothing to redirect from if it's already gone

3. **Canonical already correct** — Page exists at the right URL
   - No action needed

4. **Internal-only URLs** — Admin pages, previews, staging-only paths
   - Not indexed, no redirect needed

### DELETE (let 404) when:

1. **Duplicate content** — Exact duplicate of another page
   - Only if the duplicate has zero external links
   - If it has backlinks, redirect instead

2. **Obsolete content** — Seasonal/event content that's no longer relevant
   - Only if impressions are near zero
   - Consider: would a redirect to a newer version preserve equity?

3. **Test/staging artifacts** — Pages that were never meant to be indexed

## Priority Scoring

When generating a redirect map, prioritize by:

```
Priority Score = (clicks_90d × 10) + (impressions_90d × 0.01) + position_bonus

position_bonus:
  position < 5:   50  (page 1 top)
  position < 10:  30  (page 1)
  position < 20:  10  (page 2)
  position >= 20:  0
```

Process highest-priority redirects first. Low-priority redirects can be
batched and deployed later.

## Validation Rules

Before deploying ANY redirect:

1. Target URL returns HTTP 200
2. Target content matches the topic of the source (no misleading redirects)
3. No redirect chains (target doesn't redirect again)
4. No redirect loops
5. Source and target are not the same URL

## Deployment Order

1. Generate redirect map from GSC data
2. Validate all targets return 200
3. Deploy to staging
4. Verify on staging with verify-redirects-live.py
5. Wait 24 hours, check for issues
6. Deploy to production
7. Verify on production
8. Monitor GSC for crawl errors over next 7 days
