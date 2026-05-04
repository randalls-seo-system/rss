<?php
/**
 * Force-enable search engine indexing (blog_public = 1) and prevent it from being changed.
 * Install: put this file at wp-content/mu-plugins/force-enable-indexing.php
 *
 * Notes:
 * - MU-plugins run on every request and cannot be deactivated via the WP admin.
 * - If you use an object cache (Redis, Memcached), you may need to flush it after installing.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

/**
 * Always return '1' when WP tries to read the option.
 * This prevents get_option('blog_public') from returning 0.
 */
add_filter( 'pre_option_blog_public', function( $pre ) {
    return '1';
} );

/**
 * Prevent updates to blog_public by forcing the updated value to '1'.
 * This runs before update_option() writes to the DB.
 */
add_filter( 'pre_update_option_blog_public', function( $new_value, $old_value ) {
    return '1';
}, 10, 2 );

/**
 * Double-safety: on init ensure DB has blog_public = '1'
 */
add_action( 'init', function() {
    $current = get_option( 'blog_public' );
    if ( $current !== '1' && $current !== 1 ) {
        update_option( 'blog_public', '1' );
    }
} );

/**
 * Hide the admin checkbox row on Settings → Reading to reduce accidental toggles.
 */
add_action( 'admin_head-options-reading.php', function() {
    echo '<style>#blog_public, label[for="blog_public"], input#blog_public { display:none !important; }</style>';
} );

add_action( 'admin_footer-options-reading.php', function() {
    echo "<script>(function(){ var el = document.getElementById('blog_public'); if(el){ var tr = el.closest('tr'); if(tr) tr.style.display='none'; } })();</script>";
} );
