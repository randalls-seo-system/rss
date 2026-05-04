<?php
/**
 * RSS Redirects Module — force-enable-indexing.php
 * Source: VALN production (pulled 2026-05-04)
 * Status: Template (no site-specific variables — universal)
 *
 * Forces blog_public=1 and prevents accidental noindex.
 * Safety net against staging settings leaking to production.
 */
if ( ! defined( 'ABSPATH' ) ) exit;

add_filter( 'pre_option_blog_public', function( $pre ) {
    return '1';
} );

add_filter( 'pre_update_option_blog_public', function( $new_value, $old_value ) {
    return '1';
}, 10, 2 );

add_action( 'init', function() {
    $current = get_option( 'blog_public' );
    if ( $current !== '1' && $current !== 1 ) {
        update_option( 'blog_public', '1' );
    }
} );

add_action( 'admin_head-options-reading.php', function() {
    echo '<style>#blog_public, label[for="blog_public"], input#blog_public { display:none !important; }</style>';
} );

add_action( 'admin_footer-options-reading.php', function() {
    echo "<script>(function(){ var el = document.getElementById('blog_public'); if(el){ var tr = el.closest('tr'); if(tr) tr.style.display='none'; } })();</script>";
} );
