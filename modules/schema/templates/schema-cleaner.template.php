<?php
/**
 * RSS Schema Module — schema-cleaner.php
 * Source: VALN production (pulled 2026-05-04)
 * Status: Template
 *
 * Template variables:
 * - {{SITE_PREFIX_UPPER}} — uppercase prefix for class name
 *
 * Removes inline FAQPage and HowTo JSON-LD scripts from rendered content
 * sitewide. Prevents duplicate schema from page builders like Divi.
 */
if ( ! defined( 'ABSPATH' ) ) exit;

final class {{SITE_PREFIX_UPPER}}_Schema_Cleaner {

    public static function init(): void {
        add_filter( 'the_content',          [ __CLASS__, 'clean_jsonld_in_content' ], 1 );
        add_filter( 'the_excerpt',          [ __CLASS__, 'clean_jsonld_in_content' ], 1 );
        add_filter( 'widget_text',          [ __CLASS__, 'clean_jsonld_in_content' ], 1 );
        add_filter( 'widget_text_content',  [ __CLASS__, 'clean_jsonld_in_content' ], 1 );
        add_filter( 'et_builder_render_layout', [ __CLASS__, 'clean_jsonld_in_content' ], 1 );
    }

    public static function clean_jsonld_in_content( $content ) {
        if ( ! is_string( $content ) || $content === '' ) return $content;

        $pattern = '#<script[^>]*type=("|\')application/ld\+json\1[^>]*>(.*?)</script>#is';

        if ( ! preg_match_all( $pattern, $content, $matches, PREG_SET_ORDER ) ) {
            return $content;
        }

        foreach ( $matches as $m ) {
            $full = $m[0];
            $raw  = trim( $m[2] );

            if ( $raw === '' ) {
                $content = str_replace( $full, '', $content );
                continue;
            }

            $decoded = json_decode( $raw, true );
            if ( json_last_error() !== JSON_ERROR_NONE ) {
                $content = str_replace( $full, '', $content );
                continue;
            }

            $hasHowTo = self::contains_type( $decoded, 'HowTo' );
            $hasFAQ   = self::contains_type( $decoded, 'FAQPage' );

            if ( $hasHowTo || $hasFAQ ) {
                $content = str_replace( $full, '', $content );
            }
        }

        return $content;
    }

    private static function contains_type( $node, string $type ): bool {
        if ( ! is_array( $node ) ) return false;

        if ( isset( $node['@type'] ) ) {
            if ( is_string( $node['@type'] ) && strcasecmp( $node['@type'], $type ) === 0 ) return true;
            if ( is_array( $node['@type'] ) ) {
                foreach ( $node['@type'] as $t ) {
                    if ( is_string( $t ) && strcasecmp( $t, $type ) === 0 ) return true;
                }
            }
        }

        if ( isset( $node['@graph'] ) && is_array( $node['@graph'] ) ) {
            foreach ( $node['@graph'] as $g ) {
                if ( self::contains_type( $g, $type ) ) return true;
            }
        }

        foreach ( $node as $v ) {
            if ( is_array( $v ) && self::contains_type( $v, $type ) ) return true;
        }

        return false;
    }
}

{{SITE_PREFIX_UPPER}}_Schema_Cleaner::init();
