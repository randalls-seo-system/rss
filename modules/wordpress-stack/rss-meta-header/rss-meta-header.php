<?php
/**
 * Plugin Name: RSS Meta Header
 * Description: EEAT meta header block (Written/Reviewed/Updated) for posts and pages. Hooks into Divi et_before_main_content with wp_body_open fallback. Supports per-post reviewer selection, label customization, and spacing overrides. Part of Randall's SEO System standard plugin stack.
 * Version: 1.0.0
 * Author: Randall's SEO System
 * License: GPL2+
 */

if (!defined('ABSPATH')) {
    exit;
}

// Compatibility: prevent multiple meta header instances (RSS or legacy VALN variants).
if (defined('RSS_META_HEADER_ACTIVE') || defined('VALN_META_HEADER_CLASSIC_ACTIVE') || defined('VALN_META_HEADER_CLASSIC92_ACTIVE')) {
    add_action('admin_notices', function () {
        echo '<div class="notice notice-error"><p><strong>RSS Meta Header:</strong> Another Meta Header plugin variant is already active (RSS or VALN). Deactivate the other version to avoid conflicts.</p></div>';
    });
    return;
}
define('RSS_META_HEADER_ACTIVE', 1);

class RSS_Meta_Header {

    /* -----------------
     * Post meta keys
     * ----------------- */
    const META_ENABLE          = '_rss_enable_block';
    const META_REVIEWER_SELECT = '_rss_reviewer_select';
    const META_REVIEWER        = '_rss_reviewer_override';

    const META_MODE            = '_rss_eeat_mode';
    const META_POSITION        = '_rss_eeat_position';
    const META_HIDE_REVIEWER   = '_rss_eeat_hide_reviewer';
    const META_LABEL_AUTHOR    = '_rss_eeat_label_author';
    const META_LABEL_REVIEWER  = '_rss_eeat_label_reviewer';
    const META_LABEL_UPDATED   = '_rss_eeat_label_updated';

    /**
     * Per-post/page spacing override.
     * Blank  = use the global gap setting from the Settings page.
     * Integer = use this px value as margin-top for THIS post only (applied inline).
     * Supports negatives to pull the block up when Divi's hero section adds excess space.
     */
    const META_GAP_OVERRIDE    = '_rss_gap_override';

    /* -----------------
     * Options (wp_options) — Spacing & Font
     * ----------------- */
    const OPT_GAP_POST_DESKTOP = 'rss_mh_gap_post_desktop';
    const OPT_GAP_POST_MOBILE  = 'rss_mh_gap_post_mobile';
    const OPT_GAP_PAGE_DESKTOP = 'rss_mh_gap_page_desktop';
    const OPT_GAP_PAGE_MOBILE  = 'rss_mh_gap_page_mobile';

    const OPT_FONT_POST_DESKTOP = 'rss_mh_font_post_desktop';
    const OPT_FONT_POST_MOBILE  = 'rss_mh_font_post_mobile';
    const OPT_FONT_PAGE_DESKTOP = 'rss_mh_font_page_desktop';
    const OPT_FONT_PAGE_MOBILE  = 'rss_mh_font_page_mobile';

    const OPT_ENABLE_MORE_ABOUT = 'rss_mh_enable_more_about';

    const OPT_DESKTOP_LEFT_OFFSET = 'rss_mh_desktop_left_offset';

    const OPT_LEGACY_META_TOP_SPACING = 'rss_mh_legacy_top_spacing';

    const OPT_JSONLD_FALLBACK = 'rss_mh_emit_jsonld_without_yoast';

    /* -----------------
     * Options (wp_options) — Default Reviewer Identity
     * Configured via Settings > RSS Meta Header.
     * ----------------- */
    const OPT_REVIEWER_TYPE     = 'rss_mh_reviewer_type';
    const OPT_REVIEWER_NAME     = 'rss_mh_reviewer_name';
    const OPT_REVIEWER_URL      = 'rss_mh_reviewer_url';
    const OPT_REVIEWER_ROLE     = 'rss_mh_reviewer_role';
    const OPT_REVIEWER_IMG      = 'rss_mh_reviewer_img';
    const OPT_REVIEWER_NMLS     = 'rss_mh_reviewer_nmls';
    const OPT_REVIEWER_NMLS_URL = 'rss_mh_reviewer_nmls_url';

    /* -----------------
     * Options (wp_options) — Editorial Team Identity
     * ----------------- */
    const OPT_EDITORIAL_NAME        = 'rss_mh_editorial_name';
    const OPT_EDITORIAL_NAME_MOBILE = 'rss_mh_editorial_name_mobile';
    const OPT_EDITORIAL_URL         = 'rss_mh_editorial_url';
    const OPT_EDITORIAL_IMG         = 'rss_mh_editorial_img';

    /* ----- Gap clamp bounds (px) ----- */
    // Negative values let you pull the meta block UP to counteract Divi's hero
    // section bottom padding which varies per template and causes per-page drift.
    const GAP_MIN = -60;
    const GAP_MAX = 120;

    /** @var bool */
    private $yoast_active = false;

    public function __construct() {
        $this->yoast_active = class_exists('WPSEO_Schema') || defined('WPSEO_VERSION');

        add_action('add_meta_boxes', array($this, 'add_meta_box'));
        add_action('save_post',      array($this, 'save_meta_box'));
        add_action('wp_insert_post', array($this, 'default_on_new'), 10, 3);

        add_action('admin_menu',  array($this, 'add_settings_page'));
        add_action('admin_init',  array($this, 'register_settings'));

        add_action('wp_head',   array($this, 'output_frontend_css'), 20);
        add_action('wp_footer', array($this, 'output_frontend_js'),  99);

        // Top position: injects via the_content filter (after first </h1>).
        // Alternative for Divi: uncomment et_before_main_content for a different injection point.
        // add_action('et_before_main_content', array($this, 'render_top'), 5);
        add_filter('the_content', array($this, 'inject_after_h1'), 5);
        add_action('et_after_main_content',  array($this, 'render_bottom'), 5);

        // Non-Divi fallback for bottom position.
        // add_action('wp_body_open', array($this, 'render_top_fallback'), 20);
        add_action('wp_footer',    array($this, 'render_bottom_fallback'), 20);

        if ($this->yoast_active) {
            add_filter('wpseo_schema_article', array($this, 'yoast_article'), 20, 2);
            add_filter('wpseo_schema_graph',   array($this, 'yoast_graph'),   20, 2);
        } else {
            add_action('wp_head', array($this, 'emit_jsonld_fallback'), 99);
        }
    }

    /* =========================================================
     * Environment detection
     * ========================================================= */
    private function is_divi_env(): bool {
        if (defined('ET_CORE_VERSION') || defined('ET_BUILDER_VERSION')) return true;
        if (class_exists('ET_Builder_Plugin')) return true;
        if (function_exists('et_setup_theme')) return true;
        return false;
    }

    /* =========================================================
     * Helpers: settings
     * ========================================================= */
    private function clamp_int($value, int $min, int $max, int $fallback): int {
        $n = is_numeric($value) ? (int) $value : $fallback;
        if ($n < $min) $n = $min;
        if ($n > $max) $n = $max;
        return $n;
    }

    private function get_option_int(string $key, int $default, int $min, int $max): int {
        $raw = get_option($key, null);
        if ($raw === null || $raw === '') {
            return $this->clamp_int($default, $min, $max, $default);
        }
        return $this->clamp_int($raw, $min, $max, $default);
    }

    private function is_more_about_enabled(): bool {
        return (bool) get_option(self::OPT_ENABLE_MORE_ABOUT, false);
    }

    /* =========================================================
     * Helpers: meta defaults
     * ========================================================= */
    private function meta_enabled_for(int $post_id): bool {
        $raw = get_post_meta($post_id, self::META_ENABLE, true);
        if ($raw === '' || $raw === null) return true;
        return ((int) $raw) === 1;
    }

    private function meta_position_for(int $post_id): string {
        $pos = (string) get_post_meta($post_id, self::META_POSITION, true);
        return ($pos === 'bottom') ? 'bottom' : 'top';
    }

    private function meta_mode_for(int $post_id): string {
        $mode = (string) get_post_meta($post_id, self::META_MODE, true);
        if ($mode === '') $mode = 'article';
        if (!in_array($mode, array('article', 'tool'), true)) $mode = 'article';
        return $mode;
    }

    private function meta_hide_reviewer_for(int $post_id): bool {
        return ((int) get_post_meta($post_id, self::META_HIDE_REVIEWER, true)) === 1;
    }

    /**
     * Returns null (= use global) or an integer px value for the per-post gap override.
     * Range: GAP_MIN-GAP_MAX. Applied as margin-top inline on .rss-mh-wrap--top.
     */
    private function meta_gap_override_for(int $post_id): ?int {
        $raw = get_post_meta($post_id, self::META_GAP_OVERRIDE, true);
        if ($raw === '' || $raw === null || $raw === false) return null;
        if (!is_numeric($raw)) return null;
        return $this->clamp_int($raw, self::GAP_MIN, self::GAP_MAX, 0);
    }

    private function clean_label_string($s): string {
        $s = (string) $s;
        $s = str_replace(array("\\n", "\\r"), '', $s);
        $s = str_replace(array("\r", "\n", "\t"), ' ', $s);
        $s = preg_replace('/\s+/', ' ', $s);
        return trim((string) $s);
    }

    private function resolved_labels(int $post_id): array {
        $mode = $this->meta_mode_for($post_id);

        $def_author   = ($mode === 'tool') ? 'Created by:'   : 'Written by:';
        $def_reviewer = ($mode === 'tool') ? 'Validated by:' : 'Reviewed by:';
        $def_updated  = ($mode === 'tool') ? 'Last updated'  : 'Updated on';

        $la = $this->clean_label_string(get_post_meta($post_id, self::META_LABEL_AUTHOR,   true));
        $lr = $this->clean_label_string(get_post_meta($post_id, self::META_LABEL_REVIEWER, true));
        $lu = $this->clean_label_string(get_post_meta($post_id, self::META_LABEL_UPDATED,  true));

        return array(
            'mode'     => $mode,
            'author'   => ($la !== '' ? $la : $def_author),
            'reviewer' => ($lr !== '' ? $lr : $def_reviewer),
            'updated'  => ($lu !== '' ? $lu : $def_updated),
        );
    }

    /* =========================================================
     * Helpers: author/reviewer resolution
     *
     * Author data comes from the WP user profile. Per-user
     * customisation uses user meta:
     *   rss_mh_avatar       — custom avatar URL (overrides gravatar)
     *   rss_mh_profile_url  — profile page URL (overrides author_posts_url)
     *   rss_mh_role         — role/title shown on desktop
     *   rss_mh_role_mobile  — shorter role for mobile (optional)
     *   rss_mh_name_mobile  — shorter display name for mobile (optional)
     *   rss_mh_nmls         — NMLS number
     *   rss_mh_nmls_url     — NMLS lookup URL
     *
     * Set via WP-CLI:  wp user meta update <ID> rss_mh_role "Loan Officer"
     * Or via ACF / custom code.
     * ========================================================= */
    private function author_data(int $post_id): array {
        $post    = get_post($post_id);
        $user_id = $post ? (int) $post->post_author : 0;

        $display  = $user_id ? (string) get_the_author_meta('display_name', $user_id) : '';
        $nicename = $user_id ? (string) get_the_author_meta('user_nicename', $user_id) : '';

        // Profile URL: custom meta overrides default author posts URL.
        $url = '';
        if ($user_id) {
            $custom_url = (string) get_user_meta($user_id, 'rss_mh_profile_url', true);
            $url = $custom_url !== '' ? $custom_url : get_author_posts_url($user_id);
        }

        // Avatar: custom meta overrides gravatar.
        $img = '';
        if ($user_id) {
            $custom_img = (string) get_user_meta($user_id, 'rss_mh_avatar', true);
            $img = $custom_img !== '' ? $custom_img : get_avatar_url($user_id, array('size' => 112));
        }
        if (!$img) {
            $img = get_site_icon_url(64);
        }

        // Role (desktop and optional mobile variant).
        $role_desktop = $user_id ? (string) get_user_meta($user_id, 'rss_mh_role', true) : '';
        $role_mobile  = $user_id ? (string) get_user_meta($user_id, 'rss_mh_role_mobile', true) : '';

        // Mobile name (e.g., shortened editorial team name).
        $name_mobile = $user_id ? (string) get_user_meta($user_id, 'rss_mh_name_mobile', true) : '';

        // NMLS (financial industry).
        $nmls     = $user_id ? (string) get_user_meta($user_id, 'rss_mh_nmls', true) : '';
        $nmls_url = $user_id ? (string) get_user_meta($user_id, 'rss_mh_nmls_url', true) : '';

        return array(
            'user_id'      => $user_id,
            'name'         => $display,
            'name_mobile'  => $name_mobile,
            'url'          => $url,
            'img'          => $img,
            'role_desktop' => $role_desktop,
            'role_mobile'  => $role_mobile,
            'nmls'         => $nmls,
            'nmls_url'     => $nmls_url,
            'nicename'     => $nicename,
        );
    }

    private function reviewer_data(int $post_id): array {
        $sel = (string) get_post_meta($post_id, self::META_REVIEWER_SELECT, true);
        if ($sel === '') $sel = 'default';
        if (!in_array($sel, array('default', 'editorial_team', 'custom'), true)) {
            $sel = 'default';
        }

        // Editorial team (from Settings).
        if ($sel === 'editorial_team') {
            $name = (string) get_option(self::OPT_EDITORIAL_NAME, '');
            if ($name === '') {
                $sel = 'default'; // not configured — fall through to default
            } else {
                $url = (string) get_option(self::OPT_EDITORIAL_URL, '');
                return array(
                    'type'     => 'Organization',
                    'name'     => $name,
                    'url'      => $url,
                    'id'       => $url ? trailingslashit($url) . '#organization' : '#editorial-team',
                    'role'     => 'Editorial Team',
                    'img'      => (string) get_option(self::OPT_EDITORIAL_IMG, '') ?: get_site_icon_url(64),
                    'nmls'     => '',
                    'nmls_url' => '',
                    'kind'     => 'editorial',
                );
            }
        }

        // Custom (per-post fields).
        if ($sel === 'custom') {
            $ov = get_post_meta($post_id, self::META_REVIEWER, true);
            if (!is_array($ov)) $ov = array();
            $name = isset($ov['name']) ? trim((string) $ov['name']) : '';
            $role = isset($ov['role']) ? trim((string) $ov['role']) : '';
            $nmls = isset($ov['nmls']) ? trim((string) $ov['nmls']) : '';
            $url  = isset($ov['url'])  ? trim((string) $ov['url'])  : '';
            $img  = isset($ov['img'])  ? trim((string) $ov['img'])  : '';
            if (!$img) $img = get_site_icon_url(64);

            return array(
                'type'     => 'Person',
                'name'     => $name,
                'url'      => $url,
                'id'       => $url ? trailingslashit($url) . '#person' : '#custom-reviewer',
                'role'     => $role,
                'img'      => $img,
                'nmls'     => $nmls,
                'nmls_url' => '',
                'kind'     => 'custom',
            );
        }

        // Default reviewer (from Settings).
        $name = (string) get_option(self::OPT_REVIEWER_NAME, '');
        $type = (string) get_option(self::OPT_REVIEWER_TYPE, 'Person');
        if (!in_array($type, array('Person', 'Organization'), true)) $type = 'Person';
        $url  = (string) get_option(self::OPT_REVIEWER_URL, '');

        $id_suffix = ($type === 'Organization') ? '#organization' : '#person';
        $id = $url ? trailingslashit($url) . $id_suffix : '#default-reviewer';

        return array(
            'type'     => $type,
            'name'     => $name,
            'url'      => $url,
            'id'       => $id,
            'role'     => (string) get_option(self::OPT_REVIEWER_ROLE, ''),
            'img'      => (string) get_option(self::OPT_REVIEWER_IMG, '') ?: get_site_icon_url(64),
            'nmls'     => (string) get_option(self::OPT_REVIEWER_NMLS, ''),
            'nmls_url' => (string) get_option(self::OPT_REVIEWER_NMLS_URL, ''),
            'kind'     => 'default',
        );
    }

    private function first_name(string $full): string {
        $full = trim($full);
        if ($full === '') return '';
        $parts = preg_split('/\s+/', $full);
        return $parts && !empty($parts[0]) ? (string) $parts[0] : $full;
    }

    private function bio_text_for_author(array $author): string {
        $uid = isset($author['user_id']) ? (int) $author['user_id'] : 0;
        if (!$uid) return '';

        $desc = wp_strip_all_tags((string) get_the_author_meta('description', $uid));
        $desc = trim(preg_replace('/\s+/', ' ', $desc));
        if ($desc === '') return '';

        return wp_trim_words($desc, 40, '');
    }

    /* =========================================================
     * Frontend: CSS (settings-driven variables)
     * ========================================================= */
    public function output_frontend_css() {
        if (is_admin()) return;

        $legacy_gap = $this->get_option_int(self::OPT_LEGACY_META_TOP_SPACING, 12, self::GAP_MIN, self::GAP_MAX);

        $gap_post_desktop = $this->get_option_int(self::OPT_GAP_POST_DESKTOP, $legacy_gap, self::GAP_MIN, self::GAP_MAX);
        $gap_post_mobile  = $this->get_option_int(self::OPT_GAP_POST_MOBILE,  $legacy_gap, self::GAP_MIN, self::GAP_MAX);
        $gap_page_desktop = $this->get_option_int(self::OPT_GAP_PAGE_DESKTOP, $legacy_gap, self::GAP_MIN, self::GAP_MAX);
        $gap_page_mobile  = $this->get_option_int(self::OPT_GAP_PAGE_MOBILE,  $legacy_gap, self::GAP_MIN, self::GAP_MAX);

        $font_default_desktop = 15;
        $font_default_mobile  = 15;

        $font_post_desktop = $this->get_option_int(self::OPT_FONT_POST_DESKTOP, $font_default_desktop, 12, 22);
        $font_post_mobile  = $this->get_option_int(self::OPT_FONT_POST_MOBILE,  $font_default_mobile,  12, 22);
        $font_page_desktop = $this->get_option_int(self::OPT_FONT_PAGE_DESKTOP, $font_default_desktop, 12, 22);
        $font_page_mobile  = $this->get_option_int(self::OPT_FONT_PAGE_MOBILE,  $font_default_mobile,  12, 22);

        $left_offset_desktop = $this->get_option_int(self::OPT_DESKTOP_LEFT_OFFSET, 80, 0, 240);

        echo "\n<style id=\"rss-mh-css\">\n";
        echo ":root{";
        echo "--rss-mh-gap-post-desktop:{$gap_post_desktop}px;";
        echo "--rss-mh-gap-post-mobile:{$gap_post_mobile}px;";
        echo "--rss-mh-gap-page-desktop:{$gap_page_desktop}px;";
        echo "--rss-mh-gap-page-mobile:{$gap_page_mobile}px;";
        echo "--rss-mh-font-post-desktop:{$font_post_desktop}px;";
        echo "--rss-mh-font-post-mobile:{$font_post_mobile}px;";
        echo "--rss-mh-font-page-desktop:{$font_page_desktop}px;";
        echo "--rss-mh-font-page-mobile:{$font_page_mobile}px;";
        echo "--rss-mh-left-offset-desktop:{$left_offset_desktop}px;";
        echo "}\n";

        echo <<<CSS
/* ============================
   RSS Meta Header
   ============================ */

/* Default to POST variables; PAGE overrides below. */
body{
  --rss-mh-gap-desktop: var(--rss-mh-gap-post-desktop);
  --rss-mh-gap-mobile:  var(--rss-mh-gap-post-mobile);
  --rss-mh-font-desktop: var(--rss-mh-font-post-desktop);
  --rss-mh-font-mobile:  var(--rss-mh-font-post-mobile);
}
body.page{
  --rss-mh-gap-desktop: var(--rss-mh-gap-page-desktop);
  --rss-mh-gap-mobile:  var(--rss-mh-gap-page-mobile);
  --rss-mh-font-desktop: var(--rss-mh-font-page-desktop);
  --rss-mh-font-mobile:  var(--rss-mh-font-page-mobile);
}

.rss-mh-wrap{width:100%;max-width:100%;text-align:left;}
/*
 * .rss-mh-wrap--top margin-top is driven by --rss-mh-gap-desktop (CSS variable, global).
 * When a per-post gap override is set, an inline style="margin-top:Xpx" is added to this element
 * which wins over this rule. Mobile override is still applied via the @media query below UNLESS
 * the inline style is also written for mobile (it is not — inline is desktop only; see build_block_html).
 */
.rss-mh-wrap--top{margin:var(--rss-mh-gap-desktop) 0 16px 0;}
.rss-mh-wrap--bottom{margin:16px 0 0 0;}

@media (max-width: 767px){
  .rss-mh-wrap--top{margin-top:var(--rss-mh-gap-mobile);}
  .rss-mh-wrap--top{margin-bottom:14px;}
}

.rss-mh-inner{
  max-width: 1100px;
  margin: 0 auto;
  padding: 0 20px;
}

@media (min-width: 768px){
  .rss-mh-inner{margin-left:0 !important;margin-right:auto !important;padding-left:var(--rss-mh-left-offset-desktop) !important;}
}
@media (max-width: 767px){
  .rss-mh-inner{padding: 0 16px;}
}

.rss-mh-block{
  border:1px solid #e6e9ee;
  background:#f5f7fb;
  border-radius:12px;
  padding:12px 14px;
  max-width:100%;
  overflow:hidden;
  --rss-mh-avatar-size:56px;
  --rss-mh-avatar-overlap:8px;
}
@media (max-width: 767px){
  .rss-mh-block{--rss-mh-avatar-size:40px;padding:10px 12px;}
}

.rss-mh-row{display:flex;align-items:flex-start;gap:12px;}
.rss-mh-avatars{display:flex;align-items:center;flex:0 0 auto;}
.rss-mh-lines{flex:1 1 auto;min-width:0;}

@media (max-width: 767px){
  .rss-mh-row{flex-direction:row;align-items:flex-start;gap:10px;}
  .rss-mh-lines{width:auto;}
}

.rss-mh-avatar{
  width:var(--rss-mh-avatar-size);
  height:var(--rss-mh-avatar-size);
  border-radius:999px;
  object-fit:cover;
  border:2px solid #ffffff;
  box-shadow:0 0 0 1px #e6e9ee;
  background:#ffffff;
}
.rss-mh-avatar--reviewer{z-index:1;}
.rss-mh-avatar--author{z-index:2;margin-left:calc(-1 * var(--rss-mh-avatar-overlap));}
.rss-mh-avatars--single .rss-mh-avatar--author{margin-left:0;}

.rss-mh-line{
  margin:0;
  font-family: Georgia, "Times New Roman", Times, serif;
  font-style: italic;
  font-weight: 400;
  font-size: var(--rss-mh-font-desktop);
  line-height: 1.5;
  color:#111827;
  overflow-wrap:anywhere;
}
.rss-mh-line + .rss-mh-line{margin-top:2px;}
@media (max-width: 767px){
  .rss-mh-line{font-size: var(--rss-mh-font-mobile);}
}

.rss-mh-line--updated{
  font-weight: 700;
  font-size: clamp(11px, calc(var(--rss-mh-font-desktop) - 2px), 999px);
}
@media (max-width: 767px){
  .rss-mh-line--updated{font-size: clamp(11px, calc(var(--rss-mh-font-mobile) - 2px), 999px);}
}

.rss-mh-block a{color:#0b5cab;text-decoration:underline;text-underline-offset:2px;}
.rss-mh-block a:hover{text-decoration:none;}

.rss-mh-sep{display:inline;}

.rss-mh-line__mobile{display:none;}
@media (max-width: 767px){
  .rss-mh-line__desktop{display:none;}
  .rss-mh-line__mobile{display:inline;}
  .rss-mh-line__mobile--lock{
    white-space: nowrap;
    font-size: clamp(12px, 4.1vw, var(--rss-mh-font-mobile));
  }
}

.rss-mh-role--mobile{display:none;}
@media (max-width: 767px){
  .rss-mh-role--desktop{display:none;}
  .rss-mh-role--mobile{display:inline;}
}

.rss-mh-name--mobile{display:none;}
@media (max-width: 767px){
  .rss-mh-name--desktop{display:none;}
  .rss-mh-name--mobile{display:inline;}
}

.rss-mh-actions{margin-top:8px;}
.rss-mh-more{
  appearance:none;
  background:transparent;
  border:1px solid #cbd5e1;
  border-radius:999px;
  padding:6px 12px;
  font-weight:800;
  font-size:13px;
  line-height:1;
  color:#0b5cab;
  cursor:pointer;
}
.rss-mh-more:hover{background:rgba(11,92,171,.06);}
.rss-mh-more:focus-visible{outline:3px solid rgba(11,92,171,.18);outline-offset:2px;}

.rss-mh-bio{
  max-height:0;
  overflow:hidden;
  opacity:0;
  transition:max-height .25s ease, opacity .25s ease;
}
.rss-mh-bio.is-open{opacity:1;}
.rss-mh-bio__inner{
  padding-top:8px;
  font:400 14px/1.6 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;
  color:#374151;
}

.rss-mh-block p{margin:0 !important;padding:0 !important;}
.rss-mh-block p:empty{display:none !important;}
.rss-mh-block br{display:none !important;}
CSS;

        echo "\n</style>\n";
    }

    /* =========================================================
     * Frontend: JS (More About accordion)
     * ========================================================= */
    public function output_frontend_js() {
        if (is_admin()) return;
        if (!$this->is_more_about_enabled()) return;
        if (!is_singular()) return;

        ?>
        <script id="rss-mh-more-about-js">
        (function(){
          function openPanel(btn, panel){
            btn.setAttribute('aria-expanded','true');
            panel.hidden = false;
            panel.style.maxHeight = '0px';
            panel.offsetHeight;
            panel.classList.add('is-open');
            panel.style.maxHeight = panel.scrollHeight + 'px';
          }

          function closePanel(btn, panel){
            btn.setAttribute('aria-expanded','false');
            panel.style.maxHeight = panel.scrollHeight + 'px';
            panel.offsetHeight;
            panel.classList.remove('is-open');
            panel.style.maxHeight = '0px';

            var done = false;
            function finish(){
              if (done) return;
              done = true;
              panel.hidden = true;
            }

            function onEnd(e){
              if (e && e.propertyName !== 'max-height') return;
              panel.removeEventListener('transitionend', onEnd);
              finish();
            }

            panel.addEventListener('transitionend', onEnd);
            setTimeout(finish, 450);
          }

          function bind(){
            var btns = document.querySelectorAll('.rss-mh-more');
            btns.forEach(function(btn){
              if (btn.__rssMhBound) return;
              btn.__rssMhBound = true;
              btn.addEventListener('click', function(){
                var id = btn.getAttribute('aria-controls');
                if (!id) return;
                var panel = document.getElementById(id);
                if (!panel) return;
                var expanded = btn.getAttribute('aria-expanded') === 'true';
                if (expanded){ closePanel(btn, panel); } else { openPanel(btn, panel); }
              });
            });
          }

          document.addEventListener('DOMContentLoaded', function(){
            bind();
            window.addEventListener('resize', function(){
              document.querySelectorAll('.rss-mh-bio.is-open').forEach(function(panel){
                panel.style.maxHeight = panel.scrollHeight + 'px';
              });
            });
          });
        })();
        </script>
        <?php
    }

    /* =========================================================
     * Rendering (top/bottom)
     * ========================================================= */

    /**
     * Inject meta header HTML after the first </h1> in the post content.
     * Replaces the old et_before_main_content hook for top-position rendering.
     */
    public function inject_after_h1($content) {
        if (is_admin()) return $content;
        if (!is_singular()) return $content;

        $post_id = (int) get_queried_object_id();
        if (!$post_id) return $content;

        $pt = get_post_type($post_id);
        if (!in_array($pt, array('post', 'page'), true)) return $content;

        if (!$this->meta_enabled_for($post_id)) return $content;

        $pos = $this->meta_position_for($post_id);
        if ($pos !== 'top') return $content;

        // Build the meta header HTML
        $meta_html = $this->build_block_html($post_id, 'top');

        // Find the first </h1> and inject after it
        $h1_pos = stripos($content, '</h1>');
        if ($h1_pos !== false) {
            $insert_at = $h1_pos + 5;
            $content = substr($content, 0, $insert_at) . "\n" . $meta_html . "\n" . substr($content, $insert_at);
        } else {
            // No H1 found — prepend to content (fallback)
            $content = $meta_html . "\n" . $content;
        }

        return $content;
    }

    public function render_top() {
        $this->render_for_position('top');
    }

    public function render_bottom() {
        $this->render_for_position('bottom');
    }

    public function render_top_fallback() {
        if ($this->is_divi_env()) return;
        $this->render_for_position('top');
    }

    public function render_bottom_fallback() {
        if ($this->is_divi_env()) return;
        $this->render_for_position('bottom');
    }

    private function render_for_position(string $position) {
        if (is_admin()) return;
        if (!is_singular()) return;

        $post_id = (int) get_queried_object_id();
        if (!$post_id) return;

        $pt = get_post_type($post_id);
        if (!in_array($pt, array('post', 'page'), true)) return;

        if (!$this->meta_enabled_for($post_id)) return;

        $pos = $this->meta_position_for($post_id);
        if ($pos !== $position) return;

        echo $this->build_block_html($post_id, $position);
    }

    private function build_block_html(int $post_id, string $position): string {
        $hide_reviewer = $this->meta_hide_reviewer_for($post_id);

        $labels   = $this->resolved_labels($post_id);
        $author   = $this->author_data($post_id);
        $reviewer = $this->reviewer_data($post_id);

        $updated_ts   = (int) get_post_modified_time('U', true, $post_id);
        $display_date = date_i18n(get_option('date_format'), $updated_ts);
        $machine_dt   = get_post_modified_time('c', true, $post_id);

        // Author name (optional mobile-short version via user meta).
        if (!empty($author['name_mobile'])) {
            $author_name_html = '<span class="rss-mh-name rss-mh-name--desktop">' . esc_html($author['name']) . '</span>'
                . '<span class="rss-mh-name rss-mh-name--mobile">' . esc_html($author['name_mobile']) . '</span>';
        } else {
            $author_name_html = esc_html($author['name']);
        }

        $author_link = '<a class="rss-mh-link rss-mh-link--author" href="' . esc_url($author['url']) . '" rel="author">' . $author_name_html . '</a>';
        $sep         = '<span class="rss-mh-sep" aria-hidden="true">&nbsp;&bull;&nbsp;</span>';

        // NMLS fragments (author).
        $author_nmls_desktop = '';
        $author_nmls_mobile  = '';
        if (!empty($author['nmls'])) {
            $n = esc_html($author['nmls']);
            if (!empty($author['nmls_url'])) {
                $author_nmls_desktop = '<a class="rss-mh-link rss-mh-link--nmls" href="' . esc_url($author['nmls_url']) . '" target="_blank" rel="nofollow noopener noreferrer">NMLS#' . $n . '</a>';
                $author_nmls_mobile  = '<a class="rss-mh-link rss-mh-link--nmls" href="' . esc_url($author['nmls_url']) . '" target="_blank" rel="nofollow noopener noreferrer">NMLS ' . $n . '</a>';
            } else {
                $author_nmls_desktop = 'NMLS#' . $n;
                $author_nmls_mobile  = 'NMLS ' . $n;
            }
        }

        // NMLS fragments (reviewer).
        $reviewer_nmls_desktop = '';
        $reviewer_nmls_mobile  = '';
        if (!empty($reviewer['nmls'])) {
            $n = esc_html($reviewer['nmls']);
            if (!empty($reviewer['nmls_url'])) {
                $reviewer_nmls_desktop = '<a class="rss-mh-link rss-mh-link--nmls" href="' . esc_url($reviewer['nmls_url']) . '" target="_blank" rel="nofollow noopener noreferrer">NMLS#' . $n . '</a>';
                $reviewer_nmls_mobile  = '<a class="rss-mh-link rss-mh-link--nmls" href="' . esc_url($reviewer['nmls_url']) . '" target="_blank" rel="nofollow noopener noreferrer">NMLS ' . $n . '</a>';
            } else {
                $reviewer_nmls_desktop = 'NMLS#' . $n;
                $reviewer_nmls_mobile  = 'NMLS ' . $n;
            }
        }

        // --- Build author line HTML ---
        $has_nmls        = !empty($author['nmls']);
        $has_mobile_role = (!empty($author['role_mobile']) && $author['role_mobile'] !== $author['role_desktop']);

        $author_line_html = '';

        if ($has_nmls) {
            // Desktop: "Written by: Name, Role • NMLS#XXX" (role optional).
            $desktop = esc_html($labels['author']) . ' ' . $author_link;
            if (!empty($author['role_desktop'])) {
                $desktop .= ', ' . esc_html($author['role_desktop']);
            }
            $desktop .= $sep . $author_nmls_desktop;

            // Mobile: compact "Written by: Name (NMLS XXX)".
            $mobile_label = trim(preg_replace('/:\s*$/', '', (string) $labels['author']));
            if ($mobile_label === '') $mobile_label = trim((string) $labels['author']);
            $mobile = esc_html($mobile_label) . ': ' . $author_link . ' (' . $author_nmls_mobile . ')';

            $author_line_html = '<span class="rss-mh-line__desktop">' . $desktop . '</span>'
                . '<span class="rss-mh-line__mobile rss-mh-line__mobile--lock">' . $mobile . '</span>';

        } elseif ($has_mobile_role) {
            // Desktop: "Written by: Name, Desktop Role".
            $desktop = esc_html($labels['author']) . ' ' . $author_link;
            if (!empty($author['role_desktop'])) {
                $desktop .= '<span class="rss-mh-role rss-mh-role--desktop">, ' . esc_html($author['role_desktop']) . '</span>';
            }
            // Mobile: "Written by: Name, Mobile Role".
            $mobile = esc_html($labels['author']) . ' ' . $author_link
                . '<span class="rss-mh-role rss-mh-role--mobile">, ' . esc_html($author['role_mobile']) . '</span>';

            $author_line_html = '<span class="rss-mh-line__desktop">' . $desktop . '</span>'
                . '<span class="rss-mh-line__mobile">' . $mobile . '</span>';

        } else {
            // Simple: "Written by: Name" with optional role.
            $line = esc_html($labels['author']) . ' ' . $author_link;
            if (!empty($author['role_desktop'])) {
                $line .= '<span class="rss-mh-role">, ' . esc_html($author['role_desktop']) . '</span>';
            }
            $author_line_html = $line;
        }

        // --- Build reviewer line HTML ---
        $reviewer_line_html = '';
        if (!$hide_reviewer && !empty($reviewer['name'])) {
            $reviewer_link         = '<a class="rss-mh-link rss-mh-link--reviewer" href="' . esc_url($reviewer['url']) . '">' . esc_html($reviewer['name']) . '</a>';
            $reviewer_line_desktop = esc_html($labels['reviewer']) . ' ' . $reviewer_link;

            if (!empty($reviewer['role'])) {
                $reviewer_line_desktop .= '<span class="rss-mh-role rss-mh-role--reviewer">, ' . esc_html($reviewer['role']) . '</span>';
            }
            if ($reviewer_nmls_desktop) {
                $reviewer_line_desktop .= $sep . $reviewer_nmls_desktop;
            }

            // If reviewer has NMLS, use compact mobile layout.
            if (!empty($reviewer['nmls']) && $reviewer_nmls_mobile) {
                $reviewer_label_mobile = trim(preg_replace('/:\s*$/', '', (string) $labels['reviewer']));
                if ($reviewer_label_mobile === '') $reviewer_label_mobile = trim((string) $labels['reviewer']);
                $reviewer_label_mobile = preg_replace('/\s+by$/i', '', $reviewer_label_mobile);
                $reviewer_label_mobile = trim($reviewer_label_mobile);
                if ($reviewer_label_mobile === '') $reviewer_label_mobile = 'Reviewed';

                $reviewer_line_mobile = esc_html($reviewer_label_mobile) . ': ' . $reviewer_link . ' (' . $reviewer_nmls_mobile . ')';
                $reviewer_line_html = '<span class="rss-mh-line__desktop">' . $reviewer_line_desktop . '</span>'
                    . '<span class="rss-mh-line__mobile rss-mh-line__mobile--lock">' . $reviewer_line_mobile . '</span>';
            } else {
                $reviewer_line_html = $reviewer_line_desktop;
            }
        }

        // Updated line.
        $updated_line_html = esc_html($labels['updated']) . ' <time class="rss-mh-updated" datetime="' . esc_attr($machine_dt) . '">' . esc_html($display_date) . '</time>';

        // Avatars.
        $author_img   = !empty($author['img']) ? (string) $author['img'] : get_site_icon_url(64);
        $reviewer_img = (!$hide_reviewer && !empty($reviewer['img'])) ? (string) $reviewer['img'] : '';
        if (!$reviewer_img && !$hide_reviewer) {
            $reviewer_img = get_site_icon_url(64);
        }

        // More about (bio accordion).
        $more_about_enabled = $this->is_more_about_enabled();
        $bio_text           = $more_about_enabled ? $this->bio_text_for_author($author) : '';
        $show_more_about    = ($more_about_enabled && $bio_text !== '');

        $bio_id    = 'rss-mh-bio-' . $post_id;
        $btn_label = 'More about ' . $this->first_name((string) $author['name']);

        $wrap_class = 'rss-mh-wrap rss-mh-wrap--' . $position;

        // Per-post gap override (only applied to the top wrap).
        // This inline style wins over the global CSS variable, letting you fine-tune
        // spacing per page/post when Divi's hero section padding varies.
        $gap_inline_style = '';
        if ($position === 'top') {
            $gap_override = $this->meta_gap_override_for($post_id);
            if ($gap_override !== null) {
                $gap_inline_style = ' style="margin-top:' . $gap_override . 'px"';
            }
        }

        ob_start();
        ?>
        <div class="<?php echo esc_attr($wrap_class); ?>"<?php echo $gap_inline_style; ?>>
            <div class="rss-mh-inner">
                <div class="rss-mh-block">
                    <div class="rss-mh-row">
                        <div class="rss-mh-avatars<?php echo $reviewer_img ? '' : ' rss-mh-avatars--single'; ?>" aria-hidden="true">
                            <?php if ($reviewer_img): ?>
                                <img class="rss-mh-avatar rss-mh-avatar--reviewer" src="<?php echo esc_url($reviewer_img); ?>" alt="" loading="lazy" decoding="async" width="56" height="56">
                            <?php endif; ?>
                            <?php if ($author_img): ?>
                                <img class="rss-mh-avatar rss-mh-avatar--author" src="<?php echo esc_url($author_img); ?>" alt="" loading="lazy" decoding="async" width="56" height="56">
                            <?php endif; ?>
                        </div>

                        <div class="rss-mh-lines">
                            <div class="rss-mh-line rss-mh-line--author"><?php echo $author_line_html; ?></div>

                            <?php if ($reviewer_line_html): ?>
                                <div class="rss-mh-line rss-mh-line--reviewer"><?php echo $reviewer_line_html; ?></div>
                            <?php endif; ?>

                            <div class="rss-mh-line rss-mh-line--updated"><?php echo $updated_line_html; ?></div>

                            <?php if ($show_more_about): ?>
                                <div class="rss-mh-actions">
                                    <button type="button" class="rss-mh-more" aria-expanded="false" aria-controls="<?php echo esc_attr($bio_id); ?>"><?php echo esc_html($btn_label); ?></button>
                                </div>
                                <div id="<?php echo esc_attr($bio_id); ?>" class="rss-mh-bio" hidden>
                                    <div class="rss-mh-bio__inner"><?php echo esc_html($bio_text); ?></div>
                                </div>
                            <?php endif; ?>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        <?php

        $html = ob_get_clean();
        $html = preg_replace('/>\s+</', '><', (string) $html);
        return trim((string) $html) . "\n";
    }

    /* =========================================================
     * Admin: meta box
     * ========================================================= */
    public function add_meta_box() {
        foreach (array('post', 'page') as $pt) {
            add_meta_box('rss_mh_meta', 'RSS Meta Header', array($this, 'render_meta_box'), $pt, 'side', 'high');
        }
    }

    public function render_meta_box($post) {
        wp_nonce_field('rss_mh_save', 'rss_mh_nonce');

        $enabled_raw = get_post_meta($post->ID, self::META_ENABLE, true);
        $enabled     = ($enabled_raw === '' || $enabled_raw === null) ? 1 : (int) $enabled_raw;

        $sel = (string) get_post_meta($post->ID, self::META_REVIEWER_SELECT, true);
        if ($sel === '') $sel = 'default';

        $ov = get_post_meta($post->ID, self::META_REVIEWER, true);
        if (!is_array($ov)) $ov = array('name' => '', 'role' => '', 'nmls' => '', 'url' => '', 'img' => '');

        $mode     = $this->meta_mode_for((int) $post->ID);
        $pos      = $this->meta_position_for((int) $post->ID);
        $hide_rev = $this->meta_hide_reviewer_for((int) $post->ID);

        $label_author   = (string) get_post_meta($post->ID, self::META_LABEL_AUTHOR,   true);
        $label_reviewer = (string) get_post_meta($post->ID, self::META_LABEL_REVIEWER, true);
        $label_updated  = (string) get_post_meta($post->ID, self::META_LABEL_UPDATED,  true);

        // Per-post gap override.
        $gap_raw      = get_post_meta($post->ID, self::META_GAP_OVERRIDE, true);
        $gap_override = ($gap_raw !== '' && $gap_raw !== null && $gap_raw !== false && is_numeric($gap_raw)) ? (int) $gap_raw : '';

        // Configured identity names for dropdown labels.
        $reviewer_name_default = (string) get_option(self::OPT_REVIEWER_NAME, '');
        $editorial_name        = (string) get_option(self::OPT_EDITORIAL_NAME, '');

        echo '<p><label><input type="checkbox" name="rss_mh_disable_block" value="1" ' . checked((bool) (!$enabled), true, false) . '> Disable meta header on this post/page</label></p>';

        echo '<p><label><strong>Content type</strong></label><br><select name="rss_mh_mode" class="widefat">';
        echo '<option value="article" ' . selected($mode, 'article', false) . '>Article (Written by / Reviewed by)</option>';
        echo '<option value="tool" ' . selected($mode, 'tool', false) . '>Tool/Data (Created by / Validated by)</option>';
        echo '</select></p>';

        echo '<p><label><strong>Placement</strong></label><br><select name="rss_mh_position" class="widefat">';
        echo '<option value="top" ' . selected($pos, 'top', false) . '>Top (below hero)</option>';
        echo '<option value="bottom" ' . selected($pos, 'bottom', false) . '>Bottom (after content)</option>';
        echo '</select></p>';

        echo '<p><label><input type="checkbox" name="rss_mh_hide_reviewer" value="1" ' . checked($hide_rev, true, false) . '> Hide reviewer line</label></p>';

        echo '<p><label><strong>Reviewer</strong></label><br><select name="rss_mh_reviewer_select" id="rss_mh_reviewer_select" class="widefat">';
        echo '<option value="default" ' . selected($sel, 'default', false) . '>Default reviewer' . ($reviewer_name_default ? ' (' . esc_html($reviewer_name_default) . ')' : ' (not configured)') . '</option>';
        echo '<option value="editorial_team" ' . selected($sel, 'editorial_team', false) . '>Editorial Team' . ($editorial_name ? ' (' . esc_html($editorial_name) . ')' : ' (not configured)') . '</option>';
        echo '<option value="custom" ' . selected($sel, 'custom', false) . '>Custom (enter below)</option>';
        echo '</select></p>';

        echo '<p style="margin-top:-6px;"><small><em>Configure default reviewer and editorial team in Settings &gt; RSS Meta Header.</em></small></p>';

        $wrap = ($sel === 'custom') ? '' : ' style="display:none"';
        echo '<div id="rss_mh_rev_wrap"' . $wrap . '>';
        echo '<p><strong>Reviewer override</strong><br><small>Only used when Reviewer is set to Custom.</small></p>';
        echo '<p><input type="text" class="widefat" name="rss_mh_ov_name" placeholder="Name" value="' . esc_attr((string) ($ov['name'] ?? '')) . '"></p>';
        echo '<p><input type="text" class="widefat" name="rss_mh_ov_role" placeholder="Role/Title" value="' . esc_attr((string) ($ov['role'] ?? '')) . '"></p>';
        echo '<p><input type="text" class="widefat" name="rss_mh_ov_nmls" placeholder="NMLS#" value="' . esc_attr((string) ($ov['nmls'] ?? '')) . '"></p>';
        echo '<p><input type="url" class="widefat" name="rss_mh_ov_url" placeholder="Profile URL" value="' . esc_attr((string) ($ov['url'] ?? '')) . '"></p>';
        echo '<p><input type="url" class="widefat" name="rss_mh_ov_img" placeholder="Image URL" value="' . esc_attr((string) ($ov['img'] ?? '')) . '"></p>';
        echo '</div>';

        echo '<hr style="margin:12px 0;">';
        echo '<p><label><strong>Spacing override (px)</strong></label><br>';
        echo '<small>Leave blank to use the global gap from Settings. Enter a number (can be negative) to override the space between the hero and this meta block on this page only. Useful when Divi sections have inconsistent built-in padding.</small><br>';
        echo '<input type="number" class="widefat" name="rss_mh_gap_override" placeholder="Blank = use global" value="' . esc_attr((string) $gap_override) . '" min="' . self::GAP_MIN . '" max="' . self::GAP_MAX . '" style="margin-top:4px;"></p>';

        echo '<hr style="margin:12px 0;">';
        echo '<p><strong>Label overrides (optional)</strong><br><small>Leave blank to use defaults from Content type.</small></p>';
        echo '<p><input type="text" class="widefat" name="rss_mh_label_author" placeholder="Author label" value="' . esc_attr($label_author) . '"></p>';
        echo '<p><input type="text" class="widefat" name="rss_mh_label_reviewer" placeholder="Reviewer label" value="' . esc_attr($label_reviewer) . '"></p>';
        echo '<p><input type="text" class="widefat" name="rss_mh_label_updated" placeholder="Date label" value="' . esc_attr($label_updated) . '"></p>';

        echo '<script>(function(){var s=document.getElementById("rss_mh_reviewer_select");var w=document.getElementById("rss_mh_rev_wrap");function t(){if(!s||!w)return;w.style.display=(s.value==="custom")?"block":"none";}t();s&&s.addEventListener("change",t);})();</script>';
    }

    public function save_meta_box($post_id) {
        $has_fields = isset($_POST['rss_mh_disable_block']) || isset($_POST['rss_mh_mode']) || isset($_POST['rss_mh_position'])
            || isset($_POST['rss_mh_hide_reviewer']) || isset($_POST['rss_mh_reviewer_select'])
            || isset($_POST['rss_mh_label_author'])  || isset($_POST['rss_mh_label_reviewer']) || isset($_POST['rss_mh_label_updated'])
            || isset($_POST['rss_mh_ov_name'])        || isset($_POST['rss_mh_ov_role'])        || isset($_POST['rss_mh_ov_nmls'])
            || isset($_POST['rss_mh_ov_url'])         || isset($_POST['rss_mh_ov_img'])
            || array_key_exists('rss_mh_gap_override', $_POST);

        if (!$has_fields) return;

        if (defined('DOING_AUTOSAVE') && DOING_AUTOSAVE) return;
        if (wp_is_post_revision($post_id) || wp_is_post_autosave($post_id)) return;
        if (!current_user_can('edit_post', $post_id)) return;
        if (!isset($_POST['rss_mh_nonce']) || !wp_verify_nonce($_POST['rss_mh_nonce'], 'rss_mh_save')) return;

        update_post_meta($post_id, self::META_ENABLE, isset($_POST['rss_mh_disable_block']) ? 0 : 1);

        $mode = isset($_POST['rss_mh_mode']) ? sanitize_key($_POST['rss_mh_mode']) : 'article';
        if (!in_array($mode, array('article', 'tool'), true)) $mode = 'article';
        update_post_meta($post_id, self::META_MODE, $mode);

        $pos = isset($_POST['rss_mh_position']) ? sanitize_key($_POST['rss_mh_position']) : 'top';
        if (!in_array($pos, array('top', 'bottom'), true)) $pos = 'top';
        update_post_meta($post_id, self::META_POSITION, $pos);

        update_post_meta($post_id, self::META_HIDE_REVIEWER, isset($_POST['rss_mh_hide_reviewer']) ? 1 : 0);

        $sel = isset($_POST['rss_mh_reviewer_select']) ? sanitize_key($_POST['rss_mh_reviewer_select']) : 'default';
        if (!in_array($sel, array('default', 'editorial_team', 'custom'), true)) $sel = 'default';
        update_post_meta($post_id, self::META_REVIEWER_SELECT, $sel);

        $ov = array(
            'name' => isset($_POST['rss_mh_ov_name']) ? sanitize_text_field($_POST['rss_mh_ov_name']) : '',
            'role' => isset($_POST['rss_mh_ov_role']) ? sanitize_text_field($_POST['rss_mh_ov_role']) : '',
            'nmls' => isset($_POST['rss_mh_ov_nmls']) ? sanitize_text_field($_POST['rss_mh_ov_nmls']) : '',
            'url'  => isset($_POST['rss_mh_ov_url'])  ? esc_url_raw($_POST['rss_mh_ov_url']) : '',
            'img'  => isset($_POST['rss_mh_ov_img'])  ? esc_url_raw($_POST['rss_mh_ov_img']) : '',
        );
        if ($sel !== 'custom') {
            $ov = array('name' => '', 'role' => '', 'nmls' => '', 'url' => '', 'img' => '');
        }
        update_post_meta($post_id, self::META_REVIEWER, $ov);

        $la = isset($_POST['rss_mh_label_author'])   ? $this->clean_label_string(sanitize_text_field($_POST['rss_mh_label_author']))   : '';
        $lr = isset($_POST['rss_mh_label_reviewer'])  ? $this->clean_label_string(sanitize_text_field($_POST['rss_mh_label_reviewer'])) : '';
        $lu = isset($_POST['rss_mh_label_updated'])   ? $this->clean_label_string(sanitize_text_field($_POST['rss_mh_label_updated']))  : '';
        update_post_meta($post_id, self::META_LABEL_AUTHOR,   $la);
        update_post_meta($post_id, self::META_LABEL_REVIEWER, $lr);
        update_post_meta($post_id, self::META_LABEL_UPDATED,  $lu);

        // Per-post gap override. Empty string = delete (use global).
        if (array_key_exists('rss_mh_gap_override', $_POST)) {
            $raw_gap = trim((string) $_POST['rss_mh_gap_override']);
            if ($raw_gap === '') {
                delete_post_meta($post_id, self::META_GAP_OVERRIDE);
            } elseif (is_numeric($raw_gap)) {
                $clamped = $this->clamp_int((int) $raw_gap, self::GAP_MIN, self::GAP_MAX, 0);
                update_post_meta($post_id, self::META_GAP_OVERRIDE, $clamped);
            }
        }
    }

    public function default_on_new($post_id, $post, $update) {
        if ($update) return;
        if (!is_object($post) || !in_array($post->post_type, array('post', 'page'), true)) return;

        if (get_post_meta($post_id, self::META_ENABLE, true) === '') {
            update_post_meta($post_id, self::META_ENABLE, 1);
        }
        if (get_post_meta($post_id, self::META_REVIEWER_SELECT, true) === '') {
            update_post_meta($post_id, self::META_REVIEWER_SELECT, 'default');
        }
        if (get_post_meta($post_id, self::META_MODE, true) === '') {
            update_post_meta($post_id, self::META_MODE, 'article');
        }
        if (get_post_meta($post_id, self::META_POSITION, true) === '') {
            update_post_meta($post_id, self::META_POSITION, 'top');
        }
        if (get_post_meta($post_id, self::META_HIDE_REVIEWER, true) === '') {
            update_post_meta($post_id, self::META_HIDE_REVIEWER, 0);
        }
        // META_GAP_OVERRIDE: intentionally NOT defaulted — blank means "use global".
    }

    /* =========================================================
     * Admin: settings page
     * ========================================================= */
    public function add_settings_page() {
        add_options_page(
            'RSS Meta Header',
            'RSS Meta Header',
            'manage_options',
            'rss-meta-header',
            array($this, 'render_settings_page')
        );
    }

    public function register_settings() {
        // Gap: extended range -60 to 120px.
        $gap_sanitize = function ($v) {
            $n = (int) $v;
            if ($n < self::GAP_MIN) $n = self::GAP_MIN;
            if ($n > self::GAP_MAX) $n = self::GAP_MAX;
            return $n;
        };
        $font_sanitize = function ($v) {
            $n = (int) $v;
            if ($n < 12) $n = 12;
            if ($n > 22) $n = 22;
            return $n;
        };

        register_setting('rss_mh', self::OPT_GAP_POST_DESKTOP, array('type' => 'integer', 'default' => 12, 'sanitize_callback' => $gap_sanitize));
        register_setting('rss_mh', self::OPT_GAP_POST_MOBILE,  array('type' => 'integer', 'default' => 12, 'sanitize_callback' => $gap_sanitize));
        register_setting('rss_mh', self::OPT_GAP_PAGE_DESKTOP, array('type' => 'integer', 'default' => 12, 'sanitize_callback' => $gap_sanitize));
        register_setting('rss_mh', self::OPT_GAP_PAGE_MOBILE,  array('type' => 'integer', 'default' => 12, 'sanitize_callback' => $gap_sanitize));

        register_setting('rss_mh', self::OPT_FONT_POST_DESKTOP, array('type' => 'integer', 'default' => 15, 'sanitize_callback' => $font_sanitize));
        register_setting('rss_mh', self::OPT_FONT_POST_MOBILE,  array('type' => 'integer', 'default' => 15, 'sanitize_callback' => $font_sanitize));
        register_setting('rss_mh', self::OPT_FONT_PAGE_DESKTOP, array('type' => 'integer', 'default' => 15, 'sanitize_callback' => $font_sanitize));
        register_setting('rss_mh', self::OPT_FONT_PAGE_MOBILE,  array('type' => 'integer', 'default' => 15, 'sanitize_callback' => $font_sanitize));

        register_setting('rss_mh', self::OPT_ENABLE_MORE_ABOUT, array(
            'type' => 'boolean', 'default' => false,
            'sanitize_callback' => function ($v) { return (bool) $v; }
        ));

        register_setting('rss_mh', self::OPT_DESKTOP_LEFT_OFFSET, array(
            'type' => 'integer', 'default' => 80,
            'sanitize_callback' => function ($v) {
                $n = intval($v);
                if ($n < 0) $n = 0;
                if ($n > 240) $n = 240;
                return $n;
            }
        ));

        register_setting('rss_mh', self::OPT_JSONLD_FALLBACK, array(
            'type' => 'boolean', 'default' => true,
            'sanitize_callback' => function ($v) { return (bool) $v; }
        ));

        // Default Reviewer Identity.
        register_setting('rss_mh', self::OPT_REVIEWER_TYPE, array(
            'type' => 'string', 'default' => 'Person',
            'sanitize_callback' => function ($v) {
                return in_array($v, array('Person', 'Organization'), true) ? $v : 'Person';
            }
        ));
        register_setting('rss_mh', self::OPT_REVIEWER_NAME,     array('type' => 'string', 'default' => '', 'sanitize_callback' => 'sanitize_text_field'));
        register_setting('rss_mh', self::OPT_REVIEWER_URL,      array('type' => 'string', 'default' => '', 'sanitize_callback' => 'esc_url_raw'));
        register_setting('rss_mh', self::OPT_REVIEWER_ROLE,     array('type' => 'string', 'default' => '', 'sanitize_callback' => 'sanitize_text_field'));
        register_setting('rss_mh', self::OPT_REVIEWER_IMG,      array('type' => 'string', 'default' => '', 'sanitize_callback' => 'esc_url_raw'));
        register_setting('rss_mh', self::OPT_REVIEWER_NMLS,     array('type' => 'string', 'default' => '', 'sanitize_callback' => 'sanitize_text_field'));
        register_setting('rss_mh', self::OPT_REVIEWER_NMLS_URL, array('type' => 'string', 'default' => '', 'sanitize_callback' => 'esc_url_raw'));

        // Editorial Team Identity.
        register_setting('rss_mh', self::OPT_EDITORIAL_NAME,        array('type' => 'string', 'default' => '', 'sanitize_callback' => 'sanitize_text_field'));
        register_setting('rss_mh', self::OPT_EDITORIAL_NAME_MOBILE, array('type' => 'string', 'default' => '', 'sanitize_callback' => 'sanitize_text_field'));
        register_setting('rss_mh', self::OPT_EDITORIAL_URL,         array('type' => 'string', 'default' => '', 'sanitize_callback' => 'esc_url_raw'));
        register_setting('rss_mh', self::OPT_EDITORIAL_IMG,         array('type' => 'string', 'default' => '', 'sanitize_callback' => 'esc_url_raw'));
    }

    public function render_settings_page() {
        if (!current_user_can('manage_options')) return;

        $legacy_gap = $this->get_option_int(self::OPT_LEGACY_META_TOP_SPACING, 12, self::GAP_MIN, self::GAP_MAX);

        $gap_post_desktop = $this->get_option_int(self::OPT_GAP_POST_DESKTOP, $legacy_gap, self::GAP_MIN, self::GAP_MAX);
        $gap_post_mobile  = $this->get_option_int(self::OPT_GAP_POST_MOBILE,  $legacy_gap, self::GAP_MIN, self::GAP_MAX);
        $gap_page_desktop = $this->get_option_int(self::OPT_GAP_PAGE_DESKTOP, $legacy_gap, self::GAP_MIN, self::GAP_MAX);
        $gap_page_mobile  = $this->get_option_int(self::OPT_GAP_PAGE_MOBILE,  $legacy_gap, self::GAP_MIN, self::GAP_MAX);

        $font_post_desktop = $this->get_option_int(self::OPT_FONT_POST_DESKTOP, 15, 12, 22);
        $font_post_mobile  = $this->get_option_int(self::OPT_FONT_POST_MOBILE,  15, 12, 22);
        $font_page_desktop = $this->get_option_int(self::OPT_FONT_PAGE_DESKTOP, 15, 12, 22);
        $font_page_mobile  = $this->get_option_int(self::OPT_FONT_PAGE_MOBILE,  15, 12, 22);

        $desktop_left_offset = $this->get_option_int(self::OPT_DESKTOP_LEFT_OFFSET, 80, 0, 240);
        $more_about          = $this->is_more_about_enabled();
        $jsonld_fallback     = (bool) get_option(self::OPT_JSONLD_FALLBACK, true);

        $gap_min = self::GAP_MIN;
        $gap_max = self::GAP_MAX;

        // Reviewer identity values.
        $reviewer_type     = (string) get_option(self::OPT_REVIEWER_TYPE, 'Person');
        $reviewer_name     = (string) get_option(self::OPT_REVIEWER_NAME, '');
        $reviewer_url      = (string) get_option(self::OPT_REVIEWER_URL, '');
        $reviewer_role     = (string) get_option(self::OPT_REVIEWER_ROLE, '');
        $reviewer_img      = (string) get_option(self::OPT_REVIEWER_IMG, '');
        $reviewer_nmls     = (string) get_option(self::OPT_REVIEWER_NMLS, '');
        $reviewer_nmls_url = (string) get_option(self::OPT_REVIEWER_NMLS_URL, '');

        // Editorial team values.
        $editorial_name        = (string) get_option(self::OPT_EDITORIAL_NAME, '');
        $editorial_name_mobile = (string) get_option(self::OPT_EDITORIAL_NAME_MOBILE, '');
        $editorial_url         = (string) get_option(self::OPT_EDITORIAL_URL, '');
        $editorial_img         = (string) get_option(self::OPT_EDITORIAL_IMG, '');

        echo '<div class="wrap">';
        echo '<h1>RSS Meta Header</h1>';
        echo '<form method="post" action="options.php">';
        settings_fields('rss_mh');
        do_settings_sections('rss_mh');

        /* --- Default Reviewer Identity --- */
        echo '<h2>Default Reviewer</h2>';
        echo '<p class="description">The default reviewer shown on every post unless overridden per-post. Leave <strong>Name</strong> empty to hide the reviewer line by default.</p>';
        echo '<table class="form-table" role="presentation">';
        echo '<tr><th scope="row">Type</th><td><select name="' . esc_attr(self::OPT_REVIEWER_TYPE) . '">';
        echo '<option value="Person" ' . selected($reviewer_type, 'Person', false) . '>Person</option>';
        echo '<option value="Organization" ' . selected($reviewer_type, 'Organization', false) . '>Organization</option>';
        echo '</select></td></tr>';
        echo '<tr><th scope="row">Name</th><td><input type="text" class="regular-text" name="' . esc_attr(self::OPT_REVIEWER_NAME) . '" value="' . esc_attr($reviewer_name) . '"></td></tr>';
        echo '<tr><th scope="row">Profile URL</th><td><input type="url" class="regular-text" name="' . esc_attr(self::OPT_REVIEWER_URL) . '" value="' . esc_attr($reviewer_url) . '"></td></tr>';
        echo '<tr><th scope="row">Role / Title</th><td><input type="text" class="regular-text" name="' . esc_attr(self::OPT_REVIEWER_ROLE) . '" value="' . esc_attr($reviewer_role) . '"></td></tr>';
        echo '<tr><th scope="row">Image URL</th><td><input type="url" class="regular-text" name="' . esc_attr(self::OPT_REVIEWER_IMG) . '" value="' . esc_attr($reviewer_img) . '"><p class="description">Falls back to site icon if empty.</p></td></tr>';
        echo '<tr><th scope="row">NMLS #</th><td><input type="text" class="regular-text" name="' . esc_attr(self::OPT_REVIEWER_NMLS) . '" value="' . esc_attr($reviewer_nmls) . '"><p class="description">Leave empty if not applicable.</p></td></tr>';
        echo '<tr><th scope="row">NMLS Lookup URL</th><td><input type="url" class="regular-text" name="' . esc_attr(self::OPT_REVIEWER_NMLS_URL) . '" value="' . esc_attr($reviewer_nmls_url) . '"></td></tr>';
        echo '</table>';

        /* --- Editorial Team Identity --- */
        echo '<h2>Editorial Team</h2>';
        echo '<p class="description">Optional second reviewer option. Appears as a reviewer choice in the per-post meta box. Schema type is always <code>Organization</code>.</p>';
        echo '<table class="form-table" role="presentation">';
        echo '<tr><th scope="row">Team Name</th><td><input type="text" class="regular-text" name="' . esc_attr(self::OPT_EDITORIAL_NAME) . '" value="' . esc_attr($editorial_name) . '"><p class="description">Leave empty to disable this reviewer option.</p></td></tr>';
        echo '<tr><th scope="row">Short Name (Mobile)</th><td><input type="text" class="regular-text" name="' . esc_attr(self::OPT_EDITORIAL_NAME_MOBILE) . '" value="' . esc_attr($editorial_name_mobile) . '"></td></tr>';
        echo '<tr><th scope="row">Team Page URL</th><td><input type="url" class="regular-text" name="' . esc_attr(self::OPT_EDITORIAL_URL) . '" value="' . esc_attr($editorial_url) . '"></td></tr>';
        echo '<tr><th scope="row">Image URL</th><td><input type="url" class="regular-text" name="' . esc_attr(self::OPT_EDITORIAL_IMG) . '" value="' . esc_attr($editorial_img) . '"><p class="description">Falls back to site icon if empty.</p></td></tr>';
        echo '</table>';

        /* --- Spacing --- */
        echo '<h2>Meta Top Spacing (gap below hero)</h2>';
        echo '<p class="description">Controls <code>margin-top</code> on the meta block. Negative values pull the block <em>up</em> — useful when Divi adds excess section padding above the meta area. For per-page fine-tuning, use the <strong>Spacing override</strong> field in the post/page meta box.</p>';

        echo '<table class="form-table" role="presentation">';
        echo '<tr><th scope="row">Posts (Desktop)</th><td><input type="number" name="' . esc_attr(self::OPT_GAP_POST_DESKTOP) . '" value="' . esc_attr($gap_post_desktop) . '" min="' . $gap_min . '" max="' . $gap_max . '" style="width:90px;"> px</td></tr>';
        echo '<tr><th scope="row">Posts (Mobile)</th><td><input type="number" name="' . esc_attr(self::OPT_GAP_POST_MOBILE) . '" value="' . esc_attr($gap_post_mobile) . '" min="' . $gap_min . '" max="' . $gap_max . '" style="width:90px;"> px</td></tr>';
        echo '<tr><th scope="row">Pages (Desktop)</th><td><input type="number" name="' . esc_attr(self::OPT_GAP_PAGE_DESKTOP) . '" value="' . esc_attr($gap_page_desktop) . '" min="' . $gap_min . '" max="' . $gap_max . '" style="width:90px;"> px</td></tr>';
        echo '<tr><th scope="row">Pages (Mobile)</th><td><input type="number" name="' . esc_attr(self::OPT_GAP_PAGE_MOBILE) . '" value="' . esc_attr($gap_page_mobile) . '" min="' . $gap_min . '" max="' . $gap_max . '" style="width:90px;"> px</td></tr>';
        echo '</table>';

        echo '<h2>Meta Font Size</h2>';
        echo '<table class="form-table" role="presentation">';
        echo '<tr><th scope="row">Posts (Desktop)</th><td><input type="number" name="' . esc_attr(self::OPT_FONT_POST_DESKTOP) . '" value="' . esc_attr($font_post_desktop) . '" min="12" max="22" style="width:90px;"> px</td></tr>';
        echo '<tr><th scope="row">Posts (Mobile)</th><td><input type="number" name="' . esc_attr(self::OPT_FONT_POST_MOBILE) . '" value="' . esc_attr($font_post_mobile) . '" min="12" max="22" style="width:90px;"> px</td></tr>';
        echo '<tr><th scope="row">Pages (Desktop)</th><td><input type="number" name="' . esc_attr(self::OPT_FONT_PAGE_DESKTOP) . '" value="' . esc_attr($font_page_desktop) . '" min="12" max="22" style="width:90px;"> px</td></tr>';
        echo '<tr><th scope="row">Pages (Mobile)</th><td><input type="number" name="' . esc_attr(self::OPT_FONT_PAGE_MOBILE) . '" value="' . esc_attr($font_page_mobile) . '" min="12" max="22" style="width:90px;"> px</td></tr>';
        echo '</table>';

        echo '<h2>Desktop Left Offset</h2>';
        echo '<p class="description">Shifts the meta block right on desktop only (horizontal alignment, not vertical). Default is <strong>80px</strong>. If your content area starts at the left edge without padding, set this to 0 or match your theme\'s content left margin. Mobile is not affected.</p>';
        echo '<p><label><strong>Left offset (Desktop only):</strong> <input type="number" name="' . esc_attr(self::OPT_DESKTOP_LEFT_OFFSET) . '" value="' . esc_attr($desktop_left_offset) . '" min="0" max="240" style="width:90px;"> px</label></p>';

        echo '<h2>More About (Bio Accordion)</h2>';
        echo '<p><label><input type="checkbox" name="' . esc_attr(self::OPT_ENABLE_MORE_ABOUT) . '" value="1" ' . checked($more_about, true, false) . '> Enable the "More about {First Name}" pill (default OFF)</label></p>';
        echo '<p class="description">Bio text is pulled from each author\'s WordPress user profile (Biographical Info field).</p>';

        if (!$this->yoast_active) {
            echo '<h2>Schema Output</h2>';
            echo '<p><label><input type="checkbox" name="' . esc_attr(self::OPT_JSONLD_FALLBACK) . '" value="1" ' . checked($jsonld_fallback, true, false) . '> Emit JSON-LD in &lt;head&gt; when Yoast is not active</label></p>';
        } else {
            echo '<p><strong>Yoast SEO detected.</strong> This plugin injects <code>reviewedBy</code> into Yoast\'s Article graph (no duplicate Article schema).</p>';
        }

        submit_button('Save Settings');
        echo '</form></div>';
    }

    /* =========================================================
     * Yoast integration: reviewedBy
     * ========================================================= */
    public function yoast_article($data, $context) {
        if (!is_singular()) return $data;
        $pid = (int) get_the_ID();
        if (!$pid) return $data;
        if (!$this->meta_enabled_for($pid)) return $data;
        if ($this->meta_hide_reviewer_for($pid)) return $data;

        $r = $this->reviewer_data($pid);
        if (empty($r['id'])) return $data;

        $data['reviewedBy'] = array('@id' => $r['id']);
        return $data;
    }

    public function yoast_graph($graph, $context) {
        if (!is_singular()) return $graph;
        $pid = (int) get_the_ID();
        if (!$pid) return $graph;
        if (!$this->meta_enabled_for($pid)) return $graph;
        if ($this->meta_hide_reviewer_for($pid)) return $graph;

        $r = $this->reviewer_data($pid);
        if (empty($r['id'])) return $graph;

        $node = array(
            '@type' => ($r['type'] === 'Organization' ? 'Organization' : 'Person'),
            '@id'   => $r['id'],
            'name'  => $r['name'],
        );
        if (!empty($r['url'])) $node['url'] = $r['url'];
        if ($r['type'] !== 'Organization' && !empty($r['role'])) $node['jobTitle'] = $r['role'];
        if (!empty($r['nmls'])) {
            $node['identifier'] = array('@type' => 'PropertyValue', 'propertyID' => 'NMLS', 'value' => $r['nmls']);
        }

        // Update-or-append: if a node with this @id already exists, merge our fields onto it
        // (so fields stick even when another filter added a bare Person node first).
        $found = false;
        foreach ($graph as $i => $n) {
            if (isset($n['@id']) && $n['@id'] === $r['id']) {
                $graph[$i] = array_merge(is_array($n) ? $n : array(), $node);
                $found = true;
                break;
            }
        }
        if (!$found) {
            $graph[] = $node;
        }

        return $graph;
    }

    /* =========================================================
     * Fallback JSON-LD (only if Yoast not active)
     * ========================================================= */
    public function emit_jsonld_fallback() {
        if ($this->yoast_active) return;
        if (!is_singular()) return;
        if (!get_option(self::OPT_JSONLD_FALLBACK, true)) return;

        $pid = (int) get_the_ID();
        if (!$pid) return;
        if (!$this->meta_enabled_for($pid)) return;
        if ($this->meta_hide_reviewer_for($pid)) return;

        $r = $this->reviewer_data($pid);
        if (empty($r['id'])) return;

        $page       = get_permalink($pid);
        $article_id = trailingslashit($page) . '#article';
        $headline   = get_the_title($pid);
        $end        = get_post_modified_time('c', false, $pid);

        $reviewer_node = array(
            '@type' => ($r['type'] === 'Organization' ? 'Organization' : 'Person'),
            '@id'   => $r['id'],
            'name'  => $r['name'],
        );
        if (!empty($r['url'])) $reviewer_node['url'] = $r['url'];
        if ($r['type'] !== 'Organization' && !empty($r['role'])) $reviewer_node['jobTitle'] = $r['role'];
        if (!empty($r['nmls'])) {
            $reviewer_node['identifier'] = array('@type' => 'PropertyValue', 'propertyID' => 'NMLS', 'value' => $r['nmls']);
        }

        $graph = array(
            $reviewer_node,
            array(
                '@type'   => 'ReviewAction',
                'agent'   => array('@id' => $r['id']),
                'object'  => array('@type' => 'Article', '@id' => $article_id, 'headline' => $headline),
                'endTime' => $end,
            ),
            array(
                '@type'      => 'WebPage',
                '@id'        => trailingslashit($page),
                'reviewedBy' => array('@id' => $r['id']),
            ),
        );

        echo "\n<script type=\"application/ld+json\">" . wp_json_encode(array('@context' => 'https://schema.org', '@graph' => $graph), JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) . "</script>\n";
    }
}

new RSS_Meta_Header();
