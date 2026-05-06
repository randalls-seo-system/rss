# LRG Deployment Learnings — 2026-05-06

## Post 2662 Silent SQL Failure

**Problem:** `wp db query "UPDATE wp_posts SET post_content = UNHEX('...') WHERE ID=2662"` returned exit code 0 but didn't update the post. Content remained unchanged. No error output.

**Root cause:** WP Engine staging has a query size limit or timeout for inline SQL via `wp db query`. The hex-encoded content was ~120KB of SQL — too large for the pipe.

**Solution:** SCP the content file to `/tmp/`, then execute PHP via `wp eval-file` that reads the local file and calls `wp_update_post()`:

```php
<?php
$content = file_get_contents('/tmp/post-content-2662.html');
$result = wp_update_post(['ID' => 2662, 'post_content' => $content, 'post_status' => 'draft'], true);
if (is_wp_error($result)) { echo "ERROR: " . $result->get_error_message(); exit(1); }
echo "STATUS=" . get_post(2662)->post_status . "|LEN=" . strlen(get_post(2662)->post_content) . "|OK=1|";
```

**Result:** 100% success rate across 25 posts in batch 1.

## Bulk Author Update

**Problem:** 1,158 LRG posts had wrong author (user 2 from Squarespace import). Needed to reassign all to user 1.

**Solution:** Single SQL UPDATE with WHERE clause filtering post_type and post_status. Verified via spot-check of 5 random posts.

**Lesson:** For metadata-only changes (no content modification), `wp db query` works fine — the failure is specific to large post_content payloads.

## Key Takeaways

1. **Never use `wp db query` for post_content writes** — silently fails on WPE with large payloads
2. **Always SCP content first, then read in PHP** — avoids shell escaping entirely
3. **Always verify post-write** — compare content length, grep for expected classes
4. **5s sleep minimum between writes** — WP Engine's object cache needs time to settle
5. **WPE `/tmp/` is session-ephemeral** — files written in one SSH session are invisible to the next. Upload + execute in the same SSH call, or use stdin pipe method.
