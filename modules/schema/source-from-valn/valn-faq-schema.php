<?php
/**
 * Plugin Name: VALN FAQ Schema
 * Description: Outputs FAQPage JSON-LD from vlnFaq <details>/<summary> blocks.
 *              Deduplication: questions on 3+ pages sitewide are excluded.
 *              Frequency table cached in wp_options; refreshed daily via wp-cron.
 */
if ( ! defined( 'ABSPATH' ) ) exit;

define( 'VALN_FAQSC_FREQ_OPT', 'valn_faq_schema_freq'    ); // serialized array: qkey => page count
define( 'VALN_FAQSC_TS_OPT',   'valn_faq_schema_freq_ts' ); // unix timestamp of last build
define( 'VALN_FAQSC_TTL',      86400 );  // refresh every 24 hours
define( 'VALN_FAQSC_THRESH',   3     );  // exclude if question appears on this many+ pages
define( 'VALN_FAQSC_MIN_QA',   2     );  // minimum qualifying Q/A pairs to output schema

/* ── Cron ────────────────────────────────────────────────────────────────── */

add_action( 'valn_faqsc_rebuild_cron', 'valn_faqsc_build_freq' );

add_action( 'init', function () {
    if ( ! wp_next_scheduled( 'valn_faqsc_rebuild_cron' ) ) {
        wp_schedule_event( time() + VALN_FAQSC_TTL, 'daily', 'valn_faqsc_rebuild_cron' );
    }
} );

/* ── Frequency table ─────────────────────────────────────────────────────── */

/**
 * Return the cached frequency table, rebuilding if stale or missing.
 * Returns: array of qkey (lowercase normalized question text) => int (page count)
 */
function valn_faqsc_get_freq() {
    $stored = get_option( VALN_FAQSC_FREQ_OPT, null );
    $ts     = (int) get_option( VALN_FAQSC_TS_OPT, 0 );

    if ( $stored === null || ( time() - $ts ) > VALN_FAQSC_TTL ) {
        return valn_faqsc_build_freq();
    }
    return (array) $stored;
}

/**
 * Scan all published posts/pages with vlnFaq content and build
 * a map of normalized question text => number of distinct pages it appears on.
 * Stores result in wp_options with a timestamp.
 */
function valn_faqsc_build_freq() {
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
        $pairs    = valn_faqsc_extract_pairs( $p->post_content );
        $seen_here = [];

        foreach ( $pairs as $pair ) {
            $key = valn_faqsc_qkey( $pair['q'] );
            if ( isset( $seen_here[ $key ] ) ) continue; // count each question once per page
            $freq[ $key ]  = ( $freq[ $key ] ?? 0 ) + 1;
            $seen_here[ $key ] = true;
        }
    }

    update_option( VALN_FAQSC_FREQ_OPT, $freq, false );
    update_option( VALN_FAQSC_TS_OPT,   time(), false );

    return $freq;
}

/** Normalize a question string to a stable comparison key. */
function valn_faqsc_qkey( $q ) {
    return strtolower( trim( preg_replace( '/\s+/', ' ', strip_tags( $q ) ) ) );
}

/* ── Q/A extraction ──────────────────────────────────────────────────────── */

/**
 * Extract all Q/A pairs from raw post_content HTML.
 * Looks for <details> blocks containing span.vlnFaqQ and div.ans.
 * Returns: array of ['q' => string, 'a' => string]
 */
function valn_faqsc_extract_pairs( $html ) {
    $pairs = [];

    // Match every <details>…</details> block (vlnFaq items are never nested)
    if ( ! preg_match_all( '~<details\b[^>]*>(.*?)</details>~is', $html, $dm ) ) {
        return $pairs;
    }

    foreach ( $dm[1] as $inner ) {
        // Question: <span class="vlnFaqQ …">text</span>
        if ( ! preg_match( '~<span\b[^>]+class="[^"]*vlnFaqQ[^"]*"[^>]*>(.*?)</span>~is', $inner, $qm ) ) continue;
        $q = trim( strip_tags( $qm[1] ) );
        if ( $q === '' ) continue;

        // Answer: <div class="ans …">…</div>  (div.ans never contains nested <div>)
        if ( ! preg_match( '~<div\b[^>]+class="[^"]*\bans\b[^"]*"[^>]*>(.*?)</div>~is', $inner, $am ) ) continue;
        $a = trim( $am[1] );
        if ( $a === '' ) continue;

        $pairs[] = [ 'q' => $q, 'a' => $a ];
    }

    return $pairs;
}

/* ── wp_head output ──────────────────────────────────────────────────────── */

add_action( 'wp_head', 'valn_faqsc_output', 90 );

function valn_faqsc_output() {
    // Only on singular front-end pages; never on the application page
    if ( ! is_singular() || is_page( 385 ) ) return;

    $post = get_post();
    if ( ! $post ) return;

    // Quick bail if no vlnFaq markup at all
    if ( stripos( $post->post_content, 'class="vlnFaq"' ) === false ) return;

    $all_pairs = valn_faqsc_extract_pairs( $post->post_content );
    if ( empty( $all_pairs ) ) return;

    $freq      = valn_faqsc_get_freq();
    $qualified = [];
    $seen      = [];

    foreach ( $all_pairs as $pair ) {
        $key = valn_faqsc_qkey( $pair['q'] );

        // Skip duplicate questions within this page
        if ( isset( $seen[ $key ] ) ) continue;
        $seen[ $key ] = true;

        // Skip sitewide-common questions (appear on THRESH+ pages)
        if ( ( $freq[ $key ] ?? 1 ) >= VALN_FAQSC_THRESH ) continue;

        $qualified[] = $pair;
    }

    // Need at least MIN_QA unique questions to produce valid FAQPage schema
    if ( count( $qualified ) < VALN_FAQSC_MIN_QA ) return;

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
