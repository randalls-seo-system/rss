<?php
/**
 * Plugin Name: VALN — Yoast Org @id Canonicalizer
 * Description: Forces Yoast Organization node to @id https://your-site/#organization
 * Author: VALN
 */

add_filter( 'wpseo_schema_organization', function( $data ) {
    $data['@id']  = home_url( '#organization' );
    $data['name'] = isset( $data['name'] ) ? $data['name'] : 'VA Loan Network';
    return $data;
}, 10 );
