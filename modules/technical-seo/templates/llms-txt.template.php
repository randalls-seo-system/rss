<?php
/**
 * RSS Technical SEO Module — llms-txt.php
 * Source: VALN production (pulled 2026-05-03)
 * Status: Template
 *
 * Template variables (replaced at deploy time):
 * - {{SITE_PREFIX}} — function/identifier prefix (lowercase)
 * - {{SITE_NAME}} — display name
 *
 * Render with: ./modules/technical-seo/render.sh <site-config>
 */
if ( ! defined( 'ABSPATH' ) ) exit;

/* ---------- Rewrite rule ---------- */

add_action( 'init', function () {
    add_rewrite_rule( '^llms\.txt$', 'index.php?{{SITE_PREFIX}}_llms_txt=1', 'top' );
} );

add_filter( 'query_vars', function ( $vars ) {
    $vars[] = '{{SITE_PREFIX}}_llms_txt';
    return $vars;
} );

/* ---------- Serve the file ---------- */

add_action( 'template_redirect', function () {
    if ( ! get_query_var( '{{SITE_PREFIX}}_llms_txt' ) ) {
        return;
    }

    header( 'Content-Type: text/plain; charset=UTF-8' );
    header( 'Cache-Control: public, max-age=3600' );
    header( 'X-Robots-Tag: index, follow' );

    $content = get_transient( '{{SITE_PREFIX}}_llms_txt_v2' );
    if ( false === $content ) {
        $content = {{SITE_PREFIX}}_llms_txt_generate();
        set_transient( '{{SITE_PREFIX}}_llms_txt_v2', $content, DAY_IN_SECONDS );
    }

    echo $content;
    exit;
} );

/* ---------- Static file via daily cron ---------- */

add_action( '{{SITE_PREFIX}}_llms_txt_daily_write', '{{SITE_PREFIX}}_llms_txt_write_static' );

add_action( 'init', function () {
    if ( ! wp_next_scheduled( '{{SITE_PREFIX}}_llms_txt_daily_write' ) ) {
        wp_schedule_event( time(), 'daily', '{{SITE_PREFIX}}_llms_txt_daily_write' );
    }
}, 20 );

function {{SITE_PREFIX}}_llms_txt_write_static() {
    $content = {{SITE_PREFIX}}_llms_txt_generate();
    set_transient( '{{SITE_PREFIX}}_llms_txt_v2', $content, DAY_IN_SECONDS );

    $doc_root = defined( 'ABSPATH' ) ? ABSPATH : $_SERVER['DOCUMENT_ROOT'] . '/';
    $path     = rtrim( $doc_root, '/' ) . '/llms.txt';
    file_put_contents( $path, $content );
}

/* ---------- Cache invalidation on curated post save ---------- */

add_action( 'save_post', function ( $post_id ) {
    if ( ! function_exists( '{{SITE_PREFIX}}_llms_get_all_post_ids' ) ) {
        return;
    }
    if ( in_array( (int) $post_id, {{SITE_PREFIX}}_llms_get_all_post_ids(), true ) ) {
        delete_transient( '{{SITE_PREFIX}}_llms_txt_v2' );
    }
}, 20 );

/* ---------- Generator ---------- */

function {{SITE_PREFIX}}_llms_txt_generate() {
    if ( ! function_exists( '{{SITE_PREFIX}}_llms_get_config' ) ) {
        return '# {{SITE_NAME}}' . "\n" . '> Configuration not loaded.' . "\n";
    }

    $config = {{SITE_PREFIX}}_llms_get_config();
    $b      = rtrim( home_url(), '/' );
    $lines  = [];

    // Header
    $lines[] = '# {{SITE_NAME}}';
    $lines[] = '> ' . $config['intro'];
    $lines[] = '';

    // Sections
    foreach ( $config['sections'] as $section ) {
        $lines[] = '## ' . $section['title'];
        foreach ( $section['items'] as $item ) {
            $url     = $b . $item['path'];
            $lines[] = '- [' . $item['title'] . '](' . $url . '): ' . $item['desc'];
        }
        $lines[] = '';
    }

    // Contact
    $cta     = $config['contact']['cta'];
    $lines[] = '## Contact';
    $lines[] = '- [' . $cta['title'] . '](' . $b . $cta['path'] . '): ' . $cta['desc'];
    $lines[] = '- Phone: ' . $config['contact']['phone'];
    $lines[] = '';

    // Disclosures
    $lines[] = '## Important Disclosures';
    $lines[] = $config['disclosures'];
    $lines[] = '';

    return implode( "\n", $lines );
}
