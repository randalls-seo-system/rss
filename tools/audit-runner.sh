#!/bin/bash
# =============================================================================
# RSS — Run QA Audit Suite on a Target Site
# =============================================================================
# Top-level orchestrator that calls the QA Gates module.
#
# Usage:
#   ./tools/audit-runner.sh <path-to-site.conf>
#   ./tools/audit-runner.sh <path-to-site.conf> --audit anchor-splits
#   ./tools/audit-runner.sh <path-to-site.conf> --output ~/reports/
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [ $# -lt 1 ]; then
    echo "Usage: $0 <path-to-site.conf> [--audit <name>] [--output <dir>]"
    echo ""
    echo "Available audits: anchor-splits, generic-anchors, repeated-urls, link-balance"
    exit 1
fi

# Pass all arguments through to the QA Gates module
exec "${REPO_ROOT}/modules/qa-gates/run-audit.sh" "$@"
