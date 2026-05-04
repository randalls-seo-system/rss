<?php
/**
 * Plugin Name: VALN llms-full.txt Generator
 * Description: Single-file markdown export of top 50-75 curated VA
 *              loan pages at /llms-full.txt for AI agent ingestion.
 * Version: 1.0.0
 * Author: VALN
 */
if ( ! defined( 'ABSPATH' ) ) exit;

/* ---------- Rewrite rule (fallback if nginx misses the static file) ---------- */

add_action( 'init', function () {
    add_rewrite_rule( '^llms-full\.txt$', 'index.php?valn_llms_full=1', 'top' );
} );

add_filter( 'query_vars', function ( $vars ) {
    $vars[] = 'valn_llms_full';
    return $vars;
} );

/* ---------- Serve: WP fallback (nginx normally serves the static file) ---------- */

add_action( 'template_redirect', function () {
    if ( ! get_query_var( 'valn_llms_full' ) ) {
        return;
    }

    header( 'Content-Type: text/markdown; charset=UTF-8' );
    header( 'Cache-Control: public, max-age=3600' );
    header( 'X-Robots-Tag: index, follow' );

    $static = valn_llms_full_docroot_path();
    if ( file_exists( $static ) ) {
        readfile( $static );
    } else {
        $content = valn_llms_full_generate();
        valn_llms_full_write_files( $content );
        echo $content;
    }

    exit;
} );

/* ---------- Daily cron regeneration ---------- */

add_action( 'valn_regenerate_llms_full', 'valn_llms_full_regenerate' );

add_action( 'init', function () {
    if ( ! wp_next_scheduled( 'valn_regenerate_llms_full' ) ) {
        $next = strtotime( 'tomorrow 02:00:00 UTC' );
        wp_schedule_event( $next, 'daily', 'valn_regenerate_llms_full' );
    }
}, 20 );

function valn_llms_full_regenerate() {
    $content = valn_llms_full_generate();
    valn_llms_full_write_files( $content );
}

/* ---------- File paths ---------- */

function valn_llms_full_docroot_path() {
    $doc_root = defined( 'ABSPATH' ) ? ABSPATH : $_SERVER['DOCUMENT_ROOT'] . '/';
    return rtrim( $doc_root, '/' ) . '/llms-full.txt';
}

function valn_llms_full_cache_path() {
    $upload_dir = wp_upload_dir();
    return $upload_dir['basedir'] . '/llms-full-cache.txt';
}

function valn_llms_full_write_files( $content ) {
    // Write to doc root (nginx serves this)
    file_put_contents( valn_llms_full_docroot_path(), $content );
    // Also write to uploads as backup
    file_put_contents( valn_llms_full_cache_path(), $content );
}

/* ---------- Generator ---------- */

function valn_llms_full_generate() {
    if ( ! function_exists( 'valn_llms_get_config' ) || ! function_exists( 'valn_md_html_to_markdown' ) ) {
        return "# VA Loan Network\n> Dependencies not loaded.\n";
    }

    $config   = valn_llms_get_config();
    $base_url = rtrim( home_url(), '/' );
    $out      = [];
    $seen_ids = [];
    $count    = 0;
    $max      = 75;

    // Header
    $out[] = '# VA Loan Network';
    $out[] = '> ' . $config['intro'];
    $out[] = '';

    // Priority order for sections (per spec)
    $priority_keys = [ 'guides', 'eligibility', 'rates', 'refinance', 'tools', 'special', 'disability', 'about' ];

    // Index sections by key
    $sections_by_key = [];
    foreach ( $config['sections'] as $section ) {
        $sections_by_key[ $section['key'] ] = $section;
    }

    foreach ( $priority_keys as $key ) {
        if ( $count >= $max ) break;
        if ( ! isset( $sections_by_key[ $key ] ) ) continue;

        $section = $sections_by_key[ $key ];

        foreach ( $section['items'] as $item ) {
            if ( $count >= $max ) break;

            $post_id = $item['id'];

            // Skip duplicates (e.g. IRRRL appears in both tools and refinance)
            if ( isset( $seen_ids[ $post_id ] ) ) continue;
            $seen_ids[ $post_id ] = true;

            $post = get_post( $post_id );
            if ( ! $post || $post->post_status !== 'publish' ) continue;

            $permalink = get_permalink( $post_id );
            $prod_url  = str_replace( $base_url, 'https://valoannetwork.com', $permalink );

            $out[] = '## ' . $post->post_title;
            $out[] = '';
            $out[] = '**URL:** ' . $prod_url;
            $out[] = '**Section:** ' . $section['title'];
            $out[] = '';

            // Tool pages: description only
            if ( function_exists( 'valn_llms_is_tool_page' ) && valn_llms_is_tool_page( $post_id ) ) {
                $out[] = 'This page contains the ' . $post->post_title . ' interactive calculator/tool.';
                $out[] = 'Visit ' . $prod_url . ' to use it.';
                $meta = get_post_meta( $post_id, '_yoast_wpseo_metadesc', true );
                if ( $meta ) {
                    $out[] = '';
                    $out[] = $meta;
                }
            } else {
                // Full markdown conversion
                $md = valn_md_html_to_markdown( $post->post_content );
                $out[] = $md;
            }

            $out[] = '';
            $out[] = '---';
            $out[] = '';
            $count++;
        }
    }

    // Disclosures at the end
    $out[] = '## Important Disclosures';
    $out[] = '';
    $out[] = $config['disclosures'];
    $out[] = '';

    $result = implode( "\n", $out );

    // Safety: truncate if over 500KB
    if ( strlen( $result ) > 500000 ) {
        $result = substr( $result, 0, 499000 );
        $result .= "\n\n---\n\n*[Content truncated at 500KB limit]*\n";
    }

    return $result;
}
