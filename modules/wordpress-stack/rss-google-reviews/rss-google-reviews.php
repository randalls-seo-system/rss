<?php
/**
 * Plugin Name: RSS Google Reviews
 * Description: Google reviews widget with slider, compact slider, full list, ticker, and Google Places API sync. Part of the RSS standard WordPress stack.
 * Version: 1.0.0
 * Author: Randall's SEO System
 * License: GPLv2 or later
 * Text Domain: rss-google-reviews
 */

if (!defined('ABSPATH')) { exit; }

define('RSS_REVIEWS_VERS', '1.0.0');
define('RSS_REVIEWS_URL', plugin_dir_url(__FILE__));
define('RSS_REVIEWS_PATH', plugin_dir_path(__FILE__));

class RSS_Google_Reviews {
    const OPT_BUSINESS = 'rss_reviews_business';
    const OPT_REVIEWS  = 'rss_reviews_list';
    const OPT_GOOGLE   = 'rss_reviews_google';
    const OPT_TICKER   = 'rss_reviews_ticker';
    const NONCE        = 'rss_reviews_nonce';
    const CRON_HOOK    = 'rss_reviews_google_sync';

    public function __construct() {
        add_action('init', [$this, 'register_shortcodes']);
        add_action('admin_menu', [$this, 'admin_menu']);
        add_action('admin_enqueue_scripts', [$this, 'admin_assets']);
        add_action('wp_enqueue_scripts', [$this, 'maybe_enqueue_frontend']);
        add_action('admin_post_rss_reviews_save_all', [$this, 'handle_save_all']);
        add_action('admin_post_rss_reviews_sync_now', [$this, 'handle_sync_now']);
        add_action(self::CRON_HOOK, [$this, 'cron_google_sync']);
        register_activation_hook(__FILE__, [__CLASS__, 'on_activate']);
        register_deactivation_hook(__FILE__, [__CLASS__, 'on_deactivate']);
    }

    public static function defaults_business() {
        return [
            'name'         => get_bloginfo('name'),
            'address'      => '',
            'rating_value' => '5.0',
            'review_count' => '0',
            'accent'       => '#D4AF37',
            'bg'           => '#ffffff',
            'text'         => '#0F172A',
            'navy'         => '#0B1F44',
            'compact_gap'  => 10,
            'compact_lines'=> 6,
            'more_behavior'=> 'modal', // 'expand' or 'modal'
        ];
    }
    public static function defaults_ticker() { return ['interval' => 8, 'length'=>180]; }
    public static function defaults_google() { return ['place_id'=>'','api_key'=>'','auto_sync'=>0,'last_sync'=>'','last_result'=>'']; }
    public static function defaults_reviews() {
        return [];
    }

    public static function on_activate() {
        if (get_option(self::OPT_BUSINESS, null) === null) add_option(self::OPT_BUSINESS, self::defaults_business());
        if (get_option(self::OPT_REVIEWS, null) === null)  add_option(self::OPT_REVIEWS, self::defaults_reviews());
        if (get_option(self::OPT_GOOGLE, null) === null)   add_option(self::OPT_GOOGLE, self::defaults_google());
        if (get_option(self::OPT_TICKER, null) === null)   add_option(self::OPT_TICKER, self::defaults_ticker());
    }
    public static function on_deactivate() {
        $timestamp = wp_next_scheduled(self::CRON_HOOK);
        if ($timestamp) wp_unschedule_event($timestamp, self::CRON_HOOK);
    }

    public function admin_assets($hook) {
        if (strpos($hook, 'rss-google-reviews') === false) return;
        wp_enqueue_style('wp-color-picker');
        wp_enqueue_script('wp-color-picker');
        wp_enqueue_media();
        wp_enqueue_style('rss-reviews-admin', RSS_REVIEWS_URL . 'assets/admin.css', [], RSS_REVIEWS_VERS);
        wp_enqueue_script('rss-reviews-admin', RSS_REVIEWS_URL . 'assets/admin.js', ['jquery','wp-color-picker'], RSS_REVIEWS_VERS, true);
    }
    public function maybe_enqueue_frontend() {
        if (is_admin()) return;
        global $post;
        $enqueue = false;
        $shortcodes = ['rss_reviews','rss_reviews_list','rss_reviews_both','rss_reviews_compact','rss_reviews_ticker','tvln_reviews','va_reviews','tvln_reviews_list','tvln_reviews_both','tvln_reviews_compact','tvln_reviews_ticker'];
        if ($post && is_a($post, 'WP_Post')) {
            foreach ($shortcodes as $sc) {
                if (has_shortcode($post->post_content, $sc)) { $enqueue = true; break; }
            }
        }
        if (!$enqueue) {
            add_filter('the_content', function($content) use ($shortcodes, &$enqueue){
                foreach ($shortcodes as $sc) { if (strpos($content, $sc) !== false) { $enqueue=true; break; } }
                if ($enqueue) {
                    wp_enqueue_style('rss-reviews-frontend', RSS_REVIEWS_URL . 'assets/frontend.css', [], RSS_REVIEWS_VERS);
                    wp_enqueue_script('rss-reviews-frontend', RSS_REVIEWS_URL . 'assets/frontend.js', [], RSS_REVIEWS_VERS, true);
                }
                return $content;
            }, 1);
        } else {
            wp_enqueue_style('rss-reviews-frontend', RSS_REVIEWS_URL . 'assets/frontend.css', [], RSS_REVIEWS_VERS);
            wp_enqueue_script('rss-reviews-frontend', RSS_REVIEWS_URL . 'assets/frontend.js', [], RSS_REVIEWS_VERS, true);
        }
    }

    public function admin_menu() {
        add_menu_page(__('Google Reviews','rss-google-reviews'),__('Google Reviews','rss-google-reviews'),'manage_options','rss-google-reviews',[$this,'render_settings_page'],'dashicons-star-filled',58);
    }
    public function render_settings_page() {
        if (!current_user_can('manage_options')) return;
        $business = get_option(self::OPT_BUSINESS, self::defaults_business());
        $reviews  = get_option(self::OPT_REVIEWS, self::defaults_reviews());
        $google   = get_option(self::OPT_GOOGLE, self::defaults_google());
        $ticker   = get_option(self::OPT_TICKER, self::defaults_ticker());
        $saved = isset($_GET['rss_reviews_saved']) ? sanitize_text_field($_GET['rss_reviews_saved']) : '';
        $synced = isset($_GET['rss_reviews_synced']) ? sanitize_text_field($_GET['rss_reviews_synced']) : '';
        ?>
        <div class="wrap tvln-wrap">
            <h1>Google Reviews</h1>
            <?php if ($saved): ?><div class="notice notice-success is-dismissible"><p>Settings saved.</p></div><?php endif; ?>
            <?php if ($synced): ?><div class="notice notice-info is-dismissible"><p><?php echo esc_html($synced); ?></p></div><?php endif; ?>
            <p>Shortcodes: <code>[rss_reviews]</code>, <code>[rss_reviews_compact]</code>, <code>[rss_reviews_list]</code>, <code>[rss_reviews_both]</code>, <code>[rss_reviews_ticker interval="8" min_rating="5" length="200" show_source_link="true"]</code>. Legacy aliases: <code>[tvln_reviews]</code>, <code>[va_reviews]</code>, etc.</p>

            <form method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>">
              <?php wp_nonce_field(self::NONCE, 'rss_reviews_nonce'); ?>
              <input type="hidden" name="action" value="rss_reviews_save_all"/>

              <h2 class="title">Business & Style</h2>
              <table class="form-table" role="presentation"><tbody>
                <tr><th><label for="rss_rev_name">Name</label></th><td><input type="text" class="regular-text" id="rss_rev_name" name="business[name]" value="<?php echo esc_attr($business['name']); ?>" /></td></tr>
                <tr><th><label for="rss_rev_addr">Address</label></th><td><input type="text" class="regular-text" id="rss_rev_addr" name="business[address]" value="<?php echo esc_attr($business['address']); ?>" /></td></tr>
                <tr><th><label for="rss_rev_rating">Overall Rating</label></th><td><input type="text" id="rss_rev_rating" name="business[rating_value]" value="<?php echo esc_attr($business['rating_value']); ?>" size="4" /></td></tr>
                <tr><th><label for="rss_rev_count">Review Count</label></th><td><input type="number" id="rss_rev_count" name="business[review_count]" value="<?php echo esc_attr($business['review_count']); ?>" min="0" step="1" /></td></tr>
                <tr><th><label for="rss_rev_accent">Accent (stars)</label></th><td><input type="text" id="rss_rev_accent" class="tvln-color" name="business[accent]" value="<?php echo esc_attr($business['accent']); ?>" /></td></tr>
                <tr><th><label for="rss_rev_bg">Slider/List Background</label></th><td><input type="text" id="rss_rev_bg" class="tvln-color" name="business[bg]" value="<?php echo esc_attr($business['bg']); ?>" /> <span class="description">Use a hex color or type <code>transparent</code>.</span></td></tr>
                <tr><th><label for="rss_rev_text">Text Color</label></th><td><input type="text" id="rss_rev_text" class="tvln-color" name="business[text]" value="<?php echo esc_attr($business['text']); ?>" /></td></tr>
                <tr><th><label for="rss_rev_navy">Navy (buttons/borders)</label></th><td><input type="text" id="rss_rev_navy" class="tvln-color" name="business[navy]" value="<?php echo esc_attr($business['navy']); ?>" /></td></tr>
                <tr><th><label for="rss_rev_gap">Compact "Read more" gap (px)</label></th><td><input type="number" min="0" max="40" step="1" id="rss_rev_gap" name="business[compact_gap]" value="<?php echo esc_attr($business['compact_gap'] ?? 10); ?>" /></td></tr>
                <tr><th><label for="rss_rev_lines">Compact lines (before Read more)</label></th><td><input type="number" min="3" max="12" step="1" id="rss_rev_lines" name="business[compact_lines]" value="<?php echo esc_attr($business['compact_lines'] ?? 6); ?>" /></td></tr>
                <tr><th><label for="rss_rev_more">"Read more" opens</label></th><td>
                    <select id="rss_rev_more" name="business[more_behavior]">
                        <?php $mb = $business['more_behavior'] ?? 'modal'; ?>
                        <option value="expand" <?php selected($mb, 'expand'); ?>>Expand in card</option>
                        <option value="modal" <?php selected($mb, 'modal'); ?>>Popup modal</option>
                    </select>
                </td></tr>
              </tbody></table>

              <h2 class="title" style="margin-top:24px;">Reviews</h2>
              <p class="description">Optional fields: Badge, Avatar URL, Author URL (Google link), When (e.g., "a month ago"), “Ticker text (optional)” for the ultra‑thin slider, and “Show in thin ticker”.</p>
              <div id="tvln-reviews-list">
                <?php foreach ($reviews as $i => $r): $in_ticker = !empty($r['in_ticker']); ?>
                  <div class="tvln-review-row" data-index="<?php echo intval($i); ?>">
                    <div class="tvln-review-row__header"><strong>Review #<?php echo intval($i+1); ?></strong><button type="button" class="button-link-delete tvln-remove-review">Remove</button></div>
                    <div class="tvln-grid">
                      <p><label>Name<br/><input type="text" name="reviews[<?php echo intval($i); ?>][name]" value="<?php echo esc_attr($r['name'] ?? ''); ?>" /></label></p>
                      <p><label>Meta<br/><input type="text" name="reviews[<?php echo intval($i); ?>][meta]" value="<?php echo esc_attr($r['meta'] ?? ''); ?>" /></label></p>
                      <p><label>When (date left)<br/><input type="text" name="reviews[<?php echo intval($i); ?>][when]" value="<?php echo esc_attr($r['when'] ?? ''); ?>" placeholder="e.g., a month ago" /></label></p>
                      <p><label>Rating<br/><select name="reviews[<?php echo intval($i); ?>][rating]"><?php for($k=5;$k>=1;$k--): ?><option value="<?php echo $k; ?>" <?php selected(intval($r['rating'] ?? 5), $k); ?>><?php echo $k; ?></option><?php endfor; ?></select></label></p>
                    </div>
                    <div class="tvln-grid">
                      <p><label>Badge (optional)<br/><input type="text" name="reviews[<?php echo intval($i); ?>][badge]" value="<?php echo esc_attr($r['badge'] ?? ''); ?>" /></label></p>
                      <p><label>Avatar URL (optional)<br/><input type="url" name="reviews[<?php echo intval($i); ?>][avatar]" value="<?php echo esc_attr($r['avatar'] ?? ''); ?>" /></label></p>
                      <p><label>Author URL (optional)<br/><input type="url" name="reviews[<?php echo intval($i); ?>][author_url]" value="<?php echo esc_attr($r['author_url'] ?? ''); ?>" /></label></p>
                      <p><label><input type="checkbox" name="reviews[<?php echo intval($i); ?>][in_ticker]" value="1" <?php checked($in_ticker); ?>/> Show in thin ticker</label></p>
                    </div>
                    <p><label>Review text<br/><textarea name="reviews[<?php echo intval($i); ?>][body]" rows="5" class="large-text"><?php echo esc_textarea($r['body'] ?? ''); ?></textarea></label></p>
                    <p><label>Ticker text (optional, overrides length trim)<br/><textarea name="reviews[<?php echo intval($i); ?>][ticker_text]" rows="2" class="large-text"><?php echo esc_textarea($r['ticker_text'] ?? ''); ?></textarea></label></p>
                    <hr/>
                  </div>
                <?php endforeach; ?>
              </div>
              <p><button type="button" class="button button-secondary" id="tvln-add-review">Add Review</button></p>

              <h2 class="title" style="margin-top:24px;">Ticker Settings</h2>
              <table class="form-table" role="presentation"><tbody>
                <tr><th><label for="rss_rev_ticker_int">Default interval (seconds)</label></th>
                <td><input type="number" min="2" step="1" id="rss_rev_ticker_int" name="ticker[interval]" value="<?php echo esc_attr($ticker['interval']); ?>" /></td></tr>
                <tr><th><label for="rss_rev_ticker_len">Default snippet length (characters)</label></th>
                <td><input type="number" min="60" step="10" id="rss_rev_ticker_len" name="ticker[length]" value="<?php echo esc_attr($ticker['length']); ?>" /></td></tr>
              </tbody></table>

              <h2 class="title" style="margin-top:24px;">Google Sync (optional)</h2>
              <table class="form-table" role="presentation"><tbody>
                <tr><th><label for="rss_rev_place">Place ID</label></th><td><input type="text" class="regular-text" id="rss_rev_place" name="google[place_id]" value="<?php echo esc_attr($google['place_id']); ?>" /></td></tr>
                <tr><th><label for="rss_rev_api_key">API Key</label></th><td><input type="text" class="regular-text" id="rss_rev_api_key" name="google[api_key]" value="<?php echo esc_attr($google['api_key']); ?>" /><p class="description">Places API key (returns up to 5 latest reviews).</p></td></tr>
                <tr><th>Auto Sync Daily</th><td><label><input type="checkbox" name="google[auto_sync]" value="1" <?php checked(!empty($google['auto_sync'])); ?>/> Enable</label><p><a class="button" href="<?php echo esc_url( wp_nonce_url( admin_url('admin-post.php?action=rss_reviews_sync_now'), self::NONCE ) ); ?>">Sync Now</a></p></td></tr>
              </tbody></table>

              <p class="submit"><button type="submit" class="button button-primary">Save Changes</button></p>
            </form>

            <script type="text/template" id="tvln-review-row-template">
              <div class="tvln-review-row" data-index="{{INDEX}}">
                <div class="tvln-review-row__header"><strong>Review #{{NUM}}</strong><button type="button" class="button-link-delete tvln-remove-review">Remove</button></div>
                <div class="tvln-grid">
                  <p><label>Name<br/><input type="text" name="reviews[{{INDEX}}][name]" value="" /></label></p>
                  <p><label>Meta<br/><input type="text" name="reviews[{{INDEX}}][meta]" value="" /></label></p>
                  <p><label>When (date left)<br/><input type="text" name="reviews[{{INDEX}}][when]" value="" placeholder="e.g., a month ago" /></label></p>
                  <p><label>Rating<br/>
                    <select name="reviews[{{INDEX}}][rating]">
                      <option value="5" selected>5</option>
                      <option value="4">4</option>
                      <option value="3">3</option>
                      <option value="2">2</option>
                      <option value="1">1</option>
                    </select>
                  </label></p>
                </div>
                <div class="tvln-grid">
                  <p><label>Badge (optional)<br/><input type="text" name="reviews[{{INDEX}}][badge]" value="" placeholder="New" /></label></p>
                  <p><label>Avatar URL (optional)<br/><input type="url" name="reviews[{{INDEX}}][avatar]" value="" /></label></p>
                  <p><label>Author URL (optional)<br/><input type="url" name="reviews[{{INDEX}}][author_url]" value="" /></label></p>
                  <p><label><input type="checkbox" name="reviews[{{INDEX}}][in_ticker]" value="1" /> Show in thin ticker</label></p>
                </div>
                <p><label>Review text<br/><textarea name="reviews[{{INDEX}}][body]" rows="5" class="large-text"></textarea></label></p>
                <p><label>Ticker text (optional, overrides length trim)<br/><textarea name="reviews[{{INDEX}}][ticker_text]" rows="2" class="large-text"></textarea></label></p>
                <hr/>
              </div>
            </script>
        </div>
        <?php
    }

    public function handle_save_all() {
        if (!current_user_can('manage_options') || !isset($_POST['rss_reviews_nonce']) || !wp_verify_nonce($_POST['rss_reviews_nonce'], self::NONCE)) { wp_die('Unauthorized'); }
        $business = [
            'name' => sanitize_text_field($_POST['business']['name'] ?? ''),
            'address' => sanitize_text_field($_POST['business']['address'] ?? ''),
            'rating_value' => sanitize_text_field($_POST['business']['rating_value'] ?? '5.0'),
            'review_count' => sanitize_text_field($_POST['business']['review_count'] ?? '0'),
            'accent' => sanitize_text_field($_POST['business']['accent'] ?? '#D4AF37'),
            'bg' => sanitize_text_field($_POST['business']['bg'] ?? '#ffffff'),
            'text' => sanitize_text_field($_POST['business']['text'] ?? '#0F172A'),
            'navy' => sanitize_text_field($_POST['business']['navy'] ?? '#0B1F44'),
            'compact_gap' => max(0, intval($_POST['business']['compact_gap'] ?? 10)),
            'compact_lines' => max(3, min(12, intval($_POST['business']['compact_lines'] ?? 6))),
            'more_behavior' => in_array(($_POST['business']['more_behavior'] ?? 'modal'), ['expand','modal'], true) ? $_POST['business']['more_behavior'] : 'modal',
        ];
        update_option(self::OPT_BUSINESS, $business);

        $reviews = [];
        if (!empty($_POST['reviews']) && is_array($_POST['reviews'])) {
            foreach ($_POST['reviews'] as $rev) {
                if (empty($rev['name']) && empty($rev['body'])) continue;
                $reviews[] = [
                    'name' => sanitize_text_field($rev['name'] ?? ''),
                    'meta' => sanitize_text_field($rev['meta'] ?? ''),
                    'when' => sanitize_text_field($rev['when'] ?? ''),
                    'badge'=> sanitize_text_field($rev['badge'] ?? ''),
                    'rating'=> max(1, min(5, intval($rev['rating'] ?? 5))),
                    'avatar'=> esc_url_raw($rev['avatar'] ?? ''),
                    'author_url'=> esc_url_raw($rev['author_url'] ?? ''),
                    'body' => sanitize_textarea_field($rev['body'] ?? ''),
                    'ticker_text' => sanitize_textarea_field($rev['ticker_text'] ?? ''),
                    'source' => sanitize_text_field($rev['source'] ?? 'manual'),
                    'source_id' => sanitize_text_field($rev['source_id'] ?? ''),
                    'in_ticker' => !empty($rev['in_ticker']) ? 1 : 0,
                ];
            }
        }
        update_option(self::OPT_REVIEWS, $reviews);

        $ticker = [ 
            'interval' => max(2, intval($_POST['ticker']['interval'] ?? self::defaults_ticker()['interval'])),
            'length' => max(60, intval($_POST['ticker']['length'] ?? self::defaults_ticker()['length'])),
        ];
        update_option(self::OPT_TICKER, $ticker);

        $prevGoogle = get_option(self::OPT_GOOGLE, self::defaults_google());
        $google = [
            'place_id' => sanitize_text_field($_POST['google']['place_id'] ?? ''),
            'api_key' => sanitize_text_field($_POST['google']['api_key'] ?? ''),
            'auto_sync' => !empty($_POST['google']['auto_sync']) ? 1 : 0,
            'last_sync' => $prevGoogle['last_sync'] ?? '',
            'last_result' => $prevGoogle['last_result'] ?? '',
        ];
        update_option(self::OPT_GOOGLE, $google);

        $is_scheduled = wp_next_scheduled(self::CRON_HOOK);
        if (!empty($google['auto_sync']) && !$is_scheduled) {
            wp_schedule_event(time() + 60, 'daily', self::CRON_HOOK);
        } elseif (empty($google['auto_sync']) && $is_scheduled) {
            $timestamp = wp_next_scheduled(self::CRON_HOOK);
            if ($timestamp) wp_unschedule_event($timestamp, self::CRON_HOOK);
        }

        wp_redirect(admin_url('admin.php?page=tvln-reviews&rss_reviews_saved=1'));
        exit;
    }

    public function handle_sync_now() {
        if (!current_user_can('manage_options') || !check_admin_referer(self::NONCE)) wp_die('Unauthorized');
        $msg = $this->google_sync(true);
        wp_redirect(admin_url('admin.php?page=tvln-reviews&rss_reviews_synced=' . urlencode($msg)));
        exit;
    }
    public function cron_google_sync() { $this->google_sync(false); }
    private function google_sync($manual=false) {
        $opts = get_option(self::OPT_GOOGLE, self::defaults_google());
        $place_id = trim($opts['place_id'] ?? ''); $api_key  = trim($opts['api_key'] ?? '');
        if (empty($place_id) || empty($api_key)) return 'Google sync skipped (missing Place ID or API Key).';
        $url = add_query_arg([ 'place_id'=>$place_id, 'fields'=>'name,rating,user_ratings_total,url,reviews', 'key'=>$api_key ], 'https://maps.googleapis.com/maps/api/place/details/json');
        $resp = wp_remote_get($url, ['timeout'=>15]);
        if (is_wp_error($resp)) { $msg='Google sync failed: '.$resp->get_error_message(); $opts['last_sync']=current_time('mysql'); $opts['last_result']=$msg; update_option(self::OPT_GOOGLE,$opts); return $msg; }
        $data = json_decode(wp_remote_retrieve_body($resp), true);
        if (!$data || ($data['status'] ?? '') !== 'OK') { $msg='Google sync failed: invalid response'; $opts['last_sync']=current_time('mysql'); $opts['last_result']=$msg; update_option(self::OPT_GOOGLE,$opts); return $msg; }
        $result = $data['result'] ?? []; $g_reviews = $result['reviews'] ?? []; $imported = 0;
        $existing = get_option(self::OPT_REVIEWS, []); $existing_ids = [];
        foreach ($existing as $er) { if (!empty($er['source']) && !empty($er['source_id'])) $existing_ids[$er['source'].':'.$er['source_id']] = true; }
        foreach ($g_reviews as $gr) {
            $rid = isset($gr['time']) ? (string)$gr['time'] : substr(md5(($gr['author_name'] ?? '').($gr['text'] ?? '')),0,12);
            $key = 'google:'.$rid; if (isset($existing_ids[$key])) continue;
            $existing[] = [
                'name'=>sanitize_text_field($gr['author_name'] ?? 'Google User'),
                'meta'=>sanitize_text_field(($gr['relative_time_description'] ?? '').' · via Google'),
                'when'=>sanitize_text_field($gr['relative_time_description'] ?? ''),
                'badge'=>'','rating'=>max(1,min(5,intval($gr['rating'] ?? 5))),
                'avatar'=>esc_url_raw($gr['profile_photo_url'] ?? ''),
                'author_url'=>esc_url_raw($gr['author_url'] ?? ''),
                'body'=>sanitize_textarea_field($gr['text'] ?? ''),
                'ticker_text'=>'',
                'source'=>'google','source_id'=>$rid,
                'in_ticker'=>0
            ];
            $existing_ids[$key] = true; $imported++;
        }
        update_option(self::OPT_REVIEWS, $existing);
        $biz = get_option(self::OPT_BUSINESS, self::defaults_business());
        if (!empty($result['rating'])) $biz['rating_value'] = (string)$result['rating'];
        if (!empty($result['user_ratings_total'])) $biz['review_count'] = (string)$result['user_ratings_total'];
        update_option(self::OPT_BUSINESS, $biz);
        $msg = "Google sync complete: imported {$imported} review(s).";
        $opts['last_sync'] = current_time('mysql'); $opts['last_result'] = $msg; update_option(self::OPT_GOOGLE,$opts);
        return $msg;
    }

    public function register_shortcodes() {
        add_shortcode('rss_reviews', [$this, 'shortcode_slider']);
        add_shortcode('rss_reviews_list', [$this, 'shortcode_list']);
        add_shortcode('rss_reviews_both', [$this, 'shortcode_both']);
        add_shortcode('rss_reviews_compact', [$this, 'shortcode_compact']);
        add_shortcode('rss_reviews_ticker', [$this, 'shortcode_ticker']);
        // Backward-compatible aliases
        add_shortcode('tvln_reviews', [$this, 'shortcode_slider']);
        add_shortcode('va_reviews',   [$this, 'shortcode_slider']);
        add_shortcode('tvln_reviews_list', [$this, 'shortcode_list']);
        add_shortcode('tvln_reviews_both', [$this, 'shortcode_both']);
        add_shortcode('tvln_reviews_compact', [$this, 'shortcode_compact']);
        add_shortcode('tvln_reviews_ticker', [$this, 'shortcode_ticker']);
    }
    private function get_business_and_reviews() {
        $business = get_option(self::OPT_BUSINESS, self::defaults_business());
        $reviews  = get_option(self::OPT_REVIEWS,  self::defaults_reviews());
        return [$business, $reviews];
    }
    public function shortcode_both($atts=[]) { return $this->shortcode_slider($atts) . $this->shortcode_list($atts); }
    public function shortcode_slider($atts=[]) {
        list($business, $reviews) = $this->get_business_and_reviews();
        $accent = $business['accent'] ?? '#D4AF37'; $interval = !empty($atts['interval']) ? intval($atts['interval']) : 10000;
        $bg = $business['bg'] ?? '#ffffff'; $text = $business['text'] ?? '#0F172A';
        ob_start(); ?>
        <section class="tvln-module" style="--tvln-accent: <?php echo esc_attr($accent); ?>; --tvln-bg: <?php echo esc_attr($bg); ?>; --tvln-text: <?php echo esc_attr($text); ?>;" data-interval="<?php echo esc_attr($interval); ?>" aria-label="Customer reviews slider">
            <?php echo $this->render_header($business); ?>
            <?php echo $this->render_slider($reviews); ?>
        </section>
        <?php return ob_get_clean();
    }
    public function shortcode_compact($atts=[]) {
        list($business, $reviews) = $this->get_business_and_reviews();
        $accent = $business['accent'] ?? '#D4AF37'; $interval = !empty($atts['interval']) ? intval($atts['interval']) : 10000;
        $bg = $business['bg'] ?? '#ffffff'; $text = $business['text'] ?? '#0F172A';
        $mb = $business['more_behavior'] ?? 'modal'; $lines = intval($business['compact_lines'] ?? 6);
        ob_start(); ?>
        <section class="tvln-module tvln-compact" style="--tvln-accent: <?php echo esc_attr($accent); ?>; --tvln-bg: <?php echo esc_attr($bg); ?>; --tvln-text: <?php echo esc_attr($text); ?>; --tvln-navy: <?php echo esc_attr($business['navy'] ?? '#0B1F44'); ?>; --tvln-gap: <?php echo esc_attr(intval($business['compact_gap'] ?? 10)); ?>px; --tvln-lines: <?php echo esc_attr($lines); ?>;" data-interval="<?php echo esc_attr($interval); ?>" data-more="<?php echo esc_attr($mb); ?>" aria-label="Compact reviews slider">
            <?php echo $this->render_header($business); ?>
            <?php echo $this->render_slider($reviews, true); ?>
        </section>
        <?php return ob_get_clean();
    }
    public function shortcode_list($atts=[]) {
        list($business, $reviews) = $this->get_business_and_reviews();
        $accent = $business['accent'] ?? '#D4AF37'; $bg = $business['bg'] ?? '#ffffff'; $text = $business['text'] ?? '#0F172A';
        return $this->render_list($reviews, $accent, $bg, $text, $business['navy'] ?? '#0B1F44');
    }
    public function shortcode_ticker($atts=[]) {
        list($business, $reviews) = $this->get_business_and_reviews();
        $ticker = get_option(self::OPT_TICKER, self::defaults_ticker());
        $args = shortcode_atts([
            'interval' => '',
            'min_rating' => '',
            'show_source_link' => '',
            'length' => '',
        ], $atts, 'rss_reviews_ticker');
        $interval = $args['interval'] !== '' ? max(2, intval($args['interval'])) : max(2, intval($ticker['interval'] ?? 8));
        $min_rating = $args['min_rating'] !== '' ? max(1, min(5, intval($args['min_rating']))) : 0;
        $show_source_link = ($args['show_source_link'] === 'true' || $args['show_source_link'] === '1');
        $length = $args['length'] !== '' ? max(60, intval($args['length'])) : max(60, intval($ticker['length'] ?? 180));
        $accent = $business['accent'] ?? '#D4AF37'; $bg = $business['bg'] ?? '#ffffff'; $text = $business['text'] ?? '#0F172A';

        $selected = array_values(array_filter($reviews, function($r){ return !empty($r['in_ticker']); }));
        if (!empty($selected)) $reviews = $selected;

        if ($min_rating > 0) {
            $reviews = array_values(array_filter($reviews, function($r) use ($min_rating){ return intval($r['rating'] ?? 0) >= $min_rating; }));
        }

        ob_start(); ?>
        <section class="tvln-ticker" style="--tvln-accent: <?php echo esc_attr($accent); ?>; --tvln-bg: <?php echo esc_attr($bg); ?>; --tvln-text: <?php echo esc_attr($text); ?>;" data-interval="<?php echo esc_attr($interval*1000); ?>" aria-label="Reviews ticker">
            <div class="tvln-ticker-viewport">
                <div class="tvln-ticker-track">
                    <?php foreach ($reviews as $r):
                        $rating = isset($r['rating']) ? max(1,min(5,intval($r['rating']))) : 5;
                        $src = !empty($r['ticker_text']) ? $r['ticker_text'] : ($r['body'] ?? '');
                        $raw = trim(preg_replace('/\s+/', ' ', wp_strip_all_tags($src)));
                        if (mb_strlen($raw) > $length) {
                            $cut = mb_substr($raw, 0, $length);
                            $lastSpace = mb_strrpos($cut, ' ');
                            if ($lastSpace !== false && $lastSpace > ($length * 0.6)) { $cut = mb_substr($cut, 0, $lastSpace); }
                            $raw = rtrim($cut) . '…';
                        }
                    ?>
                    <div class="tvln-ticker-item">
                        <div class="tvln-ticker-line">
                            <strong class="name"><?php echo esc_html($r['name'] ?? ''); ?></strong>
                            <span class="tvln-stars" aria-hidden="true">
                                <?php for ($i=0;$i<=$rating-1;$i++): ?><svg viewBox="0 0 24 24" class="star"><path d="M12 .9l3.09 6.26 6.91 1-5 4.88 1.18 6.89L12 16.9 5.82 20.15l1.18-6.89-5-4.88 6.91-1L12 .9z"/></svg><?php endfor; ?>
                            </span>
                            <span class="sep">•</span>
                            <span class="snippet"><?php echo esc_html($raw); ?></span>
                            <?php if ($show_source_link && !empty($r['author_url'])): ?><a class="src" href="<?php echo esc_url($r['author_url']); ?>" target="_blank" rel="noopener nofollow">Read on Google</a><?php endif; ?>
                        </div>
                    </div>
                    <?php endforeach; ?>
                </div>
            </div>
        </section>
        <?php return ob_get_clean();
    }

    private function render_header($business) {
        ob_start(); ?>
        <header class="tvln-header" aria-label="Business information">
            <h2 class="tvln-title"><?php echo esc_html($business['name'] ?? ''); ?></h2>
            <div class="tvln-agg" aria-label="Overall rating <?php echo esc_attr($business['rating_value']); ?> based on <?php echo esc_attr($business['review_count']); ?> reviews">
                <div class="tvln-stars" aria-hidden="true">
                    <?php for ($i=0;$i<5;$i++): ?><svg viewBox="0 0 24 24" class="star"><path d="M12 .9l3.09 6.26 6.91 1-5 4.88 1.18 6.89L12 16.9 5.82 20.15l1.18-6.89-5-4.88 6.91-1L12 .9z"/></svg><?php endfor; ?>
                </div>
                <div class="tvln-rating-text"><strong><?php echo esc_html($business['rating_value']); ?></strong> <span class="muted">(Based on <?php echo esc_html($business['review_count']); ?> reviews)</span></div>
            </div>
            <div class="tvln-address"><?php echo esc_html($business['address'] ?? ''); ?></div>
        </header>
        <?php return ob_get_clean();
    }
    private function render_slider($reviews, $compact=false) {
        $business = get_option(self::OPT_BUSINESS, self::defaults_business());
        $navy = $business['navy'] ?? '#0B1F44';
        ob_start(); ?>
        <div class="tvln-slider<?php echo $compact ? ' is-compact' : ''; ?>" aria-live="off">
            <button class="tvln-nav tvln-prev" aria-label="Previous reviews" type="button">
                <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/></svg>
            </button>
            <div class="tvln-viewport">
                <div class="tvln-track">
                    <?php foreach ($reviews as $r): ?>
                        <article class="tvln-card" tabindex="0" aria-label="Review by <?php echo esc_attr($r['name'] ?? ''); ?>, <?php echo intval($r['rating'] ?? 5); ?> stars">
                            <div class="tvln-card-inner">
                                <div class="tvln-card-top">
                                    <div class="tvln-stars" aria-hidden="true">
                                        <?php $rating = isset($r['rating']) ? max(1, min(5, intval($r['rating']))) : 5;
                                        for ($i=0;$i<$rating;$i++): ?>
                                            <svg viewBox="0 0 24 24" class="star"><path d="M12 .9l3.09 6.26 6.91 1-5 4.88 1.18 6.89L12 16.9 5.82 20.15l1.18-6.89-5-4.88 6.91-1L12 .9z"/></svg>
                                        <?php endfor; for ($i=$rating;$i<5;$i++): ?>
                                            <svg viewBox="0 0 24 24" class="star star--empty"><path d="M12 .9l3.09 6.26 6.91 1-5 4.88 1.18 6.89L12 16.9 5.82 20.15l1.18-6.89-5-4.88 6.91-1L12 .9z"/></svg>
                                        <?php endfor; ?>
                                    </div>
                                    <?php if (!empty($r['badge'])): ?><span class="tvln-badge"><?php echo esc_html($r['badge']); ?></span><?php endif; ?>
                                </div>
                                <div class="tvln-author">
                                    <?php if (!empty($r['avatar'])): ?>
                                      <img class="tvln-avatar" src="<?php echo esc_url($r['avatar']); ?>" alt="" loading="lazy" onerror="this.style.display='none';"/>
                                    <?php endif; ?>
                                    <div>
                                      <h3 class="tvln-name"><?php echo esc_html($r['name'] ?? ''); ?></h3>
                                      <?php $leftMeta = trim(($r['meta'] ?? '')); if ($leftMeta !== ''): ?><div class="tvln-meta"><?php echo esc_html($leftMeta); ?><?php if (!empty($r['when'])) echo ' • ' . esc_html($r['when']); ?></div><?php elseif (!empty($r['when'])): ?><div class="tvln-meta"><?php echo esc_html($r['when']); ?></div><?php endif; ?>
                                    </div>
                                </div>
                                <div class="tvln-body">
                                <?php if (!empty($r['body'])):
                                    $paragraphs = preg_split('/\r\n|\r|\n/', $r['body']); 
                                    foreach ($paragraphs as $p) { if (trim($p) === '') continue; ?>
                                        <p><?php echo esc_html($p); ?></p>
                                <?php } endif; ?>
                                </div>
                                <?php if ($compact): ?>
                                  <button class="tvln-more" type="button" aria-expanded="false" style="--navy: <?php echo esc_attr($navy); ?>;">Read more</button>
                                <?php endif; ?>
                                <?php if (!empty($r['author_url'])): ?>
                                  <p class="tvln-readmore"><a href="<?php echo esc_url($r['author_url']); ?>" target="_blank" rel="noopener nofollow">Read on Google</a></p>
                                <?php endif; ?>
                            </div>
                        </article>
                    <?php endforeach; ?>
                </div>
            </div>
            <button class="tvln-nav tvln-next" aria-label="Next reviews" type="button">
                <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M8.59 16.59L10 18l6-6-6-6-1.41 1.41L13.17 12z"/></svg>
            </button>
        </div>
        <?php return ob_get_clean();
    }
    private function render_list($reviews, $accent, $bg, $text, $navy) {
        ob_start(); ?>
        <section class="tvln-list-wrap" style="--tvln-accent: <?php echo esc_attr($accent); ?>; --tvln-bg: <?php echo esc_attr($bg); ?>; --tvln-text: <?php echo esc_attr($text); ?>; --tvln-navy: <?php echo esc_attr($navy); ?>;">
            <div class="tvln-list">
                <?php foreach ($reviews as $r): ?>
                    <article class="tvln-item">
                        <div class="tvln-item-head">
                            <div class="tvln-item-left">
                                <?php if (!empty($r['avatar'])): ?><img class="tvln-avatar" src="<?php echo esc_url($r['avatar']); ?>" alt="" loading="lazy" onerror="this.style.display='none';"/><?php endif; ?>
                                <div class="tvln-item-title">
                                    <h3><?php echo esc_html($r['name'] ?? ''); ?></h3>
                                    <div class="tvln-meta">
                                        <span class="tvln-stars" aria-hidden="true">
                                            <?php $rating = isset($r['rating']) ? max(1,min(5,intval($r['rating']))) : 5;
                                            for ($i=0;$i<$rating;$i++): ?><svg viewBox="0 0 24 24" class="star"><path d="M12 .9l3.09 6.26 6.91 1-5 4.88 1.18 6.89L12 16.9 5.82 20.15l1.18-6.89-5-4.88 6.91-1L12 .9z"/></svg><?php endfor; for ($i=$rating;$i<5;$i++): ?><svg viewBox="0 0 24 24" class="star star--empty"><path d="M12 .9l3.09 6.26 6.91 1-5 4.88 1.18 6.89L12 16.9 5.82 20.15l1.18-6.89-5-4.88 6.91-1L12 .9z"/></svg><?php endfor; ?>
                                        </span>
                                        <?php if (!empty($r['meta'])): ?><span class="sep">•</span> <span><?php echo esc_html($r['meta']); ?></span><?php endif; ?>
                                        <?php if (!empty($r['when'])): ?><span class="sep">•</span> <span class="tvln-when"><?php echo esc_html($r['when']); ?></span><?php endif; ?>
                                    </div>
                                </div>
                            </div>
                            <div class="tvln-item-right">
                                <?php if (!empty($r['author_url'])): ?><a class="tvln-g-link" href="<?php echo esc_url($r['author_url']); ?>" target="_blank" rel="noopener nofollow">Read on Google</a><?php endif; ?>
                            </div>
                        </div>
                        <div class="tvln-item-body">
                            <?php $paragraphs = preg_split('/\r\n|\r|\n/', $r['body'] ?? ''); foreach ($paragraphs as $p) { if (trim($p)==='') continue; echo '<p>' . esc_html($p) . '</p>'; } ?>
                        </div>
                    </article>
                <?php endforeach; ?>
            </div>
        </section>
        <?php return ob_get_clean();
    }
}

new RSS_Google_Reviews();
