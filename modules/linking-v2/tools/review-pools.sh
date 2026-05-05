#!/usr/bin/env bash
# Generate review CSV and summary markdown from anchor pool JSON
# Usage: ./review-pools.sh <site-config>
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$(dirname "$MODULE_DIR")")"

if [ -z "${1:-}" ]; then
    echo "Usage: $0 <site-config-path>"
    exit 1
fi

SITE_CONFIG="$1"
if [[ ! "$SITE_CONFIG" = /* ]]; then
    SITE_CONFIG="${ROOT_DIR}/${SITE_CONFIG}"
fi

source "$SITE_CONFIG"

SITE="${SITE_SLUG:-unknown}"
POOL_FILE="${ROOT_DIR}/${ANCHOR_POOL_PATH:-sites/${SITE}-anchor-pools.json}"
DATE=$(date +%Y-%m-%d)
CSV_FILE="${ROOT_DIR}/sites/${SITE}-anchor-pools-review-${DATE}.csv"
SUMMARY_FILE="${ROOT_DIR}/sites/${SITE}-anchor-pools-summary-${DATE}.md"

if [ ! -f "$POOL_FILE" ]; then
    echo "ERROR: Anchor pool file not found: $POOL_FILE" >&2
    echo "Run generate-anchor-pool.sh first." >&2
    exit 1
fi

echo "=== Anchor Pool Review Generator ==="
echo "Pool file: $POOL_FILE"
echo "CSV output: $CSV_FILE"
echo "Summary output: $SUMMARY_FILE"
echo ""

DEST_COUNT=$(jq '.destinations | length' "$POOL_FILE")
MAX_ANCHORS=$(jq '[.destinations[].anchor_count] | max' "$POOL_FILE")

# === Generate CSV ===
echo -n "Generating review CSV..."

# Header row
HEADER="destination_url,primary_keyword,anchor_count"
for n in $(seq 1 "$MAX_ANCHORS"); do
    HEADER="${HEADER},anchor_${n}"
done
echo "$HEADER" > "$CSV_FILE"

# Data rows
jq -r '.destinations[] |
    [.url, .primary_keyword, (.anchor_count | tostring)] +
    .anchors +
    [range(.anchor_count; '"$MAX_ANCHORS"') | ""] |
    @csv' "$POOL_FILE" >> "$CSV_FILE"

echo " done ($DEST_COUNT rows)"

# === Generate Summary Markdown ===
echo -n "Generating summary markdown..."

# Collect stats
STATS=$(jq '.stats' "$POOL_FILE")
TOTAL=$(echo "$STATS" | jq '.total_destinations')
SUCCESSFUL=$(echo "$STATS" | jq '.successful')
FAILED=$(echo "$STATS" | jq '.failed')
TOTAL_ANCHORS=$(echo "$STATS" | jq '.total_anchors_generated')
AVG_ANCHORS=$(echo "$STATS" | jq '.avg_anchors_per_destination')
COST=$(echo "$STATS" | jq '.estimated_cost_usd')
ELAPSED=$(echo "$STATS" | jq '.elapsed_seconds')
PROVIDER=$(jq -r '.ai_provider' "$POOL_FILE")
MODEL=$(jq -r '.ai_model' "$POOL_FILE")
GEN_AT=$(jq -r '.generated_at' "$POOL_FILE")

# Anchor word count stats
WORD_STATS=$(jq -r '[.destinations[].anchors[]] |
    map(split(" ") | length) |
    {
        min: min,
        max: max,
        avg: ((add / length) * 10 | round / 10),
        total: length
    }' "$POOL_FILE")

AVG_WORDS=$(echo "$WORD_STATS" | jq '.avg')
MIN_WORDS=$(echo "$WORD_STATS" | jq '.min')
MAX_WORDS=$(echo "$WORD_STATS" | jq '.max')

# Check for duplicates within pools
DUPE_REPORT=$(jq -r '.destinations[] |
    .title as $title |
    [.anchors[] | ascii_downcase] |
    group_by(.) |
    map(select(length > 1)) |
    if length > 0 then
        "\($title): \(length) duplicate(s)"
    else
        empty
    end' "$POOL_FILE")

# Pool size distribution
SIZE_DIST=$(jq -r '[.destinations[].anchor_count] | group_by(.) | map({size: .[0], count: length}) | sort_by(.size) | .[] | "\(.size) anchors: \(.count) destination(s)"' "$POOL_FILE")

cat > "$SUMMARY_FILE" <<SUMMARY
# Anchor Pool Generation Summary

**Site:** ${SITE_NAME}
**Generated:** ${GEN_AT}
**Provider:** ${PROVIDER} / ${MODEL}

## Results

| Metric | Value |
|--------|-------|
| Destinations processed | ${TOTAL} |
| Successful | ${SUCCESSFUL} |
| Failed | ${FAILED} |
| Total anchors generated | ${TOTAL_ANCHORS} |
| Avg anchors per destination | ${AVG_ANCHORS} |
| Estimated cost | \$${COST} |
| Time elapsed | ${ELAPSED}s |

## Anchor Quality Stats

| Metric | Value |
|--------|-------|
| Avg word count per anchor | ${AVG_WORDS} |
| Min word count | ${MIN_WORDS} |
| Max word count | ${MAX_WORDS} |

### Pool Size Distribution

\`\`\`
${SIZE_DIST}
\`\`\`

### Duplicate Check

SUMMARY

if [ -z "$DUPE_REPORT" ]; then
    echo "No duplicates found within any pool." >> "$SUMMARY_FILE"
else
    echo "Duplicates found:" >> "$SUMMARY_FILE"
    echo '```' >> "$SUMMARY_FILE"
    echo "$DUPE_REPORT" >> "$SUMMARY_FILE"
    echo '```' >> "$SUMMARY_FILE"
fi

# Sample 5 destinations (or all if fewer)
SAMPLE_COUNT=$((DEST_COUNT < 5 ? DEST_COUNT : 5))

cat >> "$SUMMARY_FILE" <<SAMPLE

## Sample Anchor Pools (${SAMPLE_COUNT} destinations)

SAMPLE

# Pick evenly spaced samples
for idx in $(jq -n --argjson count "$DEST_COUNT" --argjson samples "$SAMPLE_COUNT" \
    '[ range(0; $samples) | (. * ($count / $samples)) | floor ] | .[]'); do

    DEST=$(jq ".destinations[$idx]" "$POOL_FILE")
    TITLE=$(echo "$DEST" | jq -r '.title')
    URL=$(echo "$DEST" | jq -r '.url')
    KEYWORD=$(echo "$DEST" | jq -r '.primary_keyword')
    ACOUNT=$(echo "$DEST" | jq '.anchor_count')

    cat >> "$SUMMARY_FILE" <<DESTBLOCK
### ${TITLE}

- **URL:** ${URL}
- **Primary Keyword:** ${KEYWORD}
- **Anchor Count:** ${ACOUNT}

| # | Anchor Text | Words |
|---|-------------|-------|
DESTBLOCK

    echo "$DEST" | jq -r '.anchors | to_entries[] | "\(.key + 1)|\(.value)|\(.value | split(" ") | length)"' | \
    while IFS='|' read -r num anchor words; do
        echo "| ${num} | ${anchor} | ${words} |" >> "$SUMMARY_FILE"
    done

    echo "" >> "$SUMMARY_FILE"
done

echo " done"
echo ""
echo "Review CSV: $CSV_FILE"
echo "Summary: $SUMMARY_FILE"
