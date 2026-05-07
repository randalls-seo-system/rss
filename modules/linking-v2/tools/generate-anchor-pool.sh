#!/usr/bin/env bash
# Generate AI-powered anchor text pools for destination URLs
# Usage: ./generate-anchor-pool.sh <site-config> [--limit N] [--start N] [--ids id1,id2,...]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(dirname "$SCRIPT_DIR")"
LIB_DIR="${MODULE_DIR}/lib"
DATA_DIR="${MODULE_DIR}/data"
ROOT_DIR="$(dirname "$(dirname "$MODULE_DIR")")"

# Parse arguments
SITE_CONFIG=""
LIMIT=0
START=0
IDS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --limit) LIMIT="$2"; shift 2 ;;
        --start) START="$2"; shift 2 ;;
        --ids)   IDS="$2"; shift 2 ;;
        *)
            if [ -z "$SITE_CONFIG" ]; then
                SITE_CONFIG="$1"
            fi
            shift ;;
    esac
done

if [ -z "$SITE_CONFIG" ]; then
    echo "Usage: $0 <site-config> [--limit N] [--start N] [--ids id1,id2,...]"
    exit 1
fi

if [[ ! "$SITE_CONFIG" = /* ]]; then
    SITE_CONFIG="${ROOT_DIR}/${SITE_CONFIG}"
fi

source "$SITE_CONFIG"

# Source AI provider
source "${LIB_DIR}/ai-provider.sh"

SITE="${SITE_SLUG:-unknown}"
DEST_FILE="${DATA_DIR}/${SITE}-destinations.json"
OUTPUT_FILE="${ROOT_DIR}/${ANCHOR_POOL_PATH:-sites/${SITE}-anchor-pools.json}"
ERROR_LOG="${DATA_DIR}/anchor-pool-errors.log"
TMPDIR_LOCAL=$(mktemp -d)
trap 'rm -rf "$TMPDIR_LOCAL"' EXIT

echo "=== Anchor Pool Generator ==="
echo "Site: ${SITE_NAME}"
echo "Provider: ${AI_PROVIDER} / ${AI_MODEL}"
echo "Pool size: ${ANCHOR_POOL_SIZE_MIN}-${ANCHOR_POOL_SIZE_MAX}"
echo "Destinations: ${DEST_FILE}"
echo "Output: ${OUTPUT_FILE}"

# Verify destinations file exists
if [ ! -f "$DEST_FILE" ]; then
    echo "ERROR: Destinations file not found: $DEST_FILE" >&2
    echo "Run pull-destinations.sh first." >&2
    exit 1
fi

TOTAL_DEST=$(jq '.count' "$DEST_FILE")
echo "Total destinations available: $TOTAL_DEST"

# Build system prompt file
SYSTEM_PROMPT_FILE="${TMPDIR_LOCAL}/system-prompt.txt"
cat > "$SYSTEM_PROMPT_FILE" <<'SYSPROMPT'
You are an expert SEO strategist specializing in internal linking architecture. Your job is to generate diverse, high-quality anchor text variations for internal links pointing to a specific destination page. Each anchor must:

1. Be 2-8 words (not single words, not long sentences)
2. Be naturally readable in body content
3. Include the destination's primary keyword OR a meaningful variant
4. Vary in structure (some descriptive, some action-oriented, some question-form, some informational)
5. Match real search intent for the destination
6. Avoid keyword stuffing or unnatural phrasing
7. Be safe to use mid-sentence (no awkward grammar when inserted)

Return ONLY a JSON object with this exact structure:
{
  "anchors": [
    "anchor variation 1",
    "anchor variation 2"
  ]
}

Generate 20-25 anchor variations. Aim for 22 as a target. Quality over quantity, but produce a robust pool — these anchors will be rotated across the site so depth matters. Only drop below 20 if the destination is genuinely narrow (e.g., a very specific long-tail topic where 22 distinct meaningful variations aren't achievable without forcing repetition or low-quality phrasing).
SYSPROMPT

# Determine which destinations to process
if [ -n "$IDS" ]; then
    # Filter by specific IDs
    IFS=',' read -ra ID_ARR <<< "$IDS"
    FILTER=$(printf '%s\n' "${ID_ARR[@]}" | jq -R . | jq -s '.')
    DESTINATIONS=$(jq --argjson ids "$FILTER" '.destinations | [.[] | select(.id | tostring | IN($ids[]))]' "$DEST_FILE")
elif [ "$LIMIT" -gt 0 ]; then
    DESTINATIONS=$(jq --argjson start "$START" --argjson limit "$LIMIT" '.destinations[$start:$start+$limit]' "$DEST_FILE")
else
    DESTINATIONS=$(jq '.destinations' "$DEST_FILE")
fi

PROCESS_COUNT=$(echo "$DESTINATIONS" | jq 'length')
echo "Processing: $PROCESS_COUNT destinations"
[ "$LIMIT" -gt 0 ] && echo "  (--limit $LIMIT, --start $START)"
echo ""

# Initialize output (persist in data dir for crash recovery)
RESULTS_FILE="${DATA_DIR}/${SITE}-results-wip.json"
echo '[]' > "$RESULTS_FILE"

# Tracking
SUCCESS=0
FAILED=0
TOTAL_ANCHORS=0
TOTAL_PROMPT_TOKENS=0
TOTAL_COMPLETION_TOKENS=0
START_TIME=$(date +%s)

# Process each destination
for i in $(seq 0 $((PROCESS_COUNT - 1))); do
    DEST=$(echo "$DESTINATIONS" | jq ".[$i]")
    DEST_ID=$(echo "$DEST" | jq -r '.id')
    DEST_URL=$(echo "$DEST" | jq -r '.url')
    DEST_TITLE=$(echo "$DEST" | jq -r '.title')
    DEST_SLUG=$(echo "$DEST" | jq -r '.slug')
    DEST_H1=$(echo "$DEST" | jq -r '.h1')
    DEST_KEYWORD=$(echo "$DEST" | jq -r '.primary_keyword')
    DEST_INTENT=$(echo "$DEST" | jq -r '.intent')
    DEST_CATEGORIES=$(echo "$DEST" | jq -r '.categories | join(", ")')
    DEST_EXCERPT=$(echo "$DEST" | jq -r '.content_excerpt' | head -c 1200)

    PROGRESS="[$((i + 1))/$PROCESS_COUNT]"
    echo -n "${PROGRESS} ID ${DEST_ID}: ${DEST_TITLE:0:60}..."

    # Build user prompt
    USER_PROMPT_FILE="${TMPDIR_LOCAL}/user-prompt.txt"
    cat > "$USER_PROMPT_FILE" <<USERPROMPT
Generate 20-25 anchor text variations for internal links pointing to this page. Aim for 22.

DESTINATION URL: ${DEST_URL}
PAGE TITLE: ${DEST_TITLE}
H1: ${DEST_H1}
PRIMARY KEYWORD: ${DEST_KEYWORD}
TOPIC CLUSTER: ${DEST_CATEGORIES}
PAGE INTENT: ${DEST_INTENT}

FIRST 200 WORDS OF CONTENT:
${DEST_EXCERPT}

Generate diverse anchor variations. Mix:
- Descriptive phrases (e.g., "VA loan duplex guide")
- Action-oriented (e.g., "buying a duplex with a VA loan")
- Question-form (e.g., "can you use a VA loan for a duplex")
- Informational (e.g., "VA duplex eligibility rules")
- Specific (e.g., "VA loan multi-unit property requirements")

Avoid:
- Single words like "duplex"
- Generic phrases like "click here", "read more", "this article"
- Awkward grammar that wouldn't work mid-sentence
- Keyword stuffing
USERPROMPT

    # Call AI
    RESULT=$(ai_generate_anchors "$SYSTEM_PROMPT_FILE" "$USER_PROMPT_FILE" "$SITE_CONFIG")

    # Check for error
    if echo "$RESULT" | jq -e '.error' &>/dev/null; then
        ERROR_MSG=$(echo "$RESULT" | jq -r '.error')
        echo " FAILED: ${ERROR_MSG}"
        FAILED=$((FAILED + 1))
        TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
        echo "[$TS] ID=$DEST_ID slug=$DEST_SLUG error=$ERROR_MSG" >> "$ERROR_LOG"
        sleep 0.5
        continue
    fi

    # Extract data
    ANCHORS=$(echo "$RESULT" | jq '.anchors // []')
    ANCHOR_COUNT=$(echo "$ANCHORS" | jq 'length')
    USAGE=$(echo "$RESULT" | jq '.usage // {prompt_tokens:0,completion_tokens:0,total_tokens:0}')
    RETRIES=$(echo "$RESULT" | jq '.retries // 1')

    # Track tokens (default 0 for missing values)
    PT=$(echo "$USAGE" | jq '.prompt_tokens // 0')
    CT=$(echo "$USAGE" | jq '.completion_tokens // 0')
    TOTAL_PROMPT_TOKENS=$((TOTAL_PROMPT_TOKENS + ${PT:-0}))
    TOTAL_COMPLETION_TOKENS=$((TOTAL_COMPLETION_TOKENS + ${CT:-0}))

    TOTAL_ANCHORS=$((TOTAL_ANCHORS + ${ANCHOR_COUNT:-0}))
    SUCCESS=$((SUCCESS + 1))

    echo " OK ($ANCHOR_COUNT anchors, ${PT}+${CT} tokens)"

    # Build destination result
    GEN_TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    DEST_RESULT=$(jq -n \
        --arg id "$DEST_ID" \
        --arg url "$DEST_URL" \
        --arg slug "$DEST_SLUG" \
        --arg title "$DEST_TITLE" \
        --arg primary_keyword "$DEST_KEYWORD" \
        --argjson anchors "$ANCHORS" \
        --arg anchor_count "$ANCHOR_COUNT" \
        --arg generated_at "$GEN_TS" \
        --argjson usage "$USAGE" \
        '{
            id: ($id | tonumber),
            url: $url,
            slug: $slug,
            title: $title,
            primary_keyword: $primary_keyword,
            anchors: $anchors,
            anchor_count: ($anchor_count | tonumber),
            generated_at: $generated_at,
            usage: $usage
        }')

    # Append to results
    jq --argjson new "$DEST_RESULT" '. + [$new]' "$RESULTS_FILE" > "${RESULTS_FILE}.tmp"
    mv "${RESULTS_FILE}.tmp" "$RESULTS_FILE"

    # Rate limiting
    sleep 0.5
done

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

# Calculate stats
AVG_ANCHORS="0"
if [ "$SUCCESS" -gt 0 ]; then
    AVG_ANCHORS=$(echo "scale=1; $TOTAL_ANCHORS / $SUCCESS" | bc)
fi

# Cost calculation (gpt-5.4-mini pricing: $0.75/1M input, $4.50/1M output)
COST="0"
if [ "$AI_PROVIDER" = "openai" ]; then
    COST=$(echo "scale=4; ($TOTAL_PROMPT_TOKENS * 0.00000075) + ($TOTAL_COMPLETION_TOKENS * 0.0000045)" | bc)
fi

echo ""
echo "=== Generation Complete ==="
echo "Time: ${ELAPSED}s"
echo "Success: ${SUCCESS}/${PROCESS_COUNT}"
echo "Failed: ${FAILED}"
echo "Total anchors: ${TOTAL_ANCHORS}"
echo "Avg anchors/dest: ${AVG_ANCHORS}"
echo "Tokens: ${TOTAL_PROMPT_TOKENS} prompt + ${TOTAL_COMPLETION_TOKENS} completion"
echo "Estimated cost: \$${COST}"

# Build final output (use --slurpfile to avoid argument length limit)
GEN_TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
jq -n \
    --arg site "$SITE" \
    --arg generated_at "$GEN_TS" \
    --arg ai_provider "$AI_PROVIDER" \
    --arg ai_model "$AI_MODEL" \
    --slurpfile destinations "$RESULTS_FILE" \
    --argjson total "$PROCESS_COUNT" \
    --argjson successful "$SUCCESS" \
    --argjson failed "$FAILED" \
    --argjson total_anchors "$TOTAL_ANCHORS" \
    --arg avg_anchors "$AVG_ANCHORS" \
    --argjson prompt_tokens "$TOTAL_PROMPT_TOKENS" \
    --argjson completion_tokens "$TOTAL_COMPLETION_TOKENS" \
    --arg cost "$COST" \
    --argjson elapsed "$ELAPSED" \
    '{
        site: $site,
        generated_at: $generated_at,
        ai_provider: $ai_provider,
        ai_model: $ai_model,
        destinations: $destinations[0],
        stats: {
            total_destinations: $total,
            successful: $successful,
            failed: $failed,
            total_anchors_generated: $total_anchors,
            avg_anchors_per_destination: ($avg_anchors | tonumber),
            prompt_tokens: $prompt_tokens,
            completion_tokens: $completion_tokens,
            estimated_cost_usd: ($cost | tonumber),
            elapsed_seconds: $elapsed
        }
    }' > "$OUTPUT_FILE"

echo ""
echo "Output saved to: $OUTPUT_FILE"
