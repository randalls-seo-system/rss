#!/bin/bash
# =============================================================================
# RSS Schema Module — Template Renderer
# =============================================================================
# Renders schema mu-plugins: FAQ schema, schema cleaner, org ID canonicalizer.
#
# Usage:
#   ./modules/schema/render.sh <path-to-site.conf>
#
# Output:
#   modules/schema/rendered/<SITE_SLUG>/
#     ├── <SITE_PREFIX>-faq-schema.php
#     ├── <SITE_PREFIX>-schema-cleaner.php
#     └── <SITE_PREFIX>-org-id.php
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
[ -z "${SITE_NAME:-}" ]    && MISSING="$MISSING SITE_NAME"

if [ -n "$MISSING" ]; then
    echo "ERROR: Missing required config variables:$MISSING"
    exit 1
fi

FORM_PAGE_SLUG="${FORM_PAGE_SLUG:-}"

OUTPUT_DIR="${SCRIPT_DIR}/rendered/${SITE_SLUG}"
mkdir -p "$OUTPUT_DIR"

echo "Rendering Schema templates for: ${SITE_NAME} (${SITE_SLUG})"
echo "  Config:    ${CONFIG_PATH}"
echo "  Templates: ${TEMPLATE_DIR}/"
echo "  Output:    ${OUTPUT_DIR}/"
echo ""

RENDERED=0
for template in "$TEMPLATE_DIR"/*.template.php; do
    [ -f "$template" ] || continue

    base_name=$(basename "$template" .template.php)
    output_file="${SITE_PREFIX}-${base_name}.php"

    sed \
        -e "s|{{SITE_PREFIX_UPPER}}|${SITE_PREFIX_UPPER}|g" \
        -e "s|{{SITE_PREFIX}}|${SITE_PREFIX}|g" \
        -e "s|{{SITE_NAME}}|${SITE_NAME}|g" \
        -e "s|{{SITE_URL}}|${SITE_URL:-}|g" \
        -e "s|{{SITE_DOMAIN}}|${SITE_DOMAIN:-}|g" \
        -e "s|{{FORM_PAGE_SLUG}}|${FORM_PAGE_SLUG}|g" \
        "$template" > "${OUTPUT_DIR}/${output_file}"

    echo "  + ${output_file}"
    RENDERED=$((RENDERED + 1))
done

echo ""
echo "Done. ${RENDERED} templates rendered to ${OUTPUT_DIR}/"

if command -v php &>/dev/null; then
    echo ""
    echo "Running PHP lint..."
    LINT_FAIL=0
    for f in "${OUTPUT_DIR}"/*.php; do
        if ! php -l "$f" 2>/dev/null | grep -q "No syntax errors"; then
            echo "  X LINT FAIL: $(basename "$f")"
            LINT_FAIL=$((LINT_FAIL + 1))
        else
            echo "  + $(basename "$f")"
        fi
    done
    if [ $LINT_FAIL -gt 0 ]; then
        echo "ERROR: ${LINT_FAIL} file(s) failed PHP lint"
        exit 1
    fi
    echo "All files pass PHP lint."
fi
