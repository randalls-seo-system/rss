#!/bin/bash
# =============================================================================
# RSS Onboarding — Intake Form to Site Config Converter
# =============================================================================
# Parses a completed intake markdown form and generates:
#   1. sites/<slug>.conf — site configuration
#   2. sites/<slug>-llms-urls.php — skeleton URL config
#   3. Prints a checklist of what needs manual completion
#
# Usage:
#   ./modules/onboarding/intake-to-config.sh <intake.md>
#
# Example:
#   ./modules/onboarding/intake-to-config.sh clients/acme/intake.md
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <path-to-intake.md>"
    exit 1
fi

INTAKE_FILE="$1"
if [[ "$INTAKE_FILE" != /* ]]; then
    INTAKE_FILE="${REPO_ROOT}/${INTAKE_FILE}"
fi

if [ ! -f "$INTAKE_FILE" ]; then
    echo "ERROR: Intake file not found: $INTAKE_FILE"
    exit 1
fi

# --- Parse key-value pairs from markdown ---
# Format: "- Field name: value" → extracts value after ": "
parse_field() {
    local label="$1"
    # Use awk to avoid sed delimiter issues with field names containing /
    grep -i "^- ${label}:" "$INTAKE_FILE" | head -1 | awk -F': ' '{print substr($0, index($0,": ")+2)}' | sed 's/ *(required[^)]*)//' | xargs
}

# --- Extract fields ---
SITE_NAME=$(parse_field "Site name")
SITE_DOMAIN=$(parse_field "Domain")
SITE_URL=$(parse_field "Site URL")
SITE_PREFIX=$(parse_field "Site prefix")
INDUSTRY=$(parse_field "Industry/vertical")
SERVICE_TIER=$(parse_field "Service tier")

SSH_HOST=$(parse_field "SSH host")
SSH_USER=$(parse_field "SSH user")
SSH_KEY_PATH=$(parse_field "SSH key path")
WP_PATH=$(parse_field "WordPress path")
MU_PLUGINS_PATH=$(parse_field "Mu-plugins path")

PRIMARY_COLOR=$(parse_field "Primary color")
SECONDARY_COLOR=$(parse_field "Secondary color")
LOGO_URL=$(parse_field "Logo URL")
SITE_PHONE=$(parse_field "Site phone")

NMLS_NUMBER=$(parse_field "NMLS number")
LICENSE_DISCLAIMER=$(parse_field "License disclaimer")

AUTHOR_NAME=$(parse_field "Primary author name")
AUTHOR_ID=$(parse_field "Primary author WP user ID")

FORM_PAGE_SLUG=$(parse_field "Form/application page slug")

# --- Derive slug ---
SITE_SLUG="${SITE_PREFIX}"

# --- Validate required fields ---
MISSING=""
[ -z "$SITE_NAME" ] && MISSING="$MISSING Site-name"
[ -z "$SITE_DOMAIN" ] && MISSING="$MISSING Domain"
[ -z "$SITE_URL" ] && MISSING="$MISSING Site-URL"
[ -z "$SITE_PREFIX" ] && MISSING="$MISSING Site-prefix"
[ -z "$SSH_HOST" ] && MISSING="$MISSING SSH-host"
[ -z "$SSH_USER" ] && MISSING="$MISSING SSH-user"
[ -z "$SSH_KEY_PATH" ] && MISSING="$MISSING SSH-key-path"
[ -z "$WP_PATH" ] && MISSING="$MISSING WordPress-path"
[ -z "$MU_PLUGINS_PATH" ] && MISSING="$MISSING Mu-plugins-path"

if [ -n "$MISSING" ]; then
    echo "ERROR: Missing required fields:$MISSING"
    echo "Fill in these fields in the intake form and re-run."
    exit 1
fi

# --- Generate site config ---
CONF_FILE="${REPO_ROOT}/sites/${SITE_SLUG}.conf"

cat > "$CONF_FILE" << CONF
# ${SITE_NAME} — Site Configuration
# Generated from intake form: $(date +%Y-%m-%d)
# Source: $(basename "$INTAKE_FILE")

# === Site Identity ===
SITE_DOMAIN="${SITE_DOMAIN}"
SITE_URL="${SITE_URL}"
SITE_NAME="${SITE_NAME}"
SITE_PREFIX="${SITE_PREFIX}"
SITE_SLUG="${SITE_SLUG}"

# === SSH/Hosting ===
SSH_HOST="${SSH_HOST}"
SSH_USER="${SSH_USER}"
SSH_KEY_PATH="${SSH_KEY_PATH}"
WP_PATH="${WP_PATH}"
MU_PLUGINS_PATH="${MU_PLUGINS_PATH}"

# === Brand ===
PRIMARY_COLOR="${PRIMARY_COLOR}"
SECONDARY_COLOR="${SECONDARY_COLOR}"
LOGO_URL="${LOGO_URL}"
SITE_PHONE="${SITE_PHONE}"

# === Content Configuration ===
CONFIG_URLS_FILE="sites/${SITE_SLUG}-llms-urls.php"
FORM_PAGE_SLUG="${FORM_PAGE_SLUG}"

# === Authors ===
PRIMARY_AUTHOR_ID="${AUTHOR_ID}"
PRIMARY_AUTHOR_NAME="${AUTHOR_NAME}"

# === NMLS / Compliance ===
NMLS_NUMBER="${NMLS_NUMBER}"
LICENSE_DISCLAIMER="${LICENSE_DISCLAIMER}"

# === Module Toggles ===
TECHNICAL_SEO_ENABLED=true
QA_GATES_ENABLED=true
LLM_INFRASTRUCTURE_ENABLED=true

# === Service Tier ===
SERVICE_TIER="${SERVICE_TIER:-Growth}"
CONF

echo "Generated: ${CONF_FILE}"

# --- Generate skeleton URLs config ---
URLS_FILE="${REPO_ROOT}/sites/${SITE_SLUG}-llms-urls.php"

cat > "$URLS_FILE" << 'URLS_HEADER'
<?php
/**
URLS_HEADER

cat >> "$URLS_FILE" << URLS_META
 * ${SITE_NAME} — LLMs URL Configuration
 *
 * Generated: $(date +%Y-%m-%d)
 * Status: SKELETON — needs manual content mapping
 *
 * TODO: Map this site's top pages into sections below.
 * See sites/valn-llms-urls.php for a complete example.
 */
URLS_META

cat >> "$URLS_FILE" << URLS_BODY
return [
    'intro' => '${SITE_NAME} — [TODO: Write 1-2 sentence site description for AI crawlers]',

    'disclosures' => '[TODO: Add required legal disclosures]',

    'sections' => [
        [
            'key'   => 'guides',
            'title' => 'Core Guides',
            'items' => [
                // TODO: Map top pages
                // [ 'id' => POST_ID, 'path' => '/slug/', 'title' => 'Page Title', 'desc' => 'Brief description' ],
            ],
        ],
        [
            'key'   => 'tools',
            'title' => 'Tools & Calculators',
            'items' => [],
        ],
    ],

    'contact' => [
        'cta'   => null,  // TODO: [ 'id' => POST_ID, 'path' => '/get-started/', 'title' => 'Get Started', 'desc' => '...' ]
        'phone' => '${SITE_PHONE}',
    ],

    'tool_post_ids' => [],
];
URLS_BODY

echo "Generated: ${URLS_FILE}"

# --- Print checklist ---
echo ""
echo "═══════════════════════════════════════════════"
echo "  Config generated for: ${SITE_NAME} (${SITE_SLUG})"
echo "═══════════════════════════════════════════════"
echo ""
echo "  Files created:"
echo "    ${CONF_FILE}"
echo "    ${URLS_FILE}"
echo ""
echo "  Manual steps remaining:"
echo "    [ ] Map site content into ${URLS_FILE}"
echo "    [ ] Verify SSH connection: ssh -i ${SSH_KEY_PATH} ${SSH_USER}@${SSH_HOST} 'echo OK'"
echo "    [ ] Test WP-CLI: ssh ... 'cd ${WP_PATH} && wp core version'"
echo "    [ ] Run: ./tools/new-client.sh sites/${SITE_SLUG}.conf"
echo ""
