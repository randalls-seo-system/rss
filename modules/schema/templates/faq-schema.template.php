<?php
/**
 * RSS Schema Module — faq-schema.php
 * Source: VALN production (pulled 2026-05-04)
 * Status: Template
 *
 * Template variables:
 * - {{SITE_PREFIX}} — function/identifier prefix (lowercase)
 * - {{SITE_PREFIX_UPPER}} — uppercase prefix for constants
 * - {{FORM_PAGE_SLUG}} — slug of form/application page to exclude (optional)
 *
 * Outputs FAQPage JSON-LD from vlnFaq <details>/<summary> blocks.
 * Deduplication: questions on 3+ pages sitewide are excluded.
 * Frequency table cached in wp_options; refreshed daily via wp-cron.
 */
if ( ! defined( 'ABSPATH' ) ) exit;

define( '{{SITE_PREFIX_UPPER}}_FAQSC_FREQ_OPT', '{{SITE_PREFIX}}_faq_schema_freq'    );
define( '{{SITE_PREFIX_UPPER}}_FAQSC_TS_OPT',   '{{SITE_PREFIX}}_faq_schema_freq_ts' );
define( '{{SITE_PREFIX_UPPER}}_FAQSC_TTL',      86400 );
define( '{{SITE_PREFIX_UPPER}}_FAQSC_THRESH',   3     );
define( '{{SITE_PREFIX_UPPER}}_FAQSC_MIN_QA',   2     );

/* -- Cron -- */

add_action( '{{SITE_PREFIX}}_faqsc_rebuild_cron', '{{SITE_PREFIX}}_faqsc_build_freq' );

add_action( 'init', function () {
    if ( ! wp_next_scheduled( '{{SITE_PREFIX}}_faqsc_rebuild_cron' ) ) {
        wp_schedule_event( time() + {{SITE_PREFIX_UPPER}}_FAQSC_TTL, 'daily', '{{SITE_PREFIX}}_faqsc_rebuild_cron' );
    }
} );

/* -- Frequency table -- */

function {{SITE_PREFIX}}_faqsc_get_freq() {
    $stored = get_option( {{SITE_PREFIX_UPPER}}_FAQSC_FREQ_OPT, null );
    $ts     = (int) get_option( {{SITE_PREFIX_UPPER}}_FAQSC_TS_OPT, 0 );

    if ( $stored === null || ( time() - $ts ) > {{SITE_PREFIX_UPPER}}_FAQSC_TTL ) {
        return {{SITE_PREFIX}}_faqsc_build_freq();
    }
    return (array) $stored;
}

function {{SITE_PREFIX}}_faqsc_build_freq() {
    global $wpdb;

    $posts = $wpdb->get_results(
        "SELECT ID, post_content
         FROM {$wpdb->posts}
         WHERE post_status = 'publish'
           AND post_type   IN ('post','page')
           AND post_content LIKE '%class=\"vlnFaq\"%'
         LIMIT 2000"
    );

    $freq = [];

    foreach ( $posts as $p ) {
        $pairs     = {{SITE_PREFIX}}_faqsc_extract_pairs( $p->post_content );
        $seen_here = [];

        foreach ( $pairs as $pair ) {
            $key = {{SITE_PREFIX}}_faqsc_qkey( $pair['q'] );
            if ( isset( $seen_here[ $key ] ) ) continue;
            $freq[ $key ]  = ( $freq[ $key ] ?? 0 ) + 1;
            $seen_here[ $key ] = true;
        }
    }

    update_option( {{SITE_PREFIX_UPPER}}_FAQSC_FREQ_OPT, $freq, false );
    update_option( {{SITE_PREFIX_UPPER}}_FAQSC_TS_OPT,   time(), false );

    return $freq;
}

function {{SITE_PREFIX}}_faqsc_qkey( $q ) {
    return strtolower( trim( preg_replace( '/\s+/', ' ', strip_tags( $q ) ) ) );
}

/* -- Q/A extraction -- */

function {{SITE_PREFIX}}_faqsc_extract_pairs( $html ) {
    $pairs = [];

    if ( ! preg_match_all( '~<details\b[^>]*>(.*?)</details>~is', $html, $dm ) ) {
        return $pairs;
    }

    foreach ( $dm[1] as $inner ) {
        if ( ! preg_match( '~<span\b[^>]+class="[^"]*vlnFaqQ[^"]*"[^>]*>(.*?)</span>~is', $inner, $qm ) ) continue;
        $q = trim( strip_tags( $qm[1] ) );
        if ( $q === '' ) continue;

        if ( ! preg_match( '~<div\b[^>]+class="[^"]*\bans\b[^"]*"[^>]*>(.*?)</div>~is', $inner, $am ) ) continue;
        $a = trim( $am[1] );
        if ( $a === '' ) continue;

        $pairs[] = [ 'q' => $q, 'a' => $a ];
    }

    return $pairs;
}

/* -- wp_head output -- */

add_action( 'wp_head', '{{SITE_PREFIX}}_faqsc_output', 90 );

function {{SITE_PREFIX}}_faqsc_output() {
    if ( ! is_singular() ) return;

    // Skip form/application page if configured
    $skip_slug = '{{FORM_PAGE_SLUG}}';
    if ( $skip_slug !== '' ) {
        $post_obj = get_post();
        if ( $post_obj && $post_obj->post_name === $skip_slug ) return;
    }

    $post = get_post();
    if ( ! $post ) return;

    if ( stripos( $post->post_content, 'class="vlnFaq"' ) === false ) return;

    $all_pairs = {{SITE_PREFIX}}_faqsc_extract_pairs( $post->post_content );
    if ( empty( $all_pairs ) ) return;

    $freq      = {{SITE_PREFIX}}_faqsc_get_freq();
    $qualified = [];
    $seen      = [];

    foreach ( $all_pairs as $pair ) {
        $key = {{SITE_PREFIX}}_faqsc_qkey( $pair['q'] );

        if ( isset( $seen[ $key ] ) ) continue;
        $seen[ $key ] = true;

        if ( ( $freq[ $key ] ?? 1 ) >= {{SITE_PREFIX_UPPER}}_FAQSC_THRESH ) continue;

        $qualified[] = $pair;
    }

    if ( count( $qualified ) < {{SITE_PREFIX_UPPER}}_FAQSC_MIN_QA ) return;

    $entities = [];
    foreach ( $qualified as $pair ) {
        $entities[] = [
            '@type'          => 'Question',
            'name'           => html_entity_decode( strip_tags( $pair['q'] ), ENT_QUOTES | ENT_HTML5, 'UTF-8' ),
            'acceptedAnswer' => [
                '@type' => 'Answer',
                'text'  => html_entity_decode( wp_strip_all_tags( $pair['a'] ), ENT_QUOTES | ENT_HTML5, 'UTF-8' ),
            ],
        ];
    }

    $schema = [
        '@context'   => 'https://schema.org',
        '@type'      => 'FAQPage',
        'mainEntity' => $entities,
    ];

    echo '<script type="application/ld+json">' . "\n"
        . wp_json_encode( $schema, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT )
        . "\n</script>\n";
}
