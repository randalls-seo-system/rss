<?php
/**
 * Plugin Name: RSS Blog Home
 * Description: Custom blog homepage at /lrg-blog/. Intercepts page render and outputs hero, featured article, grid, categories, reviews, and CTA.
 * Version: 2.0.0
 * Author: Randall's SEO System
 */

if ( ! defined( 'ABSPATH' ) ) exit;

// Hostname safety guard — staging only
if ( strpos( $_SERVER['HTTP_HOST'] ?? '', 'wpenginepowered.com' ) === false ) return;

/* ===== Settings ===== */

function rss_blog_home_defaults() {
    return [
        'enabled'        => 1,
        'hero_headline'  => 'Texas Real Estate, Written by People Who Actually Do It',
        'hero_subhead'   => 'Practical guides on buying, selling, VA loans, and living in San Antonio, Austin, and Central Texas from the LRG team.',
        'cta_text'       => 'Connect with LRG',
        'cta_url'        => '/connect-with-lrg/',
        'reviews_count'  => '1,180',
        'reviews_rating' => '4.9',
        'logo_url'       => '',
        'navy'           => '#0F1F4A',
        'red'            => '#C8102E',
        'gold'           => '#FBBF24',
        'categories'     => "Home Buying|home-buying\nNeighborhood Guides|neighborhood-guides\nAustin Blog|austin-blog\nSell Your Home|sell-your-home\nLocal News|local-news\nVA Loans|va-loans",
    ];
}

function rss_blog_home_get_settings() {
    return array_merge( rss_blog_home_defaults(), (array) get_option( 'rss_blog_home_settings', [] ) );
}

/* ===== Frontend ===== */

add_action( 'template_redirect', 'rss_blog_home_intercept', 1 );

function rss_blog_home_intercept() {
    if ( ! is_home() || is_paged() ) return;
    if ( is_admin() ) return;

    $s = rss_blog_home_get_settings();
    if ( empty( $s['enabled'] ) ) return;

    // Enqueue Google Fonts before get_header() calls wp_head()
    wp_enqueue_style( 'rss-blog-home-fonts', 'https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;500;600;700&family=Inter:wght@400;500;600;700&display=swap', [], null );

    get_header();
    rss_blog_home_output( $s );
    get_footer();
    exit;
}

/* ===== Output ===== */

function rss_blog_home_output( $s ) {
    $navy = esc_attr( $s['navy'] );
    $red  = esc_attr( $s['red'] );
    $gold = esc_attr( $s['gold'] );
?>
<div class="rss-blog-home-root" style="--rss-navy:<?php echo $navy; ?>;--rss-red:<?php echo $red; ?>;--rss-gold:<?php echo $gold; ?>;">
<style>
/* RSS Blog Home v2.0.0 */
.rss-blog-home-root {
  --navy: var(--rss-navy, #0F1F4A);
  --red: var(--rss-red, #C8102E);
  --gold: var(--rss-gold, #FBBF24);
  --paper: #fafaf7;
  --card: #ffffff;
  --ink: #0f172a;
  --muted: #64748b;
  --border: rgba(15,23,42,0.08);
  --shadow: 0 8px 28px rgba(15,23,42,0.06);
  font-family: 'Inter', -apple-system, system-ui, sans-serif;
  color: var(--ink);
  line-height: 1.6;
}
.rss-blog-home-root *, .rss-blog-home-root *::before, .rss-blog-home-root *::after { box-sizing: border-box; }
.rss-blog-home-root a { color: inherit; }
.rss-blog-home-root img { max-width: 100%; height: auto; }

/* Container */
.rss-blog-home-root .rbh-container { max-width: 1200px; margin: 0 auto; padding: 0 24px; }

/* Section titles */
.rss-blog-home-root .rbh-section-title {
  font-family: 'Fraunces', Georgia, serif; font-weight: 700;
  font-size: clamp(1.6rem, 3vw, 2.2rem); color: var(--navy);
  margin: 0 0 32px; text-align: center;
}

/* Buttons */
.rss-blog-home-root .rbh-btn {
  display: inline-flex; align-items: center; justify-content: center;
  padding: 14px 32px; border-radius: 999px;
  font-family: 'Inter', sans-serif; font-weight: 700; font-size: 1rem;
  text-decoration: none; transition: transform .15s ease, box-shadow .15s ease;
  cursor: pointer; border: none;
}
.rss-blog-home-root .rbh-btn:hover { transform: scale(1.02); box-shadow: 0 12px 32px rgba(0,0,0,0.15); }
.rss-blog-home-root .rbh-btn--red { background: var(--red); color: #fff !important; }

/* Pills */
.rss-blog-home-root .rbh-pill {
  display: inline-block; padding: 4px 12px; border-radius: 999px;
  font-size: .75rem; font-weight: 700; letter-spacing: .03em; text-transform: uppercase;
}
.rss-blog-home-root .rbh-pill--red { background: var(--red); color: #fff; }
.rss-blog-home-root .rbh-pill--navy { background: var(--navy); color: #fff; }

/* Link */
.rss-blog-home-root .rbh-link {
  font-weight: 600; text-decoration: none; color: var(--red);
  border-bottom: 2px solid transparent; transition: border-color .2s;
}
.rss-blog-home-root .rbh-link:hover { border-bottom-color: var(--red); }
.rss-blog-home-root .rbh-center { text-align: center; margin-top: 32px; }

/* Fade-in */
.rss-blog-home-root .rbh-fade { opacity: 0; transform: translateY(24px); transition: opacity .6s ease, transform .6s ease; }
.rss-blog-home-root .rbh-fade.rbh-visible { opacity: 1; transform: translateY(0); }

/* ===== Hero ===== */
.rss-blog-home-root .rbh-hero {
  background: linear-gradient(170deg, var(--navy) 0%, #1a2c52 100%);
  color: #fff; text-align: center;
  min-height: 70vh; display: flex; align-items: center;
  padding: 96px 0;
  opacity: 1; transform: none;
}
.rss-blog-home-root .rbh-hero__logo { max-height: 48px; margin-bottom: 28px; }
.rss-blog-home-root .rbh-hero__title {
  font-family: 'Fraunces', Georgia, serif; font-weight: 600;
  font-size: clamp(2rem, 4.5vw, 3.4rem); line-height: 1.1;
  margin: 0 auto 20px; max-width: 820px; color: #fff !important;
}
.rss-blog-home-root .rbh-hero__sub {
  font-size: clamp(1rem, 1.8vw, 1.25rem); opacity: .85;
  margin: 0 auto 32px; max-width: 640px; line-height: 1.55;
}
.rss-blog-home-root .rbh-hero__trust {
  margin-top: 20px; font-size: .9rem; opacity: .8;
  color: var(--gold); font-weight: 600;
}

/* ===== Featured ===== */
.rss-blog-home-root .rbh-featured { padding: 72px 0; background: var(--paper); }
.rss-blog-home-root .rbh-featured__grid {
  display: grid; grid-template-columns: 3fr 2fr; gap: 40px; align-items: center;
}
.rss-blog-home-root .rbh-featured__img {
  border-radius: 8px; min-height: 340px;
  background-size: cover; background-position: center;
  box-shadow: var(--shadow); aspect-ratio: 16/9;
}
.rss-blog-home-root .rbh-featured__pills { display: flex; gap: 8px; flex-wrap: wrap; }
.rss-blog-home-root .rbh-featured__title {
  font-family: 'Fraunces', Georgia, serif; font-weight: 600;
  font-size: clamp(1.4rem, 2.5vw, 1.8rem); line-height: 1.2;
  margin: 14px 0 12px;
}
.rss-blog-home-root .rbh-featured__title a { text-decoration: none; color: var(--navy); }
.rss-blog-home-root .rbh-featured__title a:hover { color: var(--red); }
.rss-blog-home-root .rbh-featured__excerpt { color: var(--muted); margin: 0 0 16px; line-height: 1.6; }

/* ===== Article Grid ===== */
.rss-blog-home-root .rbh-grid-section { padding: 72px 0; background: #fff; }
.rss-blog-home-root .rbh-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px;
}
.rss-blog-home-root .rbh-card {
  background: var(--card); border-radius: 16px; overflow: hidden;
  box-shadow: var(--shadow); border: 1px solid var(--border);
  transition: transform .2s ease, box-shadow .2s ease;
  display: flex; flex-direction: column;
}
.rss-blog-home-root .rbh-card:hover { transform: translateY(-4px); box-shadow: 0 16px 40px rgba(15,23,42,0.1); }
.rss-blog-home-root .rbh-card__img-wrap { display: block; aspect-ratio: 16/9; overflow: hidden; }
.rss-blog-home-root .rbh-card__img { width: 100%; height: 100%; object-fit: cover; transition: transform .3s ease; }
.rss-blog-home-root .rbh-card:hover .rbh-card__img { transform: scale(1.03); }
.rss-blog-home-root .rbh-card__body { padding: 18px 20px 22px; flex: 1; display: flex; flex-direction: column; }
.rss-blog-home-root .rbh-card__title {
  font-family: 'Inter', sans-serif; font-weight: 600; font-size: 1.05rem;
  line-height: 1.3; margin: 10px 0 8px;
}
.rss-blog-home-root .rbh-card__title a { text-decoration: none; color: var(--navy); }
.rss-blog-home-root .rbh-card__title a:hover { color: var(--red); }
.rss-blog-home-root .rbh-card__excerpt { color: var(--muted); font-size: .92rem; flex: 1; margin: 0 0 10px; }
.rss-blog-home-root .rbh-card__meta { font-size: .8rem; color: var(--muted); font-weight: 500; margin-top: auto; }

/* ===== Categories ===== */
.rss-blog-home-root .rbh-cats { padding: 72px 0; background: var(--paper); }
.rss-blog-home-root .rbh-cats__grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;
}
.rss-blog-home-root .rbh-cat {
  display: flex; flex-direction: column; gap: 6px;
  background: var(--card); border-radius: 14px; padding: 24px 22px;
  text-decoration: none; border: 1px solid var(--border);
  box-shadow: var(--shadow); transition: transform .2s ease, box-shadow .2s ease;
  border-top: 4px solid var(--navy);
}
.rss-blog-home-root .rbh-cat--red { border-top-color: var(--red); }
.rss-blog-home-root .rbh-cat:hover { transform: translateY(-3px); box-shadow: 0 14px 36px rgba(15,23,42,0.1); }
.rss-blog-home-root .rbh-cat__icon { font-size: 1.6rem; line-height: 1; }
.rss-blog-home-root .rbh-cat__name { font-family: 'Fraunces', Georgia, serif; font-weight: 600; font-size: 1.1rem; color: var(--navy); }
.rss-blog-home-root .rbh-cat__count { font-size: .85rem; color: var(--muted); }
.rss-blog-home-root .rbh-cat__arrow { font-size: .85rem; font-weight: 600; color: var(--red); margin-top: auto; }

/* ===== Reviews ===== */
.rss-blog-home-root .rbh-reviews { padding: 72px 0; background: #fff; }
.rss-blog-home-root .rbh-reviews__grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px;
}
.rss-blog-home-root .rbh-review {
  background: var(--card); border-radius: 14px; padding: 28px 24px;
  border: 1px solid var(--border); box-shadow: var(--shadow);
}
.rss-blog-home-root .rbh-review__stars { color: var(--gold); font-size: 1.1rem; letter-spacing: 2px; margin-bottom: 12px; }
.rss-blog-home-root .rbh-review__text { font-size: .95rem; color: var(--ink); line-height: 1.6; margin: 0 0 14px; font-style: italic; }
.rss-blog-home-root .rbh-review__author { font-weight: 600; font-size: .9rem; margin: 0; }
.rss-blog-home-root .rbh-review__when { font-size: .8rem; color: var(--muted); margin: 4px 0 0; }
.rss-blog-home-root .rbh-reviews__footer {
  text-align: center; margin-top: 28px; font-size: .9rem;
  color: var(--muted); font-weight: 500;
}

/* ===== Secondary CTA ===== */
.rss-blog-home-root .rbh-cta {
  background: linear-gradient(170deg, var(--navy) 0%, #1a2c52 100%);
  color: #fff; text-align: center; padding: 72px 0;
}
.rss-blog-home-root .rbh-cta__title {
  font-family: 'Fraunces', Georgia, serif; font-weight: 600;
  font-size: clamp(1.6rem, 3vw, 2.5rem); margin: 0 0 14px; color: #fff !important;
}
.rss-blog-home-root .rbh-cta__sub { opacity: .85; max-width: 560px; margin: 0 auto 28px; font-size: 1.05rem; }
.rss-blog-home-root .rbh-cta__trust { margin-top: 18px; font-size: .85rem; color: var(--gold); font-weight: 600; opacity: .8; }

/* ===== Responsive ===== */
@media (max-width: 767px) {
  .rss-blog-home-root .rbh-hero { min-height: auto; padding: 64px 0; }
  .rss-blog-home-root .rbh-hero__title { font-size: clamp(1.8rem, 6vw, 2.2rem); }
  .rss-blog-home-root .rbh-featured { padding: 48px 0; }
  .rss-blog-home-root .rbh-featured__grid { grid-template-columns: 1fr; }
  .rss-blog-home-root .rbh-featured__img { min-height: 220px; }
  .rss-blog-home-root .rbh-grid-section { padding: 48px 0; }
  .rss-blog-home-root .rbh-grid { grid-template-columns: 1fr; }
  .rss-blog-home-root .rbh-cats { padding: 48px 0; }
  .rss-blog-home-root .rbh-cats__grid { grid-template-columns: repeat(2, 1fr); }
  .rss-blog-home-root .rbh-reviews { padding: 48px 0; }
  .rss-blog-home-root .rbh-reviews__grid { grid-template-columns: 1fr; }
  .rss-blog-home-root .rbh-cta { padding: 48px 0; }
}
@media (max-width: 980px) {
  .rss-blog-home-root .rbh-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 480px) {
  .rss-blog-home-root .rbh-cats__grid { grid-template-columns: 1fr; }
}
</style>

<?php rss_blog_home_hero( $s ); ?>
<?php rss_blog_home_featured( $s ); ?>
<?php rss_blog_home_grid( $s ); ?>
<?php rss_blog_home_categories( $s ); ?>
<?php rss_blog_home_reviews( $s ); ?>
<?php rss_blog_home_cta( $s ); ?>

<script>
(function(){
  if (!('IntersectionObserver' in window)) {
    document.querySelectorAll('.rbh-fade').forEach(function(el){ el.classList.add('rbh-visible'); });
    return;
  }
  var io = new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if (e.isIntersecting) { e.target.classList.add('rbh-visible'); io.unobserve(e.target); }
    });
  }, { threshold: 0.12 });
  document.querySelectorAll('.rbh-fade').forEach(function(el){ io.observe(el); });
})();
</script>
</div>
<?php
}

/* --- Hero --- */
function rss_blog_home_hero( $s ) { ?>
<section class="rbh-hero">
  <div class="rbh-container">
    <?php if ( ! empty( $s['logo_url'] ) ): ?>
      <img class="rbh-hero__logo" src="<?php echo esc_url( $s['logo_url'] ); ?>" alt="" loading="eager"/>
    <?php endif; ?>
    <h1 class="rbh-hero__title"><?php echo esc_html( $s['hero_headline'] ); ?></h1>
    <p class="rbh-hero__sub"><?php echo esc_html( $s['hero_subhead'] ); ?></p>
    <a class="rbh-btn rbh-btn--red" href="<?php echo esc_url( home_url( $s['cta_url'] ) ); ?>"><?php echo esc_html( $s['cta_text'] ); ?></a>
    <p class="rbh-hero__trust">&#9733;&#9733;&#9733;&#9733;&#9733; <?php echo esc_html( $s['reviews_rating'] ); ?> from <?php echo esc_html( $s['reviews_count'] ); ?> Google reviews</p>
  </div>
</section>
<?php }

/* --- Featured Article --- */
function rss_blog_home_featured( $s ) {
    $q = new WP_Query([
        'posts_per_page' => 1,
        'post_type'      => 'post',
        'post_status'    => 'publish',
        'meta_key'       => '_rss_featured',
        'meta_value'     => '1',
    ]);
    if ( ! $q->have_posts() ) {
        $q = new WP_Query([
            'posts_per_page' => 1,
            'post_type'      => 'post',
            'post_status'    => 'publish',
            'orderby'        => 'date',
            'order'          => 'DESC',
        ]);
    }
    if ( ! $q->have_posts() ) return;
    $q->the_post();
    $img      = get_the_post_thumbnail_url( get_the_ID(), 'large' );
    $cats     = get_the_category();
    $cat_name = ! empty( $cats ) ? $cats[0]->name : '';
    ?>
<section class="rbh-featured rbh-fade">
  <div class="rbh-container">
    <h2 class="rbh-section-title">Featured</h2>
    <div class="rbh-featured__grid">
      <?php if ( $img ): ?>
      <div class="rbh-featured__img" style="background-image:url('<?php echo esc_url( $img ); ?>')"></div>
      <?php endif; ?>
      <div class="rbh-featured__text">
        <div class="rbh-featured__pills">
          <span class="rbh-pill rbh-pill--red">FEATURED</span>
          <?php if ( $cat_name ): ?><span class="rbh-pill rbh-pill--navy"><?php echo esc_html( $cat_name ); ?></span><?php endif; ?>
        </div>
        <h3 class="rbh-featured__title"><a href="<?php the_permalink(); ?>"><?php the_title(); ?></a></h3>
        <p class="rbh-featured__excerpt"><?php echo wp_trim_words( get_the_excerpt(), 35 ); ?></p>
        <a class="rbh-link" href="<?php the_permalink(); ?>">Read full article &rarr;</a>
      </div>
    </div>
  </div>
</section>
<?php wp_reset_postdata(); }

/* --- Article Grid --- */
function rss_blog_home_grid( $s ) {
    $q = new WP_Query([
        'posts_per_page' => 6,
        'post_type'      => 'post',
        'post_status'    => 'publish',
        'offset'         => 1,
        'orderby'        => 'date',
        'order'          => 'DESC',
    ]);
    if ( ! $q->have_posts() ) return;
    ?>
<section class="rbh-grid-section rbh-fade">
  <div class="rbh-container">
    <h2 class="rbh-section-title">Latest Stories</h2>
    <div class="rbh-grid">
      <?php while ( $q->have_posts() ): $q->the_post();
        $img      = get_the_post_thumbnail_url( get_the_ID(), 'medium_large' );
        $cats     = get_the_category();
        $cat_name = ! empty( $cats ) ? $cats[0]->name : '';
        $words    = str_word_count( wp_strip_all_tags( get_the_content() ) );
        $read_min = max( 1, round( $words / 200 ) );
      ?>
      <article class="rbh-card">
        <?php if ( $img ): ?>
        <a href="<?php the_permalink(); ?>" class="rbh-card__img-wrap">
          <img class="rbh-card__img" src="<?php echo esc_url( $img ); ?>" alt="" loading="lazy"/>
        </a>
        <?php endif; ?>
        <div class="rbh-card__body">
          <?php if ( $cat_name ): ?><span class="rbh-pill rbh-pill--navy"><?php echo esc_html( $cat_name ); ?></span><?php endif; ?>
          <h3 class="rbh-card__title"><a href="<?php the_permalink(); ?>"><?php the_title(); ?></a></h3>
          <p class="rbh-card__excerpt"><?php echo wp_trim_words( get_the_excerpt(), 20 ); ?></p>
          <span class="rbh-card__meta"><?php echo $read_min; ?> min read</span>
        </div>
      </article>
      <?php endwhile; ?>
    </div>
    <div class="rbh-center"><a class="rbh-link" href="<?php echo esc_url( home_url( '/lrg-blog/page/2/' ) ); ?>">Browse all articles &rarr;</a></div>
  </div>
</section>
<?php wp_reset_postdata(); }

/* --- Categories --- */
function rss_blog_home_categories( $s ) {
    $lines = array_filter( array_map( 'trim', explode( "\n", $s['categories'] ) ) );
    if ( empty( $lines ) ) return;
    $icons = [ "\xF0\x9F\x8F\xA0", "\xF0\x9F\x93\x8D", "\xF0\x9F\x8C\x86", "\xF0\x9F\x92\xB0", "\xF0\x9F\x93\xB0", "\xF0\x9F\x8E\x96\xEF\xB8\x8F" ];
    ?>
<section class="rbh-cats rbh-fade">
  <div class="rbh-container">
    <h2 class="rbh-section-title">Browse by Topic</h2>
    <div class="rbh-cats__grid">
      <?php foreach ( $lines as $i => $line ):
        $parts = explode( '|', $line, 2 );
        $name  = trim( $parts[0] );
        $slug  = isset( $parts[1] ) ? trim( $parts[1] ) : sanitize_title( $name );
        $term  = get_term_by( 'slug', $slug, 'category' );
        if ( ! $term ) continue;
        $count = $term->count;
        $icon  = $icons[ $i % count( $icons ) ];
        $accent = ( $i % 2 === 0 ) ? '' : 'rbh-cat--red';
      ?>
      <a class="rbh-cat <?php echo $accent; ?>" href="<?php echo esc_url( get_term_link( $term ) ); ?>">
        <span class="rbh-cat__icon"><?php echo $icon; ?></span>
        <span class="rbh-cat__name"><?php echo esc_html( $name ); ?></span>
        <span class="rbh-cat__count"><?php echo $count; ?> articles</span>
        <span class="rbh-cat__arrow">Explore &rarr;</span>
      </a>
      <?php endforeach; ?>
    </div>
  </div>
</section>
<?php }

/* --- Reviews --- */
function rss_blog_home_reviews( $s ) {
    $all = get_option( 'rss_reviews_list', [] );
    if ( empty( $all ) || ! is_array( $all ) ) return;
    $five = array_values( array_filter( $all, function( $r ) {
        return intval( $r['rating'] ?? 0 ) >= 5 && ! empty( $r['body'] );
    }));
    $show = array_slice( $five, 0, 3 );
    if ( empty( $show ) ) return;
    ?>
<section class="rbh-reviews rbh-fade">
  <div class="rbh-container">
    <h2 class="rbh-section-title">What Clients Are Saying</h2>
    <div class="rbh-reviews__grid">
      <?php foreach ( $show as $r ): ?>
      <div class="rbh-review">
        <div class="rbh-review__stars">&#9733;&#9733;&#9733;&#9733;&#9733;</div>
        <p class="rbh-review__text">&ldquo;<?php echo esc_html( wp_trim_words( $r['body'], 40 ) ); ?>&rdquo;</p>
        <p class="rbh-review__author"><?php echo esc_html( $r['name'] ); ?></p>
        <?php if ( ! empty( $r['when'] ) ): ?><p class="rbh-review__when"><?php echo esc_html( $r['when'] ); ?></p><?php endif; ?>
      </div>
      <?php endforeach; ?>
    </div>
    <p class="rbh-reviews__footer">&#9733;&#9733;&#9733;&#9733;&#9733; <?php echo esc_html( $s['reviews_rating'] ); ?> average from <?php echo esc_html( $s['reviews_count'] ); ?> reviews on Google</p>
  </div>
</section>
<?php }

/* --- Secondary CTA --- */
function rss_blog_home_cta( $s ) { ?>
<section class="rbh-cta rbh-fade">
  <div class="rbh-container">
    <h2 class="rbh-cta__title">Ready to make your next move?</h2>
    <p class="rbh-cta__sub">Talk to an LRG specialist about your situation. No pressure, just a real conversation.</p>
    <a class="rbh-btn rbh-btn--red" href="<?php echo esc_url( home_url( $s['cta_url'] ) ); ?>"><?php echo esc_html( $s['cta_text'] ); ?></a>
    <p class="rbh-cta__trust">&#9733;&#9733;&#9733;&#9733;&#9733; <?php echo esc_html( $s['reviews_rating'] ); ?> from <?php echo esc_html( $s['reviews_count'] ); ?> reviews</p>
  </div>
</section>
<?php }

/* ===== Admin Settings ===== */

if ( is_admin() && ! wp_doing_ajax() ) {
    add_action( 'admin_menu', function() {
        add_menu_page( 'RSS Blog Home', 'Blog Home', 'manage_options', 'rss-blog-home', 'rss_blog_home_settings_page', 'dashicons-admin-home', 57 );
    });
    add_action( 'admin_post_rss_blog_home_save', 'rss_blog_home_handle_save' );
}

function rss_blog_home_settings_page() {
    if ( ! current_user_can( 'manage_options' ) ) return;
    $s = rss_blog_home_get_settings();
    $saved = isset( $_GET['rbh_saved'] );
    ?>
    <div class="wrap">
        <h1>RSS Blog Home Settings</h1>
        <?php if ( $saved ): ?><div class="notice notice-success is-dismissible"><p>Settings saved.</p></div><?php endif; ?>
        <form method="post" action="<?php echo esc_url( admin_url( 'admin-post.php' ) ); ?>">
            <?php wp_nonce_field( 'rss_blog_home_nonce' ); ?>
            <input type="hidden" name="action" value="rss_blog_home_save"/>
            <h2 class="title">General</h2>
            <table class="form-table"><tbody>
                <tr><th>Enabled</th><td><label><input type="checkbox" name="enabled" value="1" <?php checked( ! empty( $s['enabled'] ) ); ?>/> Show custom blog home page</label></td></tr>
                <tr><th><label for="logo_url">Logo URL</label></th><td><input type="url" id="logo_url" name="logo_url" value="<?php echo esc_attr( $s['logo_url'] ); ?>" class="large-text"/></td></tr>
            </tbody></table>
            <h2 class="title">Hero</h2>
            <table class="form-table"><tbody>
                <tr><th><label for="hero_headline">Headline</label></th><td><input type="text" id="hero_headline" name="hero_headline" value="<?php echo esc_attr( $s['hero_headline'] ); ?>" class="large-text"/></td></tr>
                <tr><th><label for="hero_subhead">Subhead</label></th><td><textarea id="hero_subhead" name="hero_subhead" rows="3" class="large-text"><?php echo esc_textarea( $s['hero_subhead'] ); ?></textarea></td></tr>
                <tr><th><label for="cta_text">CTA text</label></th><td><input type="text" id="cta_text" name="cta_text" value="<?php echo esc_attr( $s['cta_text'] ); ?>" class="regular-text"/></td></tr>
                <tr><th><label for="cta_url">CTA URL</label></th><td><input type="text" id="cta_url" name="cta_url" value="<?php echo esc_attr( $s['cta_url'] ); ?>" class="regular-text"/></td></tr>
            </tbody></table>
            <h2 class="title">Reviews Display</h2>
            <table class="form-table"><tbody>
                <tr><th><label for="reviews_rating">Rating</label></th><td><input type="text" id="reviews_rating" name="reviews_rating" value="<?php echo esc_attr( $s['reviews_rating'] ); ?>" size="6"/></td></tr>
                <tr><th><label for="reviews_count">Count</label></th><td><input type="text" id="reviews_count" name="reviews_count" value="<?php echo esc_attr( $s['reviews_count'] ); ?>" size="10"/></td></tr>
            </tbody></table>
            <h2 class="title">Categories</h2>
            <table class="form-table"><tbody>
                <tr><th><label for="categories">Featured categories</label></th><td><textarea id="categories" name="categories" rows="8" class="large-text"><?php echo esc_textarea( $s['categories'] ); ?></textarea><br/><span class="description">One per line: Display Name|slug</span></td></tr>
            </tbody></table>
            <h2 class="title">Colors</h2>
            <table class="form-table"><tbody>
                <tr><th><label for="navy">Navy</label></th><td><input type="text" id="navy" name="navy" value="<?php echo esc_attr( $s['navy'] ); ?>" size="8"/></td></tr>
                <tr><th><label for="red">Red</label></th><td><input type="text" id="red" name="red" value="<?php echo esc_attr( $s['red'] ); ?>" size="8"/></td></tr>
                <tr><th><label for="gold">Gold</label></th><td><input type="text" id="gold" name="gold" value="<?php echo esc_attr( $s['gold'] ); ?>" size="8"/></td></tr>
            </tbody></table>
            <p class="submit"><button type="submit" class="button button-primary">Save Settings</button></p>
        </form>
    </div>
    <?php
}

function rss_blog_home_handle_save() {
    if ( ! current_user_can( 'manage_options' ) || ! check_admin_referer( 'rss_blog_home_nonce' ) ) wp_die( 'Unauthorized' );
    $fields = [ 'hero_headline', 'hero_subhead', 'cta_text', 'cta_url', 'reviews_count', 'reviews_rating', 'logo_url', 'navy', 'red', 'gold' ];
    $settings = [];
    foreach ( $fields as $f ) $settings[ $f ] = sanitize_text_field( $_POST[ $f ] ?? '' );
    $settings['enabled']    = ! empty( $_POST['enabled'] ) ? 1 : 0;
    $settings['categories'] = sanitize_textarea_field( $_POST['categories'] ?? '' );
    update_option( 'rss_blog_home_settings', $settings, false );
    wp_redirect( admin_url( 'admin.php?page=rss-blog-home&rbh_saved=1' ) );
    exit;
}
