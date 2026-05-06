#!/usr/bin/env bash
# Deploy CSS bundle to WP Engine via mu-plugin.
#
# Usage:
#   ./deploy-css.sh --site lrg --target staging
#   ./deploy-css.sh --site lrg --target production --bundle-dir ~/lrg-rewrite/css-deploy/
#
# Safety: backs up current deployed CSS before overwriting.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$(dirname "$MODULE_DIR")")"

SITE=""
BUNDLE_DIR=""
TARGET="staging"
VERSION=""
SKIP_CACHE_FLUSH=false
DRY_RUN=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --site)              SITE="$2"; shift 2 ;;
        --bundle-dir)        BUNDLE_DIR="$2"; shift 2 ;;
        --target)            TARGET="$2"; shift 2 ;;
        --version)           VERSION="$2"; shift 2 ;;
        --skip-cache-flush)  SKIP_CACHE_FLUSH=true; shift ;;
        --dry-run)           DRY_RUN=true; shift ;;
        *) echo "Unknown arg: $1" >&2; exit 1 ;;
    esac
done

if [ -z "$SITE" ]; then
    echo "Usage: $0 --site <slug> [--target staging|production] [--bundle-dir <path>] [--dry-run]"
    echo ""
    echo "Options:"
    echo "  --site <slug>          Site slug (reads sites/<slug>.conf)"
    echo "  --target <env>         staging or production (default: staging)"
    echo "  --bundle-dir <path>    Bundle directory (default: ~/<site>-rewrite/css-deploy/)"
    echo "  --version <string>     Override version (default: from manifest.json)"
    echo "  --skip-cache-flush     Don't flush WP cache after deploy"
    echo "  --dry-run              Show what would be deployed"
    exit 1
fi

# Load site config
SITE_CONFIG="${ROOT_DIR}/sites/${SITE}.conf"
if [ ! -f "$SITE_CONFIG" ]; then
    echo "ERROR: Site config not found: $SITE_CONFIG" >&2
    exit 1
fi
source "$SITE_CONFIG"

# Resolve paths
BUNDLE_DIR="${BUNDLE_DIR:-$HOME/${SITE}-rewrite/css-deploy}"
if [ -z "$VERSION" ] && [ -f "${BUNDLE_DIR}/manifest.json" ]; then
    VERSION=$(python3 -c "import json; print(json.load(open('${BUNDLE_DIR}/manifest.json'))['version'])")
fi
VERSION="${VERSION:-1.0.0}"

SSH_OPTS="-i ${SSH_KEY_PATH} -o IdentitiesOnly=yes -o ConnectTimeout=15"
MU_DIR="${WP_PATH}wp-content/mu-plugins"
CSS_DIR="${MU_DIR}/rl-css-loader/css"
LOG_FILE="/tmp/${SITE}-css-deploy.log"

echo "=== CSS Deployment ===" | tee "$LOG_FILE"
echo "Site: ${SITE_NAME}" | tee -a "$LOG_FILE"
echo "Target: ${TARGET}" | tee -a "$LOG_FILE"
echo "Version: ${VERSION}" | tee -a "$LOG_FILE"
echo "Bundle: ${BUNDLE_DIR}" | tee -a "$LOG_FILE"
echo "Dry run: ${DRY_RUN}" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# Verify bundle files exist
for f in rl-base.css "rl-${SITE}-theme.css" rl-css-loader.php; do
    if [ ! -f "${BUNDLE_DIR}/${f}" ]; then
        echo "ERROR: Missing bundle file: ${BUNDLE_DIR}/${f}" >&2
        echo "Run build-css-bundle.py first." >&2
        exit 1
    fi
done

# Verify manifest integrity
if [ -f "${BUNDLE_DIR}/manifest.json" ]; then
    echo "Verifying bundle integrity..." | tee -a "$LOG_FILE"
    python3 -c "
import json, os, sys
manifest = json.load(open('${BUNDLE_DIR}/manifest.json'))
for fname, expected_size in manifest['files'].items():
    path = os.path.join('${BUNDLE_DIR}', fname)
    actual = os.path.getsize(path)
    if actual != expected_size:
        print(f'MISMATCH: {fname} expected {expected_size}, got {actual}', file=sys.stderr)
        sys.exit(1)
    print(f'  {fname}: {actual:,} bytes OK')
" || exit 1
fi

if [ "$DRY_RUN" = true ]; then
    echo "" | tee -a "$LOG_FILE"
    echo "[DRY RUN] Would deploy:" | tee -a "$LOG_FILE"
    echo "  ${BUNDLE_DIR}/rl-base.css → ${CSS_DIR}/rl-base.css" | tee -a "$LOG_FILE"
    echo "  ${BUNDLE_DIR}/rl-${SITE}-theme.css → ${CSS_DIR}/rl-${SITE}-theme.css" | tee -a "$LOG_FILE"
    echo "  ${BUNDLE_DIR}/rl-css-loader.php → ${MU_DIR}/rl-css-loader.php" | tee -a "$LOG_FILE"
    echo "  Version: ${VERSION}" | tee -a "$LOG_FILE"
    [ "$SKIP_CACHE_FLUSH" = false ] && echo "  Would flush WP cache" | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
    echo "=== Dry run complete ===" | tee -a "$LOG_FILE"
    exit 0
fi

# Step 1: Backup current deployed CSS
BACKUP_DIR="${BUNDLE_DIR}/backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
echo "Backing up current deployment..." | tee -a "$LOG_FILE"
ssh $SSH_OPTS "${SSH_USER}@${SSH_HOST}" "cat ${CSS_DIR}/rl-base.css 2>/dev/null" > "${BACKUP_DIR}/rl-base.css" 2>/dev/null || true
ssh $SSH_OPTS "${SSH_USER}@${SSH_HOST}" "cat ${CSS_DIR}/rl-${SITE}-theme.css 2>/dev/null" > "${BACKUP_DIR}/rl-${SITE}-theme.css" 2>/dev/null || true
ssh $SSH_OPTS "${SSH_USER}@${SSH_HOST}" "cat ${MU_DIR}/rl-css-loader.php 2>/dev/null" > "${BACKUP_DIR}/rl-css-loader.php" 2>/dev/null || true
echo "  Backup: ${BACKUP_DIR}" | tee -a "$LOG_FILE"

# Step 2: Create remote directories
echo "Creating remote directories..." | tee -a "$LOG_FILE"
ssh $SSH_OPTS "${SSH_USER}@${SSH_HOST}" "mkdir -p ${CSS_DIR}"

# Step 3: Deploy files via SCP
echo "Deploying CSS files..." | tee -a "$LOG_FILE"
scp $SSH_OPTS "${BUNDLE_DIR}/rl-base.css" "${SSH_USER}@${SSH_HOST}:${CSS_DIR}/rl-base.css"
echo "  rl-base.css deployed" | tee -a "$LOG_FILE"
sleep 1

scp $SSH_OPTS "${BUNDLE_DIR}/rl-${SITE}-theme.css" "${SSH_USER}@${SSH_HOST}:${CSS_DIR}/rl-${SITE}-theme.css"
echo "  rl-${SITE}-theme.css deployed" | tee -a "$LOG_FILE"
sleep 1

scp $SSH_OPTS "${BUNDLE_DIR}/rl-css-loader.php" "${SSH_USER}@${SSH_HOST}:${MU_DIR}/rl-css-loader.php"
echo "  rl-css-loader.php deployed" | tee -a "$LOG_FILE"

# Step 4: Cache flush
if [ "$SKIP_CACHE_FLUSH" = false ]; then
    echo "Flushing WP cache..." | tee -a "$LOG_FILE"
    ssh $SSH_OPTS "${SSH_USER}@${SSH_HOST}" "cd ${WP_PATH} && wp cache flush" 2>> "$LOG_FILE"
fi

# Step 5: Verify mu-plugin loaded
echo "Verifying mu-plugin..." | tee -a "$LOG_FILE"
MU_CHECK=$(ssh $SSH_OPTS "${SSH_USER}@${SSH_HOST}" "cd ${WP_PATH} && wp eval 'echo count(wp_get_mu_plugins());'" 2>/dev/null)
echo "  Active mu-plugins: ${MU_CHECK}" | tee -a "$LOG_FILE"

# Step 6: Verify CSS files accessible
echo "Verifying CSS file access..." | tee -a "$LOG_FILE"
DOMAIN="${SITE_DOMAIN}"
for f in rl-base.css "rl-${SITE}-theme.css"; do
    CSS_URL="https://${DOMAIN}/wp-content/mu-plugins/rl-css-loader/css/${f}?v=${VERSION}"
    STATUS=$(curl -sI -o /dev/null -w "%{http_code}" --max-time 10 "$CSS_URL" 2>/dev/null)
    echo "  ${f}: HTTP ${STATUS}" | tee -a "$LOG_FILE"
done

echo "" | tee -a "$LOG_FILE"
echo "=== Deployment Complete ===" | tee -a "$LOG_FILE"
echo "Version: ${VERSION}" | tee -a "$LOG_FILE"
echo "Log: ${LOG_FILE}" | tee -a "$LOG_FILE"
