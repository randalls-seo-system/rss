<?php
/**
 * Plugin Name: RSS TOC Manager
 * Description: Generic sticky Table of Contents with configurable CTA, widget, shortcode, per-post control, and heading exclusions. Part of Randall's SEO System standard plugin stack.
 * Version: 1.0.1
 * Author: Randall's SEO System
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

if ( ! class_exists( 'RSS_TOC_Manager' ) ) :

class RSS_TOC_Manager {

    const OPTION_KEY       = 'rss_toc_settings';
    const META_KEY         = '_rss_toc_enabled';
    const META_CTA_LINE1   = '_rss_toc_cta_line1';
    const META_CTA_LINE2   = '_rss_toc_cta_line2';
    const META_CTA_LINE3   = '_rss_toc_cta_line3';
    const META_CTA_BUTTON  = '_rss_toc_cta_button';

    /**
     * Bootstrap.
     */
    public static function init() {
        // Frontend behaviour.
        add_filter( 'the_content', array( __CLASS__, 'filter_content_add_toc' ), 15 );
        add_action( 'wp_enqueue_scripts', array( __CLASS__, 'enqueue_assets' ) );
        add_action( 'wp_enqueue_scripts', array( __CLASS__, 'enqueue_scripts' ) );

        // Shortcodes.
        add_shortcode( 'rss_toc', array( __CLASS__, 'shortcode_output' ) );

        // Legacy Easy TOC alias.
        add_shortcode( 'ez-toc', array( __CLASS__, 'ez_toc_compat_shortcode' ) );

        // Admin.
        if ( is_admin() ) {
            add_action( 'admin_menu', array( __CLASS__, 'add_settings_page' ) );
            add_action( 'add_meta_boxes', array( __CLASS__, 'add_meta_box' ) );
            add_action( 'save_post', array( __CLASS__, 'save_post_meta' ) );

            add_filter( 'manage_post_posts_columns', array( __CLASS__, 'add_toc_column' ) );
            add_action( 'manage_post_posts_custom_column', array( __CLASS__, 'render_toc_column' ), 10, 2 );
            add_filter( 'manage_page_posts_columns', array( __CLASS__, 'add_toc_column' ) );
            add_action( 'manage_page_posts_custom_column', array( __CLASS__, 'render_toc_column' ), 10, 2 );

            add_filter( 'bulk_actions-edit-post', array( __CLASS__, 'register_bulk_actions' ) );
            add_filter( 'bulk_actions-edit-page', array( __CLASS__, 'register_bulk_actions' ) );
            add_filter( 'handle_bulk_actions-edit-post', array( __CLASS__, 'handle_bulk_actions' ), 10, 3 );
            add_filter( 'handle_bulk_actions-edit-page', array( __CLASS__, 'handle_bulk_actions' ), 10, 3 );
            add_action( 'admin_notices', array( __CLASS__, 'bulk_admin_notice' ) );

            add_action( 'admin_enqueue_scripts', array( __CLASS__, 'admin_enqueue' ) );
        }

        // Sidebar widget.
        add_action( 'widgets_init', array( __CLASS__, 'register_widget' ) );
    }

    /**
     * Get settings with defaults.
     */
    public static function get_settings() {
        $defaults = array(
            'enable_posts'       => 1,
            'enable_pages'       => 1,
            'default_enabled'    => 1,
            'disable_on_front'   => 0,
            'inline_nav'         => 1,
            'disable_mobile_toc' => 1,
            'mobile_breakpoint'  => 980,
            'min_headings'       => 3,
            'max_headings'       => 6,
            'insert_position'    => 'after_first_paragraph',
            'title_text'         => 'In this Article',
            'cta_text'           => '',
            'cta_url'            => '',
            // Global CTA heading lines.
            'cta_line1'          => '',
            'cta_line2'          => '',
            'cta_line3'          => '',
            'exclude_headings'   => '',
            'link_color'         => '#007BFF',
            'button_bg_color'    => '#007BFF',
            'button_text_color'  => '#FFFFFF',
        );

        $options = get_option( self::OPTION_KEY, array() );
        $options = wp_parse_args( $options, $defaults );

        $options['min_headings'] = max( 1, intval( $options['min_headings'] ) );
        $options['max_headings'] = max( $options['min_headings'], intval( $options['max_headings'] ) );
        $options['mobile_breakpoint'] = max( 480, min( 1400, intval( $options['mobile_breakpoint'] ) ) );
        $options['disable_mobile_toc'] = ! empty( $options['disable_mobile_toc'] ) ? 1 : 0;

        foreach ( array( 'link_color', 'button_bg_color', 'button_text_color' ) as $key ) {
            if ( isset( $options[ $key ] ) ) {
                if ( function_exists( 'sanitize_hex_color' ) ) {
                    $san = sanitize_hex_color( $options[ $key ] );
                    if ( $san ) {
                        $options[ $key ] = $san;
                        continue;
                    }
                }
                if ( ! preg_match( '/^#([A-Fa-f0-9]{3}){1,2}$/', $options[ $key ] ) ) {
                    $options[ $key ] = $defaults[ $key ];
                }
            } else {
                $options[ $key ] = $defaults[ $key ];
            }
        }

        return $options;
    }

    /**
     * Apply per-post CTA overrides to settings.
     */
    public static function apply_cta_overrides( $settings, $post_id ) {
        $overrides = array(
            'cta_line1' => get_post_meta( $post_id, self::META_CTA_LINE1, true ),
            'cta_line2' => get_post_meta( $post_id, self::META_CTA_LINE2, true ),
            'cta_line3' => get_post_meta( $post_id, self::META_CTA_LINE3, true ),
            'cta_text'  => get_post_meta( $post_id, self::META_CTA_BUTTON, true ),
        );

        foreach ( $overrides as $key => $value ) {
            if ( $value !== '' ) {
                $settings[ $key ] = $value;
            }
        }

        return $settings;
    }

    /**
     * Admin: enqueue colour picker.
     */
    public static function admin_enqueue( $hook ) {
        if ( $hook !== 'settings_page_rss-toc-manager' ) {
            return;
        }
        wp_enqueue_style( 'wp-color-picker' );
        wp_enqueue_script( 'wp-color-picker' );
    }

    /**
     * Frontend styles.
     */
    public static function enqueue_assets() {
        if ( is_admin() ) {
            return;
        }

        $settings          = self::get_settings();
        $link_color        = $settings['link_color'];
        $button_bg_color   = $settings['button_bg_color'];
        $button_text_color = $settings['button_text_color'];
        $mobile_breakpoint = intval( $settings['mobile_breakpoint'] );

        $handle = 'rss-toc-manager';
        wp_register_style( $handle, false );
        wp_enqueue_style( $handle );

        $css = '
/* === RSS TOC – core styling === */

.rss-toc,
.rss-toc * {
    box-sizing: border-box;
}

.rss-toc {
    background-color: #ffffff;
    border: none;
    box-shadow: none;
    padding: 16px 0 20px;
    margin: 0 0 24px;
    font-size: 0.95rem;
    font-family: "Poppins", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    width: 100%;
    max-width: 100%;
    overflow-wrap: anywhere;
    word-break: break-word;
}

.rss-toc-title {
    font-weight: 600;
    font-size: 1.05rem;
    color: #002A5C;
    margin: 0 0 8px;
    padding: 0 0 8px;
    border-bottom: 1px solid #e0e0e0;
}

/* List reset */
.rss-toc ul {
    list-style: none;
    margin: 0;
    padding: 0;
}

.rss-toc ul li {
    margin: 4px 0;
}

/* Link + arrow */
.rss-toc ul li a {
    position: relative;
    display: block;
    padding-left: 16px;
    color: ' . $link_color . ' !important;
    text-decoration: none !important;
    font-size: 0.95rem;
    font-weight: 400;
    transition: transform 0.12s ease, color 0.12s ease;
}

.rss-toc ul li a::before {
    content: ">";
    position: absolute;
    left: 0;
    top: 0;
    line-height: 1.4;
    font-size: 1rem;
    color: ' . $link_color . ' !important;
}

/* Hover: move link 4px to the right */
.rss-toc ul li a:hover {
    color: ' . $link_color . ' !important;
    transform: translateX(4px);
}

/* CTA block */
.rss-toc-cta-wrap {
    margin-top: 8px;
    text-align: center;
}

.rss-toc-cta-heading {
    margin-bottom: 10px;
    text-align: center;
    font-family: "Poppins", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    line-height: 1.05;
}

.rss-toc-cta-heading span {
    display: block;
    font-weight: 700;
    margin: 0;
    padding: 0;
    line-height: 1.05;
}

.rss-cta-line1,
.rss-cta-line3 {
    font-size: 18px;
    color: #002A5C;
}

.rss-cta-line2 {
    font-size: 30px;
    color: ' . $link_color . ';
    margin-top: 2px;
    margin-bottom: 2px;
}

/* CTA button */
.rss-toc-cta {
    display: inline-flex !important;
    align-items: center;
    justify-content: center;
    padding: 10px 24px;
    border-radius: 999px;
    background-color: ' . $button_bg_color . ' !important;
    color: ' . $button_text_color . ' !important;
    font-family: "Poppins", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
    font-size: 18px !important;
    font-weight: 600;
    text-decoration: none !important;
    border: none !important;
    cursor: pointer;
    white-space: normal;
    width: auto !important;
    max-width: 100%;
    box-shadow: none !important;
    transition: transform 0.12s ease, box-shadow 0.12s ease, background-color 0.12s ease;
    text-align: center;
}

.rss-toc-cta::before,
.rss-toc-cta::after {
    content: none !important;
    border: 0 !important;
}

.rss-toc-cta:hover {
    background-color: ' . $button_bg_color . ' !important;
    transform: scale(1.05);
}

/* Sidebar widget wrapper */
.rss-toc-sidebar-widget {
    box-sizing: border-box;
    width: 100%;
    max-width: 100%;
    clear: both;
    float: none;
    align-self: flex-start;
}

.rss-toc-sidebar {
    position: relative;
    width: 100%;
    max-width: 100%;
}

@media (min-width: ' . ( $mobile_breakpoint + 1 ) . 'px) {
    .rss-toc-sidebar-widget {
        position: -webkit-sticky;
        position: sticky;
        top: var(--rss-toc-sticky-top, 100px);
    }
}

/* Top sticky CTA bar (appears after scrolling past inline CTA) */
.rss-toc-sticky-cta {
    position: fixed;
    left: 0;
    right: 0;
    top: var(--rss-toc-header-offset, 0px);
    background-color: #ffffff;
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.04);
    z-index: 9999;
    padding: 8px 16px;
    transform: translateY(-100%);
    transition: transform 0.18s ease;
}

.rss-toc-sticky-cta.is-visible {
    transform: translateY(0);
}

.rss-toc-sticky-cta-inner {
    max-width: 1100px;
    margin: 0 auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
}

.rss-toc-sticky-cta-text {
    font-family: "Poppins", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 15px;
    font-weight: 600;
    color: #002A5C;
}

.rss-toc-sticky-cta-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 8px 20px;
    border-radius: 999px;
    background-color: ' . $button_bg_color . ' !important;
    color: ' . $button_text_color . ' !important;
    font-family: "Poppins", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 15px;
    font-weight: 600;
    text-decoration: none !important;
    white-space: nowrap;
    border: none;
}

.rss-toc-sticky-cta-btn:hover {
    transform: scale(1.04);
}

@media (max-width: 600px) {
    .rss-toc-sticky-cta-text {
        font-size: 14px;
    }
    .rss-toc-sticky-cta-btn {
        font-size: 14px;
        padding: 7px 16px;
    }
}

/* Shortcode variant: adjust CTA spacing + remove underline */
.rss-toc-shortcode .rss-toc-title {
    border-bottom: none;
    padding-bottom: 0;
    margin-bottom: 6px;
}

.rss-toc-shortcode .rss-toc-cta-wrap {
    margin-top: 8px;
}

.rss-toc-target,
h2[id] {
    scroll-margin-top: calc(var(--rss-toc-sticky-top, 100px) + 8px);
}
';

        if ( ! empty( $settings['disable_mobile_toc'] ) ) {
            $css .= '
@media (max-width: ' . $mobile_breakpoint . 'px) {
    .rss-toc-hide-mobile,
    .rss-toc-sidebar-widget,
    .rss-toc-sticky-cta {
        display: none !important;
    }
}
';
        }

        wp_add_inline_style( $handle, $css );
    }

    /**
     * Frontend scripts.
     */
    public static function enqueue_scripts() {
        if ( is_admin() ) {
            return;
        }

        $settings = self::get_settings();
        $config   = array(
            'disableMobile'    => ! empty( $settings['disable_mobile_toc'] ),
            'mobileBreakpoint' => intval( $settings['mobile_breakpoint'] ),
            'stickyGap'        => 16,
        );

        $handle = 'rss-toc-js';
        wp_register_script( $handle, '', array(), false, true );
        wp_enqueue_script( $handle );

        wp_add_inline_script( $handle, 'window.rssTocConfig = ' . wp_json_encode( $config ) . ';', 'before' );

        $js = '
document.addEventListener("DOMContentLoaded", function() {
    var cfg = window.rssTocConfig || {};
    var disableMobile = !!cfg.disableMobile;
    var mobileBreakpoint = parseInt(cfg.mobileBreakpoint, 10);
    var stickyGap = parseInt(cfg.stickyGap, 10);

    if (!mobileBreakpoint || mobileBreakpoint < 1) {
        mobileBreakpoint = 980;
    }
    if (isNaN(stickyGap) || stickyGap < 0) {
        stickyGap = 16;
    }

    function isSmallScreen() {
        return window.innerWidth <= mobileBreakpoint;
    }

    function normalizeText(str) {
        return (str || "").replace(/\s+/g, " ").trim().toLowerCase();
    }

    function getHeaderOffset() {
        var maxBottom = 0;
        var candidates = document.querySelectorAll("header, .site-header, #main-header, .et-l--header");

        candidates.forEach(function(node) {
            if (!node) {
                return;
            }

            try {
                var style = window.getComputedStyle(node);
                if (style.display === "none" || style.visibility === "hidden") {
                    return;
                }
                if (style.position !== "fixed" && style.position !== "sticky") {
                    return;
                }

                var rect = node.getBoundingClientRect();
                if (rect.height <= 0) {
                    return;
                }
                if (rect.bottom <= 0) {
                    return;
                }

                maxBottom = Math.max(maxBottom, rect.bottom);
            } catch (e) {
                // Ignore layout read issues.
            }
        });

        return Math.max(0, Math.round(maxBottom));
    }

    function applyOffsets() {
        var headerOffset = getHeaderOffset();
        document.documentElement.style.setProperty("--rss-toc-header-offset", headerOffset + "px");
        document.documentElement.style.setProperty("--rss-toc-sticky-top", (headerOffset + stickyGap) + "px");
    }

    function ensureHeadingIds() {
        var links = document.querySelectorAll(".rss-toc a[href^=\"#\"][data-rss-toc-id]");
        if (!links.length) {
            return;
        }

        var headings = Array.prototype.slice.call(document.querySelectorAll("h2"));
        if (!headings.length) {
            return;
        }

        var usedIndexes = {};

        links.forEach(function(link) {
            var id = (link.getAttribute("data-rss-toc-id") || "").replace(/^#/, "");
            if (!id) {
                return;
            }

            var target = document.getElementById(id);
            if (target) {
                target.classList.add("rss-toc-target");
                return;
            }

            var targetText = normalizeText(link.getAttribute("data-rss-toc-text") || link.textContent);
            if (!targetText) {
                return;
            }

            for (var i = 0; i < headings.length; i++) {
                if (usedIndexes[i]) {
                    continue;
                }

                var heading = headings[i];
                if (normalizeText(heading.textContent) !== targetText) {
                    continue;
                }

                if (!heading.id) {
                    heading.id = id;
                } else {
                    link.setAttribute("href", "#" + heading.id);
                    link.setAttribute("data-rss-toc-id", heading.id);
                }

                heading.classList.add("rss-toc-target");
                usedIndexes[i] = true;
                break;
            }
        });
    }

    var headingTicking = false;
    function requestHeadingSync() {
        if (headingTicking) {
            return;
        }
        headingTicking = true;
        window.requestAnimationFrame(function() {
            ensureHeadingIds();
            headingTicking = false;
        });
    }

    var offsetTicking = false;
    function requestOffsetSync() {
        if (offsetTicking) {
            return;
        }
        offsetTicking = true;
        window.requestAnimationFrame(function() {
            applyOffsets();
            offsetTicking = false;
        });
    }

    applyOffsets();
    ensureHeadingIds();

    window.addEventListener("load", function() {
        applyOffsets();
        ensureHeadingIds();
    });

    window.addEventListener("resize", function() {
        applyOffsets();
        ensureHeadingIds();
    });

    window.addEventListener("scroll", requestOffsetSync, { passive: true });

    document.addEventListener("click", function(event) {
        if (!event.target || !event.target.closest) {
            return;
        }

        var tocLink = event.target.closest(".rss-toc a[href^=\"#\"]");
        if (!tocLink) {
            return;
        }

        ensureHeadingIds();
    });

    if ("MutationObserver" in window && document.body) {
        var observerTimer = null;
        var observer = new MutationObserver(function() {
            window.clearTimeout(observerTimer);
            observerTimer = window.setTimeout(function() {
                requestHeadingSync();
            }, 50);
        });

        observer.observe(document.body, { childList: true, subtree: true });

        window.setTimeout(function() {
            try {
                observer.disconnect();
            } catch (e) {
                // Ignore observer cleanup errors.
            }
        }, 4000);
    }

    window.setTimeout(function() {
        applyOffsets();
        ensureHeadingIds();
    }, 300);

    window.setTimeout(ensureHeadingIds, 1000);

    var ctaWrap = document.querySelector(".rss-toc-shortcode .rss-toc-cta-wrap") || document.querySelector(".rss-toc:not(.rss-toc-sidebar) .rss-toc-cta-wrap");
    if (!ctaWrap) {
        return;
    }

    var ctaButton = ctaWrap.querySelector(".rss-toc-cta");
    if (!ctaButton) {
        return;
    }

    var line1 = ctaWrap.querySelector(".rss-cta-line1");
    var line2 = ctaWrap.querySelector(".rss-cta-line2");
    var line3 = ctaWrap.querySelector(".rss-cta-line3");

    var parts = [];
    [line1, line2, line3].forEach(function(node) {
        if (node && node.textContent) {
            var t = node.textContent.replace(/\s+/g, " ").trim();
            if (t.length) {
                parts.push(t);
            }
        }
    });

    var compactText = parts.join(" ");
    if (!compactText && ctaButton.textContent) {
        compactText = ctaButton.textContent.replace(/\s+/g, " ").trim();
    }

    var btnText = ctaButton.textContent ? ctaButton.textContent.trim() : "";
    var btnHref = ctaButton.getAttribute("href") || "#";

    var bar = document.createElement("div");
    bar.className = "rss-toc-sticky-cta" + (disableMobile ? " rss-toc-hide-mobile" : "");

    var inner = document.createElement("div");
    inner.className = "rss-toc-sticky-cta-inner";

    var textDiv = document.createElement("div");
    textDiv.className = "rss-toc-sticky-cta-text";
    textDiv.textContent = compactText;

    var btn = document.createElement("a");
    btn.className = "rss-toc-sticky-cta-btn";
    btn.href = btnHref;
    btn.textContent = btnText;

    inner.appendChild(textDiv);
    inner.appendChild(btn);
    bar.appendChild(inner);
    document.body.appendChild(bar);

    var triggerBottom = 0;
    var ticking = false;

    function updateTrigger() {
        var rect = ctaWrap.getBoundingClientRect();
        var scrollTop = window.pageYOffset || document.documentElement.scrollTop || 0;
        triggerBottom = rect.top + scrollTop + rect.height;
    }

    function syncBar() {
        applyOffsets();

        if (disableMobile && isSmallScreen()) {
            bar.classList.remove("is-visible");
            return;
        }

        var scrollTop = window.pageYOffset || document.documentElement.scrollTop || 0;
        if (scrollTop > triggerBottom) {
            bar.classList.add("is-visible");
        } else {
            bar.classList.remove("is-visible");
        }
    }

    function requestSync() {
        if (ticking) {
            return;
        }
        ticking = true;
        window.requestAnimationFrame(function() {
            syncBar();
            ticking = false;
        });
    }

    updateTrigger();
    syncBar();

    window.addEventListener("scroll", requestSync, { passive: true });
    window.addEventListener("resize", function() {
        updateTrigger();
        syncBar();
        ensureHeadingIds();
    });

    window.setTimeout(function() {
        updateTrigger();
        syncBar();
        ensureHeadingIds();
    }, 500);
});
';

        wp_add_inline_script( $handle, $js );
    }

    /**
     * Per-post enable logic.
     */
    public static function is_toc_enabled_for_post( $post, $settings = null ) {
        if ( ! $post ) {
            return false;
        }
        if ( ! $settings ) {
            $settings = self::get_settings();
        }

        $post_type = get_post_type( $post );
        if ( $post_type === 'post' && empty( $settings['enable_posts'] ) ) {
            return false;
        }
        if ( $post_type === 'page' && empty( $settings['enable_pages'] ) ) {
            return false;
        }
        if ( ! in_array( $post_type, array( 'post', 'page' ), true ) ) {
            return false;
        }

        if ( ! empty( $settings['disable_on_front'] ) && ( is_front_page() || is_home() ) ) {
            return false;
        }

        $meta            = get_post_meta( $post->ID, self::META_KEY, true );
        $default_enabled = ! empty( $settings['default_enabled'] );

        if ( $meta === 'on' ) {
            return true;
        }
        if ( $meta === 'off' ) {
            return false;
        }

        return $default_enabled;
    }

    /**
     * Parse headings from content.
     */
    public static function get_toc_items_from_content( $content, $settings ) {
        $items        = array();
        $used_ids     = array();
        $min_headings = intval( $settings['min_headings'] );
        $max_headings = intval( $settings['max_headings'] );

        if ( $min_headings < 1 ) {
            $min_headings = 1;
        }
        if ( $max_headings < $min_headings ) {
            $max_headings = $min_headings;
        }

        if ( ! preg_match_all( '/<h2([^>]*)>(.*?)<\/h2>/is', $content, $matches, PREG_SET_ORDER ) ) {
            return $items;
        }

        foreach ( $matches as $match ) {
            $attr  = $match[1];
            $inner = $match[2];

            $text = wp_strip_all_tags( $inner );
            $text = html_entity_decode( trim( $text ), ENT_QUOTES | ENT_HTML5, 'UTF-8' );
            if ( $text === '' ) {
                continue;
            }

            if ( self::should_exclude_heading( $text, $settings ) ) {
                continue;
            }

            $id = '';
            if ( preg_match( '/id=(["\'])(.*?)\1/i', $attr, $id_match ) ) {
                $id = trim( $id_match[2] );
            }

            if ( $id === '' ) {
                $id = self::generate_base_id( $text );
            }

            $id = self::make_unique_id( $id, $used_ids );

            $items[] = array(
                'id'   => $id,
                'text' => $text,
            );

            if ( count( $items ) >= $max_headings ) {
                break;
            }
        }

        if ( count( $items ) < $min_headings ) {
            return array();
        }

        return $items;
    }

/**
 * Inject TOC into the_content (optional).
 *
 * Important: we do not round-trip the entire HTML through DOMDocument here.
 * Divi pages with imperfect markup can be restructured by DOM repair, which is
 * exactly how sidebars get pushed below the content or into the footer.
 */
public static function filter_content_add_toc( $content ) {
    if ( is_admin() ) {
        return $content;
    }

    if ( ! is_singular() || ! in_the_loop() || ! is_main_query() ) {
        return $content;
    }

    global $post;
    if ( ! $post ) {
        return $content;
    }

    // Skip TOC on blank/full-width template pages (v1.0.1)
    $template = get_page_template_slug( $post->ID );
    if ( $template && (
        strpos( $template, 'blank' ) !== false ||
        strpos( $template, 'full-width' ) !== false ||
        strpos( $template, 'no-toc' ) !== false
    ) ) {
        return $content;
    }

    // Skip TOC on pages containing form shortcodes (v1.0.1)
    if ( has_shortcode( $content, 'lrg_lead_form' ) || has_shortcode( $content, 'rss_lead_form' ) ) {
        return $content;
    }

    $settings = self::get_settings();
    if ( ! self::is_toc_enabled_for_post( $post, $settings ) ) {
        return $content;
    }

    // Apply per-post CTA overrides.
    $settings = self::apply_cta_overrides( $settings, $post->ID );

    $items = self::get_toc_items_from_content( $content, $settings );
    if ( empty( $items ) ) {
        return $content;
    }

    /*
     * Sidebar-only / shortcode-only usage should leave the page content untouched.
     * Anchor IDs are attached client-side from the TOC links to avoid rebuilding
     * Divi's HTML on the server.
     */
    if ( empty( $settings['inline_nav'] ) ) {
        return $content;
    }

    $toc_html = self::build_toc_html( $items, $settings, false );
    $position = isset( $settings['insert_position'] ) ? $settings['insert_position'] : 'after_first_paragraph';

    $content_with_ids = self::inject_heading_ids( $content, $settings, $items );

    return self::insert_toc_markup( $content_with_ids, $toc_html, $position );
}

/**
 * Build TOC HTML.
 */
public static function build_toc_html( $items, $settings, $sidebar = false ) {
    $title   = $settings['title_text'] ? $settings['title_text'] : 'In this Article';
    $classes = array( 'rss-toc' );

    if ( $sidebar ) {
        $classes[] = 'rss-toc-sidebar';
    }

    if ( ! empty( $settings['disable_mobile_toc'] ) ) {
        $classes[] = 'rss-toc-hide-mobile';
    }

    $html  = '<nav class="' . esc_attr( implode( ' ', $classes ) ) . '" aria-label="Table of contents">';
    $html .= '<div class="rss-toc-title">' . esc_html( $title ) . '</div>';
    $html .= '<ul>';
    foreach ( $items as $index => $item ) {
        $html .= sprintf(
            '<li><a href="#%1$s" data-rss-toc-id="%1$s" data-rss-toc-index="%2$d" data-rss-toc-text="%3$s">%4$s</a></li>',
            esc_attr( $item['id'] ),
            intval( $index ),
            esc_attr( $item['text'] ),
            esc_html( $item['text'] )
        );
    }
    $html .= '</ul>';

    if ( ! empty( $settings['cta_text'] ) && ! empty( $settings['cta_url'] ) ) {
        $html .= '<div class="rss-toc-cta-wrap">';
        $html .= '<div class="rss-toc-cta-heading">';

        if ( ! empty( $settings['cta_line1'] ) ) {
            $html .= '<span class="rss-cta-line1">' . esc_html( $settings['cta_line1'] ) . '</span>';
        }

        if ( ! empty( $settings['cta_line2'] ) ) {
            $html .= '<span class="rss-cta-line2">' . esc_html( $settings['cta_line2'] ) . '</span>';
        }

        if ( ! empty( $settings['cta_line3'] ) ) {
            $html .= '<span class="rss-cta-line3">' . esc_html( $settings['cta_line3'] ) . '</span>';
        }

        $html .= '</div>'; // .rss-toc-cta-heading.

        $html .= '<a class="rss-toc-cta" href="' . esc_url( $settings['cta_url'] ) . '">';
        $html .= esc_html( $settings['cta_text'] );
        $html .= '</a>';
        $html .= '</div>'; // .rss-toc-cta-wrap.
    }

    $html .= '</nav>';

    return $html;
}

/**
 * Inject heading IDs with lightweight string replacement instead of rebuilding
 * the full document tree. This is much safer for Divi pages containing imperfect
 * custom HTML because it only touches the H2 opening tag.
 */
private static function inject_heading_ids( $content, $settings, $items ) {
    if ( empty( $content ) || empty( $items ) ) {
        return $content;
    }

    $original_content = $content;
    $cursor           = 0;

    $content = preg_replace_callback(
        '/<h2\b([^>]*)>(.*?)<\/h2>/is',
        function ( $match ) use ( $settings, $items, &$cursor ) {
            $attr  = isset( $match[1] ) ? $match[1] : '';
            $inner = isset( $match[2] ) ? $match[2] : '';

            $text = wp_strip_all_tags( $inner );
            $text = html_entity_decode( trim( $text ), ENT_QUOTES | ENT_HTML5, 'UTF-8' );

            if ( $text === '' || RSS_TOC_Manager::should_exclude_heading( $text, $settings ) ) {
                return $match[0];
            }

            if ( ! isset( $items[ $cursor ]['id'] ) ) {
                return $match[0];
            }

            $target_id = trim( (string) $items[ $cursor ]['id'] );
            $cursor++;

            if ( $target_id === '' ) {
                return $match[0];
            }

            if ( preg_match( '/\sid\s*=\s*(["\']).*?\1/i', $attr ) ) {
                $replacement = ' id="' . esc_attr( $target_id ) . '"';
                $new_attr    = preg_replace( '/\sid\s*=\s*(["\']).*?\1/i', $replacement, $attr, 1 );

                if ( null === $new_attr ) {
                    return $match[0];
                }

                return '<h2' . $new_attr . '>' . $inner . '</h2>';
            }

            return '<h2' . $attr . ' id="' . esc_attr( $target_id ) . '">' . $inner . '</h2>';
        },
        $content
    );

    return null === $content ? $original_content : $content;
}

/**
 * Insert the TOC block into content without parsing the whole page.
 */
private static function insert_toc_markup( $content, $toc_html, $position ) {
    if ( $toc_html === '' ) {
        return $content;
    }

    if ( $position === 'before_content' ) {
        return $toc_html . $content;
    }

    if ( $position === 'after_content' ) {
        return $content . $toc_html;
    }

    if ( preg_match( '/<\/p>/i', $content, $match, PREG_OFFSET_CAPTURE ) ) {
        $insert_at = $match[0][1] + strlen( $match[0][0] );

        return substr( $content, 0, $insert_at ) . $toc_html . substr( $content, $insert_at );
    }

    return $toc_html . $content;
}

    /**
     * Exclude headings containing configured phrases.
     */
    private static function should_exclude_heading( $text, $settings ) {
        if ( empty( $settings['exclude_headings'] ) ) {
            return false;
        }

        $patterns = preg_split( '/\r\n|\r|\n/', $settings['exclude_headings'] );
        if ( empty( $patterns ) ) {
            return false;
        }

        if ( function_exists( 'mb_strtolower' ) ) {
            $text_l = mb_strtolower( $text, 'UTF-8' );
        } else {
            $text_l = strtolower( $text );
        }

        foreach ( $patterns as $pattern ) {
            $pattern = trim( $pattern );
            if ( $pattern === '' ) {
                continue;
            }
            if ( function_exists( 'mb_strtolower' ) ) {
                $p_l = mb_strtolower( $pattern, 'UTF-8' );
            } else {
                $p_l = strtolower( $pattern );
            }
            if ( $p_l !== '' && strpos( $text_l, $p_l ) !== false ) {
                return true;
            }
        }

        return false;
    }

    /**
     * Generate a base heading ID.
     */
    private static function generate_base_id( $text ) {
        if ( function_exists( 'sanitize_title' ) ) {
            $id = sanitize_title( $text );
        } else {
            $id = strtolower( preg_replace( '/[^a-z0-9]+/i', '-', $text ) );
        }

        $id = trim( $id, '-' );

        if ( $id === '' ) {
            $id = 'section';
        }

        return $id;
    }

    /**
     * Ensure heading IDs are unique.
     */
    private static function make_unique_id( $id, &$used_ids ) {
        $id = trim( (string) $id );

        if ( $id === '' ) {
            $id = 'section';
        }

        $base   = $id;
        $suffix = 2;

        while ( in_array( $id, $used_ids, true ) ) {
            $id = $base . '-' . $suffix;
            $suffix++;
        }

        $used_ids[] = $id;

        return $id;
    }

    /**
     * Helper: inner HTML of an element.
     */
    private static function dom_inner_html( $element, $dom ) {
        $html = '';
        if ( ! $element ) {
            return $html;
        }
        foreach ( $element->childNodes as $child ) {
            $html .= $dom->saveHTML( $child );
        }
        return $html;
    }

    /**
     * List column.
     */
    public static function add_toc_column( $columns ) {
        $columns['rss_toc'] = 'TOC';
        return $columns;
    }

    /**
     * Column contents.
     */
    public static function render_toc_column( $column, $post_id ) {
        if ( 'rss_toc' !== $column ) {
            return;
        }

        $settings = self::get_settings();
        $meta     = get_post_meta( $post_id, self::META_KEY, true );
        $default  = ! empty( $settings['default_enabled'] ) ? 'Default (On)' : 'Default (Off)';

        if ( $meta === 'on' ) {
            $label = 'On';
        } elseif ( $meta === 'off' ) {
            $label = 'Off';
        } else {
            $label = $default;
        }

        echo esc_html( $label );
    }

    /**
     * Bulk actions.
     */
    public static function register_bulk_actions( $actions ) {
        $actions['rss_toc_enable']  = 'Enable TOC';
        $actions['rss_toc_disable'] = 'Disable TOC';
        return $actions;
    }

    public static function handle_bulk_actions( $redirect_to, $doaction, $post_ids ) {
        if ( $doaction !== 'rss_toc_enable' && $doaction !== 'rss_toc_disable' ) {
            return $redirect_to;
        }

        $status  = ( 'rss_toc_enable' === $doaction ) ? 'on' : 'off';
        $updated = 0;

        foreach ( $post_ids as $post_id ) {
            if ( ! current_user_can( 'edit_post', $post_id ) ) {
                continue;
            }
            update_post_meta( $post_id, self::META_KEY, $status );
            $updated++;
        }

        if ( $updated > 0 ) {
            $redirect_to = add_query_arg( 'rss_toc_updated', $updated, $redirect_to );
        }

        return $redirect_to;
    }

    public static function bulk_admin_notice() {
        if ( empty( $_REQUEST['rss_toc_updated'] ) ) {
            return;
        }

        $count = intval( $_REQUEST['rss_toc_updated'] );
        if ( $count <= 0 ) {
            return;
        }

        printf(
            '<div class="updated notice is-dismissible"><p>%s</p></div>',
            esc_html( sprintf( 'RSS TOC updated for %d items.', $count ) )
        );
    }

    /**
     * Meta box.
     */
    public static function add_meta_box() {
        $settings = self::get_settings();

        if ( ! empty( $settings['enable_posts'] ) ) {
            add_meta_box(
                'rss_toc_meta',
                'RSS TOC',
                array( __CLASS__, 'render_meta_box' ),
                'post',
                'side',
                'default'
            );
        }

        if ( ! empty( $settings['enable_pages'] ) ) {
            add_meta_box(
                'rss_toc_meta',
                'RSS TOC',
                array( __CLASS__, 'render_meta_box' ),
                'page',
                'side',
                'default'
            );
        }
    }

    public static function render_meta_box( $post ) {
        $meta     = get_post_meta( $post->ID, self::META_KEY, true );
        $settings = self::get_settings();
        $default  = ! empty( $settings['default_enabled'] ) ? 'On' : 'Off';

        $cta_line1  = get_post_meta( $post->ID, self::META_CTA_LINE1, true );
        $cta_line2  = get_post_meta( $post->ID, self::META_CTA_LINE2, true );
        $cta_line3  = get_post_meta( $post->ID, self::META_CTA_LINE3, true );
        $cta_button = get_post_meta( $post->ID, self::META_CTA_BUTTON, true );

        wp_nonce_field( 'rss_toc_meta_box', 'rss_toc_meta_box_nonce' );
        ?>
        <p>
            <label for="rss_toc_status"><strong>TOC status</strong></label><br />
            <select name="rss_toc_status" id="rss_toc_status">
                <option value="" <?php selected( $meta, '' ); ?>>Default (<?php echo esc_html( $default ); ?>)</option>
                <option value="on" <?php selected( $meta, 'on' ); ?>>Force ON</option>
                <option value="off" <?php selected( $meta, 'off' ); ?>>Force OFF</option>
            </select>
        </p>
        <p class="description">Override the global TOC setting for this page only.</p>

        <hr />

        <p><strong>CTA override (optional)</strong></p>

        <p>
            <label for="rss_toc_cta_line1">CTA heading line 1</label><br />
            <input type="text"
                   id="rss_toc_cta_line1"
                   name="rss_toc_cta_line1"
                   class="widefat"
                   value="<?php echo esc_attr( $cta_line1 ); ?>" />
        </p>
        <p>
            <label for="rss_toc_cta_line2">CTA heading line 2</label><br />
            <input type="text"
                   id="rss_toc_cta_line2"
                   name="rss_toc_cta_line2"
                   class="widefat"
                   value="<?php echo esc_attr( $cta_line2 ); ?>" />
        </p>
        <p>
            <label for="rss_toc_cta_line3">CTA heading line 3</label><br />
            <input type="text"
                   id="rss_toc_cta_line3"
                   name="rss_toc_cta_line3"
                   class="widefat"
                   value="<?php echo esc_attr( $cta_line3 ); ?>" />
        </p>
        <p>
            <label for="rss_toc_cta_button">CTA button text</label><br />
            <input type="text"
                   id="rss_toc_cta_button"
                   name="rss_toc_cta_button"
                   class="widefat"
                   value="<?php echo esc_attr( $cta_button ); ?>" />
            <span class="description">Leave blank to use global CTA settings.</span>
        </p>
        <?php
    }

    public static function save_post_meta( $post_id ) {
        if ( defined( 'DOING_AUTOSAVE' ) && DOING_AUTOSAVE ) {
            return;
        }
        if ( wp_is_post_revision( $post_id ) ) {
            return;
        }

        if ( ! isset( $_POST['post_type'] ) ) {
            return;
        }

        $post_type = sanitize_key( wp_unslash( $_POST['post_type'] ) );
        if ( $post_type !== 'post' && $post_type !== 'page' ) {
            return;
        }

        if ( ! current_user_can( 'edit_' . $post_type, $post_id ) ) {
            return;
        }

        if ( isset( $_POST['rss_toc_meta_box_nonce'] ) && wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['rss_toc_meta_box_nonce'] ) ), 'rss_toc_meta_box' ) ) {
            if ( isset( $_POST['rss_toc_status'] ) ) {
                $status = sanitize_text_field( wp_unslash( $_POST['rss_toc_status'] ) );
                if ( $status === 'on' || $status === 'off' ) {
                    update_post_meta( $post_id, self::META_KEY, $status );
                } else {
                    delete_post_meta( $post_id, self::META_KEY );
                }
            }

            // Save CTA override fields.
            $cta_fields = array(
                'rss_toc_cta_line1'  => self::META_CTA_LINE1,
                'rss_toc_cta_line2'  => self::META_CTA_LINE2,
                'rss_toc_cta_line3'  => self::META_CTA_LINE3,
                'rss_toc_cta_button' => self::META_CTA_BUTTON,
            );

            foreach ( $cta_fields as $form_field => $meta_key ) {
                if ( isset( $_POST[ $form_field ] ) ) {
                    $value = sanitize_text_field( wp_unslash( $_POST[ $form_field ] ) );
                    if ( $value !== '' ) {
                        update_post_meta( $post_id, $meta_key, $value );
                    } else {
                        delete_post_meta( $post_id, $meta_key );
                    }
                }
            }
        }
    }

    /**
     * Settings page.
     */
    public static function add_settings_page() {
        add_options_page(
            'RSS TOC Manager',
            'RSS TOC',
            'manage_options',
            'rss-toc-manager',
            array( __CLASS__, 'render_settings_page' )
        );
    }

    public static function render_settings_page() {
        if ( ! current_user_can( 'manage_options' ) ) {
            return;
        }

        if ( isset( $_POST['rss_toc_settings_nonce'] ) && wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['rss_toc_settings_nonce'] ) ), 'rss_toc_save_settings' ) ) {
            $options = self::get_settings();

            $options['enable_posts']       = isset( $_POST['enable_posts'] ) ? 1 : 0;
            $options['enable_pages']       = isset( $_POST['enable_pages'] ) ? 1 : 0;
            $options['default_enabled']    = isset( $_POST['default_enabled'] ) ? 1 : 0;
            $options['disable_on_front']   = isset( $_POST['disable_on_front'] ) ? 1 : 0;
            $options['inline_nav']         = isset( $_POST['inline_nav'] ) ? 1 : 0;
            $options['disable_mobile_toc'] = isset( $_POST['disable_mobile_toc'] ) ? 1 : 0;

            $options['mobile_breakpoint'] = isset( $_POST['mobile_breakpoint'] )
                ? max( 480, min( 1400, intval( wp_unslash( $_POST['mobile_breakpoint'] ) ) ) )
                : 980;

            $options['min_headings'] = isset( $_POST['min_headings'] ) ? max( 1, intval( wp_unslash( $_POST['min_headings'] ) ) ) : 3;
            $options['max_headings'] = isset( $_POST['max_headings'] ) ? max( $options['min_headings'], intval( wp_unslash( $_POST['max_headings'] ) ) ) : 6;

            $allowed_positions = array( 'before_content', 'after_first_paragraph', 'after_content' );
            $position          = isset( $_POST['insert_position'] ) ? sanitize_text_field( wp_unslash( $_POST['insert_position'] ) ) : 'after_first_paragraph';
            if ( ! in_array( $position, $allowed_positions, true ) ) {
                $position = 'after_first_paragraph';
            }
            $options['insert_position'] = $position;

            $options['title_text']       = isset( $_POST['title_text'] ) ? sanitize_text_field( wp_unslash( $_POST['title_text'] ) ) : 'In this Article';
            $options['cta_text']         = isset( $_POST['cta_text'] ) ? sanitize_text_field( wp_unslash( $_POST['cta_text'] ) ) : '';
            $options['cta_url']          = isset( $_POST['cta_url'] ) ? esc_url_raw( wp_unslash( $_POST['cta_url'] ) ) : '';
            $options['exclude_headings'] = isset( $_POST['exclude_headings'] ) ? sanitize_textarea_field( wp_unslash( $_POST['exclude_headings'] ) ) : '';

            $options['cta_line1'] = isset( $_POST['cta_line1'] )
                ? sanitize_text_field( wp_unslash( $_POST['cta_line1'] ) )
                : $options['cta_line1'];

            $options['cta_line2'] = isset( $_POST['cta_line2'] )
                ? sanitize_text_field( wp_unslash( $_POST['cta_line2'] ) )
                : $options['cta_line2'];

            $options['cta_line3'] = isset( $_POST['cta_line3'] )
                ? sanitize_text_field( wp_unslash( $_POST['cta_line3'] ) )
                : $options['cta_line3'];

            $options['link_color']        = isset( $_POST['link_color'] ) ? sanitize_text_field( wp_unslash( $_POST['link_color'] ) ) : '#007BFF';
            $options['button_bg_color']   = isset( $_POST['button_bg_color'] ) ? sanitize_text_field( wp_unslash( $_POST['button_bg_color'] ) ) : '#007BFF';
            $options['button_text_color'] = isset( $_POST['button_text_color'] ) ? sanitize_text_field( wp_unslash( $_POST['button_text_color'] ) ) : '#FFFFFF';

            update_option( self::OPTION_KEY, $options );
            echo '<div class="updated"><p>Settings saved.</p></div>';
        }

        $options = self::get_settings();

        wp_enqueue_style( 'wp-color-picker' );
        wp_enqueue_script( 'wp-color-picker' );
        ?>
        <div class="wrap">
            <h1>RSS TOC Manager</h1>
            <p>Generic sticky Table of Contents with configurable CTA.</p>

            <p><strong>Shortcodes:</strong>
                <code>[rss_toc]</code> (RSS TOC) and
                <code>[ez-toc]</code> (legacy alias; renders RSS TOC on pages, nothing on posts).
            </p>

            <form method="post">
                <?php wp_nonce_field( 'rss_toc_save_settings', 'rss_toc_settings_nonce' ); ?>

                <h2 class="title">Global behaviour</h2>
                <table class="form-table" role="presentation">
                    <tr>
                        <th scope="row">Enable on post types</th>
                        <td>
                            <label><input type="checkbox" name="enable_posts" <?php checked( ! empty( $options['enable_posts'] ) ); ?> /> Posts</label><br />
                            <label><input type="checkbox" name="enable_pages" <?php checked( ! empty( $options['enable_pages'] ) ); ?> /> Pages</label>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">Default TOC status</th>
                        <td>
                            <label>
                                <input type="checkbox" name="default_enabled" <?php checked( ! empty( $options['default_enabled'] ) ); ?> />
                                Enable TOC by default on allowed post types (override per page in the meta box).
                            </label>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">Front page</th>
                        <td>
                            <label>
                                <input type="checkbox" name="disable_on_front" <?php checked( ! empty( $options['disable_on_front'] ) ); ?> />
                                Disable TOC on the front page / blog home.
                            </label>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">Inline TOC in content</th>
                        <td>
                            <label>
                                <input type="checkbox" name="inline_nav" <?php checked( ! empty( $options['inline_nav'] ) ); ?> />
                                Inject TOC into the content area (in addition to the sidebar widget / shortcode).
                            </label>
                            <p class="description">Uncheck if you only want to use the sidebar widget or shortcodes.</p>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">Mobile / small screens</th>
                        <td>
                            <label>
                                <input type="checkbox" name="disable_mobile_toc" <?php checked( ! empty( $options['disable_mobile_toc'] ) ); ?> />
                                Disable the TOC on smaller screens.
                            </label>
                            <p class="description">Enabled by default. This hides the inline TOC, shortcode TOC, sidebar widget, and sticky CTA bar at or below the breakpoint below.</p>
                            <label>
                                Breakpoint:
                                <input type="number" name="mobile_breakpoint" value="<?php echo esc_attr( $options['mobile_breakpoint'] ); ?>" min="480" max="1400" style="width:80px;" /> px
                            </label>
                            <p class="description">Default is 980px, which lines up well with common Divi tablet/mobile layout changes.</p>
                        </td>
                    </tr>
                </table>

                <h2 class="title">TOC structure</h2>
                <table class="form-table" role="presentation">
                    <tr>
                        <th scope="row">Heading limits</th>
                        <td>
                            <label>
                                Minimum H2 headings required:
                                <input type="number" name="min_headings" value="<?php echo esc_attr( $options['min_headings'] ); ?>" min="1" style="width:70px;" />
                            </label>
                            <br />
                            <label>
                                Maximum TOC items:
                                <input type="number" name="max_headings" value="<?php echo esc_attr( $options['max_headings'] ); ?>" min="1" style="width:70px;" />
                            </label>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">Insert position (inline)</th>
                        <td>
                            <label><input type="radio" name="insert_position" value="before_content" <?php checked( $options['insert_position'], 'before_content' ); ?> /> Before content</label><br />
                            <label><input type="radio" name="insert_position" value="after_first_paragraph" <?php checked( $options['insert_position'], 'after_first_paragraph' ); ?> /> After first paragraph (recommended)</label><br />
                            <label><input type="radio" name="insert_position" value="after_content" <?php checked( $options['insert_position'], 'after_content' ); ?> /> After content</label>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">TOC title</th>
                        <td>
                            <input type="text" name="title_text" value="<?php echo esc_attr( $options['title_text'] ); ?>" class="regular-text" />
                            <p class="description">Example: "In this Article" or "Within this Article".</p>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">Exclude headings</th>
                        <td>
                            <textarea name="exclude_headings" rows="5" cols="50" class="large-text code"><?php echo esc_textarea( $options['exclude_headings'] ); ?></textarea>
                            <p class="description">
                                One phrase per line. Any H2 whose text contains one of these phrases (case-insensitive) will be skipped in the TOC.
                                Example: <code>Key Takeaways</code>, <code>FAQs</code>, <code>The Bottom Line</code>.
                            </p>
                        </td>
                    </tr>
                </table>

                <h2 class="title">Design (colors)</h2>
                <table class="form-table" role="presentation">
                    <tr>
                        <th scope="row"><label for="link_color">TOC link color</label></th>
                        <td>
                            <input type="text" name="link_color" id="link_color" value="<?php echo esc_attr( $options['link_color'] ); ?>" class="rss-color-field" data-default-color="#007BFF" />
                            <p class="description">Bright blue used for TOC links, arrows, and the middle CTA line.</p>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row"><label for="button_bg_color">CTA button background</label></th>
                        <td>
                            <input type="text" name="button_bg_color" id="button_bg_color" value="<?php echo esc_attr( $options['button_bg_color'] ); ?>" class="rss-color-field" data-default-color="#007BFF" />
                        </td>
                    </tr>
                    <tr>
                        <th scope="row"><label for="button_text_color">CTA button text color</label></th>
                        <td>
                            <input type="text" name="button_text_color" id="button_text_color" value="<?php echo esc_attr( $options['button_text_color'] ); ?>" class="rss-color-field" data-default-color="#FFFFFF" />
                        </td>
                    </tr>
                </table>

                <h2 class="title">CTA copy &amp; button</h2>
                <table class="form-table" role="presentation">
                    <tr>
                        <th scope="row">CTA heading – line 1</th>
                        <td>
                            <input type="text" name="cta_line1" value="<?php echo esc_attr( $options['cta_line1'] ); ?>" class="regular-text" />
                            <p class="description">Example: "Check Your". Leave blank to hide this line.</p>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">CTA heading – line 2</th>
                        <td>
                            <input type="text" name="cta_line2" value="<?php echo esc_attr( $options['cta_line2'] ); ?>" class="regular-text" />
                            <p class="description">Example: "VA Loan Options".</p>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">CTA heading – line 3</th>
                        <td>
                            <input type="text" name="cta_line3" value="<?php echo esc_attr( $options['cta_line3'] ); ?>" class="regular-text" />
                            <p class="description">Example: "in About 2 Minutes".</p>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">Button text</th>
                        <td>
                            <input type="text" name="cta_text" value="<?php echo esc_attr( $options['cta_text'] ); ?>" class="regular-text" />
                            <p class="description">Example: "Check Your VA Loan Options".</p>
                        </td>
                    </tr>
                    <tr>
                        <th scope="row">Button URL</th>
                        <td>
                            <input type="text" name="cta_url" value="<?php echo esc_attr( $options['cta_url'] ); ?>" class="regular-text" />
                            <p class="description">Example: /connect-with-us/ or https://example.com/contact/</p>
                        </td>
                    </tr>
                </table>

                <?php submit_button(); ?>
            </form>

            <script>
            jQuery(function($){
                if ($.fn.wpColorPicker) {
                    $(".rss-color-field").wpColorPicker();
                }
            });
            </script>
        </div>
        <?php
    }

    /**
     * Shortcode: [rss_toc]
     */
    public static function shortcode_output( $atts ) {
        if ( ! is_singular() ) {
            return '';
        }

        global $post;
        if ( ! $post ) {
            return '';
        }

        $settings = self::get_settings();
        if ( ! self::is_toc_enabled_for_post( $post, $settings ) ) {
            return '';
        }

        // Apply CTA overrides for shortcode context.
        $settings = self::apply_cta_overrides( $settings, $post->ID );

        $items = self::get_toc_items_from_content( $post->post_content, $settings );
        if ( empty( $items ) ) {
            return '';
        }

        $nav = self::build_toc_html( $items, $settings, false );

        // Wrap to target shortcode-only styling.
        return '<div class="rss-toc-shortcode">' . $nav . '</div>';
    }

    /**
     * Alias shortcode: [ez-toc]
     * - On pages: render RSS TOC (same as [rss_toc])
     * - On posts: output nothing (sidebar handles posts)
     */
    public static function ez_toc_compat_shortcode( $atts ) {
        if ( is_page() ) {
            return self::shortcode_output( $atts );
        }
        return '';
    }

    /**
     * Register sidebar widget.
     */
    public static function register_widget() {
        if ( class_exists( 'WP_Widget' ) ) {
            register_widget( 'RSS_TOC_Sidebar_Widget' );
        }
    }
}

endif;

/**
 * Sidebar widget class.
 */
if ( class_exists( 'WP_Widget' ) && ! class_exists( 'RSS_TOC_Sidebar_Widget' ) ) :

class RSS_TOC_Sidebar_Widget extends WP_Widget {

    public function __construct() {
        parent::__construct(
            'rss_toc_sidebar_widget',
            'RSS TOC Sidebar',
            array(
                'classname'   => 'widget_rss_toc_sidebar_widget rss-toc-sidebar-widget',
                'description' => 'Displays the RSS Table of Contents with CTA in the sidebar.',
            )
        );
    }

    public function widget( $args, $instance ) {
        if ( ! is_singular() ) {
            return;
        }

        global $post;
        if ( ! $post ) {
            return;
        }

        $settings = RSS_TOC_Manager::get_settings();
        if ( ! RSS_TOC_Manager::is_toc_enabled_for_post( $post, $settings ) ) {
            return;
        }

        // Apply per-post CTA overrides.
        $settings = RSS_TOC_Manager::apply_cta_overrides( $settings, $post->ID );

        $items = RSS_TOC_Manager::get_toc_items_from_content( $post->post_content, $settings );
        if ( empty( $items ) ) {
            return;
        }

        $title = ! empty( $instance['title'] ) ? $instance['title'] : $settings['title_text'];
        if ( ! $title ) {
            $title = 'In this Article';
        }

        echo $args['before_widget'];

        $html = RSS_TOC_Manager::build_toc_html( $items, $settings, true );

        if ( $title && $title !== $settings['title_text'] ) {
            $html = preg_replace(
                '#<div class="rss-toc-title">.*?</div>#',
                '<div class="rss-toc-title">' . esc_html( $title ) . '</div>',
                $html,
                1
            );
        }

        echo $html; // phpcs:ignore WordPress.Security.EscapeOutput.OutputNotEscaped

        echo $args['after_widget'];
    }

    public function form( $instance ) {
        $title = isset( $instance['title'] ) ? $instance['title'] : '';
        ?>
        <p>
            <label for="<?php echo esc_attr( $this->get_field_id( 'title' ) ); ?>">Widget title:</label>
            <input class="widefat"
                   id="<?php echo esc_attr( $this->get_field_id( 'title' ) ); ?>"
                   name="<?php echo esc_attr( $this->get_field_name( 'title' ) ); ?>"
                   type="text"
                   value="<?php echo esc_attr( $title ); ?>" />
            <small>Leave blank to use the global TOC title from settings.</small>
        </p>
        <?php
    }

    public function update( $new_instance, $old_instance ) {
        $instance          = array();
        $instance['title'] = isset( $new_instance['title'] ) ? sanitize_text_field( $new_instance['title'] ) : '';
        return $instance;
    }
}

endif;

RSS_TOC_Manager::init();
