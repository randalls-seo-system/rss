#!/usr/bin/env bash
# Deploy approved meta proposals via WP-CLI.
# Usage: deploy-meta-updates.sh --site lrg --proposals-csv path.csv [--dry-run] [--batch-size 50]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SITES_DIR="$(cd "$SCRIPT_DIR/../../../sites" && pwd)"

# Defaults
BATCH_SIZE=50
DRY_RUN=false
SKIP_VERIFY=false
BACKUP_CSV=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --site) SITE="$2"; shift 2 ;;
    --proposals-csv) PROPOSALS="$2"; shift 2 ;;
    --batch-size) BATCH_SIZE="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --backup-csv) BACKUP_CSV="$2"; shift 2 ;;
    --skip-verification) SKIP_VERIFY=true; shift ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ -z "${SITE:-}" || -z "${PROPOSALS:-}" ]]; then
  echo "Usage: deploy-meta-updates.sh --site <slug> --proposals-csv <path> [--dry-run]"
  exit 1
fi

# Load site config
CONF="$SITES_DIR/$SITE.conf"
if [[ ! -f "$CONF" ]]; then echo "Config not found: $CONF"; exit 1; fi
source "$CONF"

SSH_CMD="ssh -i $SSH_KEY_PATH -o IdentitiesOnly=yes ${SSH_USER}@${SSH_HOST}"

# Auto backup path
if [[ -z "$BACKUP_CSV" ]]; then
  BACKUP_CSV="$(dirname "$PROPOSALS")/meta-backup-$(date +%Y%m%d-%H%M%S).csv"
fi

echo "=== Meta Update Deploy ==="
echo "Site: $SITE ($SITE_DOMAIN)"
echo "Proposals: $PROPOSALS"
echo "Backup: $BACKUP_CSV"
echo "Batch size: $BATCH_SIZE"
echo "Dry run: $DRY_RUN"
echo ""

# Initialize backup CSV
echo "post_id,old_yoast_title,old_yoast_meta,new_title,new_meta" > "$BACKUP_CSV"

count=0
success=0
fail=0

# Read proposals CSV (skip header)
tail -n +2 "$PROPOSALS" | while IFS=',' read -r post_id url current_title proposed_title title_len current_meta proposed_meta meta_len rest; do
  # Skip empty or error rows
  if [[ -z "$post_id" || "$post_id" == "?" || -z "$proposed_title" ]]; then
    continue
  fi

  count=$((count + 1))

  # Strip surrounding quotes
  proposed_title="${proposed_title#\"}"
  proposed_title="${proposed_title%\"}"
  proposed_meta="${proposed_meta#\"}"
  proposed_meta="${proposed_meta%\"}"

  if $DRY_RUN; then
    echo "DRY: $post_id | $proposed_title"
    continue
  fi

  # Backup current values
  old_title=$($SSH_CMD "wp post meta get $post_id _yoast_wpseo_title 2>/dev/null" 2>/dev/null || echo "")
  old_meta=$($SSH_CMD "wp post meta get $post_id _yoast_wpseo_metadesc 2>/dev/null" 2>/dev/null || echo "")

  echo "$post_id,\"$old_title\",\"$old_meta\",\"$proposed_title\",\"$proposed_meta\"" >> "$BACKUP_CSV"

  # Update title
  $SSH_CMD "wp post meta update $post_id _yoast_wpseo_title '$proposed_title'" 2>/dev/null
  t_exit=$?

  # Update meta
  $SSH_CMD "wp post meta update $post_id _yoast_wpseo_metadesc '$proposed_meta'" 2>/dev/null
  m_exit=$?

  if [[ $t_exit -eq 0 && $m_exit -eq 0 ]]; then
    success=$((success + 1))
    echo "OK $post_id | $proposed_title"
  else
    fail=$((fail + 1))
    echo "FAIL $post_id | title=$t_exit meta=$m_exit"
  fi

  sleep 3

  # Batch checkpoint
  if [[ $((count % BATCH_SIZE)) -eq 0 ]]; then
    echo "--- Batch checkpoint: $success ok, $fail fail ---"
    $SSH_CMD "wp cache flush" 2>/dev/null
    sleep 5
  fi
done

echo ""
echo "=== COMPLETE ==="
echo "Processed: $count"
echo "Success: $success"
echo "Failed: $fail"
echo "Backup: $BACKUP_CSV"
