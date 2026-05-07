#!/usr/bin/env bash
# ==========================================================
# Rank Logic — Overnight Batch Content Production
#
# Runs produce-article.py on each post in a batch CSV.
# Designed for parallel use across 3 terminals (green/blue/red).
#
# Usage:
#   bash run-overnight-batch.sh --site lrg \
#     --batch-csv ~/lrg-rewrite/overnight-batch-green.csv \
#     --terminal-name green
#
# Safety:
#   - All pushes as DRAFT (never publish)
#   - Backs up original content before every write
#   - Halts after --max-failures consecutive or total failures
#   - Sleeps between articles to avoid SSH saturation
#   - Logs everything to /tmp/lrg-overnight-{terminal}.log
# ==========================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Defaults
SITE=""
BATCH_CSV=""
TERMINAL_NAME="default"
MAX_FAILURES=5
STATUS="draft"
SLEEP_BETWEEN=30
PROVIDER="claude"
MODEL=""
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --site)          SITE="$2"; shift 2 ;;
        --batch-csv)     BATCH_CSV="$2"; shift 2 ;;
        --terminal-name) TERMINAL_NAME="$2"; shift 2 ;;
        --max-failures)  MAX_FAILURES="$2"; shift 2 ;;
        --status)        STATUS="$2"; shift 2 ;;
        --sleep-between) SLEEP_BETWEEN="$2"; shift 2 ;;
        --provider)      PROVIDER="$2"; shift 2 ;;
        --model)         MODEL="$2"; shift 2 ;;
        --dry-run)       DRY_RUN=true; shift ;;
        *) echo "Unknown: $1"; exit 1 ;;
    esac
done

if [[ -z "$SITE" || -z "$BATCH_CSV" ]]; then
    echo "Usage: run-overnight-batch.sh --site <slug> --batch-csv <path> --terminal-name <name>"
    exit 1
fi

if [[ ! -f "$BATCH_CSV" ]]; then
    echo "ERROR: Batch CSV not found: $BATCH_CSV"
    exit 1
fi

# Setup
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
DATE_SHORT=$(date +%Y-%m-%d)
LOG_FILE="/tmp/lrg-overnight-${TERMINAL_NAME}.log"
SUMMARY_FILE="${HOME}/${SITE}-rewrite/overnight-${TERMINAL_NAME}-${DATE_SHORT}.summary.md"
BACKUP_DIR="${HOME}/${SITE}-rewrite/backups"
OUTPUT_DIR="${HOME}/${SITE}-rewrite/articles-v3"

mkdir -p "$BACKUP_DIR" "$OUTPUT_DIR" "$(dirname "$SUMMARY_FILE")"

# Count posts
TOTAL=$(tail -n +2 "$BATCH_CSV" | wc -l | tr -d ' ')

echo "============================================================" | tee "$LOG_FILE"
echo "OVERNIGHT BATCH: ${TERMINAL_NAME}" | tee -a "$LOG_FILE"
echo "============================================================" | tee -a "$LOG_FILE"
echo "  Site: ${SITE}" | tee -a "$LOG_FILE"
echo "  Batch: ${BATCH_CSV}" | tee -a "$LOG_FILE"
echo "  Posts: ${TOTAL}" | tee -a "$LOG_FILE"
echo "  Status: ${STATUS}" | tee -a "$LOG_FILE"
echo "  Max failures: ${MAX_FAILURES}" | tee -a "$LOG_FILE"
echo "  Sleep between: ${SLEEP_BETWEEN}s" | tee -a "$LOG_FILE"
echo "  Provider: ${PROVIDER}" | tee -a "$LOG_FILE"
echo "  Started: $(date)" | tee -a "$LOG_FILE"
echo "============================================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Counters
SUCCESS=0
FAILED=0
SKIPPED=0
FAILED_IDS=""
START_TIME=$(date +%s)

# Process each post (read from fd 3 to prevent child processes from consuming CSV stdin)
INDEX=0
exec 3< "$BATCH_CSV"
while IFS=, read -r POST_ID PARENT_QUERY DOMINANT_INTENT CLUSTER_IMPS <&3; do
    # Skip header
    if [[ "$POST_ID" == "post_id" ]]; then
        continue
    fi

    INDEX=$((INDEX + 1))
    ARTICLE_START=$(date +%s)

    echo "[${INDEX}/${TOTAL}] Post ${POST_ID}: ${PARENT_QUERY:0:50}" | tee -a "$LOG_FILE"
    echo "  Impressions: ${CLUSTER_IMPS}" | tee -a "$LOG_FILE"

    if [[ "$DRY_RUN" == "true" ]]; then
        echo "  [DRY RUN] Would produce article" | tee -a "$LOG_FILE"
        SKIPPED=$((SKIPPED + 1))
        continue
    fi

    # Build command
    CMD=(python3 "${SCRIPT_DIR}/produce-article.py"
        --site "$SITE"
        --post-id "$POST_ID"
        --target-keyword "$PARENT_QUERY"
        --status "$STATUS"
        --provider "$PROVIDER"
    )
    if [[ -n "$MODEL" ]]; then
        CMD+=(--model "$MODEL")
    fi

    # Run produce-article.py (close fd 3 so child can't consume CSV, /dev/null stdin)
    if "${CMD[@]}" < /dev/null >> "$LOG_FILE" 2>&1; then
        ARTICLE_END=$(date +%s)
        ARTICLE_ELAPSED=$((ARTICLE_END - ARTICLE_START))
        SUCCESS=$((SUCCESS + 1))
        echo "  OK (${ARTICLE_ELAPSED}s) [${SUCCESS} ok / ${FAILED} fail]" | tee -a "$LOG_FILE"
    else
        ARTICLE_END=$(date +%s)
        ARTICLE_ELAPSED=$((ARTICLE_END - ARTICLE_START))
        FAILED=$((FAILED + 1))
        FAILED_IDS="${FAILED_IDS}${POST_ID},"
        echo "  FAIL (${ARTICLE_ELAPSED}s) [${SUCCESS} ok / ${FAILED} fail]" | tee -a "$LOG_FILE"

        # Check halt threshold
        if [[ "$FAILED" -ge "$MAX_FAILURES" ]]; then
            echo "" | tee -a "$LOG_FILE"
            echo "HALTED: ${FAILED} failures reached max-failures threshold (${MAX_FAILURES})" | tee -a "$LOG_FILE"
            echo "Last failure: Post ${POST_ID}" | tee -a "$LOG_FILE"
            break
        fi
    fi

    # Sleep between articles (skip after last)
    if [[ "$INDEX" -lt "$TOTAL" ]]; then
        echo "  Sleeping ${SLEEP_BETWEEN}s..." | tee -a "$LOG_FILE"
        sleep "$SLEEP_BETWEEN"
    fi

    echo "" | tee -a "$LOG_FILE"

done
exec 3<&-  # Close fd 3

# Summary
END_TIME=$(date +%s)
TOTAL_ELAPSED=$((END_TIME - START_TIME))
MINUTES=$((TOTAL_ELAPSED / 60))
SECONDS=$((TOTAL_ELAPSED % 60))

echo "" | tee -a "$LOG_FILE"
echo "============================================================" | tee -a "$LOG_FILE"
echo "BATCH COMPLETE: ${TERMINAL_NAME}" | tee -a "$LOG_FILE"
echo "============================================================" | tee -a "$LOG_FILE"
echo "  Total: ${TOTAL}" | tee -a "$LOG_FILE"
echo "  Success: ${SUCCESS}" | tee -a "$LOG_FILE"
echo "  Failed: ${FAILED}" | tee -a "$LOG_FILE"
echo "  Skipped: ${SKIPPED}" | tee -a "$LOG_FILE"
echo "  Time: ${MINUTES}m ${SECONDS}s" | tee -a "$LOG_FILE"
echo "  Finished: $(date)" | tee -a "$LOG_FILE"
if [[ -n "$FAILED_IDS" ]]; then
    echo "  Failed IDs: ${FAILED_IDS%,}" | tee -a "$LOG_FILE"
fi
echo "============================================================" | tee -a "$LOG_FILE"

# Write summary markdown
cat > "$SUMMARY_FILE" << MDEOF
# Overnight Batch Summary: ${TERMINAL_NAME}

**Date:** ${DATE_SHORT}
**Site:** ${SITE}
**Batch:** ${BATCH_CSV}

## Results

| Metric | Value |
|--------|-------|
| Total posts | ${TOTAL} |
| Success | ${SUCCESS} |
| Failed | ${FAILED} |
| Skipped | ${SKIPPED} |
| Duration | ${MINUTES}m ${SECONDS}s |
| Avg per article | $((TOTAL_ELAPSED / (SUCCESS + FAILED + 1)))s |

## Failed Posts

${FAILED_IDS:-None}

## Spot Check (first 5 successful)

Preview URLs for visual review:
MDEOF

# Add preview URLs for first 5 successful articles
PREVIEW_COUNT=0
while IFS=, read -r POST_ID PARENT_QUERY DOMINANT_INTENT CLUSTER_IMPS; do
    if [[ "$POST_ID" == "post_id" ]]; then continue; fi
    if [[ "$FAILED_IDS" == *"${POST_ID},"* ]]; then continue; fi
    PREVIEW_COUNT=$((PREVIEW_COUNT + 1))
    echo "- Post ${POST_ID}: https://lrgrealtyblog.wpenginepowered.com/?p=${POST_ID}&preview=true" >> "$SUMMARY_FILE"
    if [[ "$PREVIEW_COUNT" -ge 5 ]]; then break; fi
done < "$BATCH_CSV"

echo "" >> "$SUMMARY_FILE"
echo "## Log" >> "$SUMMARY_FILE"
echo "Full log: ${LOG_FILE}" >> "$SUMMARY_FILE"

echo ""
echo "Summary written to: ${SUMMARY_FILE}"
echo "Full log: ${LOG_FILE}"
