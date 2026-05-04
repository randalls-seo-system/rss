<?php
/**
 * Plugin Name: VALN – Form Submit Guard
 * Description: Adds error handling + retry UI to GF Form 9 AJAX submissions.
 *              Generates client-side UUID for server-side deduplication.
 *              Detects 429, 5xx, network errors, and 15s timeouts.
 * Version: 1.0.0
 * Author: VA Loan Network
 */

if (!defined('ABSPATH')) exit;

// ============================================================
// JS ENQUEUE — only on form 9 pages
// ============================================================
add_filter('gform_enqueue_scripts', function($form, $is_ajax) {
    if ((int) $form['id'] !== 9) return;

    $js_url = content_url('mu-plugins/valn-form-submit-guard.js');
    $js_path = WP_CONTENT_DIR . '/mu-plugins/valn-form-submit-guard.js';
    $ver = file_exists($js_path) ? filemtime($js_path) : '1.0.0';

    wp_enqueue_script(
        'valn-form-submit-guard',
        $js_url,
        ['jquery', 'valn-form-tracker'],
        $ver,
        true
    );
}, 30, 2);

// ============================================================
// SERVER-SIDE UUID DEDUPLICATION
// ============================================================

/**
 * Before GF processes the submission, check for duplicate UUID.
 * If the UUID was already processed (transient exists), skip the
 * FUB webhook and email notifications but still return success.
 */
add_filter('gform_entry_post_save', function($entry, $form) {
    if ((int) $form['id'] !== 9) return $entry;

    $uuid = isset($_POST['valn_submit_uuid']) ? sanitize_text_field($_POST['valn_submit_uuid']) : '';
    if (empty($uuid) || strlen($uuid) > 64) return $entry;

    $transient_key = 'valn_lead_uuid_' . md5($uuid);

    if (get_transient($transient_key)) {
        // Duplicate submission — mark the entry so downstream hooks can skip
        gform_update_meta($entry['id'], 'valn_duplicate_submit', '1');
        error_log('[VALN Submit Guard] Duplicate UUID detected: ' . $uuid . ' entry=' . $entry['id']);
    } else {
        // First submission — cache the UUID for 5 minutes
        set_transient($transient_key, $entry['id'], 5 * MINUTE_IN_SECONDS);
        gform_update_meta($entry['id'], 'valn_submit_uuid', $uuid);
    }

    return $entry;
}, 5, 2);

/**
 * Skip FUB webhook for duplicate submissions.
 * The GF Webhooks addon checks gform_webhooks_enabled_{form_id} before firing.
 */
add_filter('gform_webhooks_enabled_9', function($enabled, $feed, $entry, $form) {
    $is_dupe = gform_get_meta($entry['id'], 'valn_duplicate_submit');
    if ($is_dupe) {
        error_log('[VALN Submit Guard] Skipping FUB webhook for duplicate entry ' . $entry['id']);
        return false;
    }
    return $enabled;
}, 10, 4);

/**
 * Skip email notifications for duplicate submissions.
 */
add_filter('gform_disable_notification_9', function($disabled, $notification, $form, $entry) {
    $is_dupe = gform_get_meta($entry['id'], 'valn_duplicate_submit');
    if ($is_dupe) {
        error_log('[VALN Submit Guard] Skipping notification "' . $notification['name'] . '" for duplicate entry ' . $entry['id']);
        return true;
    }
    return $disabled;
}, 10, 4);
