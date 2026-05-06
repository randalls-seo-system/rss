#!/usr/bin/env bash
# Deploy redirects to a WordPress site via Redirection plugin import CSV
# or by generating an mu-plugin PHP file.
#
# Usage:
#   ./deploy-redirects.sh <site-config> <redirect-csv> [--method plugin|mu-plugin] [--dry-run]
#
# Methods:
#   plugin     Generate Redirection plugin import CSV (default)
#              User imports manually via WP Admin > Tools > Redirection > Import
#   mu-plugin  Generate PHP mu-plugin for server-side redirects
#              Deployed via SCP to wp-content/mu-plugins/
#
# IMPORTANT: Always validate targets before deploying.
#   Run validate-redirect-targets.py first and confirm all targets return 200.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$(dirname "$MODULE_DIR")")"

# Parse arguments
SITE_CONFIG=""
REDIRECT_CSV=""
METHOD="plugin"
DRY_RUN=false
GROUP_NAME="RSS redirect cleanup"

while [[ $# -gt 0 ]]; do
    case $1 in
        --method)  METHOD="$2"; shift 2 ;;
        --dry-run) DRY_RUN=true; shift ;;
        --group)   GROUP_NAME="$2"; shift 2 ;;
        *)
            if [ -z "$SITE_CONFIG" ]; then
                SITE_CONFIG="$1"
            elif [ -z "$REDIRECT_CSV" ]; then
                REDIRECT_CSV="$1"
            fi
            shift ;;
    esac
done

if [ -z "$SITE_CONFIG" ] || [ -z "$REDIRECT_CSV" ]; then
    echo "Usage: $0 <site-config> <redirect-csv> [--method plugin|mu-plugin] [--dry-run]"
    echo ""
    echo "Methods:"
    echo "  plugin      Generate Redirection plugin import CSV (default)"
    echo "  mu-plugin   Generate PHP mu-plugin for server-side redirects"
    echo ""
    echo "Options:"
    echo "  --group NAME    Redirect group name (default: 'RSS redirect cleanup')"
    echo "  --dry-run       Show what would be generated without writing files"
    exit 1
fi

# Resolve config path
if [[ ! "$SITE_CONFIG" = /* ]]; then
    SITE_CONFIG="${ROOT_DIR}/${SITE_CONFIG}"
fi
if [[ ! "$REDIRECT_CSV" = /* ]]; then
    REDIRECT_CSV="${ROOT_DIR}/${REDIRECT_CSV}"
fi

source "$SITE_CONFIG"

SITE="${SITE_SLUG:-unknown}"
DOMAIN="${SITE_DOMAIN:-unknown}"
DATE=$(date +%Y-%m-%d)

echo "=== Redirect Deployment ==="
echo "Site: ${SITE_NAME}"
echo "Domain: ${DOMAIN}"
echo "Method: ${METHOD}"
echo "Input: ${REDIRECT_CSV}"
echo "Dry run: ${DRY_RUN}"
echo ""

# Count redirects
REDIRECT_COUNT=$(tail -n +2 "$REDIRECT_CSV" | wc -l | tr -d ' ')
echo "Redirects to deploy: ${REDIRECT_COUNT}"

if [ "$METHOD" = "plugin" ]; then
    # ── Redirection Plugin Import CSV ──────────────────────────────────────
    OUTPUT_FILE="${MODULE_DIR}/rendered/${SITE}/${SITE}-redirects-import-${DATE}.csv"
    mkdir -p "$(dirname "$OUTPUT_FILE")"

    echo ""
    echo "Generating Redirection plugin import CSV..."

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY RUN] Would generate: ${OUTPUT_FILE}"
        echo ""
        echo "Preview (first 5 rows):"
        echo "source,target,match_type,action_type,group_name,status,regex"
        tail -n +2 "$REDIRECT_CSV" | head -5 | while IFS=, read -r old_url new_url rest; do
            # Strip domain to get path
            source=$(echo "$old_url" | sed "s|https\?://${DOMAIN}||")
            target=$(echo "$new_url" | sed "s|https\?://${DOMAIN}||")
            echo "${source},${target},url,url,${GROUP_NAME},enabled,0"
        done
    else
        {
            echo "source,target,match_type,action_type,group_name,status,regex"
            tail -n +2 "$REDIRECT_CSV" | while IFS=, read -r old_url new_url rest; do
                source=$(echo "$old_url" | sed "s|https\?://${DOMAIN}||")
                target=$(echo "$new_url" | sed "s|https\?://${DOMAIN}||")
                echo "${source},${target},url,url,${GROUP_NAME},enabled,0"
            done
        } > "$OUTPUT_FILE"

        echo "Generated: ${OUTPUT_FILE}"
        echo ""
        echo "Next steps:"
        echo "  1. Review the CSV file"
        echo "  2. Go to WP Admin > Tools > Redirection > Import/Export"
        echo "  3. Import the CSV file"
        echo "  4. Run verify-redirects-live.py to confirm deployment"
    fi

elif [ "$METHOD" = "mu-plugin" ]; then
    # ── PHP mu-plugin ─────────────────────────────────────────────────────
    OUTPUT_FILE="${MODULE_DIR}/rendered/${SITE}/${SITE}-redirects-${DATE}.php"
    mkdir -p "$(dirname "$OUTPUT_FILE")"

    echo ""
    echo "Generating mu-plugin PHP..."

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY RUN] Would generate: ${OUTPUT_FILE}"
        echo ""
        echo "Preview (first 5 redirects):"
        tail -n +2 "$REDIRECT_CSV" | head -5 | while IFS=, read -r old_url new_url rest; do
            source=$(echo "$old_url" | sed "s|https\?://${DOMAIN}||")
            target=$(echo "$new_url" | sed "s|https\?://${DOMAIN}||")
            echo "  '${source}' => '${target}',"
        done
    else
        {
            cat <<'PHPHEADER'
<?php
/**
 * RSS Redirect Manager
 *
 * Auto-generated 301 redirects. Do not edit manually.
 * Generated by: modules/redirect-management/tools/deploy-redirects.sh
PHPHEADER
            echo " * Site: ${SITE_NAME}"
            echo " * Date: ${DATE}"
            echo " * Count: ${REDIRECT_COUNT}"
            echo " */"
            echo ""
            echo "add_action('template_redirect', function() {"
            echo "    \$redirects = ["

            tail -n +2 "$REDIRECT_CSV" | while IFS=, read -r old_url new_url rest; do
                source=$(echo "$old_url" | sed "s|https\?://${DOMAIN}||")
                target=$(echo "$new_url" | sed "s|https\?://${DOMAIN}||")
                echo "        '${source}' => '${target}',"
            done

            cat <<'PHPFOOTER'
    ];

    $request_uri = rtrim($_SERVER['REQUEST_URI'], '/');
    // Also check with trailing slash
    $request_uri_slash = $request_uri . '/';

    foreach ($redirects as $source => $target) {
        $source_clean = rtrim($source, '/');
        if ($request_uri === $source_clean || $request_uri_slash === $source . '/') {
            wp_redirect($target, 301);
            exit;
        }
    }
}, 1);
PHPFOOTER
        } > "$OUTPUT_FILE"

        echo "Generated: ${OUTPUT_FILE}"
        echo ""
        echo "Next steps:"
        echo "  1. Review the PHP file"
        echo "  2. Deploy to staging first:"
        echo "     scp ${OUTPUT_FILE} ${SSH_USER}@${SSH_HOST}:${MU_PLUGINS_PATH}${SITE}-redirects.php"
        echo "  3. Verify on staging with verify-redirects-live.py"
        echo "  4. Deploy to production after verification"
    fi

else
    echo "ERROR: Unknown method '${METHOD}'. Use 'plugin' or 'mu-plugin'." >&2
    exit 1
fi

echo ""
echo "=== Done ==="
