<?php
/**
 * RSS Technical SEO Module — llms-config.php
 * Source: VALN production (pulled 2026-05-03)
 * Status: Template
 *
 * Template variables (replaced at deploy time):
 * - {{SITE_PREFIX}} — function/identifier prefix (lowercase)
 * - {{SITE_NAME}} — display name (used in fallback only)
 *
 * Site-specific URL configuration loaded from companion file:
 *   {{SITE_PREFIX}}-llms-urls.php (must be in same directory)
 *
 * Render with: ./modules/technical-seo/render.sh <site-config>
 */
if ( ! defined( 'ABSPATH' ) ) exit;

/**
 * Return the curated content configuration.
 *
 * Each item: [ 'id' => post_id, 'path' => '/slug/', 'title' => '...', 'desc' => '...' ]
 * Post IDs are used for content retrieval (llms-full.txt, markdown variants).
 * Paths + titles + descriptions are used for llms.txt generation.
 */
function {{SITE_PREFIX}}_llms_get_config() {
    $data_file = __DIR__ . '/{{SITE_PREFIX}}-llms-urls.php';
    if ( ! file_exists( $data_file ) ) {
        return [
            'intro'       => '{{SITE_NAME}}',
            'disclosures' => '',
            'sections'    => [],
            'contact'     => [
                'cta'   => [ 'id' => 0, 'path' => '/', 'title' => 'Get Started', 'desc' => '' ],
                'phone' => '',
            ],
        ];
    }
    return require $data_file;
}

/**
 * Get flat array of all unique post IDs in the curated list.
 */
function {{SITE_PREFIX}}_llms_get_all_post_ids() {
    $config = {{SITE_PREFIX}}_llms_get_config();
    $ids = [];
    foreach ( $config['sections'] as $section ) {
        foreach ( $section['items'] as $item ) {
            $ids[] = $item['id'];
        }
    }
    if ( isset( $config['contact']['cta']['id'] ) ) {
        $ids[] = $config['contact']['cta']['id'];
    }
    return array_unique( $ids );
}

/**
 * Get post IDs flagged as interactive tools (get description-only markdown fallback).
 */
function {{SITE_PREFIX}}_llms_get_tool_post_ids() {
    $config = {{SITE_PREFIX}}_llms_get_config();
    return isset( $config['tool_post_ids'] ) ? $config['tool_post_ids'] : [];
}

/**
 * Check if a given post ID is a tool/calculator page.
 */
function {{SITE_PREFIX}}_llms_is_tool_page( $post_id ) {
    return in_array( (int) $post_id, {{SITE_PREFIX}}_llms_get_tool_post_ids(), true );
}
