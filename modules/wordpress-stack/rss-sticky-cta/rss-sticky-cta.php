<?php
/**
 * Plugin Name: RSS Sticky CTA Bar
 * Description: Fixed bottom bar with star rating, reviews ticker, and CTA button. Configurable via WP Admin → Sticky CTA.
 * Version: 1.0.0
 * Author: Randall's SEO System
 */

if ( is_admin() && ! wp_doing_ajax() ) {
    add_action('admin_menu', 'rss_sticky_cta_admin_menu');
    add_action('admin_post_rss_sticky_cta_save', 'rss_sticky_cta_handle_save');
    return;
}

if ( is_admin() ) { return; }

add_action('wp_footer', 'rss_sticky_cta_render', 99);
add_action('wp_enqueue_scripts', 'rss_sticky_cta_enqueue_deps');

function rss_sticky_cta_enqueue_deps() {
    $s = rss_sticky_cta_get_settings();
    if ( ! empty($s['ticker_shortcode']) && defined('RSS_REVIEWS_URL') ) {
        $v = defined('RSS_REVIEWS_VERS') ? RSS_REVIEWS_VERS : '1.0.0';
        wp_enqueue_style('rss-reviews-frontend', RSS_REVIEWS_URL . 'assets/frontend.css', [], $v);
        wp_enqueue_script('rss-reviews-frontend', RSS_REVIEWS_URL . 'assets/frontend.js', [], $v, true);
    }
}

function rss_sticky_cta_defaults() {
    return [
        'bar_bg'           => '#0b1e3a',
        'star_color'       => '#FBBF24',
        'accent_color'     => '#2F7BFF',
        'cta_bg'           => '#ffd500',
        'cta_text_color'   => '#00296b',
        'cta_url'          => '',
        'cta_label'        => 'Get Started',
        'reviews_url'      => '',
        'reviews_label'    => 'Read Our Reviews',
        'rating_value'     => '5.0',
        'rating_tagline'   => 'by our clients',
        'mobile_summary'   => 'Rated {rating} out of 5 stars',
        'ticker_shortcode' => '[rss_reviews_ticker interval="15" min_rating="5" length="275" show_source_link="false"]',
        'disclosure_text'  => '',
        'disclosure_urls'  => '/apply',
        'exclude_urls'     => '/confirmation',
        'show_after_scroll'=> 1,
    ];
}

function rss_sticky_cta_get_settings() {
    return array_merge(rss_sticky_cta_defaults(), (array) get_option('rss_sticky_cta', []));
}

function rss_sticky_cta_render() {
    $s = rss_sticky_cta_get_settings();
    $url = $_SERVER['REQUEST_URI'] ?? '';
    if ( ! is_string($url) ) $url = '';

    // Check exclusions
    $excludes = array_filter(array_map('trim', explode("\n", $s['exclude_urls'])));
    foreach ( $excludes as $pattern ) {
        if ( $pattern !== '' && strpos($url, $pattern) !== false ) return;
    }

    // Check disclosure mode
    $is_disclosure = false;
    $disc_urls = array_filter(array_map('trim', explode("\n", $s['disclosure_urls'])));
    foreach ( $disc_urls as $pattern ) {
        if ( $pattern !== '' && strpos($url, $pattern) !== false ) { $is_disclosure = true; break; }
    }

    // Build ticker HTML
    $ticker_html = '';
    if ( ! $is_disclosure && $s['ticker_shortcode'] && function_exists('do_shortcode') ) {
        $ticker_html = do_shortcode($s['ticker_shortcode']);
    }

    // Mobile summary with {rating} placeholder
    $mobile_text = str_replace('{rating}', esc_html($s['rating_value']), $s['mobile_summary']);

    $bar_bg       = esc_attr($s['bar_bg']);
    $star_color   = esc_attr($s['star_color']);
    $accent_color = esc_attr($s['accent_color']);
    $cta_bg       = esc_attr($s['cta_bg']);
    $cta_text     = esc_attr($s['cta_text_color']);
    $show_scroll  = ! empty($s['show_after_scroll']);
    ?>

<style>
body.rss-sticky-pad{
  padding-bottom: calc(var(--rssStickyH, 0px) + env(safe-area-inset-bottom, 0px)) !important;
}
.rssSticky, .rssSticky *{ box-sizing:border-box; }
.rssSticky{
  position:fixed; left:0; right:0; bottom:0; width:100%; z-index:999999;
  background:<?php echo $bar_bg; ?>; color:#fff; box-shadow:0 -10px 26px rgba(0,0,0,0.18); overflow:hidden;
}
.rssSticky__inner{
  max-width:1850px; margin:0 auto; padding:12px 14px; display:flex; align-items:center; gap:16px;
}

/* Rating block */
.rssRatingBlock{
  display:grid; grid-template-columns:auto 1fr; grid-template-rows:auto auto;
  column-gap:12px; row-gap:0; align-items:center; flex:0 0 auto; min-width:260px;
}
.rssRatingNum{ grid-row:1/span 2; font:900 54px/1 system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif; letter-spacing:-0.02em; }
.rssRatingTop{ grid-column:2; grid-row:1; font:800 14px/1.15 system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif; white-space:nowrap; }
.rssRatingSub{ grid-column:2; grid-row:2; font:700 12px/1 system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif; opacity:.92; margin-top:-2px; }
.rssAccent{ color:<?php echo $accent_color; ?> !important; }
.rssStars{ color:<?php echo $star_color; ?> !important; letter-spacing:3px; margin-left:6px; position:relative; top:-1px; }

/* Buttons */
.rssBtn{
  display:inline-flex; align-items:center; justify-content:center; height:34px; padding:0 14px;
  border-radius:999px; font:800 13px/1 system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
  text-decoration:none !important; white-space:nowrap;
}
.rssBtn--outline{ border:2px solid rgba(255,255,255,0.35); color:#fff !important; background:transparent; }
.rssBtn--cta{ background:<?php echo $cta_bg; ?>; color:<?php echo $cta_text; ?> !important; padding:0 18px; }

/* Ticker */
.rssTickerWrap{ flex:1 1 auto; min-width:0; }
.rssTickerWrap .tvln-ticker, .rssTickerWrap .tvln-ticker *{ color:#fff !important; }
.rssTickerWrap .tvln-ticker{ overflow:hidden !important; max-width:100% !important; background:transparent !important; }
.rssTickerWrap .tvln-ticker .name{ color:#fff !important; }
.rssTickerWrap .tvln-ticker-viewport{ overflow:hidden !important; width:100% !important; }
.rssTickerWrap .tvln-stars svg.star{ width:14px !important; height:14px !important; fill:<?php echo $star_color; ?> !important; }
.rssTickerWrap .snippet{ color:rgba(255,255,255,0.88) !important; }

/* Scroll reveal */
<?php if ( $show_scroll && ! $is_disclosure ) : ?>
#rssStickyBar{
  transform:translateY(120%); opacity:0; pointer-events:none;
  transition:transform .22s ease, opacity .22s ease;
}
#rssStickyBar.rss-visible{ transform:translateY(0); opacity:1; pointer-events:auto; }
<?php endif; ?>

/* Mobile */
.rssMobileView{ display:none; }
@media (max-width:767px){
  .rssDesktopView{ display:none !important; }
  .rssMobileView{ display:block; }
  .rssMobileView .rssSticky__inner{
    flex-direction:column; align-items:stretch; gap:10px; padding:6px 10px;
  }
  .rssMobileSummary{
    text-align:center; font:800 13px/1 system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
    white-space:nowrap;
  }
  .rssMobileSummary .rssStars{ color:<?php echo $star_color; ?> !important; letter-spacing:4px; margin-left:8px; top:0; }
  .rssMobileActions{ display:flex; gap:10px; }
  .rssMobileActions .rssBtn{ height:42px; flex:1 1 0; padding:0 10px; font-size:15px; }
}

/* Disclosure bar */
.rssDisclosure .rssSticky__inner{ justify-content:center; padding:10px 14px; }
.rssDisclosure p{ margin:0; text-align:center; font:600 11px/1.35 system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif; color:rgba(255,255,255,0.92); }
.rssDisclosure p strong{ font-weight:800; color:#fff; }
</style>

<?php if ( $is_disclosure && $s['disclosure_text'] ) : ?>
  <div id="rssStickyBar" class="rssSticky rssDisclosure" role="contentinfo" aria-label="Disclosure">
    <div class="rssSticky__inner">
      <p><?php echo wp_kses_post($s['disclosure_text']); ?></p>
    </div>
  </div>
  <script>
  (function(){
    var bar = document.getElementById('rssStickyBar');
    if(!bar) return;
    function pad(){ var h=Math.ceil(bar.getBoundingClientRect().height); document.body.style.setProperty('--rssStickyH',h+'px'); document.body.classList.add('rss-sticky-pad'); }
    window.addEventListener('load',pad,{once:true}); window.addEventListener('resize',pad);
    if(window.ResizeObserver) new ResizeObserver(pad).observe(bar);
    setTimeout(pad,60);
  })();
  </script>

<?php elseif ( ! $is_disclosure ) : ?>
  <div id="rssStickyBar" class="rssSticky" role="contentinfo" aria-label="Reviews and CTA">
    <div class="rssDesktopView">
      <div class="rssSticky__inner">
        <div class="rssRatingBlock">
          <div class="rssRatingNum"><?php echo esc_html($s['rating_value']); ?></div>
          <div class="rssRatingTop">See why we're rated <span class="rssAccent"><?php echo esc_html($s['rating_value']); ?> stars</span><span class="rssStars" aria-hidden="true">★★★★★</span></div>
          <div class="rssRatingSub"><?php echo esc_html($s['rating_tagline']); ?></div>
        </div>
        <?php if ( $s['reviews_url'] ) : ?>
          <a class="rssBtn rssBtn--outline" href="<?php echo esc_url(home_url($s['reviews_url'])); ?>"><?php echo esc_html($s['reviews_label']); ?></a>
        <?php endif; ?>
        <div class="rssTickerWrap"><?php echo $ticker_html; ?></div>
        <?php if ( $s['cta_url'] ) : ?>
          <a class="rssBtn rssBtn--cta" href="<?php echo esc_url(home_url($s['cta_url'])); ?>"><?php echo esc_html($s['cta_label']); ?></a>
        <?php endif; ?>
      </div>
    </div>
    <div class="rssMobileView">
      <div class="rssSticky__inner">
        <div class="rssMobileSummary"><?php echo wp_kses_post($mobile_text); ?> <span class="rssStars" aria-hidden="true">★★★★★</span></div>
        <div class="rssMobileActions">
          <?php if ( $s['cta_url'] ) : ?>
            <a class="rssBtn rssBtn--cta" href="<?php echo esc_url(home_url($s['cta_url'])); ?>"><?php echo esc_html($s['cta_label']); ?></a>
          <?php endif; ?>
          <?php if ( $s['reviews_url'] ) : ?>
            <a class="rssBtn rssBtn--outline" href="<?php echo esc_url(home_url($s['reviews_url'])); ?>"><?php echo esc_html($s['reviews_label']); ?></a>
          <?php endif; ?>
        </div>
      </div>
    </div>
  </div>

  <script>
  (function(){
    var bar = document.getElementById('rssStickyBar');
    if(!bar) return;
    var body = document.body;
    function setPad(px){ body.style.setProperty('--rssStickyH',px+'px'); if(px>0) body.classList.add('rss-sticky-pad'); else body.classList.remove('rss-sticky-pad'); }
    function h(){ return Math.ceil(bar.getBoundingClientRect().height); }
    function threshold(){ return Math.max(64, Math.round(window.innerHeight*0.10)); }
    <?php if ( $show_scroll ) : ?>
    function update(){ var show=window.scrollY>threshold(); bar.classList.toggle('rss-visible',show); setPad(show?h():0); }
    window.addEventListener('scroll',update,{passive:true});
    window.addEventListener('resize',update);
    if(window.ResizeObserver) new ResizeObserver(function(){ if(bar.classList.contains('rss-visible')) setPad(h()); }).observe(bar);
    update();
    <?php else : ?>
    function pad(){ setPad(h()); }
    window.addEventListener('load',pad,{once:true}); window.addEventListener('resize',pad);
    if(window.ResizeObserver) new ResizeObserver(pad).observe(bar);
    setTimeout(pad,60);
    <?php endif; ?>
  })();
  </script>
<?php endif; ?>
<?php
}

/* ===== Admin Settings Page ===== */

function rss_sticky_cta_admin_menu() {
    add_menu_page('Sticky CTA', 'Sticky CTA', 'manage_options', 'rss-sticky-cta', 'rss_sticky_cta_settings_page', 'dashicons-megaphone', 59);
}

function rss_sticky_cta_settings_page() {
    if ( ! current_user_can('manage_options') ) return;
    $s = rss_sticky_cta_get_settings();
    $saved = isset($_GET['rss_saved']);
    ?>
    <div class="wrap">
        <h1>Sticky CTA Bar Settings</h1>
        <?php if ($saved): ?><div class="notice notice-success is-dismissible"><p>Settings saved.</p></div><?php endif; ?>
        <form method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>">
            <?php wp_nonce_field('rss_sticky_cta_nonce'); ?>
            <input type="hidden" name="action" value="rss_sticky_cta_save"/>

            <h2 class="title">Rating Display</h2>
            <table class="form-table"><tbody>
                <tr><th><label for="rating_value">Rating</label></th><td><input type="text" id="rating_value" name="rating_value" value="<?php echo esc_attr($s['rating_value']); ?>" size="4"/></td></tr>
                <tr><th><label for="rating_tagline">Tagline</label></th><td><input type="text" id="rating_tagline" name="rating_tagline" value="<?php echo esc_attr($s['rating_tagline']); ?>" class="regular-text"/> <span class="description">e.g. "by our clients", "out of 5"</span></td></tr>
                <tr><th><label for="mobile_summary">Mobile summary</label></th><td><input type="text" id="mobile_summary" name="mobile_summary" value="<?php echo esc_attr($s['mobile_summary']); ?>" class="regular-text"/> <span class="description">Use {rating} as placeholder</span></td></tr>
            </tbody></table>

            <h2 class="title">Buttons</h2>
            <table class="form-table"><tbody>
                <tr><th><label for="cta_url">CTA URL</label></th><td><input type="text" id="cta_url" name="cta_url" value="<?php echo esc_attr($s['cta_url']); ?>" class="regular-text" placeholder="/apply/"/> <span class="description">Relative path. Leave blank to hide CTA button.</span></td></tr>
                <tr><th><label for="cta_label">CTA label</label></th><td><input type="text" id="cta_label" name="cta_label" value="<?php echo esc_attr($s['cta_label']); ?>" class="regular-text"/></td></tr>
                <tr><th><label for="reviews_url">Reviews URL</label></th><td><input type="text" id="reviews_url" name="reviews_url" value="<?php echo esc_attr($s['reviews_url']); ?>" class="regular-text" placeholder="/reviews/"/> <span class="description">Relative path. Leave blank to hide.</span></td></tr>
                <tr><th><label for="reviews_label">Reviews label</label></th><td><input type="text" id="reviews_label" name="reviews_label" value="<?php echo esc_attr($s['reviews_label']); ?>" class="regular-text"/></td></tr>
            </tbody></table>

            <h2 class="title">Colors</h2>
            <table class="form-table"><tbody>
                <tr><th><label for="bar_bg">Bar background</label></th><td><input type="text" id="bar_bg" name="bar_bg" value="<?php echo esc_attr($s['bar_bg']); ?>" size="8"/></td></tr>
                <tr><th><label for="accent_color">Accent</label></th><td><input type="text" id="accent_color" name="accent_color" value="<?php echo esc_attr($s['accent_color']); ?>" size="8"/></td></tr>
                <tr><th><label for="star_color">Stars</label></th><td><input type="text" id="star_color" name="star_color" value="<?php echo esc_attr($s['star_color']); ?>" size="8"/></td></tr>
                <tr><th><label for="cta_bg">CTA button bg</label></th><td><input type="text" id="cta_bg" name="cta_bg" value="<?php echo esc_attr($s['cta_bg']); ?>" size="8"/></td></tr>
                <tr><th><label for="cta_text_color">CTA button text</label></th><td><input type="text" id="cta_text_color" name="cta_text_color" value="<?php echo esc_attr($s['cta_text_color']); ?>" size="8"/></td></tr>
            </tbody></table>

            <h2 class="title">Ticker</h2>
            <table class="form-table"><tbody>
                <tr><th><label for="ticker_shortcode">Ticker shortcode</label></th><td><input type="text" id="ticker_shortcode" name="ticker_shortcode" value="<?php echo esc_attr($s['ticker_shortcode']); ?>" class="large-text"/> <span class="description">Leave blank to hide ticker. Requires RSS Google Reviews plugin.</span></td></tr>
            </tbody></table>

            <h2 class="title">Behavior</h2>
            <table class="form-table"><tbody>
                <tr><th>Show after scroll</th><td><label><input type="checkbox" name="show_after_scroll" value="1" <?php checked(!empty($s['show_after_scroll'])); ?>/> Bar slides up after user scrolls 10% of viewport</label></td></tr>
                <tr><th><label for="exclude_urls">Hidden on URLs containing</label></th><td><textarea id="exclude_urls" name="exclude_urls" rows="3" class="regular-text"><?php echo esc_textarea($s['exclude_urls']); ?></textarea><br/><span class="description">One pattern per line. Bar won't render on matching URLs.</span></td></tr>
            </tbody></table>

            <h2 class="title">Disclosure Mode</h2>
            <table class="form-table"><tbody>
                <tr><th><label for="disclosure_urls">Show disclosure on URLs containing</label></th><td><textarea id="disclosure_urls" name="disclosure_urls" rows="3" class="regular-text"><?php echo esc_textarea($s['disclosure_urls']); ?></textarea><br/><span class="description">One pattern per line. These pages show the disclosure bar instead of the full bar.</span></td></tr>
                <tr><th><label for="disclosure_text">Disclosure text</label></th><td><textarea id="disclosure_text" name="disclosure_text" rows="3" class="large-text"><?php echo esc_textarea($s['disclosure_text']); ?></textarea><br/><span class="description">HTML allowed. Use &lt;strong&gt; for emphasis.</span></td></tr>
            </tbody></table>

            <p class="submit"><button type="submit" class="button button-primary">Save Settings</button></p>
        </form>
    </div>
    <?php
}

function rss_sticky_cta_handle_save() {
    if ( ! current_user_can('manage_options') || ! check_admin_referer('rss_sticky_cta_nonce') ) wp_die('Unauthorized');

    $fields = ['bar_bg','star_color','accent_color','cta_bg','cta_text_color','cta_url','cta_label',
               'reviews_url','reviews_label','rating_value','rating_tagline','mobile_summary','ticker_shortcode'];

    $settings = [];
    foreach ( $fields as $f ) {
        $settings[$f] = sanitize_text_field($_POST[$f] ?? '');
    }
    $settings['disclosure_text']   = wp_kses_post($_POST['disclosure_text'] ?? '');
    $settings['disclosure_urls']   = sanitize_textarea_field($_POST['disclosure_urls'] ?? '');
    $settings['exclude_urls']      = sanitize_textarea_field($_POST['exclude_urls'] ?? '');
    $settings['show_after_scroll'] = ! empty($_POST['show_after_scroll']) ? 1 : 0;

    update_option('rss_sticky_cta', $settings);
    wp_redirect(admin_url('admin.php?page=rss-sticky-cta&rss_saved=1'));
    exit;
}
