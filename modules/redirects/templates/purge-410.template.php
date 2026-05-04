<?php
/**
 * RSS Redirects Module — purge-410.php
 * Source: VALN production base-purge-410.php (pulled 2026-05-04)
 * Status: Template
 *
 * Template variables:
 * - {{SITE_PREFIX}} — function prefix
 *
 * Data-driven HTTP 410 Gone handler for retired content paths.
 * Loads 410 patterns from companion file (<prefix>-410-patterns.php).
 *
 * Pattern file returns an array of:
 * - Exact paths: '/old-page/' => true
 * - Regex patterns: '#^/military-bases(/|$)#i' => true
 */
if ( ! defined( 'ABSPATH' ) ) exit;

add_action( 'template_redirect', function () {
    $uri = $_SERVER['REQUEST_URI'] ?? '';
    if ( $uri === '' ) return;

    $path = parse_url( $uri, PHP_URL_PATH ) ?: '/';
    $norm = rtrim( $path, '/' );
    if ( $norm === '' ) $norm = '/';

    // Load 410 patterns from companion data file
    static $patterns = null;
    if ( $patterns === null ) {
        $pat_file = __DIR__ . '/{{SITE_PREFIX}}-410-patterns.php';
        if ( file_exists( $pat_file ) ) {
            $patterns = include $pat_file;
            if ( ! is_array( $patterns ) ) $patterns = [];
        } else {
            $patterns = [];
        }
    }

    if ( empty( $patterns ) ) return;

    foreach ( $patterns as $pattern => $active ) {
        if ( ! $active ) continue;

        // If pattern starts with # or ~, treat as regex
        if ( $pattern[0] === '#' || $pattern[0] === '~' ) {
            if ( preg_match( $pattern, $path ) ) {
                status_header( 410 );
                header( 'Cache-Control: no-store, no-cache, must-revalidate, max-age=0' );
                header( 'Pragma: no-cache' );
                echo 'Gone';
                exit;
            }
        } else {
            // Exact path match (case-insensitive)
            if ( strcasecmp( $norm, rtrim( $pattern, '/' ) ) === 0 ) {
                status_header( 410 );
                header( 'Cache-Control: no-store, no-cache, must-revalidate, max-age=0' );
                header( 'Pragma: no-cache' );
                echo 'Gone';
                exit;
            }
        }
    }
}, 0 );
