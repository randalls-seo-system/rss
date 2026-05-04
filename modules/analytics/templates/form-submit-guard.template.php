<?php
/**
 * RSS Analytics Module — form-submit-guard.php
 * Source: VALN production valn-form-submit-guard.php (pulled 2026-05-04)
 * Status: Template
 *
 * Template variables:
 * - {{SITE_PREFIX}} — function/file prefix
 * - {{SITE_PREFIX_UPPER}} — uppercase prefix for log tags
 * - {{LEAD_FORM_ID}} — Gravity Forms lead form ID
 *
 * Adds error handling + retry UI to GF AJAX submissions.
 * Client-side UUID for server-side deduplication.
 * Detects 429, 5xx, network errors, and 15s timeouts.
 */
if ( ! defined( 'ABSPATH' ) ) exit;

// JS enqueue — only on lead form pages
add_filter( 'gform_enqueue_scripts', function( $form, $is_ajax ) {
    $lead_form_id = '{{LEAD_FORM_ID}}';
    if ( $lead_form_id === '' || (int) $form['id'] !== (int) $lead_form_id ) return;

    $js_url  = content_url( 'mu-plugins/{{SITE_PREFIX}}-form-submit-guard.js' );
    $js_path = WP_CONTENT_DIR . '/mu-plugins/{{SITE_PREFIX}}-form-submit-guard.js';
    $ver = file_exists( $js_path ) ? filemtime( $js_path ) : '1.0.0';

    wp_enqueue_script(
        '{{SITE_PREFIX}}-form-submit-guard',
        $js_url,
        [ 'jquery' ],
        $ver,
        true
    );
}, 30, 2 );

// Server-side UUID deduplication
add_filter( 'gform_entry_post_save', function( $entry, $form ) {
    $lead_form_id = '{{LEAD_FORM_ID}}';
    if ( $lead_form_id === '' || (int) $form['id'] !== (int) $lead_form_id ) return $entry;

    $uuid = isset( $_POST['{{SITE_PREFIX}}_submit_uuid'] ) ? sanitize_text_field( $_POST['{{SITE_PREFIX}}_submit_uuid'] ) : '';
    if ( empty( $uuid ) || strlen( $uuid ) > 64 ) return $entry;

    $transient_key = '{{SITE_PREFIX}}_lead_uuid_' . md5( $uuid );

    if ( get_transient( $transient_key ) ) {
        gform_update_meta( $entry['id'], '{{SITE_PREFIX}}_duplicate_submit', '1' );
        error_log( '[{{SITE_PREFIX_UPPER}} Submit Guard] Duplicate UUID: ' . $uuid . ' entry=' . $entry['id'] );
    } else {
        set_transient( $transient_key, $entry['id'], 5 * MINUTE_IN_SECONDS );
        gform_update_meta( $entry['id'], '{{SITE_PREFIX}}_submit_uuid', $uuid );
    }

    return $entry;
}, 5, 2 );

// Skip webhook for duplicates
$lead_form_id_for_filter = '{{LEAD_FORM_ID}}';
if ( $lead_form_id_for_filter !== '' ) {
    add_filter( 'gform_webhooks_enabled_' . $lead_form_id_for_filter, function( $enabled, $feed, $entry, $form ) {
        $is_dupe = gform_get_meta( $entry['id'], '{{SITE_PREFIX}}_duplicate_submit' );
        if ( $is_dupe ) {
            error_log( '[{{SITE_PREFIX_UPPER}} Submit Guard] Skipping webhook for duplicate entry ' . $entry['id'] );
            return false;
        }
        return $enabled;
    }, 10, 4 );

    // Skip email notifications for duplicates
    add_filter( 'gform_disable_notification_' . $lead_form_id_for_filter, function( $disabled, $notification, $form, $entry ) {
        $is_dupe = gform_get_meta( $entry['id'], '{{SITE_PREFIX}}_duplicate_submit' );
        if ( $is_dupe ) {
            error_log( '[{{SITE_PREFIX_UPPER}} Submit Guard] Skipping notification for duplicate entry ' . $entry['id'] );
            return true;
        }
        return $disabled;
    }, 10, 4 );
}
