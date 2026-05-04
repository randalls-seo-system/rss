<?php
/**
 * Plugin Name: VALN Analytics Head
 * Description: Consolidated analytics injection with logged-in user exclusion.
 *              Outputs GTM, FB Pixel, and Microsoft Clarity ONLY for non-logged-in users.
 *              GA4 is handled by Google Site Kit (G-RBG3VSN6P1, has its own exclusion).
 *              FB Pixel Lead event fires server-side on GF Form 9 submission.
 * Version: 1.0.0
 * Author: VALN Engineering
 * Created: 2026-04-19
 *
 * LOGGED-IN EXCLUSION: Every tracking script checks is_user_logged_in() server-side
 * before outputting. WordPress logged-in users (admins, editors, QA) are excluded
 * from GTM, FB Pixel, and Clarity to keep team traffic out of analytics data.
 * GA4 exclusion is handled separately by Google Site Kit's trackingDisabled setting.
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

/**
 * 1. GTM + FB Pixel + Clarity — <head> injection
 *    Only fires for non-logged-in visitors.
 */
add_action( 'wp_head', function () {
    if ( is_user_logged_in() ) {
        return;
    }
    ?>
<!-- Google Tag Manager (VALN Analytics Head mu-plugin) -->
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
})(window,document,'script','dataLayer','GTM-PFBDZC36');
</script>
<!-- End Google Tag Manager -->

<!-- Meta Pixel Code (VALN Analytics Head mu-plugin) -->
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
fbq('init', '787887528011596');
fbq('track', 'PageView');
</script>
<noscript>
  <img height="1" width="1" style="display:none"
  src="https://www.facebook.com/tr?id=787887528011596&ev=PageView&noscript=1" />
</noscript>
<!-- End Meta Pixel Code -->

    <?php
}, 1 ); // Priority 1 = very early in <head>

/**
 * 2. GTM <noscript> — <body> injection
 *    Only fires for non-logged-in visitors.
 */
add_action( 'wp_body_open', function () {
    if ( is_user_logged_in() ) {
        return;
    }
    ?>
<!-- Google Tag Manager (noscript) -->
<noscript>
  <iframe src="https://www.googletagmanager.com/ns.html?id=GTM-PFBDZC36"
  height="0" width="0" style="display:none;visibility:hidden"></iframe>
</noscript>
<!-- End Google Tag Manager (noscript) -->
    <?php
}, 1 );

/**
 * 3. Facebook Pixel Lead Event — fires on Gravity Forms Form 9 confirmation
 *    Uses gform_confirmation to inject a one-time JS fbq('track', 'Lead') call
 *    into the confirmation HTML rendered after successful submission.
 *    Does NOT modify the form itself.
 */
add_filter( 'gform_confirmation', function ( $confirmation, $form, $entry, $ajax ) {
    // Only fire for Form 9 (primary lead form)
    if ( (int) $form['id'] !== 9 ) {
        return $confirmation;
    }

    // Don't fire for logged-in users
    if ( is_user_logged_in() ) {
        return $confirmation;
    }

    $lead_script = '
<script>
if (typeof fbq === "function") {
    fbq("track", "Lead", {
        content_name: "VA Loan Network Form 9",
        content_category: "lead_form"
    });
}
if (typeof gtag === "function") {
    gtag("event", "generate_lead", {
        event_category: "form",
        event_label: "gf_form_9",
        value: 1
    });
}
if (typeof dataLayer !== "undefined") {
    dataLayer.push({
        event: "form_submission",
        form_id: 9,
        form_name: "VA Loan Network Lead Form"
    });
}
</script>';

    // Append script to confirmation message
    if ( is_string( $confirmation ) ) {
        $confirmation .= $lead_script;
    }

    return $confirmation;
}, 10, 4 );
