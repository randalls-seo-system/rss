#!/usr/bin/env bash
# AI Provider Abstraction for Linking v2
# Supports OpenAI and Anthropic APIs for anchor pool generation
# Source this file, then call: ai_generate_anchors <prompt_file> <site_config>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ERROR_LOG="${SCRIPT_DIR}/../data/anchor-pool-errors.log"

# Load jq dependency check
_ai_check_deps() {
    if ! command -v jq &>/dev/null; then
        echo "ERROR: jq is required but not installed" >&2
        return 1
    fi
}

# Call OpenAI Chat Completions API
# Args: $1=system_prompt_file $2=user_prompt_file
_ai_call_openai() {
    local system_prompt_file="$1"
    local user_prompt_file="$2"
    local api_key="${!AI_API_KEY_ENV_VAR}"

    if [ -z "$api_key" ]; then
        echo "ERROR: ${AI_API_KEY_ENV_VAR} not set" >&2
        return 1
    fi

    # Build JSON payload with jq to handle escaping
    local payload
    payload=$(jq -n \
        --arg model "$AI_MODEL" \
        --rawfile system "$system_prompt_file" \
        --rawfile user "$user_prompt_file" \
        '{
            model: $model,
            messages: [
                {role: "system", content: $system},
                {role: "user", content: $user}
            ],
            response_format: {type: "json_object"},
            temperature: 0.7
        }')

    curl -s --max-time "$AI_REQUEST_TIMEOUT" \
        "https://api.openai.com/v1/chat/completions" \
        -H "Authorization: Bearer ${api_key}" \
        -H "Content-Type: application/json" \
        -d "$payload"
}

# Call Anthropic Messages API
# Args: $1=system_prompt_file $2=user_prompt_file
_ai_call_anthropic() {
    local system_prompt_file="$1"
    local user_prompt_file="$2"
    local api_key="${!AI_API_KEY_ENV_VAR}"

    if [ -z "$api_key" ]; then
        echo "ERROR: ${AI_API_KEY_ENV_VAR} not set" >&2
        return 1
    fi

    local system_text user_text
    system_text=$(cat "$system_prompt_file")
    user_text=$(cat "$user_prompt_file")

    local payload
    payload=$(jq -n \
        --arg model "$AI_MODEL" \
        --rawfile system "$system_prompt_file" \
        --rawfile user "$user_prompt_file" \
        '{
            model: $model,
            max_tokens: 1024,
            system: $system,
            messages: [
                {role: "user", content: ($user + "\n\nReturn ONLY a JSON object with key \"anchors\" containing an array of strings.")}
            ]
        }')

    curl -s --max-time "$AI_REQUEST_TIMEOUT" \
        "https://api.anthropic.com/v1/messages" \
        -H "x-api-key: ${api_key}" \
        -H "anthropic-version: 2023-06-01" \
        -H "Content-Type: application/json" \
        -d "$payload"
}

# Extract anchors array from API response
# Args: $1=raw_response $2=provider
_ai_extract_anchors() {
    local response="$1"
    local provider="$2"

    if [ "$provider" = "openai" ]; then
        # OpenAI: .choices[0].message.content is a JSON string
        local content
        content=$(echo "$response" | jq -r '.choices[0].message.content // empty' 2>/dev/null)
        if [ -z "$content" ]; then
            echo "ERROR: No content in OpenAI response" >&2
            return 1
        fi
        echo "$content" | jq -r '.anchors' 2>/dev/null
    elif [ "$provider" = "anthropic" ]; then
        # Anthropic: .content[0].text is a JSON string
        local content
        content=$(echo "$response" | jq -r '.content[0].text // empty' 2>/dev/null)
        if [ -z "$content" ]; then
            echo "ERROR: No content in Anthropic response" >&2
            return 1
        fi
        # Strip markdown code fences if present
        content=$(echo "$content" | sed 's/^```json//;s/^```//;s/```$//')
        echo "$content" | jq -r '.anchors' 2>/dev/null
    fi
}

# Extract token usage from response for cost tracking
# Args: $1=raw_response $2=provider
_ai_extract_usage() {
    local response="$1"
    local provider="$2"

    if [ "$provider" = "openai" ]; then
        echo "$response" | jq '{prompt_tokens: .usage.prompt_tokens, completion_tokens: .usage.completion_tokens, total_tokens: .usage.total_tokens}' 2>/dev/null
    elif [ "$provider" = "anthropic" ]; then
        echo "$response" | jq '{prompt_tokens: .usage.input_tokens, completion_tokens: .usage.output_tokens, total_tokens: (.usage.input_tokens + .usage.output_tokens)}' 2>/dev/null
    fi
}

# Validate anchor pool meets quality requirements
# Args: $1=anchors_json (array)
# Returns: 0 if valid, 1 if invalid (prints reason to stderr)
_ai_validate_anchors() {
    local anchors_json="$1"

    # Check it's a valid JSON array
    if ! echo "$anchors_json" | jq 'type == "array"' 2>/dev/null | grep -q true; then
        echo "ERROR: Response is not a JSON array" >&2
        return 1
    fi

    # Check count in range
    local count
    count=$(echo "$anchors_json" | jq 'length' 2>/dev/null)
    if [ "$count" -lt "$ANCHOR_POOL_SIZE_MIN" ] || [ "$count" -gt "$ANCHOR_POOL_SIZE_MAX" ]; then
        echo "WARNING: Anchor count $count outside range [$ANCHOR_POOL_SIZE_MIN-$ANCHOR_POOL_SIZE_MAX]" >&2
        # Allow it if at least 10 — still usable
        if [ "$count" -lt 10 ]; then
            echo "ERROR: Too few anchors ($count < 10)" >&2
            return 1
        fi
    fi

    # Check all elements are strings
    local non_strings
    non_strings=$(echo "$anchors_json" | jq '[.[] | select(type != "string")] | length' 2>/dev/null)
    if [ "$non_strings" -gt 0 ]; then
        echo "ERROR: $non_strings non-string elements in anchors array" >&2
        return 1
    fi

    # Check no single-word anchors
    local single_word
    single_word=$(echo "$anchors_json" | jq '[.[] | select(split(" ") | length <= 1)] | length' 2>/dev/null)
    if [ "$single_word" -gt 0 ]; then
        echo "WARNING: $single_word single-word anchors found (will be filtered)" >&2
    fi

    # Check no generic anchors
    local generic
    generic=$(echo "$anchors_json" | jq '[.[] | select(ascii_downcase | test("^(click here|read more|this article|learn more|here|this page)$"))] | length' 2>/dev/null)
    if [ "$generic" -gt 0 ]; then
        echo "WARNING: $generic generic anchors found (will be filtered)" >&2
    fi

    return 0
}

# Clean anchor pool: remove single-word and generic anchors
_ai_clean_anchors() {
    local anchors_json="$1"
    echo "$anchors_json" | jq '[.[] | select(
        (split(" ") | length >= 2) and
        (ascii_downcase | test("^(click here|read more|this article|learn more|here|this page)$") | not)
    )]'
}

# Main function: generate anchor pool for a destination
# Args: $1=system_prompt_file $2=user_prompt_file $3=site_config_path
# Outputs: JSON object {anchors: [...], usage: {...}, retries: N}
ai_generate_anchors() {
    local system_prompt_file="$1"
    local user_prompt_file="$2"
    local site_config="$3"

    _ai_check_deps || return 1

    # Source config if not already loaded
    if [ -z "$AI_PROVIDER" ] && [ -n "$site_config" ]; then
        source "$site_config"
    fi

    local provider="${AI_PROVIDER:-openai}"
    local max_retries="${AI_MAX_RETRIES:-3}"
    local attempt=0
    local response anchors usage

    while [ "$attempt" -lt "$max_retries" ]; do
        attempt=$((attempt + 1))

        # Call the appropriate provider
        if [ "$provider" = "openai" ]; then
            response=$(_ai_call_openai "$system_prompt_file" "$user_prompt_file")
        elif [ "$provider" = "anthropic" ]; then
            response=$(_ai_call_anthropic "$system_prompt_file" "$user_prompt_file")
        else
            echo "ERROR: Unknown AI_PROVIDER: $provider" >&2
            return 1
        fi

        # Check for HTTP errors in response
        local error_msg
        error_msg=$(echo "$response" | jq -r '.error.message // empty' 2>/dev/null)
        if [ -n "$error_msg" ]; then
            local error_type
            error_type=$(echo "$response" | jq -r '.error.type // .error.code // "unknown"' 2>/dev/null)

            # Rate limit — exponential backoff
            if echo "$error_type" | grep -qi "rate_limit\|429"; then
                local wait_time=$((2 ** attempt * 2))
                echo "WARN: Rate limited, waiting ${wait_time}s (attempt $attempt/$max_retries)" >&2
                sleep "$wait_time"
                continue
            fi

            # Server error — retry
            if echo "$error_msg" | grep -qi "server\|503\|502\|500"; then
                local wait_time=$((2 ** attempt))
                echo "WARN: Server error, waiting ${wait_time}s (attempt $attempt/$max_retries)" >&2
                sleep "$wait_time"
                continue
            fi

            echo "ERROR: API error: $error_msg" >&2
            echo "{\"error\": \"$error_msg\", \"retries\": $attempt}"
            return 1
        fi

        # Extract anchors
        anchors=$(_ai_extract_anchors "$response" "$provider")
        if [ -z "$anchors" ] || [ "$anchors" = "null" ]; then
            echo "WARN: Failed to extract anchors (attempt $attempt/$max_retries)" >&2
            sleep 2
            continue
        fi

        # Extract usage
        usage=$(_ai_extract_usage "$response" "$provider")

        # Validate
        if _ai_validate_anchors "$anchors"; then
            # Clean (remove single-word/generic)
            local cleaned
            cleaned=$(_ai_clean_anchors "$anchors")
            local clean_count
            clean_count=$(echo "$cleaned" | jq 'length')

            # Ensure usage is valid JSON
            if [ -z "$usage" ] || ! echo "$usage" | jq '.' &>/dev/null; then
                usage='{"prompt_tokens":0,"completion_tokens":0,"total_tokens":0}'
            fi

            jq -n \
                --argjson anchors "$cleaned" \
                --argjson usage "$usage" \
                --argjson retries "$attempt" \
                '{anchors: $anchors, usage: $usage, retries: $retries}'
            return 0
        else
            echo "WARN: Validation failed (attempt $attempt/$max_retries)" >&2
            sleep 1
            continue
        fi
    done

    # All retries exhausted
    local ts
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    echo "[$ts] FAILED after $max_retries retries" >> "$ERROR_LOG"
    echo "{\"error\": \"All retries exhausted\", \"retries\": $max_retries}"
    return 1
}
