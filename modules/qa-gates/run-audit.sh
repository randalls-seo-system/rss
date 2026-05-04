#!/bin/bash
# =============================================================================
# RSS QA Gates — Run Audit Suite on Target Site
# =============================================================================
# Uploads audit PHP scripts to target site, runs them via wp eval-file,
# pulls CSV results back, and generates a summary report.
#
# Usage:
#   ./modules/qa-gates/run-audit.sh <path-to-site.conf>
#   ./modules/qa-gates/run-audit.sh <path-to-site.conf> --audit anchor-splits
#   ./modules/qa-gates/run-audit.sh <path-to-site.conf> --output ~/reports/
#
# Flags:
#   --audit <name>   Run only this audit (anchor-splits, generic-anchors,
#                    repeated-urls, link-balance)
#   --output <dir>   Custom output directory (default: reports/<slug>/<date>/)
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
AUDITS_DIR="${SCRIPT_DIR}/audits"
LIB_DIR="${SCRIPT_DIR}/lib"

# --- Parse arguments ---
CONFIG_ARG=""
SINGLE_AUDIT=""
CUSTOM_OUTPUT=""

while [ $# -gt 0 ]; do
    case "$1" in
        --audit)  SINGLE_AUDIT="$2"; shift 2 ;;
        --output) CUSTOM_OUTPUT="$2"; shift 2 ;;
        *)        CONFIG_ARG="$1"; shift ;;
    esac
done

if [ -z "$CONFIG_ARG" ]; then
    echo "Usage: $0 <path-to-site.conf> [--audit <name>] [--output <dir>]"
    exit 1
fi

CONFIG_PATH="$CONFIG_ARG"
if [[ "$CONFIG_PATH" != /* ]]; then
    CONFIG_PATH="${REPO_ROOT}/${CONFIG_PATH}"
fi

if [ ! -f "$CONFIG_PATH" ]; then
    echo "ERROR: Config file not found: $CONFIG_PATH"
    exit 1
fi

source "$CONFIG_PATH"

# --- SSH setup ---
SSH_CMD="ssh -i ${SSH_KEY_PATH/#\~/$HOME} -o IdentitiesOnly=yes -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=accept-new ${SSH_USER}@${SSH_HOST}"

# --- Output directory ---
DATE_STAMP=$(date +%Y-%m-%d)
if [ -n "$CUSTOM_OUTPUT" ]; then
    OUTPUT_DIR="$CUSTOM_OUTPUT"
else
    OUTPUT_DIR="${SCRIPT_DIR}/reports/${SITE_SLUG}/${DATE_STAMP}"
fi
mkdir -p "$OUTPUT_DIR"

# --- Logging ---
log() { echo "[$(date +%H:%M:%S)] $*"; }
err() { echo "[$(date +%H:%M:%S)] ERROR: $*" >&2; }
sep() { echo "────────────────────────────────────────────────"; }

# --- Available audits ---
ALL_AUDITS=( "anchor-splits" "generic-anchors" "repeated-urls" "link-balance" )

if [ -n "$SINGLE_AUDIT" ]; then
    AUDITS=( "$SINGLE_AUDIT" )
else
    AUDITS=( "${ALL_AUDITS[@]}" )
fi

echo ""
echo "RSS QA Gates — Audit Suite"
sep
echo "  Site:    ${SITE_NAME} (${SITE_SLUG})"
echo "  Target:  ${SSH_USER}@${SSH_HOST}"
echo "  Output:  ${OUTPUT_DIR}"
echo "  Audits:  ${AUDITS[*]}"
sep
echo ""

# --- Pre-flight ---
log "Pre-flight: testing SSH..."
if ! $SSH_CMD 'echo OK' 2>/dev/null | grep -q 'OK'; then
    err "SSH connection failed"
    exit 1
fi
log "SSH: OK"
sleep 2

log "Pre-flight: testing WP-CLI..."
WP_VERSION=$($SSH_CMD "cd '${WP_PATH}' && wp core version 2>/dev/null" 2>/dev/null || echo "FAILED")
if [ "$WP_VERSION" = "FAILED" ]; then
    err "WP-CLI not available at ${WP_PATH}"
    exit 1
fi
log "WordPress: ${WP_VERSION}"
sleep 2

# --- Prepare helpers for inlining ---
# Each audit script needs helpers inlined because WP Engine /tmp is
# session-local and __DIR__ paths don't resolve reliably.
HELPERS_BODY=$(sed '1d' "$LIB_DIR/audit-helpers.php")  # Strip opening <?php
log "Helpers loaded ($(echo "$HELPERS_BODY" | wc -l | tr -d ' ') lines)"

sep
echo ""

# --- Run each audit ---
TOTAL_ISSUES=0
SUMMARY_LINES=()

for audit_name in "${AUDITS[@]}"; do
    log "Running: ${audit_name}..."

    CSV_FILE="${OUTPUT_DIR}/${audit_name}.csv"
    STDERR_FILE="${OUTPUT_DIR}/${audit_name}.log"

    # WP Engine /tmp is session-local. Must pipe file AND run wp eval-file
    # in the SAME SSH session. Pipe combined script via stdin, write to
    # /tmp, then eval-file — all in one command.
    COMBINED_SCRIPT="${OUTPUT_DIR}/.${audit_name}-combined.php"

    # Build combined script locally
    AUDIT_FILE="${AUDITS_DIR}/${audit_name}.php"
    AUDIT_BODY=$(sed '1d' "$AUDIT_FILE" | grep -v 'require_once.*audit-helpers')
    printf '<?php\n%s\n%s\n' "$HELPERS_BODY" "$AUDIT_BODY" > "$COMBINED_SCRIPT"

    # Pipe to server: write file + eval in single session
    cat "$COMBINED_SCRIPT" | $SSH_CMD "cat > /tmp/rss-audit.php && cd '${WP_PATH}' && wp eval-file /tmp/rss-audit.php 2>/dev/stderr" \
        > "$CSV_FILE" 2>"$STDERR_FILE" || true

    # Count issues (CSV lines minus header)
    ISSUE_COUNT=$(( $(wc -l < "$CSV_FILE" | tr -d ' ') - 1 ))
    if [ $ISSUE_COUNT -lt 0 ]; then ISSUE_COUNT=0; fi

    STDERR_MSG=$(head -1 "$STDERR_FILE" 2>/dev/null)
    log "  Result: ${ISSUE_COUNT} issues → ${CSV_FILE}"
    if [ -n "$STDERR_MSG" ]; then
        log "  Server: ${STDERR_MSG}"
    fi

    # Cleanup temp combined script
    rm -f "$COMBINED_SCRIPT"

    TOTAL_ISSUES=$((TOTAL_ISSUES + ISSUE_COUNT))
    SUMMARY_LINES+=( "| ${audit_name} | ${ISSUE_COUNT} |" )

    sleep 5
done

sep
echo ""

# --- Cleanup remote /tmp ---
log "Cleaning up remote scripts..."
$SSH_CMD "rm -f /tmp/rss-audit.php" 2>/dev/null || true
log "Cleanup: done"

sep
echo ""

# --- Generate summary report ---
SUMMARY_FILE="${OUTPUT_DIR}/summary.md"
cat > "$SUMMARY_FILE" << REPORT
# QA Gates Audit Report — ${SITE_NAME}

**Date:** ${DATE_STAMP}
**Site:** ${SITE_DOMAIN}
**Total issues:** ${TOTAL_ISSUES}

## Results

| Audit | Issues |
|-------|--------|
$(printf '%s\n' "${SUMMARY_LINES[@]}")

## Files

$(for audit_name in "${AUDITS[@]}"; do echo "- \`${audit_name}.csv\`"; done)

## Severity Guide

- **critical** — Visible content corruption or SEO damage
- **high** — Garbled text or significant quality issue
- **medium** — Suboptimal but not visually broken
- **low** — Minor, likely cosmetic

---
Generated by RSS QA Gates v1.0
REPORT

log "Summary report: ${SUMMARY_FILE}"

# --- Final summary ---
echo ""
log "AUDIT COMPLETE"
sep
echo ""
echo "  Site:         ${SITE_NAME}"
echo "  Total issues: ${TOTAL_ISSUES}"
echo "  Reports:      ${OUTPUT_DIR}/"
echo ""
for line in "${SUMMARY_LINES[@]}"; do
    echo "  $line"
done
echo ""
