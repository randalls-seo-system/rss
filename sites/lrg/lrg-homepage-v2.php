<?php
/**
 * Plugin Name: LRG Homepage V2 (Staging)
 * Description: Replaces homepage content with custom V2 build. Divi-compatible — hooks the_content so Divi's theme builder header and footer render normally. Staging only.
 * Version: 2.1.1
 * Author: Randall's SEO System
 *
 * INSTALL: Drop in /wp-content/mu-plugins/ on STAGING ONLY.
 * REMOVE: Delete file, or rename to .disabled
 *
 * Strategy:
 * - Hooks the_content filter (NOT template_redirect)
 * - Divi's theme builder renders header/footer normally
 * - Only the page content area is replaced
 * - Removes the old rss-blog-home.php approach
 */

if ( ! defined( 'ABSPATH' ) ) exit;

// Safety guard: only run on staging
if ( ! isset( $_SERVER['HTTP_HOST'] ) || strpos( $_SERVER['HTTP_HOST'], 'wpenginepowered.com' ) === false ) {
    return;
}

add_filter( 'the_content', 'lrg_homepage_v2_content', 99 );

function lrg_homepage_v2_content( $content ) {
    // Only fire on the lrg-blog page (now a real static front page)
    if ( ! is_page( 'lrg-blog' ) ) return $content;
    if ( ! in_the_loop() ) return $content;
    if ( ! is_main_query() ) return $content;

    ob_start();
    lrg_homepage_v2_output();
    return ob_get_clean();
}

/**
 * Helper: Get featured + recent articles
 */
function lrg_v2_get_articles( $count = 7 ) {
    $args = array(
        'post_type' => 'post',
        'posts_per_page' => $count,
        'post_status' => 'publish',
        'orderby' => 'date',
        'order' => 'DESC',
        'no_found_rows' => true,
        'ignore_sticky_posts' => true,
    );
    $q = new WP_Query( $args );
    $articles = array();
    if ( ! empty( $q->posts ) ) {
        foreach ( $q->posts as $p ) {
            $excerpt = $p->post_excerpt ? $p->post_excerpt : wp_trim_words( strip_tags( $p->post_content ), 28, '…' );
            $cats = get_the_category( $p->ID );
            $cat_name = '';
            $cat_link = '';
            if ( ! empty( $cats ) ) {
                $cat_name = $cats[0]->name;
                $cl = get_category_link( $cats[0]->term_id );
                $cat_link = is_wp_error( $cl ) ? '' : $cl;
            }
            $word_count = str_word_count( strip_tags( $p->post_content ) );
            $articles[] = array(
                'id' => $p->ID,
                'title' => get_the_title( $p->ID ),
                'excerpt' => wp_trim_words( $excerpt, 22, '…' ),
                'permalink' => get_permalink( $p->ID ),
                'thumb' => get_the_post_thumbnail_url( $p->ID, 'large' ),
                'date' => get_the_date( 'M j, Y', $p->ID ),
                'category' => $cat_name,
                'category_link' => $cat_link,
                'read_time' => max( 3, ceil( $word_count / 220 ) ),
            );
        }
    }
    return $articles;
}

/**
 * Helper: Get reviews from rss-google-reviews option
 */
function lrg_v2_get_reviews( $count = 3 ) {
    $reviews = get_option( 'rss_reviews_list', array() );

    // Hardcoded fallback — mix of Google + Zillow real reviews
    $fallback = array(
        array(
            'author_name' => 'Henry Wallis',
            'rating' => 5,
            'text' => "As a first-time home buyer relocating from the United Kingdom to San Antonio, I truly had no idea where to begin. The home buying process in the U.S. is quite different, and it initially felt overwhelming — but working with Tania completely changed that experience.",
            'time_relative' => '5/4/2026',
            'source' => 'Zillow',
        ),
        array(
            'author_name' => 'Jenn Hunt-Petrak',
            'rating' => 5,
            'text' => "Imelda Luquin helped our family understand some landlord/tenant information when we had to deal with some difficult situations. She was extremely knowledgeable and kind. When we decided to sell the property she was there to guide us through the process.",
            'time_relative' => '6 days ago',
            'source' => 'Google',
        ),
        array(
            'author_name' => 'Israel Lares',
            'rating' => 5,
            'text' => "Joseph went above and beyond to help us find our new home. Given we only had a week into town to find a home that meets our needs he didn't let that pressure get to him. He even treated us out to breakfast and lunch to really get to know us and to figure out what we were looking for.",
            'time_relative' => '4/26/2026',
            'source' => 'Zillow',
        ),
    );

    if ( empty( $reviews ) || ! is_array( $reviews ) ) {
        return $fallback;
    }

    // Try to normalize different possible structures from rss-google-reviews plugin
    $normalized = array();
    foreach ( $reviews as $r ) {
        if ( ! is_array( $r ) ) continue;

        // Try multiple key variations
        $name = $r['author_name'] ?? $r['name'] ?? $r['reviewer_name'] ?? $r['author'] ?? '';
        $text = $r['text'] ?? $r['review'] ?? $r['review_text'] ?? $r['content'] ?? $r['body'] ?? '';
        $rating = intval( $r['rating'] ?? $r['stars'] ?? $r['score'] ?? 5 );
        $time = $r['time'] ?? $r['timestamp'] ?? $r['created'] ?? 0;
        $time_str = $r['relative_time_description'] ?? $r['time_relative'] ?? '';
        $source = $r['source'] ?? 'Google';

        if ( empty( $time_str ) && $time ) {
            $time_str = human_time_diff( $time, current_time( 'timestamp' ) ) . ' ago';
        }

        // Skip reviews with no text — they're useless for display
        if ( empty( $text ) || empty( $name ) ) continue;

        $normalized[] = array(
            'author_name' => $name,
            'rating' => $rating,
            'text' => $text,
            'time_relative' => $time_str ?: 'Recently',
            'source' => $source,
        );
    }

    // If normalization yielded nothing usable, use fallback
    if ( empty( $normalized ) ) {
        return $fallback;
    }

    // Filter to 5-star, sort by recency, take top N
    $five_star = array_filter( $normalized, function( $r ) {
        return $r['rating'] >= 5;
    });

    if ( empty( $five_star ) ) $five_star = $normalized;

    return array_slice( $five_star, 0, $count );
}

/**
 * Helper: Get category by slug with fallback
 */
function lrg_v2_get_cat( $slug, $fallback_name, $fallback_count = 0 ) {
    $term = get_term_by( 'slug', $slug, 'category' );
    if ( $term && ! is_wp_error( $term ) ) {
        $link = get_term_link( $term );
        if ( is_wp_error( $link ) ) {
            $link = '#';
        }
        return array(
            'name' => $term->name,
            'count' => intval( $term->count ),
            'link' => $link,
            'desc' => $term->description ?: '',
        );
    }
    return array(
        'name' => $fallback_name,
        'count' => $fallback_count,
        'link' => '#',
        'desc' => '',
    );
}

function lrg_homepage_v2_output() {
    $articles = lrg_v2_get_articles( 7 );
    $featured = ! empty( $articles ) ? $articles[0] : null;
    $grid_articles = array_slice( $articles, 1, 6 );
    $reviews = lrg_v2_get_reviews( 3 );

    // Featured review — Josecarlos Violeta with photo (real Google review with image)
    $featured_review = array(
        'author_name' => 'Josecarlos Violeta',
        'author_initials' => 'JV',
        'rating' => 5,
        'text' => 'The absolute GOAT Stephanie Campa closed on my purchase negotiating for me a 30k reduction in the original asking price for a home. This netted me 10k equity FROM THE RIP! She was extremely knowledgeable, poignant, diligent and everything you need in an REA. Above all that she was kind. Making sure she fought for my side of the deal with the things I was asking for. I met Levi Rodgers through the ordeal of homebuying and I was thoroughly impressed by his aptitude as a broker. As a First Time Veteran (Gen Z with no wealth) homebuyer. I was both thoroughly impressed and felt as if I was in good hands.',
        'time_relative' => 'Closed 8 weeks ago · Google Review',
        'detail' => 'First-time Veteran buyer · El Paso → San Antonio',
        'photo' => 'https://lh3.googleusercontent.com/grass-cs/ANxoTn3OrO9i_OmvOJg9BFsbGHqoPSrg_QXozS88hkQuZtAI5oekJyt6N9lnPaJogd6whU52rxZUg_-19YM1QdkjyzFnoXBHs0B1aHuIqZqN-itnRU8jMwoZpwH6bHgJCj7p2LqSLEUHcipEsj-5=s1920-w1920-h846-rw-k-p',
    );

    // Categories — pull live from WP, fallback to sensible defaults
    $cats = array(
        lrg_v2_get_cat( 'home-buying', 'Home Buying', 154 ),
        lrg_v2_get_cat( 'sell-your-home', 'Sell Your Home', 81 ),
        lrg_v2_get_cat( 'va-loans', 'VA Loans & Veterans', 16 ),
        lrg_v2_get_cat( 'san-antonio', 'San Antonio', 47 ),
        lrg_v2_get_cat( 'austin', 'Austin', 32 ),
        lrg_v2_get_cat( 'neighborhood-guides', 'Neighborhood Guides', 101 ),
    );
    ?>
<style>
  .lrg-v2-home {
    --lrg-navy: #0F1F4A;
    --lrg-navy-deep: #08142B;
    --lrg-navy-soft: #1A2C52;
    --lrg-red: #C8102E;
    --lrg-red-deep: #991B1B;
    --lrg-red-bright: #DC2538;
    --lrg-gold: #D4A574;
    --lrg-gold-bright: #E8C094;
    --lrg-star: #FBBF24;
    --lrg-white: #FFFFFF;
    --lrg-cream: #FAFAF7;
    --lrg-paper: #F5F2EC;
    --lrg-gray-100: #E5E7EB;
    --lrg-gray-200: #D1D5DB;
    --lrg-gray-300: #94A3B8;
    --lrg-gray-400: #64748B;
    --lrg-gray-500: #475569;
    --lrg-gray-700: #1F2937;
    --lrg-ink: #0F172A;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
    color: var(--lrg-gray-700);
    line-height: 1.5;
    margin: 0 -50vw;
    padding: 0;
    position: relative;
    left: 50%;
    right: 50%;
    width: 100vw;
  }
  .lrg-v2-home *, .lrg-v2-home *::before, .lrg-v2-home *::after { box-sizing: border-box; }
  .lrg-v2-home img { max-width: 100%; height: auto; display: block; }
  .lrg-v2-home a { text-decoration: none; }
  .lrg-v2-container { max-width: 1280px; margin: 0 auto; padding: 0 24px; }

  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Fraunces:opsz,wght,SOFT@9..144,400;9..144,500;9..144,600;9..144,700&display=swap');

  /* Hide Divi page title above our content */
  body.page-id-lrg-blog .entry-title,
  body.page-template-default h1.entry-title,
  body .et_pb_section.et_pb_section_0_tb_body,
  body.page #left-area > article > .entry-title,
  body.page #page-container .et_post_meta_wrapper {
    display: none !important;
  }
  /* Remove top padding from main content area on lrg-blog page */
  body.page #main-content,
  body.page #et-main-area,
  body.page #main-content .container,
  body.page #left-area {
    padding-top: 0 !important;
    margin-top: 0 !important;
  }
  body.page #content-area {
    padding-top: 0 !important;
  }

  /* STAGING BANNER */
  .lrg-v2-staging-banner {
    background: var(--lrg-red);
    color: var(--lrg-white);
    text-align: center;
    padding: 6px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
  }

  /* HERO */
  .lrg-v2-hero {
    background:
      radial-gradient(circle at 85% 15%, rgba(212, 165, 116, 0.10) 0%, transparent 55%),
      radial-gradient(circle at 10% 90%, rgba(200, 16, 46, 0.08) 0%, transparent 50%),
      linear-gradient(180deg, var(--lrg-navy) 0%, var(--lrg-navy-deep) 100%);
    color: var(--lrg-white);
    padding: 80px 0 88px;
    position: relative;
    overflow: hidden;
  }
  .lrg-v2-hero::before {
    content: '';
    position: absolute;
    inset: 0;
    background-image:
      radial-gradient(1px 1px at 12% 22%, rgba(255, 255, 255, 0.10) 50%, transparent 100%),
      radial-gradient(1px 1px at 58% 68%, rgba(212, 165, 116, 0.18) 50%, transparent 100%),
      radial-gradient(1px 1px at 82% 18%, rgba(200, 16, 46, 0.14) 50%, transparent 100%);
    background-size: 280px 280px, 320px 320px, 240px 240px;
    pointer-events: none;
  }
  .lrg-v2-hero-inner {
    text-align: center;
    max-width: 880px;
    margin: 0 auto;
    position: relative;
    z-index: 1;
  }
  .lrg-v2-hero-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    background: rgba(212, 165, 116, 0.12);
    border: 1px solid rgba(212, 165, 116, 0.30);
    color: var(--lrg-gold-bright);
    padding: 6px 14px;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin-bottom: 22px;
  }
  .lrg-v2-hero-eyebrow::before {
    content: '';
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--lrg-gold-bright);
    box-shadow: 0 0 8px var(--lrg-gold);
  }
  .lrg-v2-hero-h1 {
    font-family: 'Fraunces', Georgia, serif;
    font-size: clamp(40px, 5.5vw, 64px);
    line-height: 1.04;
    font-weight: 500;
    letter-spacing: -0.025em;
    margin: 0 0 24px;
    color: var(--lrg-white);
    font-variation-settings: "opsz" 100, "SOFT" 30;
  }
  .lrg-v2-hero-h1 em {
    color: var(--lrg-gold-bright);
    font-style: italic;
    font-weight: 600;
    text-shadow: 0 0 28px rgba(212, 165, 116, 0.35);
  }
  .lrg-v2-hero-sub {
    font-size: 19px;
    line-height: 1.6;
    color: rgba(255,255,255,0.86);
    margin: 0 auto 32px;
    max-width: 720px;
  }
  .lrg-v2-hero-ctas {
    display: inline-flex;
    gap: 14px;
    flex-wrap: wrap;
    justify-content: center;
    margin-bottom: 32px;
  }
  .lrg-v2-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    padding: 14px 28px;
    border-radius: 8px;
    font-weight: 600;
    font-size: 15px;
    letter-spacing: 0.01em;
    transition: all 0.22s;
    cursor: pointer;
    border: none;
    font-family: inherit;
    text-decoration: none !important;
  }
  .lrg-v2-btn-primary {
    background: linear-gradient(135deg, var(--lrg-red) 0%, var(--lrg-red-bright) 100%);
    color: var(--lrg-white) !important;
    box-shadow: 0 4px 16px rgba(200, 16, 46, 0.32);
  }
  .lrg-v2-btn-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 28px rgba(200, 16, 46, 0.45);
    color: var(--lrg-white) !important;
  }
  .lrg-v2-btn-secondary {
    background: transparent;
    color: var(--lrg-white) !important;
    border: 1.5px solid rgba(255,255,255,0.28);
  }
  .lrg-v2-btn-secondary:hover {
    border-color: var(--lrg-white);
    background: rgba(255,255,255,0.06);
    color: var(--lrg-white) !important;
  }
  .lrg-v2-hero-trust {
    display: inline-flex;
    gap: 26px;
    align-items: center;
    justify-content: center;
    font-size: 13px;
    color: rgba(255,255,255,0.78);
    flex-wrap: wrap;
  }
  .lrg-v2-hero-trust-item {
    display: flex;
    align-items: center;
    gap: 7px;
  }
  .lrg-v2-hero-stars {
    color: var(--lrg-star);
    font-size: 14px;
    letter-spacing: 1px;
  }

  /* HERO RIGHT — Editorial card */
  .lrg-v2-hero-card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 16px;
    padding: 32px;
    box-shadow: 0 24px 64px rgba(0,0,0,0.40);
    backdrop-filter: blur(8px);
    position: relative;
  }
  .lrg-v2-hero-card-eyebrow {
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--lrg-gold-bright);
    margin-bottom: 10px;
  }
  .lrg-v2-hero-card-title {
    font-family: 'Fraunces', serif;
    font-size: 24px;
    font-weight: 600;
    margin: 0 0 16px;
    letter-spacing: -0.015em;
    color: var(--lrg-white);
    line-height: 1.2;
  }
  .lrg-v2-hero-card-quote {
    font-family: 'Fraunces', serif;
    font-style: italic;
    font-size: 17px;
    line-height: 1.55;
    color: rgba(255,255,255,0.88);
    margin: 0 0 20px;
    padding-left: 16px;
    border-left: 2px solid var(--lrg-gold);
  }
  .lrg-v2-hero-card-quote em {
    color: var(--lrg-gold-bright);
    font-style: italic;
    font-weight: 600;
  }
  .lrg-v2-hero-card-meta {
    border-top: 1px solid rgba(255,255,255,0.12);
    padding-top: 16px;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
  }
  .lrg-v2-hero-card-attr {
    font-size: 13px;
  }
  .lrg-v2-hero-card-attr-name {
    color: var(--lrg-white);
    font-weight: 600;
    margin-bottom: 2px;
  }
  .lrg-v2-hero-card-attr-role {
    color: rgba(255,255,255,0.6);
    font-size: 12px;
  }
  .lrg-v2-hero-card-cta {
    color: var(--lrg-gold-bright) !important;
    font-size: 13px;
    font-weight: 600;
    text-decoration: none !important;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    transition: gap 0.2s;
  }
  .lrg-v2-hero-card-cta:hover { gap: 8px; }

  /* STAT BAR */
  .lrg-v2-statbar {
    background: var(--lrg-cream);
    border-bottom: 1px solid var(--lrg-gray-100);
    padding: 40px 0;
  }
  .lrg-v2-statbar-inner {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 32px;
  }
  .lrg-v2-stat {
    text-align: center;
    border-right: 1px solid var(--lrg-gray-100);
    padding: 0 16px;
  }
  .lrg-v2-stat:last-child { border-right: none; }
  .lrg-v2-stat-num {
    font-family: 'Fraunces', serif;
    font-size: 38px;
    font-weight: 600;
    color: var(--lrg-navy);
    letter-spacing: -0.025em;
    line-height: 1;
    margin-bottom: 6px;
  }
  .lrg-v2-stat-num em {
    color: var(--lrg-red);
    font-style: italic;
  }
  .lrg-v2-stat-label {
    font-size: 12px;
    color: var(--lrg-gray-500);
    font-weight: 500;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  /* SECTION SCAFFOLDING */
  .lrg-v2-section { padding: 88px 0; }
  .lrg-v2-section.alt { background: var(--lrg-cream); }
  .lrg-v2-section.paper { background: var(--lrg-paper); }
  .lrg-v2-section.dark { background: var(--lrg-navy); color: var(--lrg-white); }
  .lrg-v2-section-header {
    text-align: center;
    max-width: 880px;
    margin: 0 auto 56px;
  }
  .lrg-v2-section-eyebrow {
    display: inline-block;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--lrg-red);
    margin-bottom: 16px;
  }
  .lrg-v2-section.dark .lrg-v2-section-eyebrow { color: var(--lrg-gold-bright); }
  .lrg-v2-section-h2 {
    font-family: 'Fraunces', serif;
    font-size: clamp(30px, 3.8vw, 44px);
    line-height: 1.15;
    font-weight: 500;
    letter-spacing: -0.025em;
    color: var(--lrg-navy);
    margin: 0 0 18px;
  }
  .lrg-v2-section.dark .lrg-v2-section-h2 { color: var(--lrg-white); }
  .lrg-v2-section-h2 em {
    color: var(--lrg-red);
    font-style: italic;
    font-weight: 600;
  }
  .lrg-v2-section.dark .lrg-v2-section-h2 em { color: var(--lrg-gold-bright); }
  .lrg-v2-section-sub {
    font-size: 17px;
    color: var(--lrg-gray-500);
    line-height: 1.65;
    margin: 0;
  }
  .lrg-v2-section.dark .lrg-v2-section-sub { color: rgba(255,255,255,0.78); }

  /* FEATURED ARTICLE — Magazine treatment */
  .lrg-v2-featured {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0;
    align-items: stretch;
    background: var(--lrg-white);
    border: 1px solid var(--lrg-gray-100);
    border-radius: 16px;
    overflow: hidden;
    box-shadow: 0 20px 60px rgba(15, 31, 74, 0.08);
  }
  .lrg-v2-featured-img {
    width: 100%;
    height: 100%;
    min-height: 380px;
    overflow: hidden;
    background: var(--lrg-cream);
    position: relative;
  }
  .lrg-v2-featured-img img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    object-position: center center;
    background: var(--lrg-cream);
  }
  .lrg-v2-featured-img-placeholder {
    width: 100%;
    height: 100%;
    background:
      radial-gradient(circle at 30% 30%, rgba(212, 165, 116, 0.18) 0%, transparent 60%),
      linear-gradient(135deg, var(--lrg-navy) 0%, var(--lrg-navy-deep) 100%);
  }
  .lrg-v2-featured-body { padding: 44px 48px; }
  .lrg-v2-featured-tags {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-bottom: 18px;
  }
  .lrg-v2-featured-pill {
    display: inline-block;
    background: var(--lrg-red);
    color: var(--lrg-white);
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }
  .lrg-v2-featured-cat {
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--lrg-gray-400);
  }
  .lrg-v2-featured-title {
    font-family: 'Fraunces', serif;
    font-size: clamp(28px, 3.2vw, 38px);
    line-height: 1.18;
    font-weight: 500;
    letter-spacing: -0.02em;
    color: var(--lrg-navy);
    margin: 0 0 18px;
  }
  .lrg-v2-featured-title a {
    color: inherit !important;
    transition: color 0.2s;
  }
  .lrg-v2-featured-title a:hover { color: var(--lrg-red) !important; }
  .lrg-v2-featured-excerpt {
    font-size: 17px;
    line-height: 1.65;
    color: var(--lrg-gray-500);
    margin: 0 0 28px;
  }
  .lrg-v2-featured-meta {
    display: flex;
    align-items: center;
    gap: 16px;
    padding-top: 20px;
    border-top: 1px solid var(--lrg-gray-100);
  }
  .lrg-v2-featured-link {
    color: var(--lrg-red) !important;
    font-weight: 600;
    font-size: 15px;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: gap 0.2s;
  }
  .lrg-v2-featured-link:hover { gap: 10px; }
  .lrg-v2-featured-readtime {
    font-size: 13px;
    color: var(--lrg-gray-400);
    margin-left: auto;
  }

  /* ARTICLE GRID — Magazine layout */
  .lrg-v2-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 28px;
  }
  .lrg-v2-card {
    background: var(--lrg-white);
    border: 1px solid var(--lrg-gray-100);
    border-radius: 12px;
    overflow: hidden;
    transition: all 0.25s;
    display: flex;
    flex-direction: column;
  }
  .lrg-v2-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 18px 44px rgba(15, 31, 74, 0.10);
    border-color: var(--lrg-gold);
  }
  .lrg-v2-card-img {
    width: 100%;
    aspect-ratio: 16/9;
    overflow: hidden;
    background: var(--lrg-gray-100);
  }
  .lrg-v2-card-img img,
  .lrg-v2-card-img-placeholder {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  .lrg-v2-card-img-placeholder {
    background:
      radial-gradient(circle at 30% 30%, rgba(212, 165, 116, 0.15) 0%, transparent 60%),
      linear-gradient(135deg, var(--lrg-navy) 0%, var(--lrg-navy-soft) 100%);
  }
  .lrg-v2-card-body {
    padding: 22px 24px 24px;
    display: flex;
    flex-direction: column;
    flex: 1;
  }
  .lrg-v2-card-cat {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--lrg-red);
    margin-bottom: 10px;
  }
  .lrg-v2-card-title {
    font-family: 'Fraunces', serif;
    font-size: 21px;
    font-weight: 500;
    line-height: 1.28;
    letter-spacing: -0.015em;
    color: var(--lrg-navy);
    margin: 0 0 12px;
  }
  .lrg-v2-card-title a { color: inherit !important; transition: color 0.2s; }
  .lrg-v2-card-title a:hover { color: var(--lrg-red) !important; }
  .lrg-v2-card-excerpt {
    font-size: 14.5px;
    line-height: 1.6;
    color: var(--lrg-gray-500);
    margin: 0 0 18px;
    flex: 1;
  }
  .lrg-v2-card-meta {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-top: 14px;
    border-top: 1px solid var(--lrg-gray-100);
    font-size: 12.5px;
    color: var(--lrg-gray-400);
  }
  .lrg-v2-card-date { font-weight: 500; }
  .lrg-v2-card-readtime { font-weight: 500; }

  .lrg-v2-grid-cta {
    text-align: center;
    margin-top: 44px;
  }
  .lrg-v2-grid-cta a {
    color: var(--lrg-red) !important;
    font-weight: 600;
    font-size: 15px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
    transition: gap 0.2s;
    border-bottom: 1px solid var(--lrg-red);
    padding-bottom: 2px;
  }
  .lrg-v2-grid-cta a:hover { gap: 12px; }

  /* SECTIONS GRID — Editorial nav */
  .lrg-v2-sections {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
  }
  .lrg-v2-section-card {
    background: var(--lrg-white);
    border: 1px solid var(--lrg-gray-100);
    border-radius: 12px;
    padding: 32px 28px;
    transition: all 0.25s;
    display: block;
    text-decoration: none !important;
    color: inherit !important;
    position: relative;
    overflow: hidden;
  }
  .lrg-v2-section-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    background: var(--lrg-navy);
    transition: background 0.25s;
  }
  .lrg-v2-section-card:nth-child(2)::before,
  .lrg-v2-section-card:nth-child(4)::before,
  .lrg-v2-section-card:nth-child(6)::before { background: var(--lrg-red); }
  .lrg-v2-section-card:hover {
    transform: translateY(-3px);
    box-shadow: 0 16px 40px rgba(15, 31, 74, 0.10);
    border-color: var(--lrg-gold);
  }
  .lrg-v2-section-card:hover::before { background: var(--lrg-gold); }
  .lrg-v2-section-card-num {
    font-family: 'Fraunces', serif;
    font-size: 13px;
    font-weight: 600;
    color: var(--lrg-gray-300);
    letter-spacing: 0.1em;
    margin-bottom: 10px;
  }
  .lrg-v2-section-card-title {
    font-family: 'Fraunces', serif;
    font-size: 22px;
    font-weight: 600;
    color: var(--lrg-navy);
    letter-spacing: -0.01em;
    margin: 0 0 8px;
    line-height: 1.2;
  }
  .lrg-v2-section-card-count {
    font-size: 13px;
    color: var(--lrg-gray-400);
    margin-bottom: 14px;
  }
  .lrg-v2-section-card-arrow {
    color: var(--lrg-red);
    font-size: 14px;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    transition: gap 0.2s;
  }
  .lrg-v2-section-card:hover .lrg-v2-section-card-arrow { gap: 8px; }

  /* REVIEWS — VALN-style featured + 3 stack matching heights */
  .lrg-v2-reviews-layout {
    display: grid;
    grid-template-columns: 1.05fr 1fr;
    gap: 22px;
    margin-bottom: 32px;
    align-items: stretch;
  }
  .lrg-v2-review-featured {
    background: var(--lrg-white);
    border: 1px solid var(--lrg-gray-100);
    border-radius: 14px;
    overflow: hidden;
    box-shadow: 0 12px 36px rgba(15, 31, 74, 0.08);
    display: flex;
    flex-direction: column;
  }
  .lrg-v2-review-featured-photo {
    width: 100%;
    aspect-ratio: 4 / 3;
    overflow: hidden;
    background: var(--lrg-cream);
  }
  .lrg-v2-review-featured-photo img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    object-position: center;
    background: var(--lrg-cream);
  }
  .lrg-v2-review-featured-body {
    padding: 22px 26px 24px;
    display: flex;
    flex-direction: column;
    flex: 1;
  }
  .lrg-v2-review-featured-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(200, 16, 46, 0.08);
    border: 1px solid rgba(200, 16, 46, 0.25);
    color: var(--lrg-red);
    padding: 4px 10px;
    border-radius: 5px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin-bottom: 14px;
    align-self: flex-start;
  }
  .lrg-v2-review-featured-stars {
    color: var(--lrg-star);
    font-size: 16px;
    letter-spacing: 2px;
    margin-bottom: 14px;
  }
  .lrg-v2-review-featured-quote {
    font-family: 'Fraunces', serif;
    font-size: 16px;
    line-height: 1.55;
    color: var(--lrg-gray-700);
    margin: 0 0 18px;
    font-style: italic;
    letter-spacing: -0.005em;
    flex: 1;
  }
  .lrg-v2-review-featured-quote em {
    color: var(--lrg-red);
    font-style: italic;
    font-weight: 600;
  }
  .lrg-v2-review-featured-author {
    display: flex;
    align-items: center;
    gap: 12px;
    padding-top: 16px;
    border-top: 1px solid var(--lrg-gray-100);
  }
  .lrg-v2-review-featured-avatar {
    width: 42px;
    height: 42px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--lrg-navy) 0%, var(--lrg-navy-soft) 100%);
    color: var(--lrg-white);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 14px;
    flex-shrink: 0;
  }
  .lrg-v2-review-featured-name {
    font-size: 14.5px;
    font-weight: 700;
    color: var(--lrg-navy);
    line-height: 1.2;
    margin-bottom: 3px;
  }
  .lrg-v2-review-featured-detail {
    font-size: 12px;
    color: var(--lrg-gray-400);
  }
  .lrg-v2-reviews-stack {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .lrg-v2-review-stack-card {
    background: var(--lrg-white);
    border: 1px solid var(--lrg-gray-100);
    border-radius: 11px;
    padding: 20px 22px;
    transition: all 0.22s;
    flex: 1;
    display: flex;
    flex-direction: column;
  }
  .lrg-v2-review-stack-card:hover {
    border-color: var(--lrg-gold);
    box-shadow: 0 8px 24px rgba(15, 31, 74, 0.06);
  }
  .lrg-v2-review-stack-stars {
    color: var(--lrg-star);
    font-size: 13px;
    letter-spacing: 2px;
    margin-bottom: 10px;
  }
  .lrg-v2-review-stack-quote {
    font-family: 'Fraunces', serif;
    font-size: 14px;
    line-height: 1.55;
    color: var(--lrg-gray-700);
    margin: 0 0 12px;
    font-style: italic;
    letter-spacing: -0.005em;
    flex: 1;
    display: -webkit-box;
    -webkit-line-clamp: 5;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .lrg-v2-review-stack-author {
    display: flex;
    align-items: center;
    gap: 10px;
    padding-top: 10px;
    border-top: 1px solid var(--lrg-gray-100);
  }
  .lrg-v2-review-stack-avatar {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--lrg-navy) 0%, var(--lrg-navy-soft) 100%);
    color: var(--lrg-white);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 12px;
    flex-shrink: 0;
  }
  .lrg-v2-review-stack-name {
    font-size: 13.5px;
    font-weight: 700;
    color: var(--lrg-navy);
    line-height: 1.2;
    margin-bottom: 2px;
  }
  .lrg-v2-review-stack-detail {
    font-size: 11.5px;
    color: var(--lrg-gray-400);
  }
  .lrg-v2-reviews-meta {
    text-align: center;
    padding-top: 8px;
  }
  .lrg-v2-reviews-meta-stars {
    color: var(--lrg-star);
    font-size: 22px;
    letter-spacing: 3px;
    margin-bottom: 6px;
  }
  .lrg-v2-reviews-meta-text {
    font-size: 14px;
    color: var(--lrg-gray-500);
  }
  .lrg-v2-reviews-meta-text strong {
    color: var(--lrg-navy);
    font-weight: 700;
  }
  .lrg-v2-reviews-meta-link {
    display: inline-block;
    margin-top: 14px;
    color: var(--lrg-red) !important;
    font-size: 13.5px;
    font-weight: 600;
  }
  .lrg-v2-reviews-meta-links {
    display: inline-flex;
    gap: 20px;
    align-items: center;
    margin-top: 18px;
    flex-wrap: wrap;
    justify-content: center;
  }
  .lrg-v2-reviews-meta-link-primary {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: linear-gradient(135deg, var(--lrg-red) 0%, var(--lrg-red-bright) 100%);
    color: var(--lrg-white) !important;
    padding: 11px 22px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    transition: all 0.2s;
    box-shadow: 0 4px 14px rgba(200, 16, 46, 0.28);
  }
  .lrg-v2-reviews-meta-link-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 22px rgba(200, 16, 46, 0.40);
    color: var(--lrg-white) !important;
  }
  .lrg-v2-reviews-meta-link-secondary {
    color: var(--lrg-gray-500) !important;
    font-size: 13px;
    font-weight: 500;
    border-bottom: 1px solid var(--lrg-gray-200);
    padding-bottom: 2px;
    transition: all 0.2s;
  }
  .lrg-v2-reviews-meta-link-secondary:hover {
    color: var(--lrg-navy) !important;
    border-color: var(--lrg-navy);
  }

  /* CTA BAND */
  .lrg-v2-cta-band {
    background:
      radial-gradient(circle at 80% 0%, rgba(212, 165, 116, 0.10) 0%, transparent 50%),
      radial-gradient(circle at 0% 100%, rgba(200, 16, 46, 0.12) 0%, transparent 50%),
      linear-gradient(135deg, var(--lrg-navy) 0%, var(--lrg-navy-deep) 100%);
    color: var(--lrg-white);
    padding: 88px 0;
    text-align: center;
    position: relative;
    overflow: hidden;
  }
  .lrg-v2-cta-band::before {
    content: '';
    position: absolute;
    inset: 0;
    background-image:
      radial-gradient(1px 1px at 20% 30%, rgba(255, 255, 255, 0.10) 50%, transparent 100%),
      radial-gradient(1px 1px at 70% 60%, rgba(212, 165, 116, 0.18) 50%, transparent 100%);
    background-size: 200px 200px, 260px 260px;
    pointer-events: none;
  }
  .lrg-v2-cta-band-inner {
    max-width: 720px;
    margin: 0 auto;
    position: relative;
    z-index: 1;
  }
  .lrg-v2-cta-band-eyebrow {
    display: inline-block;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--lrg-gold-bright);
    margin-bottom: 18px;
  }
  .lrg-v2-cta-band-h2 {
    font-family: 'Fraunces', serif;
    font-size: clamp(32px, 4vw, 48px);
    line-height: 1.15;
    font-weight: 500;
    letter-spacing: -0.025em;
    color: var(--lrg-white);
    margin: 0 0 18px;
  }
  .lrg-v2-cta-band-h2 em {
    color: var(--lrg-gold-bright);
    font-style: italic;
    font-weight: 600;
  }
  .lrg-v2-cta-band-sub {
    font-size: 17px;
    color: rgba(255,255,255,0.82);
    line-height: 1.6;
    margin: 0 0 36px;
  }
  .lrg-v2-cta-band-trust {
    margin-top: 24px;
    font-size: 13px;
    color: rgba(255,255,255,0.66);
  }
  .lrg-v2-cta-band-trust .lrg-v2-hero-stars { margin-right: 8px; }

  /* CALCULATOR SECTION */
  .lrg-v2-calc-wrap {
    display: grid;
    grid-template-columns: 1fr 1.1fr;
    gap: 56px;
    align-items: center;
    max-width: 1100px;
    margin: 0 auto;
  }
  .lrg-v2-calc-content-eyebrow {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--lrg-red);
    margin-bottom: 14px;
  }
  .lrg-v2-section.dark .lrg-v2-calc-content-eyebrow { color: var(--lrg-gold-bright); }
  .lrg-v2-calc-content-h2 {
    font-family: 'Fraunces', serif;
    font-size: clamp(28px, 3.5vw, 40px);
    line-height: 1.2;
    font-weight: 500;
    letter-spacing: -0.02em;
    color: var(--lrg-navy);
    margin: 0 0 18px;
  }
  .lrg-v2-section.dark .lrg-v2-calc-content-h2 { color: var(--lrg-white); }
  .lrg-v2-calc-content-h2 em {
    color: var(--lrg-red);
    font-style: italic;
    font-weight: 600;
  }
  .lrg-v2-section.dark .lrg-v2-calc-content-h2 em { color: var(--lrg-gold-bright); }
  .lrg-v2-calc-content-text {
    font-size: 16px;
    line-height: 1.65;
    color: var(--lrg-gray-500);
    margin: 0 0 14px;
  }
  .lrg-v2-section.dark .lrg-v2-calc-content-text { color: rgba(255,255,255,0.78); }
  .lrg-v2-calc-content-bullets {
    list-style: none;
    padding: 0;
    margin: 18px 0 22px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }
  .lrg-v2-calc-content-bullet {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    font-size: 14.5px;
    color: var(--lrg-gray-700);
  }
  .lrg-v2-section.dark .lrg-v2-calc-content-bullet { color: rgba(255,255,255,0.88); }
  .lrg-v2-calc-content-bullet::before {
    content: '✓';
    color: var(--lrg-red);
    font-weight: 700;
    font-size: 16px;
    flex-shrink: 0;
  }
  .lrg-v2-section.dark .lrg-v2-calc-content-bullet::before { color: var(--lrg-gold-bright); }
  .lrg-v2-calc-card {
    background: linear-gradient(135deg, var(--lrg-navy) 0%, var(--lrg-navy-deep) 100%);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 14px;
    padding: 32px;
    color: var(--lrg-white);
    box-shadow: 0 20px 50px rgba(15, 31, 74, 0.20);
    position: relative;
    overflow: hidden;
  }
  .lrg-v2-calc-card::before {
    content: '';
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at 80% 0%, rgba(212, 165, 116, 0.10) 0%, transparent 60%);
    pointer-events: none;
  }
  .lrg-v2-calc-card-inner { position: relative; z-index: 1; }
  .lrg-v2-calc-card-label {
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--lrg-gold-bright);
    margin-bottom: 6px;
  }
  .lrg-v2-calc-card-title {
    font-family: 'Fraunces', serif;
    font-size: 24px;
    font-weight: 600;
    margin: 0 0 6px;
    letter-spacing: -0.01em;
    color: var(--lrg-white);
  }
  .lrg-v2-calc-card-sub {
    font-size: 13px;
    color: rgba(255,255,255,0.7);
    margin: 0 0 22px;
    line-height: 1.5;
  }
  .lrg-v2-calc {
    display: flex;
    flex-direction: column;
    gap: 14px;
  }
  .lrg-v2-calc-field {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }
  .lrg-v2-calc-label {
    font-size: 11px;
    font-weight: 600;
    color: rgba(255,255,255,0.7);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .lrg-v2-calc-input {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.15);
    color: var(--lrg-white);
    padding: 12px 14px;
    border-radius: 7px;
    font-size: 15px;
    font-family: inherit;
    font-weight: 500;
    transition: all 0.2s;
  }
  .lrg-v2-calc-input:focus {
    outline: none;
    border-color: var(--lrg-gold-bright);
    background: rgba(212, 165, 116, 0.06);
    box-shadow: 0 0 0 3px rgba(212, 165, 116, 0.18);
  }
  .lrg-v2-calc-result {
    background: linear-gradient(135deg, rgba(200, 16, 46, 0.12), rgba(200, 16, 46, 0.04));
    border: 1px solid rgba(200, 16, 46, 0.30);
    border-radius: 9px;
    padding: 16px 18px;
    margin-top: 6px;
  }
  .lrg-v2-calc-result-label {
    font-size: 10.5px;
    color: rgba(255,255,255,0.65);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    font-weight: 600;
    margin-bottom: 3px;
  }
  .lrg-v2-calc-result-value {
    font-family: 'Fraunces', serif;
    font-size: 34px;
    font-weight: 700;
    color: var(--lrg-gold-bright);
    letter-spacing: -0.01em;
    margin-bottom: 4px;
  }
  .lrg-v2-calc-result-detail {
    font-size: 12.5px;
    color: rgba(255,255,255,0.7);
    line-height: 1.45;
  }
  .lrg-v2-calc-cta {
    width: 100%;
    background: linear-gradient(135deg, var(--lrg-red) 0%, var(--lrg-red-bright) 100%);
    color: var(--lrg-white) !important;
    border: none;
    padding: 14px;
    border-radius: 8px;
    font-weight: 700;
    font-size: 14.5px;
    cursor: pointer;
    transition: all 0.2s;
    margin-top: 12px;
    font-family: inherit;
    text-decoration: none !important;
    display: block;
    text-align: center;
  }
  .lrg-v2-calc-cta:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(200, 16, 46, 0.40);
    color: var(--lrg-white) !important;
  }

  /* RESPONSIVE */
  @media (max-width: 980px) {
    .lrg-v2-hero { padding: 56px 0 64px; }
    .lrg-v2-hero-inner { grid-template-columns: 1fr; gap: 40px; }
    .lrg-v2-statbar-inner { grid-template-columns: repeat(2, 1fr); gap: 24px; }
    .lrg-v2-stat:nth-child(2) { border-right: none; }
    .lrg-v2-featured { grid-template-columns: 1fr; }
    .lrg-v2-featured-img { height: 320px; }
    .lrg-v2-featured-body { padding: 32px 28px 36px; }
    .lrg-v2-grid { grid-template-columns: repeat(2, 1fr); }
    .lrg-v2-sections { grid-template-columns: repeat(2, 1fr); }
    .lrg-v2-reviews-layout { grid-template-columns: 1fr; }
    .lrg-v2-calc-wrap { grid-template-columns: 1fr; gap: 32px; }
    .lrg-v2-section { padding: 64px 0; }
  }
  @media (max-width: 640px) {
    .lrg-v2-hero-ctas { flex-direction: column; align-items: stretch; }
    .lrg-v2-btn { width: 100%; }
    .lrg-v2-statbar-inner { grid-template-columns: 1fr; }
    .lrg-v2-stat { border-right: none; border-bottom: 1px solid var(--lrg-gray-100); padding-bottom: 24px; }
    .lrg-v2-stat:last-child { border-bottom: none; padding-bottom: 0; }
    .lrg-v2-grid { grid-template-columns: 1fr; }
    .lrg-v2-sections { grid-template-columns: 1fr; }
    .lrg-v2-review-featured-photo { height: 280px; }
    .lrg-v2-section { padding: 56px 0; }
    .lrg-v2-cta-band { padding: 64px 0; }
  }
</style>

<div class="lrg-v2-home">

<div class="lrg-v2-staging-banner">Staging Preview — Homepage V2.1.1</div>

<!-- HERO -->
<section class="lrg-v2-hero">
  <div class="lrg-v2-container">
    <div class="lrg-v2-hero-inner">
      <div class="lrg-v2-hero-eyebrow">Texas Real Estate · San Antonio · Austin · Killeen</div>
      <h1 class="lrg-v2-hero-h1">
        Texas real estate, written by <em>people who actually do it.</em>
      </h1>
      <p class="lrg-v2-hero-sub">
        Practical guides on buying, selling, VA loans, and living in San Antonio, Austin, and Central Texas. Written by the LRG team from over 20 years of closing real transactions — not from a content farm.
      </p>
      <div class="lrg-v2-hero-ctas">
        <a href="/lrg-blog/connect-with-lrg/" class="lrg-v2-btn lrg-v2-btn-primary">Talk to an LRG Specialist →</a>
        <a href="#latest" class="lrg-v2-btn lrg-v2-btn-secondary">Read Latest Stories</a>
      </div>
      <div class="lrg-v2-hero-trust">
        <div class="lrg-v2-hero-trust-item">
          <span class="lrg-v2-hero-stars">★★★★★</span>
          <span>4.9 from 3,627+ Google & Zillow reviews</span>
        </div>
        <div class="lrg-v2-hero-trust-item">Veteran-Owned & Operated</div>
        <div class="lrg-v2-hero-trust-item">Locally rooted</div>
      </div>
    </div>
  </div>
</section>

<!-- STAT BAR -->
<section class="lrg-v2-statbar">
  <div class="lrg-v2-container">
    <div class="lrg-v2-statbar-inner">
      <div class="lrg-v2-stat">
        <div class="lrg-v2-stat-num">3,627<em>+</em></div>
        <div class="lrg-v2-stat-label">Verified reviews</div>
      </div>
      <div class="lrg-v2-stat">
        <div class="lrg-v2-stat-num">4.9<em>★</em></div>
        <div class="lrg-v2-stat-label">Average rating</div>
      </div>
      <div class="lrg-v2-stat">
        <div class="lrg-v2-stat-num">20<em>+yr</em></div>
        <div class="lrg-v2-stat-label">Serving Texas</div>
      </div>
      <div class="lrg-v2-stat">
        <div class="lrg-v2-stat-num">100<em>%</em></div>
        <div class="lrg-v2-stat-label">Veteran Owned & Operated</div>
      </div>
    </div>
  </div>
</section>

<!-- REVIEWS — VALN-style featured + 3 stack, right under hero/stat bar -->
<section class="lrg-v2-section">
  <div class="lrg-v2-container">
    <div class="lrg-v2-section-header">
      <div class="lrg-v2-section-eyebrow">Real Client Reviews</div>
      <h2 class="lrg-v2-section-h2">Hear from people we've <em>actually helped.</em></h2>
      <p class="lrg-v2-section-sub">Real Google reviews from clients who closed with the LRG team. No paid testimonials, no actor headshots.</p>
    </div>

    <div class="lrg-v2-reviews-layout">

      <!-- Featured review with photo -->
      <div class="lrg-v2-review-featured">
        <?php if ( ! empty( $featured_review['photo'] ) ) : ?>
        <div class="lrg-v2-review-featured-photo">
          <img src="<?php echo esc_url( $featured_review['photo'] ); ?>" alt="<?php echo esc_attr( $featured_review['author_name'] ); ?> at her new home" loading="lazy">
        </div>
        <?php endif; ?>
        <div class="lrg-v2-review-featured-body">
          <div class="lrg-v2-review-featured-badge">★ Featured Review</div>
          <div class="lrg-v2-review-featured-stars">★★★★★</div>
          <p class="lrg-v2-review-featured-quote"><?php echo esc_html( $featured_review['text'] ); ?></p>
          <div class="lrg-v2-review-featured-author">
            <div class="lrg-v2-review-featured-avatar"><?php echo esc_html( $featured_review['author_initials'] ); ?></div>
            <div>
              <div class="lrg-v2-review-featured-name"><?php echo esc_html( $featured_review['author_name'] ); ?></div>
              <div class="lrg-v2-review-featured-detail"><?php echo esc_html( $featured_review['time_relative'] ); ?></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Stack of 3 supporting reviews -->
      <div class="lrg-v2-reviews-stack">
        <?php foreach ( $reviews as $r ) :
          $initials = '';
          $name_parts = explode( ' ', trim( $r['author_name'] ) );
          foreach ( $name_parts as $part ) {
            if ( $part !== '' ) $initials .= strtoupper( substr( $part, 0, 1 ) );
            if ( strlen( $initials ) >= 2 ) break;
          }
        ?>
        <div class="lrg-v2-review-stack-card">
          <div class="lrg-v2-review-stack-stars">★★★★★</div>
          <p class="lrg-v2-review-stack-quote"><?php echo esc_html( $r['text'] ); ?></p>
          <div class="lrg-v2-review-stack-author">
            <div class="lrg-v2-review-stack-avatar"><?php echo esc_html( $initials ?: '★' ); ?></div>
            <div>
              <div class="lrg-v2-review-stack-name"><?php echo esc_html( $r['author_name'] ); ?></div>
              <div class="lrg-v2-review-stack-detail"><?php echo esc_html( $r['time_relative'] ); ?> · <?php echo esc_html( $r['source'] ?? 'Google' ); ?> Review</div>
            </div>
          </div>
        </div>
        <?php endforeach; ?>
      </div>

    </div>

    <div class="lrg-v2-reviews-meta">
      <div class="lrg-v2-reviews-meta-stars">★★★★★</div>
      <div class="lrg-v2-reviews-meta-text"><strong>4.9 / 5</strong> from 3,627+ verified reviews — 1,180+ on Google, 2,447+ on Zillow</div>
      <div class="lrg-v2-reviews-meta-links">
        <a href="/lrg-blog/reviews/" class="lrg-v2-reviews-meta-link-primary">Read all reviews →</a>
        <a href="https://www.google.com/search?q=Levi+Rodgers+Real+Estate+Group+reviews" target="_blank" rel="noopener" class="lrg-v2-reviews-meta-link-secondary">View on Google ↗</a>
        <a href="https://www.zillow.com/profile/VA%20Texas%20Vet%20Expert#reviews" target="_blank" rel="noopener" class="lrg-v2-reviews-meta-link-secondary">View on Zillow ↗</a>
      </div>
    </div>
  </div>
</section>

<!-- CALCULATOR — Affordability tool, San Antonio defaults -->
<section class="lrg-v2-section dark">
  <div class="lrg-v2-container">
    <div class="lrg-v2-calc-wrap">
      <div class="lrg-v2-calc-content">
        <div class="lrg-v2-calc-content-eyebrow">Affordability Calculator</div>
        <h2 class="lrg-v2-calc-content-h2">How much home can <em>you afford?</em></h2>
        <p class="lrg-v2-calc-content-text">Run the numbers before you start touring homes. Built on Texas-specific rates and property taxes — what you'll actually qualify for, not a generic national estimate.</p>
        <ul class="lrg-v2-calc-content-bullets">
          <li class="lrg-v2-calc-content-bullet">Texas property tax rates baked in (~2.2% effective)</li>
          <li class="lrg-v2-calc-content-bullet">36% backend DTI cap (standard conventional qualifying)</li>
          <li class="lrg-v2-calc-content-bullet">PITI estimate at today's market rate</li>
          <li class="lrg-v2-calc-content-bullet">No credit pull, no email required</li>
        </ul>
        <p class="lrg-v2-calc-content-text" style="margin-top: 8px;"><strong style="color: var(--lrg-white);">Want a real lender read?</strong> Connect with an LRG specialist for an actual pre-qualification based on your full financial picture.</p>
      </div>

      <div class="lrg-v2-calc-card">
        <div class="lrg-v2-calc-card-inner">
          <div class="lrg-v2-calc-card-label">Quick Affordability Check</div>
          <div class="lrg-v2-calc-card-title">Texas home affordability calculator</div>
          <p class="lrg-v2-calc-card-sub">60 seconds. No credit pull. Real numbers using Texas property tax rates.</p>

          <div class="lrg-v2-calc">
            <div class="lrg-v2-calc-field">
              <label class="lrg-v2-calc-label" for="lrgV2Income">Annual household income</label>
              <input type="text" class="lrg-v2-calc-input" id="lrgV2Income" placeholder="$85,000" value="$85,000">
            </div>
            <div class="lrg-v2-calc-field">
              <label class="lrg-v2-calc-label" for="lrgV2Down">Down payment</label>
              <input type="text" class="lrg-v2-calc-input" id="lrgV2Down" placeholder="$25,000" value="$25,000">
            </div>
            <div class="lrg-v2-calc-field">
              <label class="lrg-v2-calc-label" for="lrgV2Debts">Monthly debts (car, student loans, credit cards)</label>
              <input type="text" class="lrg-v2-calc-input" id="lrgV2Debts" placeholder="$500" value="$500">
            </div>

            <div class="lrg-v2-calc-result">
              <div class="lrg-v2-calc-result-label">Estimated home price you can afford</div>
              <div class="lrg-v2-calc-result-value" id="lrgV2ResultValue">$295,000</div>
              <div class="lrg-v2-calc-result-detail" id="lrgV2ResultDetail">~$2,150/mo PITI at 6.75% rate. San Antonio median is $285K — Austin median is $525K.</div>
            </div>

            <a href="/lrg-blog/connect-with-lrg/" class="lrg-v2-calc-cta">Get a Real Pre-Qualification →</a>
          </div>
        </div>
      </div>
    </div>
  </div>
</section>

<?php if ( $featured ) : ?>
<!-- FEATURED ARTICLE -->
<section class="lrg-v2-section alt">
  <div class="lrg-v2-container">
    <div class="lrg-v2-section-header">
      <div class="lrg-v2-section-eyebrow">This Week's Feature</div>
      <h2 class="lrg-v2-section-h2">The story <em>everyone's reading.</em></h2>
    </div>
    <article class="lrg-v2-featured">
      <div class="lrg-v2-featured-img">
        <?php if ( $featured['thumb'] ) : ?>
          <img src="<?php echo esc_url( $featured['thumb'] ); ?>" alt="<?php echo esc_attr( $featured['title'] ); ?>">
        <?php else : ?>
          <div class="lrg-v2-featured-img-placeholder"></div>
        <?php endif; ?>
      </div>
      <div class="lrg-v2-featured-body">
        <div class="lrg-v2-featured-tags">
          <span class="lrg-v2-featured-pill">Featured</span>
          <?php if ( $featured['category'] ) : ?>
            <span class="lrg-v2-featured-cat"><?php echo esc_html( $featured['category'] ); ?></span>
          <?php endif; ?>
        </div>
        <h3 class="lrg-v2-featured-title">
          <a href="<?php echo esc_url( $featured['permalink'] ); ?>"><?php echo esc_html( $featured['title'] ); ?></a>
        </h3>
        <p class="lrg-v2-featured-excerpt"><?php echo esc_html( $featured['excerpt'] ); ?></p>
        <div class="lrg-v2-featured-meta">
          <a href="<?php echo esc_url( $featured['permalink'] ); ?>" class="lrg-v2-featured-link">Read full article →</a>
          <span class="lrg-v2-featured-readtime"><?php echo esc_html( $featured['read_time'] ); ?> min read</span>
        </div>
      </div>
    </article>
  </div>
</section>
<?php endif; ?>

<!-- LATEST ARTICLES GRID -->
<section class="lrg-v2-section" id="latest">
  <div class="lrg-v2-container">
    <div class="lrg-v2-section-header">
      <div class="lrg-v2-section-eyebrow">Latest Stories</div>
      <h2 class="lrg-v2-section-h2">Recent <em>from the team.</em></h2>
      <p class="lrg-v2-section-sub">Fresh analysis, market reads, and practical guides from the LRG agents and specialists.</p>
    </div>
    <div class="lrg-v2-grid">
      <?php foreach ( $grid_articles as $a ) : ?>
        <a href="<?php echo esc_url( $a['permalink'] ); ?>" style="text-decoration:none;color:inherit;display:block;">
          <article class="lrg-v2-card">
            <div class="lrg-v2-card-img">
              <?php if ( $a['thumb'] ) : ?>
                <img src="<?php echo esc_url( $a['thumb'] ); ?>" alt="<?php echo esc_attr( $a['title'] ); ?>">
              <?php else : ?>
                <div class="lrg-v2-card-img-placeholder"></div>
              <?php endif; ?>
            </div>
            <div class="lrg-v2-card-body">
              <?php if ( $a['category'] ) : ?>
                <div class="lrg-v2-card-cat"><?php echo esc_html( $a['category'] ); ?></div>
              <?php endif; ?>
              <h3 class="lrg-v2-card-title"><?php echo esc_html( $a['title'] ); ?></h3>
              <p class="lrg-v2-card-excerpt"><?php echo esc_html( $a['excerpt'] ); ?></p>
              <div class="lrg-v2-card-meta">
                <span class="lrg-v2-card-date"><?php echo esc_html( $a['date'] ); ?></span>
                <span class="lrg-v2-card-readtime"><?php echo esc_html( $a['read_time'] ); ?> min read</span>
              </div>
            </div>
          </article>
        </a>
      <?php endforeach; ?>
    </div>
    <div class="lrg-v2-grid-cta">
      <a href="/lrg-blog/archive/">Browse all articles →</a>
    </div>
  </div>
</section>

<!-- BROWSE BY SECTION -->
<section class="lrg-v2-section paper">
  <div class="lrg-v2-container">
    <div class="lrg-v2-section-header">
      <div class="lrg-v2-section-eyebrow">The Sections</div>
      <h2 class="lrg-v2-section-h2">Organized by <em>how you actually search.</em></h2>
      <p class="lrg-v2-section-sub">Six topic hubs covering the questions our buyers, sellers, and Veterans ask most.</p>
    </div>
    <div class="lrg-v2-sections">
      <?php foreach ( $cats as $i => $c ) : ?>
        <a href="<?php echo esc_url( $c['link'] ); ?>" class="lrg-v2-section-card">
          <div class="lrg-v2-section-card-num">0<?php echo $i + 1; ?></div>
          <h3 class="lrg-v2-section-card-title"><?php echo esc_html( $c['name'] ); ?></h3>
          <div class="lrg-v2-section-card-count"><?php echo intval( $c['count'] ); ?> articles</div>
          <span class="lrg-v2-section-card-arrow">Explore section →</span>
        </a>
      <?php endforeach; ?>
    </div>
  </div>
</section>

<!-- CTA BAND -->
<section class="lrg-v2-cta-band">
  <div class="lrg-v2-container">
    <div class="lrg-v2-cta-band-inner">
      <div class="lrg-v2-cta-band-eyebrow">Ready when you are</div>
      <h2 class="lrg-v2-cta-band-h2">When you want a real <em>conversation.</em></h2>
      <p class="lrg-v2-cta-band-sub">No high-pressure sales calls. No auto-responder spam. An LRG specialist who knows your market personally reviews your situation and reaches out within one business day.</p>
      <a href="/lrg-blog/connect-with-lrg/" class="lrg-v2-btn lrg-v2-btn-primary" style="background:linear-gradient(135deg, var(--lrg-red) 0%, var(--lrg-red-bright) 100%);">Connect with LRG →</a>
      <div class="lrg-v2-cta-band-trust">
        <span class="lrg-v2-hero-stars">★★★★★</span>4.9 from 3,627+ Google & Zillow reviews
      </div>
    </div>
  </div>
</section>

</div>

<script>
(function() {
  'use strict';
  var incomeInput = document.getElementById('lrgV2Income');
  var downInput = document.getElementById('lrgV2Down');
  var debtsInput = document.getElementById('lrgV2Debts');
  var resultValue = document.getElementById('lrgV2ResultValue');
  var resultDetail = document.getElementById('lrgV2ResultDetail');
  if (!incomeInput) return;

  function parseCurrency(s) {
    if (!s) return 0;
    return parseFloat(String(s).replace(/[^0-9.]/g, '')) || 0;
  }
  function formatCurrency(n) {
    return '$' + Math.round(n).toLocaleString();
  }
  function calc() {
    var income = parseCurrency(incomeInput.value);
    var down = parseCurrency(downInput.value);
    var debts = parseCurrency(debtsInput.value);
    var monthlyIncome = income / 12;

    // 36% backend DTI (conventional standard)
    var maxPiti = (monthlyIncome * 0.36) - debts;

    // Mortgage math: monthly rate, 30yr term, Texas property tax ~2.2% effective, insurance ~$1200/yr
    var rate = 0.0675 / 12;
    var n = 360;
    var taxRate = 0.022 / 12; // monthly property tax rate
    var insRate = 100 / 100000; // approximate per $100K home value
    var monthlyPaymentFactor = rate * Math.pow(1 + rate, n) / (Math.pow(1 + rate, n) - 1);

    // PITI = P(payment_factor) + T*P + I*P, where P is home price (not loan amount)
    // Loan amount = price - down
    // monthly P&I = (price - down) * payment_factor
    // monthly T+I = price * (taxRate + insRate)
    // So: maxPiti = (price - down) * pf + price * (tax + ins)
    // maxPiti = price * pf - down * pf + price * (tax + ins)
    // maxPiti = price * (pf + tax + ins) - down * pf
    // maxPiti + down * pf = price * (pf + tax + ins)
    // price = (maxPiti + down * pf) / (pf + tax + ins)
    var homePrice = (maxPiti + down * monthlyPaymentFactor) / (monthlyPaymentFactor + taxRate + insRate);

    if (homePrice < 1000 || isNaN(homePrice) || maxPiti < 100) {
      resultValue.textContent = '—';
      resultDetail.textContent = 'Add your household income to see what you can afford.';
      return;
    }

    var loanAmt = homePrice - down;
    var pAndI = loanAmt * monthlyPaymentFactor;
    var taxIns = homePrice * (taxRate + insRate);
    var totalPiti = pAndI + taxIns;

    resultValue.textContent = formatCurrency(homePrice);
    resultDetail.textContent = '~' + formatCurrency(Math.max(0, totalPiti)) + '/mo PITI at 6.75% rate. San Antonio median is $285K, Austin median is $525K. Real lender numbers vary.';
  }
  function bindInput(input) {
    input.addEventListener('input', calc);
    input.addEventListener('blur', function() {
      var v = parseCurrency(input.value);
      if (v > 0) input.value = formatCurrency(v);
      else input.value = '';
    });
  }
  bindInput(incomeInput);
  bindInput(downInput);
  bindInput(debtsInput);
  calc();
})();
</script>
<?php
}
