<?php
/**
 * Plugin Name: VALN Sticky Reviews + CTA Bars (Staging Fix)
 * Description: Global sticky review ticker + CTA (after scroll). Apply page shows disclosure-only mini bar.
 * Version: 2026.02.24-stg-apply-disclosure-only
 */

if ( is_admin() ) { return; }

add_action('wp_footer', function () {
$page_url = $_SERVER['REQUEST_URI'] ?? '';
  $is_385 = (function_exists('is_page') && is_page(385));
  $page_url = is_string( $page_url ) ? $page_url : '';

  // Route checks (robust: match with or without trailing slash)
  $is_apply = ( strpos( $page_url, '/apply-now' ) !== false );
  $is_confirmation = ( strpos( $page_url, '/confirmation' ) !== false );

  $apply_url   = function_exists( 'home_url' ) ? home_url('/compare-loan-offers/') : '/apply-now/';
  $reviews_url = function_exists( 'home_url' ) ? home_url( '/reviews/' ) : '/reviews/';

  // Reviews ticker shortcode
  $ticker_html = function_exists( 'do_shortcode' )
    ? do_shortcode( '[tvln_reviews_ticker interval="15" min_rating="5" length="275" show_source_link="false"]' )
    : '';

  ?>
  <style>
    /* Kill any legacy bars if they still exist */
    #sticky-cta-bar, #valnFooterPinnedTrust { display:none !important; }

    body.valn-sticky-pad{
      padding-bottom: calc(var(--valnStickyH, 0px) + env(safe-area-inset-bottom, 0px)) !important;
    }

    .valnSticky, .valnSticky *{ box-sizing:border-box; }

    /* FULL WIDTH + NO ROUNDED CORNERS */
    .valnSticky{
      position: fixed;
      left: 0;
      right: 0;
      bottom: 0;
      width: 100%;
      z-index: 999999;
      background: #0b1e3a;
      color:#fff;
      border-radius: 0;
      box-shadow: 0 -10px 26px rgba(0,0,0,0.18);
      overflow:hidden;
    }

    .valnSticky__inner{
      max-width: 1850px;
      margin: 0 auto;
      padding: 12px 14px;
      display:flex;
      align-items:center;
      gap:16px;
    }

    /* ===== Desktop rating block ===== */
    .valnRatingBlock{
      display:grid;
      grid-template-columns: auto 1fr;
      grid-template-rows: auto auto;
      column-gap: 12px;
      row-gap: 0px;
      align-items:center;
      flex:0 0 auto;
      min-width: 260px;
    }

    .valnRatingNum{
      grid-row: 1 / span 2;
      font: 900 54px/1 system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
      letter-spacing:-0.02em;
    }

    .valnRatingTop{
      grid-column: 2;
      grid-row: 1;
      font: 800 14px/1.15 system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
      white-space:nowrap;
    }

    .valnRatingSub{
      grid-column: 2;
      grid-row: 2;
      font: 700 12px/1 system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
      opacity:.92;
      margin-top: -2px;
    }

    .valnBlue{ color:#2F7BFF !important; }

    .valnStars{
      color:#FBBF24 !important;
      letter-spacing: 3px;
      margin-left: 6px;
      position:relative;
      top:-1px;
    }

    /* Buttons */
    .valnBtn{
      display:inline-flex;
      align-items:center;
      justify-content:center;
      height: 34px;
      padding: 0 14px;
      border-radius: 999px;
      font: 800 13px/1 system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
      text-decoration:none !important;
      white-space:nowrap;
    }

    .valnBtn--outline{
      border:2px solid rgba(255,255,255,0.35);
      color:#fff !important;
      background: transparent;
    }

    .valnBtn--cta{
      background:#ffd500;
      color:#00296b !important;
      padding: 0 18px;
    }

    /* Ticker */
    .valnTickerWrap{ flex:1 1 auto; min-width:0; }
    .valnTickerWrap .tvln-ticker,
    .valnTickerWrap .tvln-ticker *{ color:#fff !important; }
    .valnTickerWrap .tvln-ticker{ overflow:hidden !important; max-width:100% !important; }
    .valnTickerWrap .tvln-ticker-viewport{ overflow:hidden !important; width:100% !important; }
    .valnTickerWrap .tvln-stars svg.star{
      width: 14px !important;
      height: 14px !important;
      fill: #FBBF24 !important;
    }
    .valnTickerWrap .snippet{ color: rgba(255,255,255,0.88) !important; }

    /* Global bar show/hide on scroll */
    #valnGlobalSticky{
      transform: translateY(120%);
      opacity: 0;
      pointer-events:none;
      transition: transform .22s ease, opacity .22s ease;
    }
    #valnGlobalSticky.valn-visible{
      transform: translateY(0);
      opacity: 1;
      pointer-events:auto;
    }

    /* Mobile layouts */
    .valnGlobalMobile{ display:none; }

    @media (max-width: 767px){
      .valnGlobalDesktop{ display:none !important; }
      .valnGlobalMobile{ display:block; }

      .valnGlobalMobile .valnSticky__inner{
        flex-direction: column;
        align-items: stretch;
        gap: 10px;
        padding: 6px 10px;
      }

      .valnMobileSummary{
        text-align:center;
        font: 800 15px/1.25 system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
      }

      .valnMobileSummary .valnNum{ font-size: 1.35em; font-weight: 900; }

      .valnGlobalMobile .valnStars{
        color:#FBBF24 !important;
        letter-spacing: 4px;
        margin-left: 8px;
        top:0;
      }

      .valnGlobalMobile .num{ color:#F5C542 !important; font-weight:900; }
      .valnGlobalMobile .blue{ color:#2F6FFF !important; }
      .valnGlobalMobile .gold{ color:#F5C542 !important; margin-left:4px; margin-right:2px; letter-spacing:0; }
      .valnGlobalMobile .vets{ color:#FFFFFF !important; font-weight:800; margin-left:0; }

      .valnMobileActions{
        display:flex;
        gap: 10px;
      }

      .valnMobileActions .valnBtn{
        height: 42px;
        flex: 1 1 0;
        padding: 0 10px;
        font-size: 15px;
      }
    }

    /* Apply disclosure mini bar */
    #valnApplyOnlySticky .valnSticky__inner{
      justify-content:center;
      padding:10px 14px;
    }
    #valnApplyOnlySticky p{
      margin:0;
      text-align:center;
      font:600 11px/1.35 system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;
      color: rgba(255,255,255,0.92);
    }
    #valnApplyOnlySticky p strong{ font-weight:800; color:#fff; }
  
    /* Page 385: hide eligibility CTA (desktop + mobile) */
    body.page-id-385 #valnGlobalSticky .valnBtn--cta{ display:none !important; }

    /* Page 385: center the remaining mobile Reviews button */
    body.page-id-385 #valnGlobalSticky .valnMobileActions{
      justify-content: center !important;
    }
    body.page-id-385 #valnGlobalSticky .valnMobileActions .valnBtn{
      flex: 0 0 auto !important;
      width: auto !important;
    }

  
    /* === VALN 385 SLIM FORCE ONLY V6 === */
    @media (max-width: 767px){
      body.page-id-385 #valnGlobalSticky .valnGlobalMobile .valnSticky__inner{
        max-width:none !important;
        width:100% !important;
        padding:6px 8px !important;
        justify-content:center !important;
      }

      /* Hide everything in the mobile bar except our line */
      body.page-id-385 #valnGlobalSticky .valnGlobalMobile .valnSticky__inner > *{
        display:none !important;
      }
      body.page-id-385 #valnGlobalSticky .valnGlobalMobile .valnSticky__inner > .valn385Line{
        display:block !important;
      }

      body.page-id-385 #valnGlobalSticky .valn385Line{
        text-align:center !important;
        white-space:nowrap !important;
        letter-spacing:0 !important;
        word-spacing:0 !important;
        font: 900 clamp(12px, 3.1vw, 14px)/1 system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif !important;
        color: rgba(255,255,255,0.92) !important;
        transform: scale(0.94);
        transform-origin: center;
      }

      body.page-id-385 #valnGlobalSticky .valn385Line .num{
        font-size: clamp(15px, 4.0vw, 18px) !important;
        font-weight: 900 !important;
        color:#fff !important;
        margin: 0 2px !important;
      }

      body.page-id-385 #valnGlobalSticky .valn385Line .blue{
        color:#0C71C3 !important;
        font-weight:900 !important;
      }

      body.page-id-385 #valnGlobalSticky .valn385Line .gold{
        color:#f5c542 !important;
        letter-spacing:1px !important;
        font-weight:900 !important;
        margin-left:4px !important;
      }

      body.page-id-385 #valnGlobalSticky .valn385Line .vets{
        color: rgba(255,255,255,0.92) !important;
        font-weight:900 !important;
        margin-left:6px !important;
      }
    }
    @media (max-width: 360px){
      body.page-id-385 #valnGlobalSticky .valn385Line{ transform: scale(0.90); }
    }

  
    @media (max-width: 767px){
      body #valnGlobalSticky .valnGlobalMobile .valnMobileSummary,
      body.page-id-385 #valnGlobalSticky .valnGlobalMobile .valn385Line{
        font-size:13px !important;
        line-height:1 !important;
        font-weight:800 !important;
        white-space:nowrap !important;
        letter-spacing:0 !important;
      }

      body #valnGlobalSticky .valnGlobalMobile .valnMobileSummary .num,
      body.page-id-385 #valnGlobalSticky .valnGlobalMobile .valn385Line .num{
        color:#F5C542 !important;
        font-weight:900 !important;
      }

      body #valnGlobalSticky .valnGlobalMobile .valnMobileSummary .blue,
      body.page-id-385 #valnGlobalSticky .valnGlobalMobile .valn385Line .blue{
        color:#2F6FFF !important;
      }

      body #valnGlobalSticky .valnGlobalMobile .valnMobileSummary .gold,
      body.page-id-385 #valnGlobalSticky .valnGlobalMobile .valn385Line .gold{
        color:#F5C542 !important;
        margin-left:4px !important;
        margin-right:2px !important;
        letter-spacing:0 !important;
      }

      body #valnGlobalSticky .valnGlobalMobile .valnMobileSummary .vets,
      body.page-id-385 #valnGlobalSticky .valnGlobalMobile .valn385Line .vets{
        color:#FFFFFF !important;
        font-weight:800 !important;
        margin-left:0 !important;
      }

      body #valnGlobalSticky .valnGlobalMobile .valnSticky__inner{
        padding-top:6px !important;
        padding-bottom:4px !important;
      }

      body.page-id-385 #valnGlobalSticky .valnGlobalMobile .valnSticky__inner{
        padding-top:6px !important;
        padding-bottom:6px !important;
      }

      body.page-id-385 #valnGlobalSticky .valnMobileActions,
      body.page-id-385 #valnGlobalSticky .valnBtn--cta{
        display:none !important;
      }

      body #valnGlobalSticky .valnMobileActions{
        gap:10px !important;
      }

      body #valnGlobalSticky .valnMobileActions .valnBtn{
        flex:1 1 0 !important;
        width:calc(50% - 5px) !important;
        min-width:0 !important;
        padding:7px 10px !important;
        min-height:40px !important;
        height:40px !important;
        line-height:1 !important;
        justify-content:center !important;
      }
    }

</style>

  <?php if ( ! $is_apply && ! $is_confirmation ) : ?>
    <div id="valnGlobalSticky" class="valnSticky" role="contentinfo" aria-label="Reviews and eligibility">
      <div class="valnGlobalDesktop">
        <div class="valnSticky__inner">
          <div class="valnRatingBlock">
            <div class="valnRatingNum">5.0</div>
            <div class="valnRatingTop">See why we're rated <span class="valnBlue">5 stars</span><span class="valnStars" aria-hidden="true">★★★★★</span></div>
            <div class="valnRatingSub">out of 5</div>
          </div>

          <a class="valnBtn valnBtn--outline" href="<?php echo esc_url( $reviews_url ); ?>">Read Our Reviews</a>

          <div class="valnTickerWrap">
            <?php echo $ticker_html; ?>
          </div>

          <a class="valnBtn valnBtn--cta" href="<?php echo esc_url( $apply_url ); ?>">Check VA Eligibility</a>
        </div>
      </div>

      <div class="valnGlobalMobile">
        <div class="valnSticky__inner">
<?php if ( ! empty($is_385) ) : ?>
          <div class="valn385Line" aria-label="VA Loan Network rating">
            Rated <span class="num">5.0</span> out of 5 <span class="blue">stars</span><span class="gold" aria-hidden="true">★★★★★</span> <span class="vets">by Veterans</span>
          </div>
<?php endif; ?>
          <div class="valnMobileSummary">
            Rated <span class="num">5.0</span> out of 5 <span class="blue">stars</span><span class="gold" aria-hidden="true">★★★★★</span> <span class="vets">by Veterans</span>
          </div>
          <div class="valnMobileActions">
            <a class="valnBtn valnBtn--cta" href="<?php echo esc_url( $apply_url ); ?>">Check VA Eligibility</a>
            <a class="valnBtn valnBtn--outline" href="<?php echo esc_url( $reviews_url ); ?>">Read Our Reviews</a>
          </div>
        </div>
      </div>
    </div>

    <script>
    (function(){
      var bar = document.getElementById('valnGlobalSticky');
      if(!bar) return;

      var body = document.body;

      function setPad(px){
        body.style.setProperty('--valnStickyH', px + 'px');
        if(px > 0){ body.classList.add('valn-sticky-pad'); }
        else{ body.classList.remove('valn-sticky-pad'); }
      }

      function barHeight(){ return Math.ceil(bar.getBoundingClientRect().height); }
      function threshold(){ return Math.max(64, Math.round(window.innerHeight * 0.10)); }

      function update(){
        var show = (document.body && document.body.classList && document.body.classList.contains("page-id-385")) ? true : (window.scrollY > threshold());
        bar.classList.toggle('valn-visible', show);
        setPad(show ? barHeight() : 0);
      }

      window.addEventListener('scroll', update, { passive:true });
      window.addEventListener('resize', update);

      if(window.ResizeObserver){
        new ResizeObserver(function(){
          if(bar.classList.contains('valn-visible')) setPad(barHeight());
        }).observe(bar);
      }

      update();
    })();
    </script>
  <?php endif; ?>

  <?php if ( $is_apply ) : ?>
    <div id="valnApplyOnlySticky" class="valnSticky" role="contentinfo" aria-label="Service disclosure">
      <div class="valnSticky__inner">
        <p><strong>Not a lender.</strong> We do not run credit checks. If you apply, we may refer you to a participating lender who may contact you.</p>
      </div>
    </div>

    <script>
    (function(){
      var bar = document.getElementById('valnApplyOnlySticky');
      if(!bar) return;

      var body = document.body;

      function applyPad(){
        var h = Math.ceil(bar.getBoundingClientRect().height);
        body.style.setProperty('--valnStickyH', h + 'px');
        body.classList.add('valn-sticky-pad');
      }

      window.addEventListener('load', applyPad, { once:true });
      window.addEventListener('resize', applyPad);
      if(window.ResizeObserver){ new ResizeObserver(applyPad).observe(bar); }
      setTimeout(applyPad, 60);
    })();
    </script>
  <?php endif; ?>

  <?php
}, 99 );

/* === STAGING HOTFIX: force apply disclosure bar to be fixed/visible === */
add_action('wp_footer', function () {
$u = $_SERVER['REQUEST_URI'] ?? '';
  if (!is_string($u) || strpos($u, '/apply-now/') === false) return;
  echo '<style>
    #valnApplySticky, #valnApplyOnlySticky{
      display:block !important;
      position:fixed !important;
      left:0 !important; right:0 !important; bottom:0 !important;
      z-index:999999 !important;
    }
  
    @media (max-width: 767px){
      body #valnGlobalSticky .valnGlobalMobile .valnMobileSummary,
      body.page-id-385 #valnGlobalSticky .valnGlobalMobile .valn385Line{
        font-size:13px !important;
        line-height:1 !important;
        font-weight:800 !important;
        white-space:nowrap !important;
        letter-spacing:0 !important;
      }

      body #valnGlobalSticky .valnGlobalMobile .valnMobileSummary .num,
      body.page-id-385 #valnGlobalSticky .valnGlobalMobile .valn385Line .num{
        color:#F5C542 !important;
        font-weight:900 !important;
      }

      body #valnGlobalSticky .valnGlobalMobile .valnMobileSummary .blue,
      body.page-id-385 #valnGlobalSticky .valnGlobalMobile .valn385Line .blue{
        color:#2F6FFF !important;
      }

      body #valnGlobalSticky .valnGlobalMobile .valnMobileSummary .gold,
      body.page-id-385 #valnGlobalSticky .valnGlobalMobile .valn385Line .gold{
        color:#F5C542 !important;
        margin-left:4px !important;
        margin-right:2px !important;
        letter-spacing:0 !important;
      }

      body #valnGlobalSticky .valnGlobalMobile .valnMobileSummary .vets,
      body.page-id-385 #valnGlobalSticky .valnGlobalMobile .valn385Line .vets{
        color:#FFFFFF !important;
        font-weight:800 !important;
        margin-left:0 !important;
      }

      body #valnGlobalSticky .valnGlobalMobile .valnSticky__inner{
        padding-top:6px !important;
        padding-bottom:4px !important;
      }

      body.page-id-385 #valnGlobalSticky .valnGlobalMobile .valnSticky__inner{
        padding-top:6px !important;
        padding-bottom:6px !important;
      }

      body.page-id-385 #valnGlobalSticky .valnMobileActions,
      body.page-id-385 #valnGlobalSticky .valnBtn--cta{
        display:none !important;
      }

      body #valnGlobalSticky .valnMobileActions{
        gap:10px !important;
      }

      body #valnGlobalSticky .valnMobileActions .valnBtn{
        flex:1 1 0 !important;
        width:calc(50% - 5px) !important;
        min-width:0 !important;
        padding:7px 10px !important;
        min-height:40px !important;
        height:40px !important;
        line-height:1 !important;
        justify-content:center !important;
      }
    }

</style>';
}, 9999);

