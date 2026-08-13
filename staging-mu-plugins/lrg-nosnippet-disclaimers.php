<?php
/**
 * Plugin Name: LRG Disclaimer Styling + Snippet Control
 * Description: Two responsibilities:
 *   1. Adds data-nosnippet attribute to Educational Notice (.rl-callout--note)
 *      and Legal & Tax Disclaimer (.rl-disclosure) blocks at render time,
 *      preventing Google from using them as SERP snippets.
 *   2. Injects CSS to style both disclaimer blocks: smaller text (0.82em),
 *      muted background (#f8f8f6), subtle grey left border. Scoped with
 *      [role="note"] and .rl-disclosure to avoid hitting other .rl-callout
 *      variants (pro-tip, deal-saver, etc.).
 * Version: 1.1.0
 * Author: Rank Logic
 *
 * This is a the_content filter, not a post_content rewrite. It operates at render
 * time so it covers all existing and future posts without touching stored content.
 */

add_filter('the_content', 'lrg_add_nosnippet_to_disclaimers', 99);
add_action('wp_head', 'lrg_disclaimer_styles', 999);

/**
 * Disclaimer styling: smaller text, muted background, subtle left border.
 * Uses .rl-page.rl-page doubled-class specificity + !important to beat
 * the existing V4 callout rules in lrg-article-styles.php which also
 * use .rl-page.rl-page + !important.
 */
function lrg_disclaimer_styles() {
    if (!is_singular()) return;
    ?>
    <style id="lrg-disclaimer-styles">
    /* Educational Notice */
    .rl-page.rl-page .rl-callout.rl-callout--note[role="note"] {
        font-size: 0.82em !important;
        line-height: 1.45 !important;
        padding: 12px 16px !important;
        background: #f8f8f6 !important;
        border: none !important;
        border-left: 3px solid #c0c0b8 !important;
        border-radius: 0 !important;
        color: #555 !important;
        margin: 16px 0 !important;
    }
    .rl-page.rl-page .rl-callout.rl-callout--note[role="note"] p {
        font-size: inherit !important;
        color: inherit !important;
    }
    .rl-page.rl-page .rl-callout.rl-callout--note[role="note"] strong {
        color: #444 !important;
    }
    .rl-page.rl-page .rl-callout.rl-callout--note[role="note"] a {
        color: #1a6bb5 !important;
    }

    /* Legal & Tax Disclaimer */
    .rl-page.rl-page .rl-callout.rl-disclosure,
    .rl-page.rl-page section.rl-disclosure {
        font-size: 0.82em !important;
        line-height: 1.45 !important;
        padding: 12px 16px !important;
        background: #f8f8f6 !important;
        border: none !important;
        border-left: 3px solid #c0c0b8 !important;
        border-radius: 0 !important;
        color: #555 !important;
    }
    .rl-page.rl-page .rl-callout.rl-disclosure p,
    .rl-page.rl-page section.rl-disclosure p {
        font-size: inherit !important;
        color: inherit !important;
    }
    .rl-page.rl-page .rl-callout.rl-disclosure h3,
    .rl-page.rl-page section.rl-disclosure h3 {
        font-size: 0.95em !important;
        color: #444 !important;
        margin: 0 0 8px !important;
    }
    </style>
    <?php
}

function lrg_add_nosnippet_to_disclaimers($content) {
    if (!is_singular()) {
        return $content;
    }

    // Educational Notice: <div class="rl-callout rl-callout--note" ...>
    if (preg_match('/<div[^>]*rl-callout--note[^>]*data-nosnippet/i', $content) === 0) {
        $content = preg_replace(
            '/(<div\b[^>]*class="[^"]*rl-callout--note[^"]*"[^>]*)>/i',
            '$1 data-nosnippet>',
            $content
        );
    }

    // Legal & Tax Disclaimer: <section class="rl-callout rl-disclosure" ...>
    if (preg_match('/<section[^>]*rl-disclosure[^>]*data-nosnippet/i', $content) === 0) {
        $content = preg_replace(
            '/(<section\b[^>]*class="[^"]*rl-disclosure[^"]*"[^>]*)>/i',
            '$1 data-nosnippet>',
            $content
        );
    }

    return $content;
}
