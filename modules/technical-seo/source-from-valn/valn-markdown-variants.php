<?php
/**
 * Plugin Name: VALN Markdown Variants
 * Description: Serves clean Markdown versions of pages at ?format=md
 *              for AI crawler ingestion. Aggressive Divi/nav stripping.
 * Version: 1.0.0
 * Author: VALN
 */
if ( ! defined( 'ABSPATH' ) ) exit;

add_action( 'template_redirect', function () {
    $is_md = false;

    if ( isset( $_GET['format'] ) && $_GET['format'] === 'md' ) {
        $is_md = true;
    } elseif ( isset( $_SERVER['HTTP_ACCEPT'] ) && strpos( $_SERVER['HTTP_ACCEPT'], 'text/markdown' ) !== false ) {
        $is_md = true;
    }

    if ( ! $is_md || ! is_singular() ) {
        return;
    }

    $post = get_queried_object();
    if ( ! $post || ! isset( $post->ID ) ) {
        return;
    }

    // Skip compare-loan-offers (Gravity Forms, no good markdown conversion)
    if ( $post->post_name === 'compare-loan-offers' ) {
        return;
    }

    header( 'Content-Type: text/markdown; charset=UTF-8' );
    header( 'Cache-Control: public, max-age=3600' );
    header( 'X-Robots-Tag: index, follow' );

    $cache_key = 'valn_md_' . $post->ID;
    $content   = get_transient( $cache_key );

    if ( false === $content ) {
        $content = valn_md_render( $post );
        set_transient( $cache_key, $content, 7 * DAY_IN_SECONDS );
    }

    echo $content;
    exit;
} );

/* ---------- Cache invalidation ---------- */

add_action( 'save_post', function ( $post_id ) {
    delete_transient( 'valn_md_' . $post_id );
}, 20 );

/* ---------- Render ---------- */

function valn_md_render( $post ) {
    $base_url = rtrim( home_url(), '/' );
    $permalink = get_permalink( $post->ID );

    // Use production URL in output regardless of environment
    $prod_url = str_replace(
        $base_url,
        'https://valoannetwork.com',
        $permalink
    );

    // Meta description
    $meta_desc = '';
    $yoast_desc = get_post_meta( $post->ID, '_yoast_wpseo_metadesc', true );
    if ( $yoast_desc ) {
        $meta_desc = $yoast_desc;
    } elseif ( $post->post_excerpt ) {
        $meta_desc = $post->post_excerpt;
    }

    // Front matter
    $out  = '# ' . $post->post_title . "\n";
    if ( $meta_desc ) {
        $out .= '> ' . $meta_desc . "\n";
    }
    $out .= "\n";
    $out .= '**URL:** ' . $prod_url . "\n";
    $out .= '**Last updated:** ' . date( 'F j, Y', strtotime( $post->post_modified ) ) . "\n";
    $out .= "\n---\n\n";

    // Tool page fallback
    if ( function_exists( 'valn_llms_is_tool_page' ) && valn_llms_is_tool_page( $post->ID ) ) {
        $out .= 'This page contains the ' . $post->post_title . ' interactive calculator/tool.' . "\n";
        $out .= 'Visit ' . $prod_url . ' to use it.' . "\n";
        if ( $meta_desc ) {
            $out .= "\n" . $meta_desc . "\n";
        }
        return $out;
    }

    // Also detect tool shortcodes in content
    if ( preg_match( '/\[valn_va_|\[valn_calc|\[valn_tool|\[gravityform/', $post->post_content ) ) {
        $out .= 'This page contains an interactive tool.' . "\n";
        $out .= 'Visit ' . $prod_url . ' to use it.' . "\n";
        if ( $meta_desc ) {
            $out .= "\n" . $meta_desc . "\n";
        }
        return $out;
    }

    // Convert post content to markdown
    $html = $post->post_content;
    $out .= valn_md_html_to_markdown( $html );

    return $out;
}

/* ---------- HTML to Markdown converter ---------- */

function valn_md_html_to_markdown( $html ) {
    // Phase 1: Strip Divi shortcodes (preserve inner content)
    // Remove self-closing Divi shortcodes
    $html = preg_replace( '/\[\/?et_pb_[^\]]*\]/', '', $html );

    // Strip other known shortcodes that don't produce useful text
    $html = preg_replace( '/\[gravityform[^\]]*\]/', '', $html );
    $html = preg_replace( '/\[valn_[^\]]*\]/', '', $html );
    $html = preg_replace( '/\[ez-toc[^\]]*\]/', '', $html );
    $html = preg_replace( '/\[vc_[^\]]*\]/', '', $html );

    // Phase 2: Strip elements that carry no content value
    // Remove script, style, iframe, svg, noscript blocks
    $html = preg_replace( '/<script[^>]*>.*?<\/script>/si', '', $html );
    $html = preg_replace( '/<style[^>]*>.*?<\/style>/si', '', $html );
    $html = preg_replace( '/<iframe[^>]*>.*?<\/iframe>/si', '', $html );
    $html = preg_replace( '/<iframe[^>]*\/>/si', '', $html );
    $html = preg_replace( '/<svg[^>]*>.*?<\/svg>/si', '', $html );
    $html = preg_replace( '/<noscript[^>]*>.*?<\/noscript>/si', '', $html );

    // Remove nav, header, footer, aside
    $html = preg_replace( '/<nav[^>]*>.*?<\/nav>/si', '', $html );
    $html = preg_replace( '/<header[^>]*>.*?<\/header>/si', '', $html );
    $html = preg_replace( '/<footer[^>]*>.*?<\/footer>/si', '', $html );
    $html = preg_replace( '/<aside[^>]*>.*?<\/aside>/si', '', $html );

    // Remove share buttons, social blocks
    $html = preg_replace( '/<div[^>]*class="[^"]*(?:share|social|sharedaddy)[^"]*"[^>]*>.*?<\/div>/si', '', $html );

    // Remove "Related Posts" sections
    $html = preg_replace( '/<div[^>]*class="[^"]*related[^"]*"[^>]*>.*?<\/div>/si', '', $html );

    // Phase 3: Convert structural HTML to Markdown

    // Headings
    $html = preg_replace_callback( '/<h([1-6])[^>]*>(.*?)<\/h\1>/si', function ( $m ) {
        $level = (int) $m[1];
        $text  = strip_tags( $m[2] );
        $text  = trim( $text );
        if ( ! $text ) return '';
        return "\n" . str_repeat( '#', $level ) . ' ' . $text . "\n";
    }, $html );

    // Links — convert before stripping remaining tags
    $html = preg_replace_callback( '/<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)<\/a>/si', function ( $m ) {
        $url  = $m[1];
        $text = strip_tags( $m[2] );
        $text = trim( $text );
        if ( ! $text ) return '';
        // Skip anchor links and javascript:
        if ( strpos( $url, '#' ) === 0 || strpos( $url, 'javascript:' ) === 0 ) {
            return $text;
        }
        return '[' . $text . '](' . $url . ')';
    }, $html );

    // Images — alt text only
    $html = preg_replace_callback( '/<img[^>]+alt=["\']([^"\']*)["\'][^>]*\/?>/si', function ( $m ) {
        $alt = trim( $m[1] );
        return $alt ? '![' . $alt . ']' : '';
    }, $html );

    // Bold and italic
    $html = preg_replace( '/<(strong|b)>(.*?)<\/\1>/si', '**$2**', $html );
    $html = preg_replace( '/<(em|i)>(.*?)<\/\1>/si', '*$2*', $html );

    // Unordered lists
    $html = preg_replace_callback( '/<ul[^>]*>(.*?)<\/ul>/si', function ( $m ) {
        $items = '';
        preg_match_all( '/<li[^>]*>(.*?)<\/li>/si', $m[1], $lis );
        foreach ( $lis[1] as $li ) {
            $text = strip_tags( $li, '<a><strong><em><b><i>' );
            $text = trim( $text );
            if ( $text ) {
                // Convert remaining inline HTML
                $text = preg_replace( '/<(strong|b)>(.*?)<\/\1>/si', '**$2**', $text );
                $text = preg_replace( '/<(em|i)>(.*?)<\/\1>/si', '*$2*', $text );
                $text = preg_replace_callback( '/<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)<\/a>/si', function ( $a ) {
                    return '[' . strip_tags( $a[2] ) . '](' . $a[1] . ')';
                }, $text );
                $text = strip_tags( $text );
                $items .= '- ' . $text . "\n";
            }
        }
        return "\n" . $items;
    }, $html );

    // Ordered lists
    $html = preg_replace_callback( '/<ol[^>]*>(.*?)<\/ol>/si', function ( $m ) {
        $items = '';
        $n = 1;
        preg_match_all( '/<li[^>]*>(.*?)<\/li>/si', $m[1], $lis );
        foreach ( $lis[1] as $li ) {
            $text = strip_tags( $li );
            $text = trim( $text );
            if ( $text ) {
                $items .= $n . '. ' . $text . "\n";
                $n++;
            }
        }
        return "\n" . $items;
    }, $html );

    // Simple tables
    $html = preg_replace_callback( '/<table[^>]*>(.*?)<\/table>/si', function ( $m ) {
        $md = "\n";
        // Extract rows
        preg_match_all( '/<tr[^>]*>(.*?)<\/tr>/si', $m[1], $rows );
        $is_first = true;
        foreach ( $rows[1] as $row ) {
            preg_match_all( '/<(?:td|th)[^>]*>(.*?)<\/(?:td|th)>/si', $row, $cells );
            $cell_texts = array_map( function ( $c ) {
                return trim( strip_tags( $c ) );
            }, $cells[1] );
            if ( empty( $cell_texts ) ) continue;
            $md .= '| ' . implode( ' | ', $cell_texts ) . " |\n";
            if ( $is_first ) {
                $md .= '|' . implode( '|', array_fill( 0, count( $cell_texts ), ' --- ' ) ) . "|\n";
                $is_first = false;
            }
        }
        return $md . "\n";
    }, $html );

    // Blockquotes
    $html = preg_replace_callback( '/<blockquote[^>]*>(.*?)<\/blockquote>/si', function ( $m ) {
        $text = strip_tags( $m[1] );
        $text = trim( $text );
        $lines = explode( "\n", $text );
        $quoted = array_map( function ( $l ) { return '> ' . trim( $l ); }, $lines );
        return "\n" . implode( "\n", $quoted ) . "\n";
    }, $html );

    // Horizontal rules
    $html = preg_replace( '/<hr[^>]*\/?>/i', "\n---\n", $html );

    // Paragraphs — add double newlines
    $html = preg_replace( '/<\/p>\s*/i', "\n\n", $html );
    $html = preg_replace( '/<p[^>]*>/i', '', $html );

    // Line breaks
    $html = preg_replace( '/<br\s*\/?>/i', "\n", $html );

    // Phase 4: Strip all remaining HTML tags
    $html = strip_tags( $html );

    // Phase 5: Clean up whitespace
    // Decode HTML entities
    $html = html_entity_decode( $html, ENT_QUOTES | ENT_HTML5, 'UTF-8' );

    // Collapse multiple blank lines to max 2
    $html = preg_replace( '/\n{3,}/', "\n\n", $html );

    // Trim leading/trailing whitespace per line
    $lines = explode( "\n", $html );
    $lines = array_map( 'trim', $lines );
    $html  = implode( "\n", $lines );

    // Trim overall
    $html = trim( $html );

    return $html . "\n";
}
