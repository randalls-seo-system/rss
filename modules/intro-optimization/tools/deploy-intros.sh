#!/usr/bin/env bash
# Deploy approved intro rewrites to WordPress posts.
#
# Usage:
#   ./deploy-intros.sh --site lrg --proposals-csv proposed.csv
#   ./deploy-intros.sh --site lrg --proposals-csv proposed.csv --dry-run
#
# Safety:
#   - Backs up each post before modification
#   - Sleeps 3s between WP-CLI calls
#   - Processes in batches with status reports
#   - Halts on 2 consecutive failures
#
# Requires: python3, ssh access to WP Engine, BeautifulSoup4

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODULE_DIR="$(dirname "$SCRIPT_DIR")"

# Defaults
SITE=""
PROPOSALS_CSV=""
BATCH_SIZE=25
DRY_RUN=false
BACKUP_DIR=""
SLEEP_SECS=3

usage() {
    echo "Usage: $0 --site <slug> --proposals-csv <path> [--batch-size N] [--dry-run]"
    exit 1
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --site) SITE="$2"; shift 2 ;;
        --proposals-csv) PROPOSALS_CSV="$2"; shift 2 ;;
        --batch-size) BATCH_SIZE="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        --backup-dir) BACKUP_DIR="$2"; shift 2 ;;
        *) echo "Unknown option: $1"; usage ;;
    esac
done

[[ -z "$SITE" || -z "$PROPOSALS_CSV" ]] && usage

# Site config
case "$SITE" in
    lrg)
        SSH_HOST="lrgrealtyblog@lrgrealtyblog.ssh.wpengine.net"
        SSH_KEY="$HOME/.ssh/wpengine_valn"
        ;;
    *)
        echo "ERROR: unknown site '$SITE'"
        exit 1
        ;;
esac

if [[ -z "$BACKUP_DIR" ]]; then
    BACKUP_DIR="$HOME/lrg-rewrite/backups"
fi
mkdir -p "$BACKUP_DIR"

TIMESTAMP=$(date +%Y%m%d-%H%M%S)
LOG="/tmp/${SITE}-intro-optimization.log"
echo "=== Deploy intros: $TIMESTAMP ===" >> "$LOG"

TOTAL=$(tail -n +2 "$PROPOSALS_CSV" | wc -l | tr -d ' ')
echo "Posts to process: $TOTAL"
echo "Batch size: $BATCH_SIZE"
echo "Dry run: $DRY_RUN"
echo "Log: $LOG"
echo ""

CONSECUTIVE_FAILURES=0
PROCESSED=0
SUCCEEDED=0
FAILED=0

# Read CSV line by line (skip header)
tail -n +2 "$PROPOSALS_CSV" | while IFS=, read -r POST_ID URL CURRENT PROPOSED EYEBROW DISCLAIMER CUR_WC PROP_WC CAPTURES FILLER RATIONALE; do
    PROCESSED=$((PROCESSED + 1))

    echo "[$PROCESSED/$TOTAL] Post $POST_ID"
    echo "  Proposed: ${PROP_WC} words"

    if [[ "$DRY_RUN" == true ]]; then
        echo "  [DRY RUN] Would update post $POST_ID"
        echo "$TIMESTAMP DRY_RUN post=$POST_ID" >> "$LOG"
        continue
    fi

    # Backup current content
    BACKUP_FILE="$BACKUP_DIR/intro-${POST_ID}-${TIMESTAMP}.html"
    ssh -i "$SSH_KEY" -o IdentitiesOnly=yes "$SSH_HOST" \
        "wp post get $POST_ID --field=post_content" > "$BACKUP_FILE" 2>/dev/null

    if [[ ! -s "$BACKUP_FILE" ]]; then
        echo "  ERROR: backup empty, skipping"
        FAILED=$((FAILED + 1))
        CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))
        echo "$TIMESTAMP FAIL post=$POST_ID reason=empty_backup" >> "$LOG"

        if [[ $CONSECUTIVE_FAILURES -ge 2 ]]; then
            echo "HALT: 2 consecutive failures. Stopping."
            echo "$TIMESTAMP HALT consecutive_failures=2" >> "$LOG"
            break
        fi
        sleep "$SLEEP_SECS"
        continue
    fi

    # Apply intro replacement via Python
    python3 -c "
import sys
sys.path.insert(0, '$MODULE_DIR/lib')
from html_intro_replacer import replace_intro
with open('$BACKUP_FILE') as f:
    html = f.read()
result = replace_intro(html, '''$EYEBROW''', '''$PROPOSED''', '''$DISCLAIMER''')
print(result)
" > "/tmp/intro-deploy-${POST_ID}.html" 2>/dev/null

    if [[ ! -s "/tmp/intro-deploy-${POST_ID}.html" ]]; then
        echo "  ERROR: replacement produced empty output"
        FAILED=$((FAILED + 1))
        CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))
        echo "$TIMESTAMP FAIL post=$POST_ID reason=empty_replacement" >> "$LOG"

        if [[ $CONSECUTIVE_FAILURES -ge 2 ]]; then
            echo "HALT: 2 consecutive failures. Stopping."
            echo "$TIMESTAMP HALT consecutive_failures=2" >> "$LOG"
            break
        fi
        sleep "$SLEEP_SECS"
        continue
    fi

    # Deploy via SQL UNHEX method (proven safe for WP Engine)
    HEX=$(python3 -c "
with open('/tmp/intro-deploy-${POST_ID}.html') as f:
    print(f.read().encode('utf-8').hex())
")

    echo "UPDATE wp_posts SET post_content = UNHEX('$HEX') WHERE ID=$POST_ID;" | \
        ssh -i "$SSH_KEY" -o IdentitiesOnly=yes "$SSH_HOST" 'wp db query' 2>/dev/null

    if [[ $? -eq 0 ]]; then
        echo "  OK"
        SUCCEEDED=$((SUCCEEDED + 1))
        CONSECUTIVE_FAILURES=0
        echo "$TIMESTAMP OK post=$POST_ID wc_before=$CUR_WC wc_after=$PROP_WC" >> "$LOG"
    else
        echo "  ERROR: WP update failed"
        FAILED=$((FAILED + 1))
        CONSECUTIVE_FAILURES=$((CONSECUTIVE_FAILURES + 1))
        echo "$TIMESTAMP FAIL post=$POST_ID reason=wp_update" >> "$LOG"

        if [[ $CONSECUTIVE_FAILURES -ge 2 ]]; then
            echo "HALT: 2 consecutive failures. Stopping."
            echo "$TIMESTAMP HALT consecutive_failures=2" >> "$LOG"
            break
        fi
    fi

    # Batch checkpoint
    if [[ $((PROCESSED % BATCH_SIZE)) -eq 0 ]]; then
        echo ""
        echo "=== Batch checkpoint: $PROCESSED/$TOTAL (OK: $SUCCEEDED, FAIL: $FAILED) ==="
        echo ""
    fi

    sleep "$SLEEP_SECS"
done

echo ""
echo "=== Summary ==="
echo "Processed: $PROCESSED"
echo "Succeeded: $SUCCEEDED"
echo "Failed: $FAILED"
echo "Log: $LOG"
