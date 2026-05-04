#!/bin/bash
# =============================================================================
# RSS — New Client Onboarding Orchestrator
# =============================================================================
# Full pipeline: intake → config → baseline audit → render → deploy →
# post-deploy audit → completion report.
#
# Usage:
#   ./tools/new-client.sh <intake.md>                    # full onboarding
#   ./tools/new-client.sh <intake.md> --dry-run          # pre-flight only
#   ./tools/new-client.sh <intake.md> --skip-deploy      # skip deploy step
#   ./tools/new-client.sh --use-config <site.conf>       # skip intake parsing
#   ./tools/new-client.sh --use-config <site.conf> --skip-deploy
#
# Flags:
#   --dry-run        Run pre-flight + render only, no SSH operations
#   --skip-deploy    Run audits but skip deploying mu-plugins
#   --use-config     Use existing .conf instead of parsing intake
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# --- Parse arguments ---
INPUT_FILE=""
DRY_RUN=false
SKIP_DEPLOY=false
USE_CONFIG=false

while [ $# -gt 0 ]; do
    case "$1" in
        --dry-run)       DRY_RUN=true; shift ;;
        --skip-deploy)   SKIP_DEPLOY=true; shift ;;
        --use-config)    USE_CONFIG=true; INPUT_FILE="$2"; shift 2 ;;
        *)               INPUT_FILE="$1"; shift ;;
    esac
done

if [ -z "$INPUT_FILE" ]; then
    echo "Usage: $0 <intake.md> [--dry-run] [--skip-deploy]"
    echo "       $0 --use-config <site.conf> [--skip-deploy]"
    exit 1
fi

if [[ "$INPUT_FILE" != /* ]]; then
    INPUT_FILE="${REPO_ROOT}/${INPUT_FILE}"
fi

if [ ! -f "$INPUT_FILE" ]; then
    echo "ERROR: File not found: $INPUT_FILE"
    exit 1
fi

# --- Logging ---
log() { echo "[$(date +%H:%M:%S)] $*"; }
err() { echo "[$(date +%H:%M:%S)] ERROR: $*" >&2; }
sep() { echo "════════════════════════════════════════════════"; }
step() { echo ""; echo ">>> STEP $1: $2"; sep; }

DATE_STAMP=$(date +%Y-%m-%d)

echo ""
sep
echo "  RSS New Client Onboarding"
if [ "$DRY_RUN" = true ]; then echo "  Mode: DRY RUN"; fi
if [ "$SKIP_DEPLOY" = true ]; then echo "  Mode: SKIP DEPLOY"; fi
sep

# =========================================================================
# STEP 1: Parse intake → generate config (or use existing)
# =========================================================================
if [ "$USE_CONFIG" = true ]; then
    step 1 "Using existing config"
    CONFIG_PATH="$INPUT_FILE"
    log "Config: $CONFIG_PATH"
else
    step 1 "Parse intake → generate config"
    log "Intake file: $INPUT_FILE"

    if ! "${REPO_ROOT}/modules/onboarding/intake-to-config.sh" "$INPUT_FILE"; then
        err "Intake parsing failed"
        exit 1
    fi

    # Determine generated config path from intake
    # Parse site prefix from intake to find the config
    SITE_PREFIX_PARSED=$(grep -i "^- Site prefix:" "$INPUT_FILE" | head -1 | sed 's/^- Site prefix: *//i' | sed 's/ *(required[^)]*)//' | xargs)
    if [ -z "$SITE_PREFIX_PARSED" ]; then
        err "Could not determine site prefix from intake"
        exit 1
    fi
    CONFIG_PATH="${REPO_ROOT}/sites/${SITE_PREFIX_PARSED}.conf"
fi

if [ ! -f "$CONFIG_PATH" ]; then
    err "Config not found: $CONFIG_PATH"
    exit 1
fi

source "$CONFIG_PATH"
log "Site: ${SITE_NAME} (${SITE_SLUG})"

# --- Create client directory ---
CLIENT_DIR="${REPO_ROOT}/clients/${SITE_SLUG}"
mkdir -p "${CLIENT_DIR}/audits" "${CLIENT_DIR}/notes"

# Copy intake if not using existing config
if [ "$USE_CONFIG" = false ] && [ -f "$INPUT_FILE" ]; then
    cp "$INPUT_FILE" "${CLIENT_DIR}/intake.md" 2>/dev/null || true
fi

# =========================================================================
# STEP 2: Validate site config
# =========================================================================
step 2 "Validate site config"

MISSING=""
[ -z "${SITE_PREFIX:-}" ] && MISSING="$MISSING SITE_PREFIX"
[ -z "${SITE_SLUG:-}" ] && MISSING="$MISSING SITE_SLUG"
[ -z "${SITE_NAME:-}" ] && MISSING="$MISSING SITE_NAME"
[ -z "${SITE_URL:-}" ] && MISSING="$MISSING SITE_URL"
[ -z "${SSH_HOST:-}" ] && MISSING="$MISSING SSH_HOST"
[ -z "${SSH_USER:-}" ] && MISSING="$MISSING SSH_USER"
[ -z "${SSH_KEY_PATH:-}" ] && MISSING="$MISSING SSH_KEY_PATH"
[ -z "${WP_PATH:-}" ] && MISSING="$MISSING WP_PATH"
[ -z "${MU_PLUGINS_PATH:-}" ] && MISSING="$MISSING MU_PLUGINS_PATH"

if [ -n "$MISSING" ]; then
    err "Missing config variables:$MISSING"
    exit 1
fi
log "Config validated: all required fields present"

if [ "$DRY_RUN" = false ]; then
    SSH_CMD="ssh -i ${SSH_KEY_PATH/#\~/$HOME} -o IdentitiesOnly=yes -o ConnectTimeout=10 -o BatchMode=yes -o StrictHostKeyChecking=accept-new ${SSH_USER}@${SSH_HOST}"

    log "Testing SSH to ${SSH_USER}@${SSH_HOST}..."
    if ! $SSH_CMD 'echo OK' 2>/dev/null | grep -q 'OK'; then
        err "SSH connection failed"
        exit 1
    fi
    log "SSH: OK"
    sleep 2

    WP_VERSION=$($SSH_CMD "cd '${WP_PATH}' && wp core version 2>/dev/null" 2>/dev/null || echo "FAILED")
    if [ "$WP_VERSION" = "FAILED" ]; then
        err "WP-CLI not available"
        exit 1
    fi
    log "WordPress: ${WP_VERSION}"
    sleep 2
else
    log "DRY RUN: Skipping SSH validation"
fi

# =========================================================================
# STEP 3: Baseline audit (pre-deployment)
# =========================================================================
if [ "$DRY_RUN" = false ]; then
    step 3 "Pre-deployment baseline audit"
    BASELINE_DIR="${CLIENT_DIR}/audits/baseline-${DATE_STAMP}"

    if "${REPO_ROOT}/modules/qa-gates/run-audit.sh" "$CONFIG_PATH" --output "$BASELINE_DIR"; then
        log "Baseline audit saved: ${BASELINE_DIR}/"
    else
        log "Baseline audit had issues (non-fatal, continuing)"
    fi
else
    step 3 "Pre-deployment baseline audit"
    log "DRY RUN: Skipping baseline audit"
fi

# =========================================================================
# STEP 4: Render Technical SEO module
# =========================================================================
if [ "${TECHNICAL_SEO_ENABLED:-false}" = "true" ]; then
    step 4 "Render Technical SEO templates"

    if ! "${REPO_ROOT}/modules/technical-seo/render.sh" "$CONFIG_PATH"; then
        err "Technical SEO render failed"
        exit 1
    fi
    log "Templates rendered successfully"
else
    step 4 "Render Technical SEO templates"
    log "TECHNICAL_SEO_ENABLED=false — skipping"
fi

# =========================================================================
# STEP 5: Deploy (unless --skip-deploy or --dry-run)
# =========================================================================
step 5 "Deploy Technical SEO module"

if [ "$DRY_RUN" = true ]; then
    log "DRY RUN: Running deploy pre-flight only"
    "${REPO_ROOT}/modules/technical-seo/deploy.sh" "$CONFIG_PATH" --dry-run || true
elif [ "$SKIP_DEPLOY" = true ]; then
    log "SKIP DEPLOY: Deploy step skipped per --skip-deploy flag"
elif [ "${TECHNICAL_SEO_ENABLED:-false}" = "true" ]; then
    if ! "${REPO_ROOT}/modules/technical-seo/deploy.sh" "$CONFIG_PATH"; then
        err "Deploy failed — check logs above"
        exit 1
    fi
    log "Deploy complete"
else
    log "TECHNICAL_SEO_ENABLED=false — skipping deploy"
fi

# =========================================================================
# STEP 6: Post-deployment audit
# =========================================================================
if [ "$DRY_RUN" = false ] && [ "$SKIP_DEPLOY" = false ]; then
    step 6 "Post-deployment verification audit"
    POSTDEPLOY_DIR="${CLIENT_DIR}/audits/post-deploy-${DATE_STAMP}"

    if "${REPO_ROOT}/modules/qa-gates/run-audit.sh" "$CONFIG_PATH" --output "$POSTDEPLOY_DIR"; then
        log "Post-deploy audit saved: ${POSTDEPLOY_DIR}/"
    else
        log "Post-deploy audit had issues (non-fatal)"
    fi
elif [ "$SKIP_DEPLOY" = true ] && [ "$DRY_RUN" = false ]; then
    step 6 "Post-deployment verification audit"
    log "Deploy was skipped — running audit against current state"
    POSTDEPLOY_DIR="${CLIENT_DIR}/audits/current-state-${DATE_STAMP}"

    if "${REPO_ROOT}/modules/qa-gates/run-audit.sh" "$CONFIG_PATH" --output "$POSTDEPLOY_DIR"; then
        log "Current-state audit saved: ${POSTDEPLOY_DIR}/"
    else
        log "Audit had issues (non-fatal)"
    fi
else
    step 6 "Post-deployment verification audit"
    log "DRY RUN: Skipping post-deploy audit"
fi

# =========================================================================
# STEP 7: Generate completion report + 30-day tasks
# =========================================================================
step 7 "Generate completion report"

REPORT_FILE="${CLIENT_DIR}/onboarding-complete-${DATE_STAMP}.md"

cat > "$REPORT_FILE" << REPORT
# Onboarding Complete — ${SITE_NAME}

**Date:** ${DATE_STAMP}
**Domain:** ${SITE_DOMAIN}
**Service Tier:** ${SERVICE_TIER:-Growth}
**Prefix:** ${SITE_PREFIX}

## Deployment Summary

- **Technical SEO Module:** $([ "${TECHNICAL_SEO_ENABLED:-false}" = "true" ] && echo "Deployed" || echo "Disabled")
- **QA Gates Audit:** $([ "$DRY_RUN" = false ] && echo "Completed" || echo "Skipped (dry run)")
$([ "$SKIP_DEPLOY" = true ] && echo "- **Note:** Deploy was skipped per --skip-deploy flag")
$([ "$DRY_RUN" = true ] && echo "- **Note:** This was a DRY RUN — no changes made")

## Mu-Plugins Deployed

1. \`${SITE_PREFIX}-llms-config.php\` — URL configuration for AI crawlers
2. \`${SITE_PREFIX}-llms-txt.php\` — /llms.txt endpoint
3. \`${SITE_PREFIX}-ai-crawler-log.php\` — Crawler tracking + DB table
4. \`${SITE_PREFIX}-markdown-variants.php\` — ?format=md handler
5. \`${SITE_PREFIX}-llms-full-txt.php\` — /llms-full.txt export
6. \`${SITE_PREFIX}-dashboard-ai-crawlers.php\` — Admin dashboard

## Audit Reports

- Baseline: \`audits/baseline-${DATE_STAMP}/\`
- Post-deploy: \`audits/post-deploy-${DATE_STAMP}/\`

## Next Steps

See \`30-day-tasks.md\` for the structured first-month plan.

---
Generated by RSS Onboarding v1.0
REPORT

log "Completion report: ${REPORT_FILE}"

# --- Generate 30-day task list ---
TASKS_TEMPLATE="${REPO_ROOT}/templates/first-30-days-template.md"
TASKS_FILE="${CLIENT_DIR}/30-day-tasks.md"

if [ -f "$TASKS_TEMPLATE" ]; then
    sed "s/{{SITE_NAME}}/${SITE_NAME}/g; s/{{SITE_PREFIX}}/${SITE_PREFIX}/g; s/{{SITE_DOMAIN}}/${SITE_DOMAIN}/g" \
        "$TASKS_TEMPLATE" > "$TASKS_FILE"
    log "30-day tasks: ${TASKS_FILE}"
else
    log "30-day template not found — skipping"
fi

# =========================================================================
# FINAL SUMMARY
# =========================================================================
echo ""
sep
echo "  ONBOARDING COMPLETE"
sep
echo ""
echo "  Site:       ${SITE_NAME} (${SITE_SLUG})"
echo "  Domain:     ${SITE_DOMAIN}"
echo "  Client dir: ${CLIENT_DIR}/"
echo ""
echo "  Files:"
echo "    ${REPORT_FILE}"
[ -f "$TASKS_FILE" ] && echo "    ${TASKS_FILE}"
echo ""
if [ "$DRY_RUN" = true ]; then
    echo "  Mode: DRY RUN — no changes were made"
elif [ "$SKIP_DEPLOY" = true ]; then
    echo "  Mode: Deploy skipped — audits ran against current state"
else
    echo "  Verification URLs:"
    echo "    https://${SITE_DOMAIN}/llms.txt"
    echo "    https://${SITE_DOMAIN}/?format=md"
    echo "    WP Admin → AI Crawlers dashboard"
fi
echo ""
