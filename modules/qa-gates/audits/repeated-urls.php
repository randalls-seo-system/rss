<?php
/**
 * RSS QA Gates — Audit 3: Repeated URL Count
 *
 * Flags posts where the same URL is linked 3+ times. Per SEO best
 * practice, each URL should appear at most twice per page (first
 * contextual mention + Resources Used section).
 *
 * Exception: /compare-loan-offers/ may appear up to 3 times (CTA pattern).
 *
 * Output: CSV to stdout
 * Usage:  wp eval-file /tmp/repeated-urls.php
 */

if ( ! defined( 'ABSPATH' ) ) exit;

$helpers = __DIR__ . '/audit-helpers.php';
if ( file_exists( $helpers ) ) require_once $helpers;

// URLs allowed to repeat (site-specific, loaded from env or hardcoded fallback)
$exception_slugs = [ '/compare-loan-offers/' ];
$exception_threshold = 3;  // These URLs get flagged at 4+, not 3+

rss_audit_csv_header( ['post_id', 'slug', 'repeated_url', 'count', 'is_internal', 'severity'] );

$posts = rss_audit_get_posts();
$count = 0;

foreach ( $posts as $post ) {
    $html  = rss_audit_strip_shortcodes( $post->post_content );
    $links = rss_audit_extract_links( $html );

    // Count URLs
    $url_counts = [];
    foreach ( $links as $link ) {
        $href = $link['href'];
        // Normalize: strip trailing slash, lowercase
        $normalized = strtolower( rtrim( $href, '/' ) );
        if ( $normalized === '' || $normalized === '#' ) continue;
        if ( ! isset( $url_counts[ $normalized ] ) ) {
            $url_counts[ $normalized ] = 0;
        }
        $url_counts[ $normalized ]++;
    }

    foreach ( $url_counts as $url => $url_count ) {
        // Determine threshold
        $threshold = 3;
        foreach ( $exception_slugs as $exc ) {
            if ( strpos( $url, rtrim( strtolower( $exc ), '/' ) ) !== false ) {
                $threshold = $exception_threshold + 1;
                break;
            }
        }

        if ( $url_count >= $threshold ) {
            $is_internal = rss_audit_is_internal( $url ) ? 'internal' : 'external';
            $severity = $url_count >= 5 ? 'high' : 'medium';

            rss_audit_csv_row( [
                $post->ID,
                $post->post_name,
                $url,
                $url_count,
                $is_internal,
                $severity,
            ] );
            $count++;
        }
    }
}

fwrite( STDERR, "repeated-urls: {$count} issues found\n" );
