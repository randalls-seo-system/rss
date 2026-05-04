<?php
/**
 * RSS Redirects Module — redirect-engine.php
 * Source: VALN production valn-redirect-engine.php (pulled 2026-05-04)
 * Status: Template
 *
 * Template variables:
 * - {{SITE_PREFIX}} — function prefix
 * - {{SITE_PREFIX_UPPER}} — constant prefix
 *
 * Data-driven 301 redirect handler. Loads redirect map from a companion
 * PHP file (<prefix>-redirect-map.php) that returns an associative array.
 *
 * Fires at template_redirect priority 0, before canonical/404 handling.
 * Works with full-page cache (WP Engine, Cloudflare, etc.).
 */
if ( ! defined( 'ABSPATH' ) ) exit;

add_action( 'template_redirect', function () {
    if (
        is_admin()
        || ( defined( 'DOING_AJAX' ) && DOING_AJAX )
        || ( defined( 'DOING_CRON' ) && DOING_CRON )
        || ( defined( 'REST_REQUEST' ) && REST_REQUEST )
    ) {
        return;
    }

    $uri  = $_SERVER['REQUEST_URI'] ?? '';
    $path = strtok( $uri, '?' );
    if ( $path === '' || $path[0] !== '/' ) return;

    $normalized = '/' . trim( strtolower( $path ), '/' ) . '/';

    // Load redirect map from companion data file
    static $map = null;
    if ( $map === null ) {
        $map_file = __DIR__ . '/{{SITE_PREFIX}}-redirect-map.php';
        if ( file_exists( $map_file ) ) {
            $map = include $map_file;
            if ( ! is_array( $map ) ) $map = [];
        } else {
            $map = [];
        }
    }

    if ( empty( $map ) ) return;

    // Exact match
    if ( isset( $map[ $normalized ] ) ) {
        $dest = $map[ $normalized ];
        if ( strpos( $dest, 'http' ) !== 0 ) {
            $dest = home_url( $dest );
        }
        wp_redirect( $dest, 301 );
        exit;
    }

    // Try without trailing slash
    $no_slash = rtrim( $normalized, '/' ) . '/';
    if ( $no_slash !== $normalized && isset( $map[ $no_slash ] ) ) {
        $dest = $map[ $no_slash ];
        if ( strpos( $dest, 'http' ) !== 0 ) {
            $dest = home_url( $dest );
        }
        wp_redirect( $dest, 301 );
        exit;
    }
}, 0 );
