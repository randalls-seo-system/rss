<?php
/**
 * RSS Linking Module — dedup-runner.php
 * Status: Template
 *
 * Template variables:
 * - {{SITE_URL}} — full site URL
 * - {{SITE_PREFIX}} — function prefix
 *
 * Scans published posts/pages for repeated internal link URLs (3+ occurrences)
 * and strips extras, keeping the first body occurrence + Resources Used occurrence.
 *
 * Usage: wp eval-file <rendered-file>.php [--dry-run]
 */
set_time_limit(600);
global $wpdb;

$dry_run = in_array('--dry-run', $GLOBALS['argv'] ?? [], true);

$posts = $wpdb->get_results(
    "SELECT ID, post_name, post_content
     FROM {$wpdb->posts}
     WHERE post_status = 'publish'
       AND post_type IN ('post','page')
       AND LENGTH(post_content) > 500
     ORDER BY ID"
);

echo "post_id,slug,url,occurrences,action\n";

$fixed = 0;

foreach ($posts as $post) {
    $content = $post->post_content;

    // Find all internal href occurrences
    if (!preg_match_all('~<a\s[^>]*href="((?:{{SITE_URL}})?/[^"]+)"[^>]*>~i', $content, $links, PREG_SET_ORDER)) {
        continue;
    }

    // Count occurrences per URL (normalized to path only)
    $url_counts = [];
    foreach ($links as $lm) {
        $url = str_replace('{{SITE_URL}}', '', $lm[1]);
        $url = '/' . trim($url, '/') . '/';
        $url_counts[$url] = ($url_counts[$url] ?? 0) + 1;
    }

    $needs_fix = false;
    foreach ($url_counts as $url => $cnt) {
        // Allow /compare-loan-offers/ (CTA) up to 3 times; everything else max 2
        $max = 2;
        if ($cnt > $max) {
            echo "{$post->ID},{$post->post_name},{$url},{$cnt},";
            if ($dry_run) {
                echo "would_strip\n";
            } else {
                echo "stripped\n";
            }
            $needs_fix = true;

            if (!$dry_run) {
                // Keep first occurrence, strip the rest
                $kept = 0;
                $content = preg_replace_callback(
                    '~<a\s([^>]*href="(?:' . preg_quote('{{SITE_URL}}', '~') . ')?' . preg_quote(rtrim($url, '/'), '~') . '/?"[^>]*)>(.*?)</a>~is',
                    function($m) use (&$kept, $max) {
                        $kept++;
                        if ($kept <= $max) return $m[0]; // keep
                        return $m[2]; // strip link, keep text
                    },
                    $content
                );
            }
        }
    }

    if ($needs_fix && !$dry_run) {
        $wpdb->update($wpdb->posts, ['post_content' => $content], ['ID' => $post->ID]);
        clean_post_cache($post->ID);
        $fixed++;
        sleep(3);
    }
}

echo "# " . ($dry_run ? "DRY RUN — " : "") . "Fixed: {$fixed} posts\n";
