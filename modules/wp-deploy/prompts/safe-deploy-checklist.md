# Safe Deploy Checklist

Before any bulk WordPress write operation:

- [ ] Backup target posts to local files (auto-done by tools, but verify backup dir exists)
- [ ] Coordinate with other terminals (no parallel SSH on same site — causes OOM/connection drops)
- [ ] Run with `--dry-run` first to preview changes
- [ ] Verify backup file integrity (non-zero size, contains expected classes)
- [ ] Run small batch (5 posts) before scaling to full list
- [ ] Spot check first 3 results visually (open in browser, confirm rendering)
- [ ] Sleep between posts (5s minimum for content, 3s for meta)
- [ ] Log to `/tmp/<site>-wp-deploy.log` (auto-done by SSHSession)
- [ ] Halt on first failure (default behavior, do not override unless explicitly instructed)

## After completion:

- [ ] Verify final batch via `verify-write.py` on random sample
- [ ] Check WP Engine error log for PHP fatals
- [ ] Flush object cache: `ssh ... "wp cache flush"`
- [ ] Visual spot-check 3 posts in browser (staging URL)
- [ ] Report results to operator before proceeding to next batch
