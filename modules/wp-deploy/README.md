# wp-deploy module

Safe, parameterized WordPress write operations using the proven SCP + wp eval-file pattern.

## Why this module exists

On WP Engine staging, `wp db query` with 60KB+ inline SQL **fails silently** (returns exit 0, no rows affected). This was discovered on LRG post 2662 (2026-05-06). Shell escaping of HTML content also causes silent corruption.

Solution: upload content file via stdin pipe, then execute PHP that reads the file and calls `wp_update_post()`. This pattern has a 100% success rate across 25+ posts.

## Tools

| Tool | Purpose |
|---|---|
| `push-post-content.py` | Safe post_content updates (SCP + wp eval-file) |
| `push-post-meta.py` | Yoast/custom field updates with backup |
| `push-post-status.py` | Status changes (publish, draft, trash) |
| `bulk-update-author.py` | Reassign post authorship in bulk |
| `verify-write.py` | Standalone post-write assertion tool |
| `rollback.sh` | One-step restore from local backup |

## Quick start

```bash
# Push new content (dry run first)
python3 modules/wp-deploy/tools/push-post-content.py \
  --site lrg --post-id 2662 \
  --html-file /tmp/post-2662.html --status draft --dry-run

# Push for real
python3 modules/wp-deploy/tools/push-post-content.py \
  --site lrg --post-id 2662 \
  --html-file /tmp/post-2662.html --status draft \
  --verify-greps 'rl-page,rl-quick-grid'

# Rollback
bash modules/wp-deploy/tools/rollback.sh \
  --site lrg --post-id 2662 \
  --backup-file ~/lrg-rewrite/backups/2662-original-20260506-191500.html
```

## Site config requirements

The tool reads SSH details from `sites/<slug>.conf`:
```
SSH_HOST="lrgrealtyblog.ssh.wpengine.net"
SSH_USER="lrgrealtyblog"
SSH_KEY_PATH="~/.ssh/wpengine_valn"
```

## Failure modes

| Failure | Behavior |
|---|---|
| SSH timeout | Raises exception, halts batch |
| Upload size mismatch | Returns error, halts batch |
| wp_update_post WP_Error | Parsed from PHP output, halts batch |
| verify_greps absent | Returns verify_fail, halts batch |
| forbid_greps present | Returns forbid_fail, halts batch |
| Size ratio out of bounds | Pre-flight check fails, halts batch |

## Rollback

Every push creates a backup at `~/<site>-rewrite/backups/<id>-original-<timestamp>.html`. Restore via `rollback.sh` or manually with `push-post-content.py` using the backup file.
