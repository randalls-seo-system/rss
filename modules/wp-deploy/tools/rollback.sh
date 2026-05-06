#!/usr/bin/env bash
# Restore post_content from a local backup file.
#
# Usage:
#   bash rollback.sh --site lrg --post-id 1789 \
#     --backup-file ~/lrg-rewrite/backups/1789-original-20260506-191500.html \
#     --status draft
#
# Delegates to push-post-content.py with the backup as input.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

SITE=""
POST_ID=""
BACKUP_FILE=""
STATUS="draft"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --site) SITE="$2"; shift 2 ;;
        --post-id) POST_ID="$2"; shift 2 ;;
        --backup-file) BACKUP_FILE="$2"; shift 2 ;;
        --status) STATUS="$2"; shift 2 ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
done

if [[ -z "$SITE" || -z "$POST_ID" || -z "$BACKUP_FILE" ]]; then
    echo "Usage: rollback.sh --site <slug> --post-id <id> --backup-file <path> [--status draft]"
    exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    echo "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

echo "Rolling back post $POST_ID from backup..."
echo "  File: $BACKUP_FILE"
echo "  Size: $(wc -c < "$BACKUP_FILE") bytes"
echo "  Target status: $STATUS"
echo ""

python3 "$SCRIPT_DIR/push-post-content.py" \
    --site "$SITE" \
    --post-id "$POST_ID" \
    --html-file "$BACKUP_FILE" \
    --status "$STATUS" \
    --size-min-ratio 0.5 \
    --size-max-ratio 2.0

echo ""
echo "Rollback complete."
