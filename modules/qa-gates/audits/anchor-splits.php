<?php
/**
 * RSS QA Gates — Audit 1: Sub-Word Anchor Splits
 *
 * Detects </a> immediately followed by lowercase letters — indicates
 * the link injector matched a substring instead of a whole word.
 *
 * Severity:
 *   critical — acronym matched inside unrelated word (e.g., "aus" in "because")
 *   high     — suffix creates garbled text (e.g., "costss", "pre-approvalal")
 *   medium   — plural split (e.g., "<a>cost</a>s")
 *   medium   — CTA markup corruption (literal "n" chars)
 *
 * Output: CSV to stdout
 * Usage:  wp eval-file /tmp/anchor-splits.php
 */

if ( ! defined( 'ABSPATH' ) ) exit;

// Load helpers (will be in same /tmp/ dir when piped)
$helpers = __DIR__ . '/audit-helpers.php';
if ( file_exists( $helpers ) ) {
    require_once $helpers;
} else {
    // Fallback: helpers may be loaded separately
}

// CSV header
rss_audit_csv_header( ['post_id', 'slug', 'issue_type', 'anchor_text', 'trailing_chars', 'target_url', 'severity'] );

$posts = rss_audit_get_posts();
$count = 0;

foreach ( $posts as $post ) {
    $html = rss_audit_strip_shortcodes( $post->post_content );

    // Pattern: </a> followed by 1+ lowercase letters (no space/punctuation between)
    // No 's' flag — anchor text must not span multiple lines (avoids nav/ATF noise)
    if ( ! preg_match_all( '/<a\s[^>]*href=["\']([^"\']*)["\'][^>]*>([^<]{2,120})<\/a>([a-z]+)/i', $html, $matches, PREG_SET_ORDER ) ) {
        continue;
    }

    foreach ( $matches as $m ) {
        $target_url = $m[1];
        $anchor     = trim( $m[2] );
        $trailing   = $m[3];

        // Skip if anchor is empty
        if ( trim( $anchor ) === '' ) continue;

        // Classify severity
        $issue_type = 'unknown_split';
        $severity   = 'medium';

        // Check for acronym-in-word (critical): short anchor (2-4 chars) that looks like an acronym
        $anchor_lower = strtolower( trim( $anchor ) );
        if ( strlen( $anchor_lower ) <= 4 && preg_match( '/^[a-z]{2,4}$/', $anchor_lower ) ) {
            $issue_type = 'acronym_in_word';
            $severity   = 'critical';
        }
        // Check for doubled suffix (high): trailing chars repeat end of anchor
        elseif ( strlen( $trailing ) >= 2 && substr( $anchor_lower, -strlen( $trailing ) ) === strtolower( $trailing ) ) {
            $issue_type = 'double_suffix';
            $severity   = 'high';
        }
        // Check for suffix split creating garbled text (high): trailing >= 2 chars, not just "s"
        elseif ( strlen( $trailing ) >= 2 && $trailing !== 'es' ) {
            $issue_type = 'suffix_split';
            $severity   = 'high';
        }
        // Single "s" or "es" = plural split (medium)
        elseif ( $trailing === 's' || $trailing === 'es' ) {
            $issue_type = 'plural_split';
            $severity   = 'medium';
        }
        // CTA corruption: literal "n" after anchor
        elseif ( $trailing === 'n' ) {
            $issue_type = 'cta_corruption';
            $severity   = 'medium';
        }
        else {
            $issue_type = 'trailing_split';
            $severity   = 'low';
        }

        rss_audit_csv_row( [
            $post->ID,
            $post->post_name,
            $issue_type,
            $anchor,
            $trailing,
            $target_url,
            $severity,
        ] );
        $count++;
    }
}

fwrite( STDERR, "anchor-splits: {$count} issues found\n" );
