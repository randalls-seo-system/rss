<?php
/**
 * RSS Schema Module — org-id.php
 * Source: VALN production (pulled 2026-05-04)
 * Status: Template
 *
 * Template variables:
 * - {{SITE_NAME}} — organization display name
 *
 * Forces Yoast Organization node @id to canonical home_url('#organization')
 * and ensures the org name matches the configured site name.
 */
if ( ! defined( 'ABSPATH' ) ) exit;

add_filter( 'wpseo_schema_organization', function( $data ) {
    $data['@id']  = home_url( '#organization' );
    $data['name'] = isset( $data['name'] ) ? $data['name'] : '{{SITE_NAME}}';
    return $data;
}, 10 );
