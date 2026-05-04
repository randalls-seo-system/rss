#!/bin/bash
# =============================================================================
# RSS Analytics Module — Template Renderer
# =============================================================================
# Renders analytics head injection and form submit guard mu-plugins.
#
# Usage:
#   ./modules/analytics/render.sh <path-to-site.conf>
#
# Output:
#   modules/analytics/rendered/<SITE_SLUG>/
#     ├── <SITE_PREFIX>-analytics-head.php
#     └── <SITE_PREFIX>-form-submit-guard.php
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEMPLATE_DIR="${SCRIPT_DIR}/templates"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <path-to-site.conf>"
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

source "$CONFIG_PATH"

SITE_PREFIX_UPPER=$(echo "$SITE_PREFIX" | tr '[:lower:]' '[:upper:]')

MISSING=""
[ -z "${SITE_PREFIX:-}" ]  && MISSING="$MISSING SITE_PREFIX"
[ -z "${SITE_SLUG:-}" ]    && MISSING="$MISSING SITE_SLUG"

if [ -n "$MISSING" ]; then
    echo "ERROR: Missing required config variables:$MISSING"
    exit 1
fi

# Optional analytics variables — empty is valid (features disabled)
GTM_CONTAINER_ID="${GTM_CONTAINER_ID:-}"
META_PIXEL_ID="${META_PIXEL_ID:-}"
LEAD_FORM_ID="${LEAD_FORM_ID:-}"

OUTPUT_DIR="${SCRIPT_DIR}/rendered/${SITE_SLUG}"
mkdir -p "$OUTPUT_DIR"

echo "Rendering Analytics templates for: ${SITE_NAME:-$SITE_SLUG} (${SITE_SLUG})"
echo "  Output: ${OUTPUT_DIR}/"
echo ""

RENDERED=0
for template in "$TEMPLATE_DIR"/*.template.php; do
    [ -f "$template" ] || continue

    base_name=$(basename "$template" .template.php)
    output_file="${SITE_PREFIX}-${base_name}.php"

    sed \
        -e "s|{{SITE_PREFIX_UPPER}}|${SITE_PREFIX_UPPER}|g" \
        -e "s|{{SITE_PREFIX}}|${SITE_PREFIX}|g" \
        -e "s|{{SITE_NAME}}|${SITE_NAME:-}|g" \
        -e "s|{{SITE_URL}}|${SITE_URL:-}|g" \
        -e "s|{{GTM_CONTAINER_ID}}|${GTM_CONTAINER_ID}|g" \
        -e "s|{{META_PIXEL_ID}}|${META_PIXEL_ID}|g" \
        -e "s|{{LEAD_FORM_ID}}|${LEAD_FORM_ID}|g" \
        "$template" > "${OUTPUT_DIR}/${output_file}"

    echo "  + ${output_file}"
    RENDERED=$((RENDERED + 1))
done

echo ""
echo "Done. ${RENDERED} templates rendered to ${OUTPUT_DIR}/"
if [ -z "$GTM_CONTAINER_ID" ]; then echo "  Note: GTM_CONTAINER_ID not set — GTM output will be skipped at runtime"; fi
if [ -z "$META_PIXEL_ID" ]; then echo "  Note: META_PIXEL_ID not set — Meta Pixel output will be skipped at runtime"; fi
if [ -z "$LEAD_FORM_ID" ]; then echo "  Note: LEAD_FORM_ID not set — form guard will be inactive"; fi
