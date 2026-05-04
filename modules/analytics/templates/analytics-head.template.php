<?php
/**
 * RSS Analytics Module — analytics-head.php
 * Source: VALN production valn-analytics-head.php (pulled 2026-05-04)
 * Status: Template
 *
 * Template variables:
 * - {{SITE_PREFIX}} — function prefix
 * - {{SITE_NAME}} — site display name
 * - {{GTM_CONTAINER_ID}} — Google Tag Manager container (e.g., GTM-XXXXXXXX)
 * - {{META_PIXEL_ID}} — Facebook/Meta Pixel ID (leave empty to skip)
 * - {{LEAD_FORM_ID}} — Gravity Forms lead form ID (e.g., 9)
 *
 * Consolidated analytics injection with logged-in user exclusion.
 * Outputs GTM and Meta Pixel ONLY for non-logged-in users.
 */
if ( ! defined( 'ABSPATH' ) ) exit;

/**
 * 1. GTM + Meta Pixel — <head> injection
 */
add_action( 'wp_head', function () {
    if ( is_user_logged_in() ) return;

    $gtm_id = '{{GTM_CONTAINER_ID}}';
    $pixel_id = '{{META_PIXEL_ID}}';

    if ( $gtm_id !== '' ) : ?>
<!-- Google Tag Manager ({{SITE_PREFIX}} analytics-head mu-plugin) -->
<script>
(function(w,d,s,l,i){
  w[l]=w[l]||[];
  w[l].push({'gtm.start': new Date().getTime(), event:'gtm.js'});
  var f=d.getElementsByTagName(s)[0],
      j=d.createElement(s),
      dl=l!='dataLayer'?'&l='+l:'';
  j.async=true;
  j.src='https://www.googletagmanager.com/gtm.js?id='+i+dl;
  f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','<?php echo esc_attr( $gtm_id ); ?>');
</script>
<!-- End Google Tag Manager -->
    <?php endif;

    if ( $pixel_id !== '' ) : ?>
<!-- Meta Pixel Code ({{SITE_PREFIX}} analytics-head mu-plugin) -->
<script>
!function(f,b,e,v,n,t,s){
  if(f.fbq)return;
  n=f.fbq=function(){ n.callMethod? n.callMethod.apply(n,arguments):n.queue.push(arguments) };
  if(!f._fbq)f._fbq=n;
  n.push=n; n.loaded=!0; n.version='2.0';
  n.queue=[];
  t=b.createElement(e); t.async=!0;
  t.src=v;
  s=b.getElementsByTagName(e)[0];
  s.parentNode.insertBefore(t,s);
}(window, document,'script','https://connect.facebook.net/en_US/fbevents.js');
fbq('init', '<?php echo esc_attr( $pixel_id ); ?>');
fbq('track', 'PageView');
</script>
<noscript>
  <img height="1" width="1" style="display:none"
  src="https://www.facebook.com/tr?id=<?php echo esc_attr( $pixel_id ); ?>&ev=PageView&noscript=1" />
</noscript>
<!-- End Meta Pixel Code -->
    <?php endif;
}, 1 );

/**
 * 2. GTM <noscript> — <body> injection
 */
add_action( 'wp_body_open', function () {
    if ( is_user_logged_in() ) return;

    $gtm_id = '{{GTM_CONTAINER_ID}}';
    if ( $gtm_id === '' ) return;
    ?>
<!-- Google Tag Manager (noscript) -->
<noscript>
  <iframe src="https://www.googletagmanager.com/ns.html?id=<?php echo esc_attr( $gtm_id ); ?>"
  height="0" width="0" style="display:none;visibility:hidden"></iframe>
</noscript>
<!-- End Google Tag Manager (noscript) -->
    <?php
}, 1 );

/**
 * 3. Lead event — fires on Gravity Forms confirmation
 */
add_filter( 'gform_confirmation', function ( $confirmation, $form, $entry, $ajax ) {
    $lead_form_id = '{{LEAD_FORM_ID}}';
    if ( $lead_form_id === '' || (int) $form['id'] !== (int) $lead_form_id ) {
        return $confirmation;
    }
    if ( is_user_logged_in() ) return $confirmation;

    $lead_script = '
<script>
if (typeof fbq === "function") {
    fbq("track", "Lead", {
        content_name: "{{SITE_NAME}} Form ' . esc_js( $lead_form_id ) . '",
        content_category: "lead_form"
    });
}
if (typeof gtag === "function") {
    gtag("event", "generate_lead", {
        event_category: "form",
        event_label: "gf_form_' . esc_js( $lead_form_id ) . '",
        value: 1
    });
}
if (typeof dataLayer !== "undefined") {
    dataLayer.push({
        event: "form_submission",
        form_id: ' . (int) $lead_form_id . ',
        form_name: "{{SITE_NAME}} Lead Form"
    });
}
</script>';

    if ( is_string( $confirmation ) ) {
        $confirmation .= $lead_script;
    }
    return $confirmation;
}, 10, 4 );
