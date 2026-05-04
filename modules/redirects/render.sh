#!/bin/bash
# =============================================================================
# RSS Redirects Module — Template Renderer
# =============================================================================
# Renders redirect engine, 410 handler, and force-indexing mu-plugins.
#
# Usage:
#   ./modules/redirects/render.sh <path-to-site.conf>
#
# Output:
#   modules/redirects/rendered/<SITE_SLUG>/
#     ├── <SITE_PREFIX>-redirect-engine.php
#     ├── <SITE_PREFIX>-purge-410.php
#     └── <SITE_PREFIX>-force-enable-indexing.php
#
# NOTE: Redirect and 410 data files must be created separately:
#     ├── <SITE_PREFIX>-redirect-map.php   (in clients/<slug>/ or sites/)
#     └── <SITE_PREFIX>-410-patterns.php   (in clients/<slug>/ or sites/)
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

OUTPUT_DIR="${SCRIPT_DIR}/rendered/${SITE_SLUG}"
mkdir -p "$OUTPUT_DIR"

echo "Rendering Redirects templates for: ${SITE_NAME:-$SITE_SLUG} (${SITE_SLUG})"
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
        "$template" > "${OUTPUT_DIR}/${output_file}"

    echo "  + ${output_file}"
    RENDERED=$((RENDERED + 1))
done

# Generate empty companion data files if they don't exist
REDIRECT_MAP="${OUTPUT_DIR}/${SITE_PREFIX}-redirect-map.php"
PATTERNS_410="${OUTPUT_DIR}/${SITE_PREFIX}-410-patterns.php"

if [ ! -f "$REDIRECT_MAP" ]; then
    cat > "$REDIRECT_MAP" << 'PHPEOF'
<?php
/**
 * Redirect Map — add 301 redirects as '/old-path/' => '/new-path/'
 * Keys: normalized lowercase path with trailing slash
 * Values: destination path (relative) or full URL
 */
return [
    // '/old-page/' => '/new-page/',
];
PHPEOF
    echo "  + $(basename "$REDIRECT_MAP") (empty starter)"
    RENDERED=$((RENDERED + 1))
fi

if [ ! -f "$PATTERNS_410" ]; then
    cat > "$PATTERNS_410" << 'PHPEOF'
<?php
/**
 * 410 Patterns — paths that should return HTTP 410 Gone
 * Exact paths: '/old-page/' => true
 * Regex patterns: '#^/retired-section(/|$)#i' => true
 * Set value to false to disable a pattern without removing it.
 */
return [
    // '/retired-page/' => true,
    // '#^/old-blog(/|$)#i' => true,
];
PHPEOF
    echo "  + $(basename "$PATTERNS_410") (empty starter)"
    RENDERED=$((RENDERED + 1))
fi

echo ""
echo "Done. ${RENDERED} files rendered to ${OUTPUT_DIR}/"
