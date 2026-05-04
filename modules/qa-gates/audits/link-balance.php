<?php
/**
 * RSS QA Gates — Audit 4: Internal vs External Link Balance
 *
 * Flags posts where external links outnumber internal links.
 * Only checks posts with 5+ external links (below that threshold,
 * imbalance is noise).
 *
 * Good practice: internal links >= external links on every page.
 *
 * Output: CSV to stdout (sorted by gap size, worst first)
 * Usage:  wp eval-file /tmp/link-balance.php
 */

if ( ! defined( 'ABSPATH' ) ) exit;

$helpers = __DIR__ . '/audit-helpers.php';
if ( file_exists( $helpers ) ) require_once $helpers;

$min_external = 5;  // Only flag posts with this many+ external links

rss_audit_csv_header( ['post_id', 'slug', 'internal_count', 'external_count', 'gap', 'severity'] );

$posts = rss_audit_get_posts();
$results = [];

foreach ( $posts as $post ) {
    $html  = rss_audit_strip_shortcodes( $post->post_content );
    $links = rss_audit_extract_links( $html );

    $internal = 0;
    $external = 0;

    foreach ( $links as $link ) {
        $href = $link['href'];
        // Skip anchors, javascript, empty
        if ( empty( $href ) || $href[0] === '#' || strpos( $href, 'javascript:' ) === 0 ) continue;

        if ( rss_audit_is_internal( $href ) ) {
            $internal++;
        } else {
            $external++;
        }
    }

    // Only flag if external >= min_external AND external > internal
    if ( $external >= $min_external && $external > $internal ) {
        $gap = $external - $internal;
        $severity = 'medium';
        if ( $gap >= 10 ) $severity = 'high';
        if ( $internal === 0 && $external >= 5 ) $severity = 'critical';

        $results[] = [
            'post_id'        => $post->ID,
            'slug'           => $post->post_name,
            'internal_count' => $internal,
            'external_count' => $external,
            'gap'            => $gap,
            'severity'       => $severity,
        ];
    }
}

// Sort by gap descending (worst offenders first)
usort( $results, function( $a, $b ) { return $b['gap'] - $a['gap']; } );

foreach ( $results as $r ) {
    rss_audit_csv_row( [
        $r['post_id'],
        $r['slug'],
        $r['internal_count'],
        $r['external_count'],
        $r['gap'],
        $r['severity'],
    ] );
}

$count = count( $results );
fwrite( STDERR, "link-balance: {$count} issues found\n" );
