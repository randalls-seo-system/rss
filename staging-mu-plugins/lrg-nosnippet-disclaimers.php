<?php
/**
 * Plugin Name: LRG Disclaimer data-nosnippet
 * Description: Adds data-nosnippet attribute to Educational Notice and Legal & Tax
 *              Disclaimer blocks at render time, preventing Google from using them
 *              as SERP snippets. Targets .rl-callout--note and .rl-disclosure.
 * Version: 1.0.0
 * Author: Rank Logic
 *
 * This is a the_content filter, not a post_content rewrite. It operates at render
 * time so it covers all existing and future posts without touching stored content.
 */

add_filter('the_content', 'lrg_add_nosnippet_to_disclaimers', 99);

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
