# LRG Tier A Migration: Canonical Example (2026-05-06)

## Scope
- 139 posts already in lrgArticleKit format
- Class migration only (no content rewrite)
- Goal: convert lrg* class names to rl-* for the new framework

## Process

### Step 1: Triage classification
Used server-side PHP query to identify Tier A vs Tier B based on:
- Has `lrgQuickGrid` or `lrgHero` in post_content
- Has `lrgFaq` accordion
- Word count >= 2000
- Post date >= 2025-10-01

Result:
- Tier A: 139 posts (already-good content needing class migration only)
- Tier B: 932 posts (older content needing full rewrite)

### Step 2: Prepare batch list
Sorted by GSC clicks DESC (pulled from sc-domain:lrgrealty.com, 90-day window).
Built tier-a-batch.csv with batch_order column.
Top traffic posts processed first to surface visual issues early.

### Step 3: Per-post migration
For each post:
1. Pull current post_content via `wp eval-file` (proven safe method)
2. Backup to local timestamped HTML file (`~/lrg-rewrite/backups/`)
3. Run `migrate-classes.py --canonical --site-class rl-page-lrg`
4. Push migrated HTML as DRAFT via single-session heredoc + `wp eval-file`
5. Verify: post_status=draft, rl-page count >= 1, lrgHero count = 0
6. Sleep 5s before next post

### Step 4: Author normalization
After all migrations, ran bulk SQL update:
```sql
UPDATE wp_posts SET post_author = 1 WHERE post_type = 'post'
```
Fixed inherited Squarespace author bylines (jamescross36@yahoo.com)
to Levi Rodgers (user 1) across all posts. Also updated display_name.

### Step 5: Republish drafts to publish
After visual verification, republished all 139 drafts via single SQL:
```sql
UPDATE wp_posts SET post_status = 'publish' WHERE ID IN (...)
```
Followed by `wp_cache_flush()` and `clean_post_cache()` for each post.

## Results
- 139/139 successful migrations
- 0 failures (2 retried in batch 2 due to race condition, both succeeded)
- 0 lrg* remnants in any migrated post
- All post_dates preserved (original publish dates intact)
- Live URL pattern: https://lrgrealty.com/lrg-blog/<slug>/

## Lessons Captured

1. **WPE session-local /tmp trap**: SSH commands that write to /tmp in one
   session can't read it in a subsequent session. ALWAYS use single-session
   heredoc + wp eval-file. Never split write/read across sessions.

2. **wp db query silently fails on >60KB SQL**: For post_content updates,
   ALWAYS use wp eval-file with file-based content read, never inline SQL.

3. **Class migration vs content rewrite are different operations**: Tier A
   posts (139) had good content needing only class migration. Tier B (932)
   need full content rewrites via content-production module.

4. **Authors normalize cleanly via SQL**: A simple UPDATE statement fixed
   all posts to Levi Rodgers in one operation. Object cache required flush
   for get_post() to reflect the change.

5. **post_modified updates but post_date doesn't**: Original publish dates
   preserved across migration. Draft preview mode shows post_modified
   (standard WP behavior) but published view shows post_date correctly.

6. **Batch processing pattern**: 25 posts per batch with stop-and-report
   allows visual spot-checking before committing to larger runs. Top-traffic
   posts first surfaces issues on important pages early.

## Reusable Workflow for Future Clients

This same workflow applies to any client with:
- An existing class system (vln-, valn-, lrg-, custom-)
- HTML structure that maps cleanly to rl-* via migrate-classes.py
- Tier A posts that have good content but need framework migration

Site config requirements:
- `sites/<slug>.conf` with SSH details
- A class mapping in migrate-classes.py (add mode or extend `_SHARED`)
- Local backups directory (`~/<slug>-rewrite/backups/`)
- GSC access for traffic-based priority ranking

Tools used:
- `modules/content-production/tools/migrate-classes.py` (class swap + rl-page wrapper)
- `modules/wp-deploy/tools/push-post-status.py` (surgical status changes)
- `modules/wp-deploy/lib/ssh_session.py` (single-session SSH helper)
