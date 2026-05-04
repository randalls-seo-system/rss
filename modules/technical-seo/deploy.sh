#!/bin/bash
# =============================================================================
# RSS Technical SEO Module — Deploy to Target Site
# =============================================================================
# Uploads rendered mu-plugins to a target site via SSH/SCP.
# Backs up existing files, verifies upload, and runs sanity checks.
#
# Usage:
#   ./modules/technical-seo/deploy.sh <path-to-site.conf>
#   ./modules/technical-seo/deploy.sh <path-to-site.conf> --dry-run
#
# Flags:
#   --dry-run   Run pre-flight checks only. No uploads, no modifications.
#
# Prerequisites:
#   - render.sh has already been run for this site config
#   - SSH key exists and has access to target server
#   - Target site has WP-CLI available
# =============================================================================

set -euo pipefail

# --- Resolve paths ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# --- Parse arguments ---
DRY_RUN=false
CONFIG_ARG=""
for arg in "$@"; do
    if [ "$arg" = "--dry-run" ]; then
        DRY_RUN=true
    elif [ -z "$CONFIG_ARG" ]; then
        CONFIG_ARG="$arg"
    fi
done

if [ -z "$CONFIG_ARG" ]; then
    echo "Usage: $0 <path-to-site.conf> [--dry-run]"
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

# --- Source config ---
source "$CONFIG_PATH"

# --- Auto-derive ---
SITE_PREFIX_UPPER=$(echo "$SITE_PREFIX" | tr '[:lower:]' '[:upper:]')
RENDERED_DIR="${SCRIPT_DIR}/rendered/${SITE_SLUG}"
SSH_CMD="ssh -i ${SSH_KEY_PATH/#\~/$HOME} -o IdentitiesOnly=yes -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=accept-new ${SSH_USER}@${SSH_HOST}"
SCP_CMD="scp -i ${SSH_KEY_PATH/#\~/$HOME} -o IdentitiesOnly=yes -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=accept-new"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="${MU_PLUGINS_PATH}.rss-backups/${TIMESTAMP}"

# Expected files
EXPECTED_FILES=(
    "${SITE_PREFIX}-llms-config.php"
    "${SITE_PREFIX}-llms-txt.php"
    "${SITE_PREFIX}-ai-crawler-log.php"
    "${SITE_PREFIX}-markdown-variants.php"
    "${SITE_PREFIX}-llms-full-txt.php"
    "${SITE_PREFIX}-dashboard-ai-crawlers.php"
)

URLS_FILE="${SITE_PREFIX}-llms-urls.php"

# --- Logging ---
log() { echo "[$(date +%H:%M:%S)] $*"; }
err() { echo "[$(date +%H:%M:%S)] ERROR: $*" >&2; }
sep() { echo "────────────────────────────────────────────────"; }

if [ "$DRY_RUN" = true ]; then
    echo ""
    echo "  *** DRY RUN MODE — no files will be uploaded or modified ***"
    echo ""
fi

# =============================================================================
# A. PRE-FLIGHT CHECKS
# =============================================================================
log "PRE-FLIGHT CHECKS"
sep

# 1. Rendered directory exists
if [ ! -d "$RENDERED_DIR" ]; then
    err "Rendered directory not found: $RENDERED_DIR"
    err "Run render.sh first: ./modules/technical-seo/render.sh $CONFIG_ARG"
    exit 1
fi
log "  Rendered dir: $RENDERED_DIR"

# 2. All expected files present
MISSING_FILES=()
for f in "${EXPECTED_FILES[@]}"; do
    if [ ! -f "${RENDERED_DIR}/${f}" ]; then
        MISSING_FILES+=("$f")
    fi
done
if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    err "Missing rendered files: ${MISSING_FILES[*]}"
    err "Run render.sh first"
    exit 1
fi
log "  All ${#EXPECTED_FILES[@]} mu-plugin files present"

# URLs companion file
HAS_URLS_FILE=false
if [ -f "${RENDERED_DIR}/${URLS_FILE}" ]; then
    HAS_URLS_FILE=true
    log "  URLs config file present: ${URLS_FILE}"
else
    log "  No URLs config file (llms-config will use fallback)"
fi

# 3. SSH key exists
RESOLVED_KEY="${SSH_KEY_PATH/#\~/$HOME}"
if [ ! -f "$RESOLVED_KEY" ]; then
    err "SSH key not found: ${SSH_KEY_PATH}"
    exit 1
fi
log "  SSH key: ${SSH_KEY_PATH}"

# 4. SSH connection test
log "  Testing SSH connection to ${SSH_USER}@${SSH_HOST}..."
if ! $SSH_CMD 'echo OK' 2>/dev/null | grep -q 'OK'; then
    err "SSH connection failed to ${SSH_USER}@${SSH_HOST}"
    err "Check SSH_HOST, SSH_USER, SSH_KEY_PATH in config"
    exit 1
fi
log "  SSH connection: OK"
sleep 2

# 5. MU_PLUGINS_PATH exists and is writable
log "  Checking mu-plugins path: ${MU_PLUGINS_PATH}"
if ! $SSH_CMD "test -d '${MU_PLUGINS_PATH}' && test -w '${MU_PLUGINS_PATH}' && echo WRITABLE" 2>/dev/null | grep -q 'WRITABLE'; then
    err "MU_PLUGINS_PATH not writable or doesn't exist: ${MU_PLUGINS_PATH}"
    exit 1
fi
log "  mu-plugins path: writable"
sleep 2

# 6. WP-CLI available
log "  Testing WP-CLI on target..."
WP_VERSION=$($SSH_CMD "cd '${WP_PATH}' && wp core version 2>/dev/null" 2>/dev/null || echo "FAILED")
if [ "$WP_VERSION" = "FAILED" ]; then
    err "WP-CLI not available or WP_PATH incorrect: ${WP_PATH}"
    exit 1
fi
log "  WordPress version: ${WP_VERSION}"
sleep 2

log "Pre-flight: ALL CHECKS PASSED"
sep
echo ""

# --- Files that would be deployed ---
ALL_DEPLOY_FILES=("${EXPECTED_FILES[@]}")
if [ "$HAS_URLS_FILE" = true ]; then
    ALL_DEPLOY_FILES+=("$URLS_FILE")
fi

# =============================================================================
# DRY RUN — stop here with summary
# =============================================================================
if [ "$DRY_RUN" = true ]; then
    log "DRY RUN SUMMARY"
    sep
    echo ""
    echo "  Site:      ${SITE_NAME} (${SITE_SLUG})"
    echo "  Target:    ${SSH_USER}@${SSH_HOST}:${MU_PLUGINS_PATH}"
    echo "  WP:        ${WP_VERSION}"
    echo ""
    echo "  Files that WOULD be deployed:"
    for f in "${ALL_DEPLOY_FILES[@]}"; do
        LOCAL_FILE="${RENDERED_DIR}/${f}"
        LOCAL_SIZE=$(wc -c < "$LOCAL_FILE" | tr -d ' ')
        echo "    ${f}  (${LOCAL_SIZE} bytes)"
    done
    echo ""
    echo "  Pre-flight: PASSED"
    echo "  Mode: DRY RUN — no files uploaded, no modifications made"
    echo ""
    exit 0
fi

# =============================================================================
# B. BACKUP EXISTING FILES
# =============================================================================
log "BACKUP EXISTING FILES"
sep

$SSH_CMD "mkdir -p '${BACKUP_DIR}'" 2>/dev/null
log "  Backup dir: ${BACKUP_DIR}"

BACKED_UP=0
for f in "${ALL_DEPLOY_FILES[@]}"; do
    TARGET_FILE="${MU_PLUGINS_PATH}${f}"
    EXISTS=$($SSH_CMD "test -f '${TARGET_FILE}' && echo YES || echo NO" 2>/dev/null)
    if [ "$EXISTS" = "YES" ]; then
        $SSH_CMD "cp '${TARGET_FILE}' '${BACKUP_DIR}/${f}'" 2>/dev/null
        log "  Backed up: ${f}"
        BACKED_UP=$((BACKED_UP + 1))
    else
        log "  No existing: ${f} (new install)"
    fi
    sleep 1
done

log "Backup: ${BACKED_UP} files backed up"
sep
echo ""

# =============================================================================
# C. UPLOAD FILES
# =============================================================================
log "UPLOADING MU-PLUGINS"
sep

UPLOADED=0
UPLOAD_FAILED=()

for f in "${ALL_DEPLOY_FILES[@]}"; do
    LOCAL_FILE="${RENDERED_DIR}/${f}"
    REMOTE_PATH="${MU_PLUGINS_PATH}${f}"

    LOCAL_SIZE=$(wc -c < "$LOCAL_FILE" | tr -d ' ')

    log "  Uploading: ${f} (${LOCAL_SIZE} bytes)"
    if ! $SCP_CMD "$LOCAL_FILE" "${SSH_USER}@${SSH_HOST}:${REMOTE_PATH}" 2>/dev/null; then
        err "  SCP failed for: ${f}"
        UPLOAD_FAILED+=("$f")
        continue
    fi

    # Verify upload
    REMOTE_SIZE=$($SSH_CMD "wc -c < '${REMOTE_PATH}'" 2>/dev/null | tr -d ' ')
    if [ "$LOCAL_SIZE" != "$REMOTE_SIZE" ]; then
        err "  Size mismatch for ${f}: local=${LOCAL_SIZE} remote=${REMOTE_SIZE}"
        UPLOAD_FAILED+=("$f")
        continue
    fi

    log "  Verified: ${f} (${REMOTE_SIZE} bytes)"
    UPLOADED=$((UPLOADED + 1))
    sleep 3
done

if [ ${#UPLOAD_FAILED[@]} -gt 0 ]; then
    err "Upload failed for: ${UPLOAD_FAILED[*]}"
    err "Rollback: $SSH_CMD 'cp ${BACKUP_DIR}/* ${MU_PLUGINS_PATH}'"
    exit 1
fi

log "Upload: ${UPLOADED} files deployed"
sep
echo ""

# =============================================================================
# D. VERIFICATION
# =============================================================================
log "VERIFICATION"
sep

sleep 3
MU_COUNT=$($SSH_CMD "cd '${WP_PATH}' && wp eval 'echo count(get_mu_plugins());'" 2>/dev/null || echo "ERROR")
log "  MU plugins loaded on target: ${MU_COUNT}"

FUNC_CHECK="${SITE_PREFIX}_llms_get_config"
FUNC_EXISTS=$($SSH_CMD "cd '${WP_PATH}' && wp eval 'echo function_exists(\"${FUNC_CHECK}\") ? \"OK\" : \"MISSING\";'" 2>/dev/null || echo "ERROR")
log "  Function ${FUNC_CHECK}(): ${FUNC_EXISTS}"
sleep 2

FUNC_CHECK2="${SITE_PREFIX}_ai_crawler_detect"
FUNC_EXISTS2=$($SSH_CMD "cd '${WP_PATH}' && wp eval 'echo function_exists(\"${FUNC_CHECK2}\") ? \"OK\" : \"MISSING\";'" 2>/dev/null || echo "ERROR")
log "  Function ${FUNC_CHECK2}(): ${FUNC_EXISTS2}"
sleep 2

FUNC_CHECK3="${SITE_PREFIX}_md_html_to_markdown"
FUNC_EXISTS3=$($SSH_CMD "cd '${WP_PATH}' && wp eval 'echo function_exists(\"${FUNC_CHECK3}\") ? \"OK\" : \"MISSING\";'" 2>/dev/null || echo "ERROR")
log "  Function ${FUNC_CHECK3}(): ${FUNC_EXISTS3}"
sleep 2

# =============================================================================
# E. STATIC FILE GENERATION
# =============================================================================
log "STATIC FILE GENERATION"
sep

log "  Generating static /llms.txt..."
$SSH_CMD "cd '${WP_PATH}' && wp eval '
    if ( function_exists( \"${SITE_PREFIX}_llms_txt_write_static\" ) ) {
        ${SITE_PREFIX}_llms_txt_write_static();
        echo \"llms.txt written\";
    } else {
        echo \"Function not found — skipping\";
    }
'" 2>/dev/null || log "  (llms.txt generation skipped or failed)"
sleep 3

log "  Generating static /llms-full.txt..."
$SSH_CMD "cd '${WP_PATH}' && wp eval '
    if ( function_exists( \"${SITE_PREFIX}_llms_full_regenerate\" ) ) {
        ${SITE_PREFIX}_llms_full_regenerate();
        echo \"llms-full.txt written\";
    } else {
        echo \"Function not found — skipping\";
    }
'" 2>/dev/null || log "  (llms-full.txt generation skipped or failed)"
sleep 3

log "  Flushing rewrite rules..."
$SSH_CMD "cd '${WP_PATH}' && wp rewrite flush" 2>/dev/null || log "  (rewrite flush failed)"
sleep 2

log "  Flushing cache..."
$SSH_CMD "cd '${WP_PATH}' && wp cache flush" 2>/dev/null || log "  (cache flush failed)"

sep
echo ""

# =============================================================================
# SUMMARY
# =============================================================================
log "DEPLOYMENT COMPLETE"
sep
echo ""
echo "  Site:      ${SITE_NAME} (${SITE_SLUG})"
echo "  Target:    ${SSH_USER}@${SSH_HOST}:${MU_PLUGINS_PATH}"
echo "  Files:     ${UPLOADED} mu-plugins deployed"
echo "  Backups:   ${BACKUP_DIR}"
echo ""
echo "  Function checks:"
echo "    ${SITE_PREFIX}_llms_get_config():        ${FUNC_EXISTS}"
echo "    ${SITE_PREFIX}_ai_crawler_detect():      ${FUNC_EXISTS2}"
echo "    ${SITE_PREFIX}_md_html_to_markdown():    ${FUNC_EXISTS3}"
echo ""
echo "  Next steps:"
echo "    1. Visit https://${SITE_DOMAIN}/llms.txt to verify"
echo "    2. Visit any page with ?format=md to test markdown"
echo "    3. Check WP Admin → AI Crawlers dashboard"
echo ""
echo "  Rollback command:"
echo "    $SSH_CMD 'cp ${BACKUP_DIR}/* ${MU_PLUGINS_PATH} && rm ${MU_PLUGINS_PATH}/${SITE_PREFIX}-*.php'"
echo ""
