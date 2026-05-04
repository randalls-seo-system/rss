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
echo "  Modules: v1.0 (Technical SEO, QA Gates)"
echo "           v1.1 (Schema, Linking, Redirects, Analytics)"
echo "============================================="
echo ""

MODULES_RUN=0
MODULES_FAIL=0

# --- Helper: render-only module (no deploy.sh yet) ---
render_module() {
    local name="$1"
    local toggle="$2"
    local render_script="$3"

    if [ "${toggle}" = "true" ]; then
        echo ">>> Module: ${name}"
        if [ -x "${render_script}" ]; then
            if ! "${render_script}" "$CONFIG_PATH"; then
                echo "ERROR: ${name} render failed"
                MODULES_FAIL=$((MODULES_FAIL + 1))
            else
                MODULES_RUN=$((MODULES_RUN + 1))
            fi
        else
            echo "    ${name} render.sh not found: ${render_script}"
        fi
        echo ""
    else
        echo ">>> ${name}: DISABLED (skipping)"
    fi
}

# --- Technical SEO Module (v1.0) ---
if [ "${TECHNICAL_SEO_ENABLED:-false}" = "true" ]; then
    echo ">>> Module: Technical SEO Infrastructure"
    echo ""

    echo "--- Rendering templates ---"
    if ! "${REPO_ROOT}/modules/technical-seo/render.sh" "$CONFIG_PATH"; then
        echo "ERROR: Technical SEO render failed"
        MODULES_FAIL=$((MODULES_FAIL + 1))
    else
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

# --- QA Gates Module (v1.0) ---
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
        echo "    QA Gates: render-only (no deploy.sh)"
    fi
    echo ""
fi

# --- Schema Module (v1.1) ---
render_module "Schema" "${SCHEMA_ENABLED:-false}" "${REPO_ROOT}/modules/schema/render.sh"

# --- Linking Module (v1.1) ---
render_module "Linking" "${LINKING_ENABLED:-false}" "${REPO_ROOT}/modules/linking/render.sh"

# --- Redirects Module (v1.1) ---
render_module "Redirects" "${REDIRECTS_ENABLED:-false}" "${REPO_ROOT}/modules/redirects/render.sh"

# --- Analytics Module (v1.1) ---
render_module "Analytics" "${ANALYTICS_ENABLED:-false}" "${REPO_ROOT}/modules/analytics/render.sh"

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
