#!/usr/bin/env bash
# Pull destination metadata from a site for anchor pool generation
# Usage: ./pull-destinations.sh <site-config-path>
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODULE_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$(dirname "$MODULE_DIR")")"

if [ -z "${1:-}" ]; then
    echo "Usage: $0 <site-config-path>"
    echo "  e.g., $0 sites/valn.conf"
    exit 1
fi

SITE_CONFIG="$1"
if [[ ! "$SITE_CONFIG" = /* ]]; then
    SITE_CONFIG="${ROOT_DIR}/${SITE_CONFIG}"
fi

source "$SITE_CONFIG"

SITE="${SITE_SLUG:-unknown}"
DATA_DIR="${MODULE_DIR}/data"
OUTPUT_FILE="${DATA_DIR}/${SITE}-destinations.json"

echo "=== Pull Destinations: ${SITE_NAME} ==="
echo "SSH: ${SSH_USER}@${SSH_HOST}"
echo "Output: ${OUTPUT_FILE}"

# Build the PHP extraction script
PHP_SCRIPT=$(cat <<'PHPEOF'
<?php
$posts = get_posts([
    'post_type'      => ['post', 'page'],
    'posts_per_page' => -1,
    'post_status'    => 'publish',
]);

$destinations = [];
foreach ($posts as $p) {
    // Skip very short content (likely redirects or placeholders)
    if (strlen($p->post_content) < 200) continue;

    $content_text = wp_strip_all_tags($p->post_content);
    // First ~200 words (approx 1200 chars)
    $words = explode(' ', $content_text);
    $excerpt = implode(' ', array_slice($words, 0, 200));

    // Extract first H1 from content
    $h1 = $p->post_title;
    if (preg_match('/<h1[^>]*>(.*?)<\/h1>/si', $p->post_content, $h1_match)) {
        $h1 = wp_strip_all_tags($h1_match[1]);
    }

    // Yoast focus keyword
    $yoast_keyword = get_post_meta($p->ID, '_yoast_wpseo_focuskw', true);

    // Categories for cluster hint
    $categories = wp_get_post_categories($p->ID, ['fields' => 'names']);

    // Permalink
    $url = get_permalink($p->ID);

    // Determine intent heuristic based on URL/title patterns
    $slug = $p->post_name;
    $title_lower = strtolower($p->post_title);
    $intent = 'informational';
    if (preg_match('/compare|vs|versus|best/', $title_lower)) {
        $intent = 'comparison';
    } elseif (preg_match('/how to|guide|step|tutorial/', $title_lower)) {
        $intent = 'guide';
    } elseif (preg_match('/calculator|estimate|check|apply/', $title_lower)) {
        $intent = 'transactional';
    } elseif (preg_match('/what is|what are|definition|meaning/', $title_lower)) {
        $intent = 'informational';
    }

    $destinations[] = [
        'id'              => $p->ID,
        'url'             => $url,
        'slug'            => $slug,
        'title'           => $p->post_title,
        'h1'              => $h1,
        'primary_keyword' => $yoast_keyword ?: $p->post_title,
        'categories'      => $categories,
        'intent'          => $intent,
        'content_excerpt' => $excerpt,
        'modified'        => $p->post_modified,
    ];
}

// Sort by ID for consistency
usort($destinations, function($a, $b) { return $a['id'] - $b['id']; });

echo json_encode([
    'site'       => '%%SITE_SLUG%%',
    'pulled_at'  => date('c'),
    'count'      => count($destinations),
    'destinations' => $destinations,
], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
PHPEOF
)

# Replace placeholder with actual site slug
PHP_SCRIPT="${PHP_SCRIPT//%%SITE_SLUG%%/$SITE}"

SSH_OPTS="-i ${SSH_KEY_PATH} -o IdentitiesOnly=yes -o ConnectTimeout=15"

echo ""
echo "Pulling destination metadata via WP-CLI..."

# Pipe PHP to server and capture output
RESULT=$(echo "$PHP_SCRIPT" | ssh $SSH_OPTS "${SSH_USER}@${SSH_HOST}" 'cat > /tmp/_pull_dest.php && wp eval-file /tmp/_pull_dest.php && rm -f /tmp/_pull_dest.php' 2>&1)

# Validate JSON
if echo "$RESULT" | jq '.count' &>/dev/null; then
    echo "$RESULT" > "$OUTPUT_FILE"
    COUNT=$(echo "$RESULT" | jq '.count')
    echo ""
    echo "SUCCESS: Pulled $COUNT destinations"
    echo "Saved to: $OUTPUT_FILE"

    # Show category distribution
    echo ""
    echo "Intent distribution:"
    echo "$RESULT" | jq -r '.destinations[].intent' | sort | uniq -c | sort -rn

    echo ""
    echo "Top 10 categories:"
    echo "$RESULT" | jq -r '.destinations[].categories[]' 2>/dev/null | sort | uniq -c | sort -rn | head -10
else
    echo "ERROR: Failed to pull destinations. Response:" >&2
    echo "$RESULT" | head -20 >&2
    exit 1
fi
