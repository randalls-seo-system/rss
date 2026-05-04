#!/bin/bash
# =============================================================================
# RSS Technical SEO Module — Template Renderer
# =============================================================================
# Takes a site config (.conf) and renders all template files into deployable
# mu-plugins with site-specific values.
#
# Usage:
#   ./modules/technical-seo/render.sh <path-to-site.conf>
#
# Example:
#   ./modules/technical-seo/render.sh sites/tln.conf
#
# Output:
#   modules/technical-seo/rendered/<SITE_SLUG>/
#     ├── <SITE_PREFIX>-llms-config.php
#     ├── <SITE_PREFIX>-llms-txt.php
#     ├── <SITE_PREFIX>-ai-crawler-log.php
#     ├── <SITE_PREFIX>-markdown-variants.php
#     ├── <SITE_PREFIX>-llms-full-txt.php
#     ├── <SITE_PREFIX>-dashboard-ai-crawlers.php
#     └── <SITE_PREFIX>-llms-urls.php  (copied from CONFIG_URLS_FILE)
# =============================================================================

set -euo pipefail

# --- Resolve paths ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE_DIR="${SCRIPT_DIR}/templates"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

# --- Validate argument ---
if [ $# -lt 1 ]; then
    echo "Usage: $0 <path-to-site.conf>"
    echo "  Config path can be absolute or relative to repo root."
    exit 1
fi

CONFIG_PATH="$1"
# If relative, resolve from repo root
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

# --- Validate required variables ---
MISSING=""
[ -z "${SITE_PREFIX:-}" ]  && MISSING="$MISSING SITE_PREFIX"
[ -z "${SITE_SLUG:-}" ]    && MISSING="$MISSING SITE_SLUG"
[ -z "${SITE_NAME:-}" ]    && MISSING="$MISSING SITE_NAME"
[ -z "${SITE_URL:-}" ]     && MISSING="$MISSING SITE_URL"

if [ -n "$MISSING" ]; then
    echo "ERROR: Missing required config variables:$MISSING"
    exit 1
fi

# --- Set defaults for optional variables ---
FORM_PAGE_SLUG="${FORM_PAGE_SLUG:-}"
SITE_PHONE="${SITE_PHONE:-}"
SITE_DOMAIN="${SITE_DOMAIN:-}"

# --- Create output directory ---
OUTPUT_DIR="${SCRIPT_DIR}/rendered/${SITE_SLUG}"
mkdir -p "$OUTPUT_DIR"

echo "Rendering templates for: ${SITE_NAME} (${SITE_SLUG})"
echo "  Config:    ${CONFIG_PATH}"
echo "  Templates: ${TEMPLATE_DIR}/"
echo "  Output:    ${OUTPUT_DIR}/"
echo ""

# --- Render each template ---
RENDERED=0
for template in "$TEMPLATE_DIR"/*.template.php; do
    [ -f "$template" ] || continue

    # llms-config.template.php → llms-config → <prefix>-llms-config.php
    base_name=$(basename "$template" .template.php)
    output_file="${SITE_PREFIX}-${base_name}.php"

    # Replace longer patterns first to avoid partial matches
    sed \
        -e "s|{{SITE_PREFIX_UPPER}}|${SITE_PREFIX_UPPER}|g" \
        -e "s|{{SITE_PREFIX}}|${SITE_PREFIX}|g" \
        -e "s|{{SITE_NAME}}|${SITE_NAME}|g" \
        -e "s|{{SITE_URL}}|${SITE_URL}|g" \
        -e "s|{{SITE_DOMAIN}}|${SITE_DOMAIN}|g" \
        -e "s|{{SITE_PHONE}}|${SITE_PHONE}|g" \
        -e "s|{{FORM_PAGE_SLUG}}|${FORM_PAGE_SLUG}|g" \
        "$template" > "${OUTPUT_DIR}/${output_file}"

    echo "  ✓ ${output_file}"
    RENDERED=$((RENDERED + 1))
done

# --- Copy URLs config file if specified ---
if [ -n "${CONFIG_URLS_FILE:-}" ]; then
    # Resolve relative path
    URLS_PATH="$CONFIG_URLS_FILE"
    if [[ "$URLS_PATH" != /* ]]; then
        URLS_PATH="${REPO_ROOT}/${URLS_PATH}"
    fi

    if [ -f "$URLS_PATH" ]; then
        cp "$URLS_PATH" "${OUTPUT_DIR}/${SITE_PREFIX}-llms-urls.php"
        echo "  ✓ ${SITE_PREFIX}-llms-urls.php (URL config)"
    else
        echo "  ⚠ CONFIG_URLS_FILE not found: ${URLS_PATH}"
        echo "    llms-config will use fallback empty config"
    fi
else
    echo "  ⚠ CONFIG_URLS_FILE not set — llms-config will use fallback empty config"
fi

echo ""
echo "Done. ${RENDERED} templates rendered to ${OUTPUT_DIR}/"
echo ""

# --- PHP lint check (if php available) ---
if command -v php &>/dev/null; then
    echo "Running PHP lint..."
    LINT_FAIL=0
    for f in "${OUTPUT_DIR}"/*.php; do
        if ! php -l "$f" 2>/dev/null | grep -q "No syntax errors"; then
            echo "  ✗ LINT FAIL: $(basename "$f")"
            LINT_FAIL=$((LINT_FAIL + 1))
        else
            echo "  ✓ $(basename "$f")"
        fi
    done
    if [ $LINT_FAIL -gt 0 ]; then
        echo "ERROR: ${LINT_FAIL} file(s) failed PHP lint"
        exit 1
    fi
    echo "All files pass PHP lint."
else
    echo "Note: php not found locally — skipping lint check."
    echo "Files should be lint-checked on the target server before activation."
fi
