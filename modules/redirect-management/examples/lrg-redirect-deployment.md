# LRG Redirect Deployment — Annotated Example

This documents the first use of the redirect-management module on the
LRG (Levi Rodgers Real Estate Group) site.

## Context

LRG migrated from Squarespace to WordPress (WP Engine). Squarespace URLs
used date-path patterns and hash suffixes that need to be cleaned up:

- **Date-path:** `/lrg-blog/2024/10/19/buying-vs-renting/` → `/lrg-blog/buying-vs-renting/`
- **Hash suffix:** `/lrg-blog/staging-tips-ihij7o8e6zqmhsqp` → `/lrg-blog/staging-tips/`
- **Combined:** `/lrg-blog/2024/3/20/questions-to-ask-p2lke8d14gr4eowe` → `/lrg-blog/questions-to-ask/`

## Step 1: Generate Redirect Map

Source: GSC URL export for lrgrealty.com (90-day window)

```bash
python3 modules/redirect-management/tools/generate-redirect-map.py \
    --site lrg \
    --gsc-csv ~/Downloads/lrg-gsc-urls.csv \
    --output ~/lrg-rewrite/redirects/lrg-redirect-map.csv
```

Result: 42 redirects identified
- 31 date-path only
- 9 date-path + hash suffix
- 2 hash suffix only

Traffic distribution:
- 1 redirect with 76 clicks (Dominion neighborhood comparison — highest priority)
- 5 redirects with 1-13 clicks
- 36 redirects with 0 clicks (impressions only)

## Step 2: Validate Targets

```bash
python3 modules/redirect-management/tools/validate-redirect-targets.py \
    --site lrg \
    --input ~/lrg-rewrite/redirects/lrg-redirect-map.csv \
    --output ~/lrg-rewrite/redirects/lrg-redirect-map-VALIDATED.csv
```

Result (2026-05-06):
- 200: 1 target
- 404: 41 targets

**Root cause:** WordPress permalinks not yet migrated to `/lrg-blog/%postname%/`.
The blog content exists under category-based WP URLs (e.g., `/homeowner/slug/`)
but not under the production `/lrg-blog/slug/` structure.

**Action:** HOLD deployment until permalink migration completes.

## Step 3: Deploy (PENDING)

Blocked on:
1. Terminal 1 completing WP permalink migration to `/lrg-blog/%postname%/`
2. Re-validation showing all 42 targets return HTTP 200

Deployment method will be Redirection plugin import:

```bash
./modules/redirect-management/tools/deploy-redirects.sh \
    sites/lrg.conf \
    ~/lrg-rewrite/redirects/lrg-redirect-map.csv \
    --method plugin \
    --group "LRG Squarespace cleanup"
```

## Step 4: Verify (PENDING)

After deployment:

```bash
python3 modules/redirect-management/tools/verify-redirects-live.py \
    --site lrg \
    --input ~/lrg-rewrite/redirects/lrg-redirect-map.csv \
    --output ~/lrg-rewrite/redirects/lrg-redirect-verification.csv
```

Expected: 42/42 PASS (301 to correct target, target returns 200)

## Lessons Learned

1. **Validate targets BEFORE generating the import CSV.** On LRG, the target
   URL structure didn't exist yet because permalink migration was incomplete.
   Deploying redirects to 404 targets would have been worse than no redirect.

2. **Squarespace hash suffixes are not always random.** Some contain meaningful
   slug fragments. The generate-redirect-map.py strips the hash but preserves
   the meaningful part of the slug.

3. **GSC data lag matters.** URLs may show impressions in GSC for pages that
   no longer exist. This is normal — GSC data can lag 2-3 days. Don't assume
   the URL is live just because GSC shows recent impressions.
