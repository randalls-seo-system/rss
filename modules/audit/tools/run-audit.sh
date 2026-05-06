#!/usr/bin/env bash
# Master audit orchestration script.
# Calls all sub-tools in sequence to produce a complete site audit.
#
# Usage:
#   ./run-audit.sh --site lrg --skip-gsc-pull --gsc-export ~/Downloads/lrg-gsc.zip
#   ./run-audit.sh --site valn --output-dir ~/valn-rewrite/audits/
#
# Safety: Read-only module — never modifies WP content.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$(dirname "$MODULE_DIR")")"

# Defaults
SITE=""
OUTPUT_DIR=""
SKIP_GSC_PULL=false
GSC_EXPORT=""
INCLUDE_SPANISH=false
SKIP_INVENTORY=false
SKIP_TRIAGE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --site)             SITE="$2"; shift 2 ;;
        --output-dir)       OUTPUT_DIR="$2"; shift 2 ;;
        --skip-gsc-pull)    SKIP_GSC_PULL=true; shift ;;
        --gsc-export)       GSC_EXPORT="$2"; shift 2 ;;
        --include-spanish)  INCLUDE_SPANISH=true; shift ;;
        --skip-inventory)   SKIP_INVENTORY=true; shift ;;
        --skip-triage)      SKIP_TRIAGE=true; shift ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$SITE" ]; then
    echo "Usage: $0 --site <slug> [--output-dir <path>] [--skip-gsc-pull --gsc-export <path>]"
    echo ""
    echo "Options:"
    echo "  --site <slug>          Site slug (reads sites/<slug>.conf)"
    echo "  --output-dir <path>    Output directory (default: ~/<site>-rewrite/audits/)"
    echo "  --skip-gsc-pull        Use existing GSC export instead of API pull"
    echo "  --gsc-export <path>    Path to GSC zip if --skip-gsc-pull"
    echo "  --include-spanish      Include Spanish content (default: skip)"
    echo "  --skip-inventory       Skip WP inventory pull (reuse existing)"
    echo "  --skip-triage          Skip triage classification (requires SSH)"
    exit 1
fi

# Resolve output directory
if [ -z "$OUTPUT_DIR" ]; then
    OUTPUT_DIR="$HOME/${SITE}-rewrite/audits"
fi
mkdir -p "$OUTPUT_DIR"

LOG_FILE="/tmp/${SITE}-audit.log"

echo "=== RSS Site Audit ===" | tee "$LOG_FILE"
echo "Site: ${SITE}" | tee -a "$LOG_FILE"
echo "Output: ${OUTPUT_DIR}" | tee -a "$LOG_FILE"
echo "Log: ${LOG_FILE}" | tee -a "$LOG_FILE"
echo "Started: $(date)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

START_TIME=$(date +%s)

# ── Step 1: Pull content inventory ────────────────────────────────────────
INVENTORY_CSV="${OUTPUT_DIR}/all-posts.csv"

if [ "$SKIP_INVENTORY" = true ] && [ -f "$INVENTORY_CSV" ]; then
    echo "[1/8] Content inventory: SKIPPED (using existing)" | tee -a "$LOG_FILE"
else
    echo "[1/8] Pulling content inventory..." | tee -a "$LOG_FILE"
    python3 "${SCRIPT_DIR}/pull-content-inventory.py" \
        --site "$SITE" \
        --output-csv "$INVENTORY_CSV" \
        --include-meta \
        2>> "$LOG_FILE"
    echo "  → $(wc -l < "$INVENTORY_CSV") rows" | tee -a "$LOG_FILE"
fi

# ── Step 2: GSC traffic data ──────────────────────────────────────────────
GSC_PAGES=""

if [ "$SKIP_GSC_PULL" = true ] && [ -n "$GSC_EXPORT" ]; then
    echo "[2/8] GSC data: parsing export..." | tee -a "$LOG_FILE"
    python3 "${SCRIPT_DIR}/pull-gsc-data.py" \
        --site "$SITE" \
        --gsc-export "$GSC_EXPORT" \
        --output-dir "$OUTPUT_DIR" \
        2>> "$LOG_FILE"
else
    echo "[2/8] GSC data: API pull..." | tee -a "$LOG_FILE"
    python3 "${SCRIPT_DIR}/pull-gsc-data.py" \
        --site "$SITE" \
        --output-dir "$OUTPUT_DIR" \
        2>> "$LOG_FILE"
fi

# Find the GSC pages file
GSC_PAGES=$(ls -t "${OUTPUT_DIR}"/gsc-pages-*.csv 2>/dev/null | head -1)
if [ -z "$GSC_PAGES" ]; then
    # Fallback to gsc-all-pages.csv
    GSC_PAGES="${OUTPUT_DIR}/gsc-all-pages.csv"
fi
echo "  GSC pages: ${GSC_PAGES}" | tee -a "$LOG_FILE"

# ── Step 3: Delete candidates ────────────────────────────────────────────
echo "[3/8] Identifying delete candidates..." | tee -a "$LOG_FILE"
DELETE_ARGS="--inventory-csv $INVENTORY_CSV --gsc-pages-csv $GSC_PAGES --output-csv ${OUTPUT_DIR}/delete-candidates.csv"
if [ "$INCLUDE_SPANISH" = true ]; then
    DELETE_ARGS="$DELETE_ARGS --include-spanish"
fi
python3 "${SCRIPT_DIR}/identify-deletes.py" $DELETE_ARGS 2>> "$LOG_FILE"

# ── Step 4: Slug issues ──────────────────────────────────────────────────
echo "[4/8] Identifying slug issues..." | tee -a "$LOG_FILE"
python3 "${SCRIPT_DIR}/identify-slug-issues.py" \
    --inventory-csv "$INVENTORY_CSV" \
    --gsc-pages-csv "$GSC_PAGES" \
    --output-csv "${OUTPUT_DIR}/slug-issues.csv" \
    2>> "$LOG_FILE"

# ── Step 5: Meta refresh candidates ──────────────────────────────────────
echo "[5/8] Identifying meta refresh candidates..." | tee -a "$LOG_FILE"
python3 "${SCRIPT_DIR}/identify-meta-candidates.py" \
    --gsc-pages-csv "$GSC_PAGES" \
    --inventory-csv "$INVENTORY_CSV" \
    --output-csv "${OUTPUT_DIR}/meta-candidates.csv" \
    2>> "$LOG_FILE"

# ── Step 6: Priority rewrites ────────────────────────────────────────────
echo "[6/8] Identifying priority rewrites..." | tee -a "$LOG_FILE"
python3 "${SCRIPT_DIR}/identify-priority-rewrites.py" \
    --gsc-pages-csv "$GSC_PAGES" \
    --output-csv "${OUTPUT_DIR}/priority-rewrites.csv" \
    2>> "$LOG_FILE"

# ── Step 7: Cannibalization ──────────────────────────────────────────────
echo "[7/8] Identifying cannibalization..." | tee -a "$LOG_FILE"
python3 "${SCRIPT_DIR}/identify-cannibalization.py" \
    --inventory-csv "$INVENTORY_CSV" \
    --output-csv "${OUTPUT_DIR}/cannibalization.csv" \
    --review-mode \
    2>> "$LOG_FILE"

# ── Step 8: Summary ──────────────────────────────────────────────────────
echo "[8/8] Generating summary report..." | tee -a "$LOG_FILE"
python3 "${SCRIPT_DIR}/generate-summary.py" \
    --site "$SITE" \
    --output-dir "$OUTPUT_DIR" \
    2>> "$LOG_FILE"

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo "" | tee -a "$LOG_FILE"
echo "=== Audit Complete ===" | tee -a "$LOG_FILE"
echo "Time: ${ELAPSED}s" | tee -a "$LOG_FILE"
echo "Output: ${OUTPUT_DIR}" | tee -a "$LOG_FILE"
echo "Summary: ${OUTPUT_DIR}/00-AUDIT-SUMMARY.md" | tee -a "$LOG_FILE"
echo ""
echo "Key files:"
for f in delete-candidates.csv slug-issues.csv meta-candidates.csv priority-rewrites.csv; do
    if [ -f "${OUTPUT_DIR}/${f}" ]; then
        COUNT=$(tail -n +2 "${OUTPUT_DIR}/${f}" | wc -l | tr -d ' ')
        echo "  ${f}: ${COUNT} items"
    fi
done
