#!/bin/bash
# ==========================================================
# Rank Logic — Article Rewrite Tool
# Usage: ./rewrite-article.sh <site_slug> <post_id>
#
# Pulls existing post, detects intent, generates rl-* article
# HTML, and pushes as draft via WP-CLI.
#
# Requirements:
#   - sites/<site_slug>.conf must exist
#   - SSH access configured
#   - SERPAPI_KEY env var set (optional, for SERP grounding)
#
# Safety:
#   - Drafts only (never publishes)
#   - Backs up original content before any write
#   - Single SSH connection at a time
#   - Sleep between DB writes
# ==========================================================

set -euo pipefail

SITE_SLUG="${1:?Usage: rewrite-article.sh <site_slug> <post_id>}"
POST_ID="${2:?Usage: rewrite-article.sh <site_slug> <post_id>}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
RSS_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
CONF_FILE="${RSS_ROOT}/sites/${SITE_SLUG}.conf"

if [ ! -f "$CONF_FILE" ]; then
  echo "ERROR: Config not found: $CONF_FILE"
  exit 1
fi

# shellcheck source=/dev/null
source "$CONF_FILE"

SSH_CMD="ssh -i ${SSH_KEY_PATH} -o IdentitiesOnly=yes ${SSH_USER}@${SSH_HOST}"
WORK_DIR="${HOME}/${SITE_SLUG}-rewrite"
BACKUP_DIR="${WORK_DIR}/backups"
SERP_DIR="${WORK_DIR}/serp-data"
ARTICLE_DIR="${WORK_DIR}/articles"
LOG_DIR="${WORK_DIR}/logs"

mkdir -p "$BACKUP_DIR" "$SERP_DIR" "$ARTICLE_DIR" "$LOG_DIR"

LOG_FILE="${LOG_DIR}/rewrite-${POST_ID}-$(date +%Y%m%d-%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== Rewrite started: Post ${POST_ID} on ${SITE_SLUG} ==="
echo "Timestamp: $(date)"

# 1. Get post current state
echo "--- Step 1: Pulling post metadata ---"
SLUG=$($SSH_CMD "wp post get ${POST_ID} --field=post_name" 2>/dev/null)
TITLE=$($SSH_CMD "wp post get ${POST_ID} --field=post_title" 2>/dev/null)
STATUS=$($SSH_CMD "wp post get ${POST_ID} --field=post_status" 2>/dev/null)

echo "  Slug: ${SLUG}"
echo "  Title: ${TITLE}"
echo "  Status: ${STATUS}"

# 2. Backup original content
echo "--- Step 2: Backing up original content ---"
BACKUP_FILE="${BACKUP_DIR}/${POST_ID}-${SLUG}-$(date +%Y%m%d-%H%M%S).html"
$SSH_CMD "wp post get ${POST_ID} --field=post_content" > "$BACKUP_FILE" 2>/dev/null
BACKUP_SIZE=$(wc -c < "$BACKUP_FILE" | tr -d ' ')
echo "  Backup saved: ${BACKUP_FILE} (${BACKUP_SIZE} bytes)"

if [ "$BACKUP_SIZE" -lt 100 ]; then
  echo "WARNING: Backup is very small (${BACKUP_SIZE} bytes). Post may be empty."
fi

# 3. Pull SerpAPI data (if key is set)
echo "--- Step 3: SERP data ---"
if [ -n "${SERPAPI_KEY:-}" ]; then
  KEYWORD=$(echo "$TITLE" | head -c 80)
  SERP_FILE="${SERP_DIR}/${SLUG}-serp.json"
  echo "  Querying SerpAPI for: ${KEYWORD}"
  curl -s "https://serpapi.com/search.json" \
    --data-urlencode "q=${KEYWORD}" \
    --data-urlencode "api_key=${SERPAPI_KEY}" \
    --data-urlencode "google_domain=google.com" \
    --data-urlencode "gl=us" \
    --data-urlencode "hl=en" \
    --data-urlencode "location=Texas" \
    > "$SERP_FILE"
  echo "  SERP data saved: ${SERP_FILE}"
  sleep 2
else
  echo "  SERPAPI_KEY not set — skipping SERP pull"
fi

# 4. Intent detection placeholder
echo "--- Step 4: Intent detection ---"
echo "  (Manual step: classify as Decision/Process/Comparison/News/Definition)"
echo "  Based on title: ${TITLE}"

# 5. Article generation placeholder
echo "--- Step 5: Article generation ---"
echo "  Template: modules/rl-components/templates/"
echo "  Output target: ${ARTICLE_DIR}/${SLUG}.html"
echo "  (This step requires Claude/AI generation — not automated in shell)"

# 6. Push as draft (placeholder — requires generated content)
echo "--- Step 6: Push to WP ---"
echo "  Target status: draft"
echo "  Post ID: ${POST_ID}"
echo "  (Skipped — waiting for article generation)"

echo ""
echo "=== Rewrite pipeline complete for Post ${POST_ID} ==="
echo "=== Next: Generate article HTML, then run push step ==="
