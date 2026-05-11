<?php
/**
 * Plugin Name: LRG Reviews Page V1 (Staging)
 * Description: Replaces /lrg-blog/reviews/ page content with custom V1 build. Divi-compatible — hooks the_content so Divi's theme builder header and footer render normally. Staging only. Combines Google + Zillow reviews.
 * Version: 1.1.0
 * Author: Randall's SEO System
 *
 * INSTALL: Drop in /wp-content/mu-plugins/ on STAGING ONLY.
 * REMOVE: Delete file, or rename to .disabled
 *
 * Requires: A WP page with slug "reviews" (created at /lrg-blog/reviews/)
 * Data source: rss_reviews_list option (from rss-google-reviews plugin)
 */

if ( ! defined( 'ABSPATH' ) ) exit;

if ( ! isset( $_SERVER['HTTP_HOST'] ) || strpos( $_SERVER['HTTP_HOST'], 'wpenginepowered.com' ) === false ) {
    return;
}

add_filter( 'the_content', 'lrg_reviews_page_content', 99 );

function lrg_reviews_page_content( $content ) {
    if ( ! is_page( 'reviews' ) ) return $content;
    if ( ! in_the_loop() ) return $content;
    if ( ! is_main_query() ) return $content;

    ob_start();
    lrg_reviews_page_output();
    return ob_get_clean();
}

/**
 * Get all reviews, normalized — combines Google + Zillow
 */
function lrg_reviews_get_all() {
    $reviews = get_option( 'rss_reviews_list', array() );

    // Hardcoded fallback — real Google + Zillow reviews
    $fallback = array(
        // Zillow reviews (real, from Levi's profile)
        array(
            'author_name' => 'Alex',
            'rating' => 5,
            'text' => "I couldn't have asked for a better realtor during my home buying process. He was patient, knowledgeable, and genuinely cared about helping me find the right home instead of just making a sale. He always had my best interests in mind and explained everything clearly.",
            'time_relative' => '5/7/2026',
            'source' => 'Zillow',
            'agent' => 'Eli Perez',
        ),
        array(
            'author_name' => 'ehernandez678',
            'rating' => 5,
            'text' => "Russell was very patient and tenacious in making sure our property sold. Russell has the experience and knowledge of a true real estate professional. His ability is well suited for anyone who needs assistance in their real estate transaction.",
            'time_relative' => '5/6/2026',
            'source' => 'Zillow',
            'agent' => 'Russell Marks',
        ),
        array(
            'author_name' => 'em187662',
            'rating' => 5,
            'text' => "Eli is an exceptionally talented person, great attention to detail, friendly, outgoing personality, took time to check our needs, knowledgeable in his trade, we did recommend to neighbors.",
            'time_relative' => '5/6/2026',
            'source' => 'Zillow',
            'agent' => 'Eli Perez',
        ),
        array(
            'author_name' => 'alinieto fam1',
            'rating' => 5,
            'text' => "Working with our realtor was an amazing experience from start to finish. She was knowledgeable, responsive, and truly had our best interests in mind throughout the entire process. She made what could have been a stressful experience feel smooth and manageable.",
            'time_relative' => '5/6/2026',
            'source' => 'Zillow',
            'agent' => 'Naishla Cavazos',
        ),
        array(
            'author_name' => 'Victoria Magallan',
            'rating' => 5,
            'text' => "Naishla helped me and my family find the perfect home. Very professional in the whole process and answered all our questions. First time home buyers. Highly recommend Naishla for your home buying experience.",
            'time_relative' => '5/6/2026',
            'source' => 'Zillow',
            'agent' => 'Naishla Cavazos',
        ),
        array(
            'author_name' => 'Denise',
            'rating' => 5,
            'text' => "Elisa was incredible to work with as my agent. She's professional, responsive, and truly looks out for her clients every step of the way. I will refer clients to her as she's always been consistent, reliable, and great to partner with. Highly recommend!",
            'time_relative' => '5/5/2026',
            'source' => 'Zillow',
            'agent' => 'Elisa Nabers',
        ),
        array(
            'author_name' => 'Jonathon Torres',
            'rating' => 5,
            'text' => "I had an excellent experience working with Elvia. Communication was outstanding — she was always responsive to calls, texts, and emails, and took the time to answer every question I had. She went above and beyond to make sure I felt comfortable and informed throughout the entire process.",
            'time_relative' => '5/5/2026',
            'source' => 'Zillow',
            'agent' => 'Elvia Lugo',
        ),
        array(
            'author_name' => 'Jeanette Rodriguez',
            'rating' => 5,
            'text' => "Jennifer was so awesome, she went above and beyond for us. She helped us every step of the way, any questions we had she either answered or got the answer for us and responded quickly. We will definitely work with her again and refer her to all our friends & family.",
            'time_relative' => '5/4/2026',
            'source' => 'Zillow',
            'agent' => 'Jennifer Garcia',
        ),
        array(
            'author_name' => 'Henry Wallis',
            'rating' => 5,
            'text' => "As a first-time home buyer relocating from the United Kingdom to San Antonio, I truly had no idea where to begin. The home buying process in the U.S. is quite different, and it initially felt overwhelming — but working with Tania completely changed that experience.",
            'time_relative' => '5/4/2026',
            'source' => 'Zillow',
            'agent' => 'Tania Michael',
        ),
        array(
            'author_name' => 'Mandy Pallock',
            'rating' => 5,
            'text' => "Trisha was fully available to show us properties we were interested in on an expedited schedule. She answered questions, provided expertise, and was friendly and professional. If you're looking for a new place to call home in the greater San Antonio area, I highly recommend her.",
            'time_relative' => '5/4/2026',
            'source' => 'Zillow',
            'agent' => 'Trisha Cobb',
        ),
        array(
            'author_name' => 'Keanu Marquez',
            'rating' => 5,
            'text' => "Sam was absolutely fantastic! Extremely welcoming and knowledgeable. We found him by accident and what an accident it was! Since the very beginning he's been the best and understanding and really cares for his clients! 10 out of 10, I recommend him to anyone!",
            'time_relative' => '5/1/2026',
            'source' => 'Zillow',
            'agent' => 'Samuel Sanchez',
        ),
        array(
            'author_name' => 'Olivia Cohn',
            'rating' => 5,
            'text' => "Crystall was a life saver!! As a first time home buyer, I could not have done it without her. She was so informative and knowledgeable. Crystall was there for me through the whole process. I could not recommend her enough.",
            'time_relative' => '5/1/2026',
            'source' => 'Zillow',
            'agent' => 'Crystall Massey',
        ),
        array(
            'author_name' => 'Amy Tait',
            'rating' => 5,
            'text' => "April did an outstanding service on helping with purchasing our new home. She walked us through every step of the way. We could not have done it without her help! Blessed to have her as our realtor! Very knowledgeable.",
            'time_relative' => '4/30/2026',
            'source' => 'Zillow',
            'agent' => 'April Walker',
        ),
        array(
            'author_name' => 'Marty Stubbs',
            'rating' => 5,
            'text' => "Chris was outstanding through the whole process. He went above and beyond to make things happen and fix situations. Should I decide to buy again he is my first call.",
            'time_relative' => '4/28/2026',
            'source' => 'Zillow',
            'agent' => 'Christopher Pate',
        ),
        array(
            'author_name' => 'Robin Jonge',
            'rating' => 5,
            'text' => "Rosemary did an awesome job providing us with a lot of knowledge and information when reviewing houses and did a lot of the breakdown of costs as well both in the sale process but also with the differences with houses. She was very lovely and sweet to work with.",
            'time_relative' => '4/27/2026',
            'source' => 'Zillow',
            'agent' => 'Rosemary G. Ford',
        ),
        array(
            'author_name' => 'rijker hutson',
            'rating' => 5,
            'text' => "Andre was fantastic to work with from start to finish. As a military family using a VA home loan and buying from out of state, we knew the process could be challenging, but he made it feel easy. He took the time to show us a variety of homes and really helped us get a sense of what we wanted.",
            'time_relative' => '4/27/2026',
            'source' => 'Zillow',
            'agent' => 'Andre Dickerson',
        ),
        array(
            'author_name' => 'Israel Lares',
            'rating' => 5,
            'text' => "Joseph went above and beyond to help us find our new home. Given we only had a week into town to find a home that meets our needs he didn't let that pressure get to him. He even treated us out to breakfast and lunch to really get to know us and to figure out what we were looking for.",
            'time_relative' => '4/26/2026',
            'source' => 'Zillow',
            'agent' => 'Joseph Rosen',
        ),
        array(
            'author_name' => 'Chris Hill',
            'rating' => 5,
            'text' => "Cedric was the realtor that I didn't know I needed. I really didn't expect to be guided as well through the search and buying process as he had done. His negotiation skills were way better than what I was prepared to offer and far exceeded what I expected.",
            'time_relative' => '4/26/2026',
            'source' => 'Zillow',
            'agent' => 'Cedric Akodokoun',
        ),
        array(
            'author_name' => 'Johnnie Paige',
            'rating' => 5,
            'text' => "We have worked with many realtors over the years for both buying and selling properties. Sarah is hands down the absolute best realtor you could be blessed to work with! She is very prompt and proactive in taking care of any task you can think of and then some. She has become a family friend.",
            'time_relative' => '4/22/2026',
            'source' => 'Zillow',
            'agent' => 'Sarah Custis',
        ),
        array(
            'author_name' => 'Sara V',
            'rating' => 5,
            'text' => "Jackie provided outstanding guidance throughout our entire home-buying journey. Her communication was exceptional — she was always available whenever we had questions or needed assistance, no matter the time. The passion she brings to her work was both reassuring and encouraging.",
            'time_relative' => '4/25/2026',
            'source' => 'Zillow',
            'agent' => 'Jackie Cardenas',
        ),
        // Google reviews
        array(
            'author_name' => 'Phat Vath',
            'rating' => 5,
            'text' => "Had the privilege to work with James. Words can't come close to describe how grateful me and my wife are for having him guide us through the process of buying our first home. He was very professional, knowledgeable, and patient throughout the journey.",
            'time_relative' => '6 days ago',
            'source' => 'Google',
            'agent' => 'James',
        ),
        array(
            'author_name' => 'Jenn Hunt-Petrak',
            'rating' => 5,
            'text' => "Imelda Luquin helped our family understand some landlord/tenant information when we had to deal with some difficult situations. She was extremely knowledgeable and kind. When we decided to sell the property she was there to guide us through the process.",
            'time_relative' => '6 days ago',
            'source' => 'Google',
            'agent' => 'Imelda Luquin',
        ),
        array(
            'author_name' => 'Elizabeth Melendez',
            'rating' => 5,
            'text' => "Definitely recommend Bianca Haseloff, she was the best and always there for us. Answered all our questions, she was patient and knowledgeable. She made the whole process smooth and stress-free. We are so happy with our new home!",
            'time_relative' => '1 week ago',
            'source' => 'Google',
            'agent' => 'Bianca Haseloff',
        ),
        array(
            'author_name' => 'Josecarlos Violeta',
            'rating' => 5,
            'text' => "The absolute GOAT Stephanie Campa closed on my purchase negotiating for me a 30k reduction in the original asking price for a home. This netted me 10k equity FROM THE RIP! She was extremely knowledgeable, poignant, diligent and everything you need in an REA. Above all that she was kind.",
            'time_relative' => '8 weeks ago',
            'source' => 'Google',
            'agent' => 'Stephanie Campa',
        ),
        array(
            'author_name' => 'Abujor 143',
            'rating' => 5,
            'text' => "Levi Rodgers Real Estate Group provided an outstanding real estate experience! The team was professional, knowledgeable, and made the entire process smooth and stress-free. They communicated clearly at every step, ensuring I always felt informed and confident.",
            'time_relative' => '2 weeks ago',
            'source' => 'Google',
            'agent' => 'LRG Team',
        ),
        array(
            'author_name' => 'Sara Rodriguez',
            'rating' => 5,
            'text' => "Vikki has been a dream to work with! She has taken all of our concerns to heart and made the extremely stressful home buying process easier. She is very knowledgeable, patient, and always available to answer questions.",
            'time_relative' => '3 weeks ago',
            'source' => 'Google',
            'agent' => 'Vikki Leggit',
        ),
    );

    if ( empty( $reviews ) || ! is_array( $reviews ) ) {
        return $fallback;
    }

    $normalized = array();
    foreach ( $reviews as $r ) {
        if ( ! is_array( $r ) ) continue;

        $name = $r['author_name'] ?? $r['name'] ?? $r['reviewer_name'] ?? $r['author'] ?? '';
        $text = $r['text'] ?? $r['review'] ?? $r['review_text'] ?? $r['content'] ?? $r['body'] ?? '';
        $rating = intval( $r['rating'] ?? $r['stars'] ?? $r['score'] ?? 5 );
        $time = $r['time'] ?? $r['timestamp'] ?? $r['created'] ?? 0;
        $time_str = $r['relative_time_description'] ?? $r['time_relative'] ?? '';
        $source = $r['source'] ?? 'Google';

        if ( empty( $time_str ) && $time ) {
            $time_str = human_time_diff( $time, current_time( 'timestamp' ) ) . ' ago';
        }

        if ( empty( $text ) || empty( $name ) ) continue;

        $normalized[] = array(
            'author_name' => $name,
            'rating' => $rating,
            'text' => $text,
            'time_relative' => $time_str ?: 'Recently',
            'time' => intval( $time ),
            'source' => $source,
        );
    }

    if ( empty( $normalized ) ) {
        return $fallback;
    }

    // Sort by time desc (most recent first)
    usort( $normalized, function( $a, $b ) {
        return ( $b['time'] ?? 0 ) - ( $a['time'] ?? 0 );
    });

    return $normalized;
}

/**
 * Initials from name
 */
function lrg_reviews_initials( $name ) {
    $initials = '';
    $parts = explode( ' ', trim( $name ) );
    foreach ( $parts as $p ) {
        if ( $p === '' ) continue;
        $initials .= strtoupper( substr( $p, 0, 1 ) );
        if ( strlen( $initials ) >= 2 ) break;
    }
    return $initials ?: '★';
}

function lrg_reviews_page_output() {
    $all_reviews = lrg_reviews_get_all();
    $total_count = count( $all_reviews );
    $initial_show = 30; // First batch
    $first_batch = array_slice( $all_reviews, 0, $initial_show );
    $remaining = array_slice( $all_reviews, $initial_show );
    ?>
<style>
  .lrg-rv-page {
    --lrg-navy: #0F1F4A;
    --lrg-navy-deep: #08142B;
    --lrg-navy-soft: #1A2C52;
    --lrg-red: #C8102E;
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
  .lrg-rv-page *, .lrg-rv-page *::before, .lrg-rv-page *::after { box-sizing: border-box; }
  .lrg-rv-page a { text-decoration: none; }
  .lrg-rv-container { max-width: 1280px; margin: 0 auto; padding: 0 24px; }

  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Fraunces:opsz,wght,SOFT@9..144,400;9..144,500;9..144,600;9..144,700&display=swap');

  /* Hide page title and remove padding above hero */
  body.page .entry-title,
  body.page #left-area > article > .entry-title,
  body.page #page-container .et_post_meta_wrapper,
  body.page .et_post_meta_wrapper {
    display: none !important;
  }
  body.page #main-content,
  body.page #et-main-area,
  body.page #left-area,
  body.page #content-area,
  body.page .et_pb_section_0_tb_body,
  body.page #page-container,
  body.page .container.et_pb_extra_container,
  body.page #left-area > article,
  body.page .et_pb_post {
    padding-top: 0 !important;
    margin-top: 0 !important;
  }
  body.page #left-area > article > .entry-content,
  body.page .et_pb_post .entry-content {
    padding-top: 0 !important;
    margin-top: 0 !important;
  }

  .lrg-rv-banner {
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
  .lrg-rv-hero {
    background:
      radial-gradient(circle at 85% 15%, rgba(212, 165, 116, 0.10) 0%, transparent 55%),
      radial-gradient(circle at 10% 90%, rgba(200, 16, 46, 0.08) 0%, transparent 50%),
      linear-gradient(180deg, var(--lrg-navy) 0%, var(--lrg-navy-deep) 100%);
    color: var(--lrg-white);
    padding: 72px 0 80px;
    position: relative;
    overflow: hidden;
    text-align: center;
  }
  .lrg-rv-hero::before {
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
  .lrg-rv-hero-inner { max-width: 880px; margin: 0 auto; position: relative; z-index: 1; }
  .lrg-rv-hero-eyebrow {
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
  .lrg-rv-hero-eyebrow::before {
    content: '';
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--lrg-gold-bright);
    box-shadow: 0 0 8px var(--lrg-gold);
  }
  .lrg-rv-hero-h1 {
    font-family: 'Fraunces', Georgia, serif;
    font-size: clamp(38px, 5vw, 60px);
    line-height: 1.05;
    font-weight: 500;
    letter-spacing: -0.025em;
    margin: 0 0 24px;
    color: var(--lrg-white);
  }
  .lrg-rv-hero-h1 em {
    color: var(--lrg-gold-bright);
    font-style: italic;
    font-weight: 600;
    text-shadow: 0 0 28px rgba(212, 165, 116, 0.35);
  }
  .lrg-rv-hero-sub {
    font-size: 18px;
    line-height: 1.6;
    color: rgba(255,255,255,0.86);
    margin: 0 auto 32px;
    max-width: 640px;
  }
  .lrg-rv-stats {
    display: inline-flex;
    gap: 48px;
    align-items: center;
    flex-wrap: wrap;
    justify-content: center;
    padding: 24px 0 0;
  }
  .lrg-rv-stat {
    text-align: center;
  }
  .lrg-rv-stat-num {
    font-family: 'Fraunces', serif;
    font-size: 44px;
    font-weight: 600;
    color: var(--lrg-gold-bright);
    letter-spacing: -0.025em;
    line-height: 1;
    margin-bottom: 6px;
  }
  .lrg-rv-stat-num em {
    color: var(--lrg-star);
    font-style: italic;
  }
  .lrg-rv-stat-label {
    font-size: 12px;
    color: rgba(255,255,255,0.7);
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }

  /* REVIEWS GRID */
  .lrg-rv-section { padding: 80px 0; background: var(--lrg-cream); }
  .lrg-rv-section-header {
    text-align: center;
    margin-bottom: 48px;
  }
  .lrg-rv-section-eyebrow {
    display: inline-block;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--lrg-red);
    margin-bottom: 14px;
  }
  .lrg-rv-section-h2 {
    font-family: 'Fraunces', serif;
    font-size: clamp(28px, 3.5vw, 40px);
    line-height: 1.15;
    font-weight: 500;
    letter-spacing: -0.025em;
    color: var(--lrg-navy);
    margin: 0 0 12px;
  }
  .lrg-rv-section-h2 em {
    color: var(--lrg-red);
    font-style: italic;
    font-weight: 600;
  }
  .lrg-rv-section-sub {
    font-size: 16px;
    color: var(--lrg-gray-500);
    line-height: 1.6;
    margin: 0 auto;
    max-width: 600px;
  }
  .lrg-rv-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 24px;
  }
  .lrg-rv-card {
    background: var(--lrg-white);
    border: 1px solid var(--lrg-gray-100);
    border-radius: 12px;
    padding: 28px 26px;
    transition: all 0.22s;
    display: flex;
    flex-direction: column;
    position: relative;
  }
  .lrg-rv-card:hover {
    border-color: var(--lrg-gold);
    box-shadow: 0 12px 32px rgba(15, 31, 74, 0.08);
    transform: translateY(-2px);
  }
  .lrg-rv-card::before {
    content: '"';
    position: absolute;
    top: 14px;
    right: 22px;
    font-family: 'Fraunces', serif;
    font-size: 60px;
    line-height: 1;
    color: var(--lrg-red);
    opacity: 0.10;
    font-weight: 700;
    pointer-events: none;
  }
  .lrg-rv-card-stars {
    color: var(--lrg-star);
    font-size: 15px;
    letter-spacing: 2px;
    margin-bottom: 14px;
  }
  .lrg-rv-card-text {
    font-family: 'Fraunces', serif;
    font-size: 15px;
    line-height: 1.6;
    color: var(--lrg-gray-700);
    margin: 0 0 18px;
    font-style: italic;
    letter-spacing: -0.005em;
    flex: 1;
  }
  .lrg-rv-card-text-collapsed {
    display: -webkit-box;
    -webkit-line-clamp: 5;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  .lrg-rv-card-expand {
    background: none;
    border: none;
    color: var(--lrg-red);
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    padding: 0;
    margin: -10px 0 14px;
    align-self: flex-start;
    text-decoration: none;
  }
  .lrg-rv-card-expand:hover { text-decoration: underline; }
  .lrg-rv-card-author {
    display: flex;
    align-items: center;
    gap: 12px;
    padding-top: 16px;
    border-top: 1px solid var(--lrg-gray-100);
  }
  .lrg-rv-card-avatar {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--lrg-navy) 0%, var(--lrg-navy-soft) 100%);
    color: var(--lrg-white);
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 13px;
    flex-shrink: 0;
  }
  .lrg-rv-card-name {
    font-size: 14px;
    font-weight: 700;
    color: var(--lrg-navy);
    line-height: 1.2;
    margin-bottom: 2px;
  }
  .lrg-rv-card-meta {
    font-size: 11.5px;
    color: var(--lrg-gray-400);
  }

  /* LOAD MORE */
  .lrg-rv-load-more-wrap {
    text-align: center;
    margin-top: 48px;
  }
  .lrg-rv-load-more {
    background: linear-gradient(135deg, var(--lrg-red) 0%, var(--lrg-red-bright) 100%);
    color: var(--lrg-white);
    border: none;
    padding: 14px 36px;
    border-radius: 8px;
    font-family: inherit;
    font-weight: 600;
    font-size: 15px;
    letter-spacing: 0.01em;
    cursor: pointer;
    transition: all 0.22s;
    box-shadow: 0 4px 16px rgba(200, 16, 46, 0.28);
  }
  .lrg-rv-load-more:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 28px rgba(200, 16, 46, 0.42);
  }
  .lrg-rv-load-more:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
  }
  .lrg-rv-load-more-meta {
    font-size: 13px;
    color: var(--lrg-gray-500);
    margin-top: 14px;
  }

  /* GOOGLE LINK */
  .lrg-rv-google-link {
    text-align: center;
    margin-top: 40px;
    padding-top: 40px;
    border-top: 1px solid var(--lrg-gray-200);
  }
  .lrg-rv-google-link a {
    color: var(--lrg-navy) !important;
    font-weight: 600;
    font-size: 15px;
    border-bottom: 1px solid var(--lrg-navy);
    padding-bottom: 2px;
  }
  .lrg-rv-google-link a:hover {
    color: var(--lrg-red) !important;
    border-color: var(--lrg-red);
  }

  /* RESPONSIVE */
  @media (max-width: 980px) {
    .lrg-rv-grid { grid-template-columns: repeat(2, 1fr); }
    .lrg-rv-hero { padding: 56px 0 64px; }
    .lrg-rv-stats { gap: 32px; }
  }
  @media (max-width: 640px) {
    .lrg-rv-grid { grid-template-columns: 1fr; }
    .lrg-rv-hero { padding: 48px 0 56px; }
    .lrg-rv-stats { gap: 24px; }
    .lrg-rv-stat-num { font-size: 36px; }
    .lrg-rv-section { padding: 56px 0; }
  }
</style>

<div class="lrg-rv-page">

<div class="lrg-rv-banner">Staging Preview — Reviews Page V1.1.0 — Google + Zillow</div>

<!-- HERO -->
<section class="lrg-rv-hero">
  <div class="lrg-rv-container">
    <div class="lrg-rv-hero-inner">
      <div class="lrg-rv-hero-eyebrow">Levi Rodgers Real Estate Group</div>
      <h1 class="lrg-rv-hero-h1">
        Real reviews. <em>Real clients.</em>
      </h1>
      <p class="lrg-rv-hero-sub">
        Every review below is a verified Google review from someone who actually closed with the LRG team. No paid testimonials. No actor headshots. Just real people who chose us for the biggest financial decision of their lives.
      </p>
      <div class="lrg-rv-stats">
        <div class="lrg-rv-stat">
          <div class="lrg-rv-stat-num">4.9<em>★</em></div>
          <div class="lrg-rv-stat-label">Average rating</div>
        </div>
        <div class="lrg-rv-stat">
          <div class="lrg-rv-stat-num">3,627<em>+</em></div>
          <div class="lrg-rv-stat-label">Total verified reviews</div>
        </div>
        <div class="lrg-rv-stat">
          <div class="lrg-rv-stat-num">2<em></em></div>
          <div class="lrg-rv-stat-label">Sources: Google & Zillow</div>
        </div>
      </div>
    </div>
  </div>
</section>

<!-- REVIEWS GRID -->
<section class="lrg-rv-section">
  <div class="lrg-rv-container">
    <div class="lrg-rv-section-header">
      <div class="lrg-rv-section-eyebrow">What clients are saying</div>
      <h2 class="lrg-rv-section-h2">Read every review, in their <em>own words.</em></h2>
      <p class="lrg-rv-section-sub">Sorted by most recent first. Click any review to expand and read the full story.</p>
    </div>

    <div class="lrg-rv-grid" id="lrg-rv-grid">
      <?php foreach ( $first_batch as $r ) :
        $initials = lrg_reviews_initials( $r['author_name'] );
        $text_length = mb_strlen( $r['text'] );
        $needs_expand = $text_length > 280;
      ?>
        <div class="lrg-rv-card">
          <div class="lrg-rv-card-stars">★★★★★</div>
          <p class="lrg-rv-card-text<?php echo $needs_expand ? ' lrg-rv-card-text-collapsed' : ''; ?>"><?php echo esc_html( $r['text'] ); ?></p>
          <?php if ( $needs_expand ) : ?>
            <button type="button" class="lrg-rv-card-expand" onclick="lrgRvExpand(this)">Read full review →</button>
          <?php endif; ?>
          <div class="lrg-rv-card-author">
            <div class="lrg-rv-card-avatar"><?php echo esc_html( $initials ); ?></div>
            <div>
              <div class="lrg-rv-card-name"><?php echo esc_html( $r['author_name'] ); ?></div>
              <div class="lrg-rv-card-meta"><?php echo esc_html( $r['time_relative'] ); ?> · <?php echo esc_html( $r['source'] ?? 'Google' ); ?> Review</div>
            </div>
          </div>
        </div>
      <?php endforeach; ?>
    </div>

    <?php if ( ! empty( $remaining ) ) : ?>
      <div class="lrg-rv-load-more-wrap">
        <button type="button" class="lrg-rv-load-more" id="lrg-rv-load-more">Load More Reviews</button>
        <div class="lrg-rv-load-more-meta">Showing <span id="lrg-rv-showing"><?php echo count( $first_batch ); ?></span> of <?php echo $total_count; ?> reviews</div>
      </div>

      <!-- Remaining reviews data embedded as JSON for JS to consume -->
      <script type="application/json" id="lrg-rv-data">
        <?php echo wp_json_encode( array_map( function( $r ) {
          return array(
            'name' => $r['author_name'],
            'initials' => lrg_reviews_initials( $r['author_name'] ),
            'text' => $r['text'],
            'time' => $r['time_relative'],
            'source' => $r['source'] ?? 'Google',
            'needs_expand' => mb_strlen( $r['text'] ) > 280,
          );
        }, $remaining ) ); ?>
      </script>
    <?php endif; ?>

    <div class="lrg-rv-google-link">
      <a href="https://www.google.com/search?q=Levi+Rodgers+Real+Estate+Group+reviews" target="_blank" rel="noopener" style="margin-right: 24px;">
        View on Google (1,180+) ↗
      </a>
      <a href="https://www.zillow.com/profile/VA%20Texas%20Vet%20Expert#reviews" target="_blank" rel="noopener">
        View on Zillow (2,447+) ↗
      </a>
    </div>
  </div>
</section>

</div><!-- /.lrg-rv-page -->

<script>
function lrgRvExpand(btn) {
  var card = btn.parentElement;
  var text = card.querySelector('.lrg-rv-card-text');
  text.classList.remove('lrg-rv-card-text-collapsed');
  btn.style.display = 'none';
}

(function() {
  var loadMoreBtn = document.getElementById('lrg-rv-load-more');
  var dataEl = document.getElementById('lrg-rv-data');
  var grid = document.getElementById('lrg-rv-grid');
  var showingEl = document.getElementById('lrg-rv-showing');
  if (!loadMoreBtn || !dataEl || !grid) return;

  var remaining;
  try {
    remaining = JSON.parse(dataEl.textContent);
  } catch (e) {
    loadMoreBtn.style.display = 'none';
    return;
  }

  var batchSize = 30;
  var index = 0;

  function escapeHtml(s) {
    var div = document.createElement('div');
    div.textContent = s == null ? '' : String(s);
    return div.innerHTML;
  }

  function renderBatch() {
    var batch = remaining.slice(index, index + batchSize);
    var html = '';
    batch.forEach(function(r) {
      var expandClass = r.needs_expand ? ' lrg-rv-card-text-collapsed' : '';
      var expandBtn = r.needs_expand
        ? '<button type="button" class="lrg-rv-card-expand" onclick="lrgRvExpand(this)">Read full review →</button>'
        : '';
      html += '<div class="lrg-rv-card">' +
        '<div class="lrg-rv-card-stars">★★★★★</div>' +
        '<p class="lrg-rv-card-text' + expandClass + '">' + escapeHtml(r.text) + '</p>' +
        expandBtn +
        '<div class="lrg-rv-card-author">' +
          '<div class="lrg-rv-card-avatar">' + escapeHtml(r.initials) + '</div>' +
          '<div>' +
            '<div class="lrg-rv-card-name">' + escapeHtml(r.name) + '</div>' +
            '<div class="lrg-rv-card-meta">' + escapeHtml(r.time) + ' · ' + escapeHtml(r.source || 'Google') + ' Review</div>' +
          '</div>' +
        '</div>' +
      '</div>';
    });
    grid.insertAdjacentHTML('beforeend', html);
    index += batchSize;
    var currentTotal = grid.querySelectorAll('.lrg-rv-card').length;
    if (showingEl) showingEl.textContent = currentTotal;
    if (index >= remaining.length) {
      loadMoreBtn.disabled = true;
      loadMoreBtn.textContent = 'All reviews loaded';
    }
  }

  loadMoreBtn.addEventListener('click', renderBatch);
})();
</script>
<?php
}
