#!/bin/bash
# =============================================================================
# RSS — Deploy All Enabled Modules to a Target Site
# =============================================================================
# Orchestration layer: reads site config, renders and deploys each
# enabled module in sequence.
#
# Usage:
#   ./tools/deploy-to-site.sh <path-to-site.conf>
#
# Example:
#   ./tools/deploy-to-site.sh sites/tln.conf
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# --- Validate argument ---
if [ $# -lt 1 ]; then
    echo "Usage: $0 <path-to-site.conf>"
    echo "  Config path can be absolute or relative to repo root."
    exit 1
fi

CONFIG_PATH="$1"
if [[ "$CONFIG_PATH" != /* ]]; then
    CONFIG_PATH="${REPO_ROOT}/${CONFIG_PATH}"
fi

if [ ! -f "$CONFIG_PATH" ]; then
    echo "ERROR: Config file not found: $CONFIG_PATH"
    exit 1
fi

# --- Source config ---
source "$CONFIG_PATH"

echo "============================================="
echo "RSS Deploy: ${SITE_NAME} (${SITE_SLUG})"
echo "============================================="
echo ""

MODULES_RUN=0
MODULES_FAIL=0

# --- Technical SEO Module ---
if [ "${TECHNICAL_SEO_ENABLED:-false}" = "true" ]; then
    echo ">>> Module: Technical SEO Infrastructure"
    echo ""

    # Step 1: Render templates
    echo "--- Rendering templates ---"
    if ! "${REPO_ROOT}/modules/technical-seo/render.sh" "$CONFIG_PATH"; then
        echo "ERROR: Technical SEO render failed"
        MODULES_FAIL=$((MODULES_FAIL + 1))
    else
        # Step 2: Deploy to target
        echo ""
        echo "--- Deploying to target ---"
        if ! "${REPO_ROOT}/modules/technical-seo/deploy.sh" "$CONFIG_PATH"; then
            echo "ERROR: Technical SEO deploy failed"
            MODULES_FAIL=$((MODULES_FAIL + 1))
        else
            MODULES_RUN=$((MODULES_RUN + 1))
        fi
    fi
    echo ""
else
    echo ">>> Technical SEO: DISABLED (skipping)"
fi

# --- QA Gates Module ---
if [ "${QA_GATES_ENABLED:-false}" = "true" ]; then
    echo ">>> Module: QA Gates"
    if [ -x "${REPO_ROOT}/modules/qa-gates/deploy.sh" ]; then
        if ! "${REPO_ROOT}/modules/qa-gates/deploy.sh" "$CONFIG_PATH"; then
            echo "ERROR: QA Gates deploy failed"
            MODULES_FAIL=$((MODULES_FAIL + 1))
        else
            MODULES_RUN=$((MODULES_RUN + 1))
        fi
    else
        echo "    QA Gates deploy.sh not yet built (Day 4)"
    fi
    echo ""
fi

# --- Summary ---
echo "============================================="
echo "DEPLOYMENT SUMMARY"
echo "============================================="
echo "  Site:           ${SITE_NAME}"
echo "  Modules run:    ${MODULES_RUN}"
echo "  Modules failed: ${MODULES_FAIL}"
echo ""

if [ $MODULES_FAIL -gt 0 ]; then
    echo "RESULT: PARTIAL FAILURE — check logs above"
    exit 1
fi

echo "RESULT: SUCCESS"
exit 0
