<?php
/**
 * RSS QA Gates — Shared Audit Helpers
 *
 * Loaded by each audit script. Provides common functions for
 * querying posts, parsing HTML, and writing CSV output.
 *
 * Usage: require_once __DIR__ . '/../lib/audit-helpers.php';
 *        (when piped to wp eval-file, paths are resolved at runtime)
 */

if ( ! defined( 'ABSPATH' ) ) exit;

/**
 * Get all published posts/pages with their content.
 * Returns array of objects with ID, post_title, post_name, post_content.
 */
function rss_audit_get_posts( $post_types = ['post', 'page'], $limit = 0 ) {
    global $wpdb;
    $types = implode( "','", array_map( 'esc_sql', $post_types ) );
    $sql = "SELECT ID, post_title, post_name, post_content
            FROM {$wpdb->posts}
            WHERE post_status = 'publish'
              AND post_type IN ('{$types}')
              AND post_content != ''
            ORDER BY ID ASC";
    if ( $limit > 0 ) {
        $sql .= " LIMIT " . (int) $limit;
    }
    return $wpdb->get_results( $sql );
}

/**
 * Extract all <a> tags from HTML content.
 * Returns array of [ 'href' => url, 'text' => anchor_text, 'full_match' => raw_html ]
 */
function rss_audit_extract_links( $html ) {
    $links = [];
    if ( preg_match_all( '/<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)<\/a>/si', $html, $matches, PREG_SET_ORDER ) ) {
        foreach ( $matches as $m ) {
            $links[] = [
                'href'       => $m[1],
                'text'       => strip_tags( $m[2] ),
                'full_match' => $m[0],
            ];
        }
    }
    return $links;
}

/**
 * Check if a URL is internal (matches the site domain).
 */
function rss_audit_is_internal( $url, $site_domain = '' ) {
    if ( empty( $site_domain ) ) {
        $site_domain = parse_url( home_url(), PHP_URL_HOST );
    }
    $host = parse_url( $url, PHP_URL_HOST );
    if ( ! $host ) {
        // Relative URL = internal
        return strpos( $url, '/' ) === 0 && strpos( $url, '//' ) !== 0;
    }
    return $host === $site_domain || substr( $host, -strlen( '.' . $site_domain ) ) === '.' . $site_domain;
}

/**
 * Output a CSV header row.
 */
function rss_audit_csv_header( $columns ) {
    echo implode( ',', $columns ) . "\n";
}

/**
 * Output a CSV data row, properly escaping fields.
 */
function rss_audit_csv_row( $fields ) {
    $escaped = array_map( function( $f ) {
        $f = str_replace( '"', '""', (string) $f );
        if ( strpos( $f, ',' ) !== false || strpos( $f, '"' ) !== false || strpos( $f, "\n" ) !== false ) {
            return '"' . $f . '"';
        }
        return $f;
    }, $fields );
    echo implode( ',', $escaped ) . "\n";
}

/**
 * Strip Divi shortcodes from content for cleaner HTML parsing.
 */
function rss_audit_strip_shortcodes( $html ) {
    $html = preg_replace( '/\[\/?et_pb_[^\]]*\]/', '', $html );
    return $html;
}
