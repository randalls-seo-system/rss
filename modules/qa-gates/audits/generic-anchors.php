<?php
/**
 * RSS QA Gates — Audit 2: Generic / Non-Descriptive Anchors
 *
 * Detects anchor text that provides no SEO or user value:
 *   - Generic phrases: "click here", "read more", "learn more", "here", "this"
 *   - Single-word anchors under 4 characters (excluding known product names)
 *   - Bare acronyms without expansion (DTI, COE, MPR, AUS, BAH, etc.)
 *
 * Output: CSV to stdout
 * Usage:  wp eval-file /tmp/generic-anchors.php
 */

if ( ! defined( 'ABSPATH' ) ) exit;

$helpers = __DIR__ . '/audit-helpers.php';
if ( file_exists( $helpers ) ) require_once $helpers;

// Generic phrases (case-insensitive exact match)
$generic_phrases = [
    'click here', 'read more', 'learn more', 'find out more',
    'here', 'this', 'this page', 'this article', 'this guide',
    'more', 'link', 'source', 'website', 'page',
];

// Bare acronyms — flagged when used alone as anchor text
$bare_acronyms = [
    'DTI', 'COE', 'MPR', 'AUS', 'BAH', 'DIC', 'SAH', 'SHA',
    'CRDP', 'CRSC', 'PMI', 'MIP', 'LTV', 'FICO', 'SSA',
    'COLA', 'PCS', 'TDY', 'DSCR', 'FHA', 'USDA', 'HELOC',
];
// Exception: IRRRL is acceptable as standalone anchor (it IS the product name)
$acronym_exceptions = [ 'IRRRL', 'VA', 'GI' ];

rss_audit_csv_header( ['post_id', 'slug', 'issue_type', 'anchor_text', 'target_url', 'severity'] );

$posts = rss_audit_get_posts();
$count = 0;

foreach ( $posts as $post ) {
    $html  = rss_audit_strip_shortcodes( $post->post_content );
    $links = rss_audit_extract_links( $html );

    foreach ( $links as $link ) {
        $text = trim( $link['text'] );
        $href = $link['href'];

        if ( $text === '' ) continue;
        // Skip external links for this audit (focus on internal link quality)
        if ( preg_match( '#^https?://#', $href ) && ! rss_audit_is_internal( $href ) ) continue;

        $text_lower = strtolower( $text );
        $issue_type = '';
        $severity   = 'medium';

        // Check generic phrases
        if ( in_array( $text_lower, $generic_phrases, true ) ) {
            $issue_type = 'generic_phrase';
            $severity   = 'high';
        }
        // Check single-word anchors under 4 chars
        elseif ( str_word_count( $text ) === 1 && strlen( $text ) < 4 && ! in_array( strtoupper( $text ), $acronym_exceptions, true ) ) {
            $issue_type = 'too_short';
            $severity   = 'medium';
        }
        // Check bare acronyms
        elseif ( in_array( strtoupper( $text ), $bare_acronyms, true ) ) {
            $issue_type = 'bare_acronym';
            $severity   = 'medium';
        }

        if ( $issue_type ) {
            rss_audit_csv_row( [
                $post->ID,
                $post->post_name,
                $issue_type,
                $text,
                $href,
                $severity,
            ] );
            $count++;
        }
    }
}

fwrite( STDERR, "generic-anchors: {$count} issues found\n" );
