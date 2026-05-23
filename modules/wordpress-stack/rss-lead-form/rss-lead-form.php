<?php
/**
 * Plugin Name: RSS Lead Form
 * Description: Multi-step lead capture form with AJAX submission, database storage, and email forwarding to Follow Up Boss. Shortcode [lrg_lead_form]. Part of Randall's SEO System standard plugin stack.
 * Version: 1.0.2
 * Author: Randall's SEO System
 * License: GPL2+
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

class RSS_Lead_Form {

    const VERSION    = '1.0.2';
    const OPTION_KEY = 'rss_lf_settings';
    const CPT_SLUG   = 'rss_lead';

    const PATH_LABELS = array(
        'buyer'        => 'I want to buy',
        'seller'       => 'I want to sell',
        'va'           => 'VA loan / Veteran',
        'market'       => 'Market updates',
        'neighborhood' => 'Neighborhood alerts',
        'other'        => 'Just have a question',
    );

    public static function init() {
        add_action( 'init', array( __CLASS__, 'register_cpt' ) );

        add_shortcode( 'lrg_lead_form', array( __CLASS__, 'shortcode_output' ) );

        add_action( 'wp_ajax_rss_lead_form_submit',        array( __CLASS__, 'handle_submit' ) );
        add_action( 'wp_ajax_nopriv_rss_lead_form_submit',  array( __CLASS__, 'handle_submit' ) );

        add_action( 'wp_enqueue_scripts', array( __CLASS__, 'maybe_enqueue_assets' ) );

        if ( is_admin() ) {
            add_action( 'admin_menu', array( __CLASS__, 'add_settings_page' ) );
        }
    }

    /* =========================================================
     * Settings
     * ========================================================= */

    public static function get_settings(): array {
        $defaults = array(
            'fub_email'       => '',
            'cc_recipients'   => '',
            'from_email'      => 'noreply@' . ( wp_parse_url( home_url(), PHP_URL_HOST ) ?: 'localhost' ),
            'from_name'       => get_bloginfo( 'name' ),
            'phone_for_errors' => '',
            'enable_db'       => true,
            'enable_email'    => true,
        );
        $options = get_option( self::OPTION_KEY, array() );
        return wp_parse_args( $options, $defaults );
    }

    /* =========================================================
     * Custom Post Type
     * ========================================================= */

    public static function register_cpt() {
        register_post_type( self::CPT_SLUG, array(
            'labels' => array(
                'name'          => 'Leads',
                'singular_name' => 'Lead',
                'menu_name'     => 'Leads',
            ),
            'public'       => false,
            'show_ui'      => true,
            'show_in_menu' => true,
            'menu_icon'    => 'dashicons-groups',
            'supports'     => array( 'title', 'custom-fields' ),
            'capability_type' => 'post',
        ) );
    }

    /* =========================================================
     * Asset Enqueuing (conditional on shortcode presence)
     * ========================================================= */

    public static function maybe_enqueue_assets() {
        global $post;
        if ( ! is_a( $post, 'WP_Post' ) ) {
            return;
        }
        if ( ! has_shortcode( $post->post_content, 'lrg_lead_form' ) ) {
            return;
        }

        $plugin_url = plugins_url( '', __FILE__ );

        // Google Fonts
        wp_enqueue_style(
            'rss-lf-fonts',
            'https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,300;9..144,400;9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&display=swap',
            array(),
            null
        );

        // Plugin CSS
        wp_enqueue_style(
            'rss-lead-form',
            $plugin_url . '/assets/rss-lead-form.css',
            array( 'rss-lf-fonts' ),
            self::VERSION
        );

        // Plugin JS
        wp_enqueue_script(
            'rss-lead-form',
            $plugin_url . '/assets/rss-lead-form.js',
            array(),
            self::VERSION,
            true
        );
    }

    /* =========================================================
     * Shortcode Output
     * ========================================================= */

    public static function shortcode_output( $atts ): string {
        $settings = self::get_settings();

        // Build the AJAX config script
        $config = array(
            'ajaxUrl'        => admin_url( 'admin-ajax.php' ),
            'nonce'          => wp_create_nonce( 'rss_lead_form_submit' ),
            'phoneForErrors' => $settings['phone_for_errors'],
        );

        $html = '<div class="rss-lf-root">';

        // Inline AJAX config
        $html .= '<script>window.RSS_LF_CONFIG=' . wp_json_encode( $config ) . ';</script>';

        // Form HTML (extracted from source/index.html body)
        $html .= self::get_form_html();

        $html .= '</div>';

        return $html;
    }

    private static function get_form_html(): string {
        // Note: the strategy note for Levi (#note aside) is removed from production output.
        return '
<!-- ============ HEADER ============ -->
<header class="header">
  <div class="header-inner">
    <img src="data:image/webp;base64,UklGRkYUAABXRUJQVlA4WAoAAAAYAAAAUwEAWQAAVlA4TGYTAAAvU0EWECq81ratuizlGR1q5ljL2rX+7/3XtlGy5uqoTqLPh2P/5vt9c861/g0Tf3BSiAjdHVoi+hBwd8/qCAhdcjKNHApCMif0A+iBW+YW1Vgp7q4VNqG3d4q7uzvk2u7dKVq4k1WnhN19AjihRu4ukZO3RvgZdIT7KTjZzpHU3V1rk7m71xi4u/xo6L5TnMgqb1kRkBJxCg4/7oR7vIOFQ+buri0p2YtD7lIcQ0W9OyRzJ2I0Jdu25bYNui4oAvd82E5N6X/Ka6ntAbjrfuoBZBwaQapenX6dKCT+uw9U6qSVOYmybNtu24gf4c6JxDvnggozjTr3tGc558SSgQdlEe+cC5Ux7Wn/sClAAECwjc62bdu2bdu2rST92rZt47vatm3bkihJkqU2WZJsXxzE8DqzIH6AB48gHDtq9C3pnDo5jrUpIW3m5QGzNcK6Z4I5dmAffE5R1HGvaPUvafZ+YGVrDEkbBJuK3SVpUcf99okw4hHFuKiDTgsFF1V0+M6pVfWQorKJ3QqLuw0YEu1wdNQIwVYsIGx5RB5d5eEDNhJdMP/qBHNvq+1OBzsFHABTuBaDuYs4RW91hvQCOeCll4dj2GoFcx43HXGr2yWUJbyLjdGhVY8huI1vO5Q2Z+iJsELxIO/N6oUO0VZ3RkI2dpT8MBM0mHcIuJbB7GmHglQoarKJc1FT4dtTaJjNbRRxs6U9BK1W0QtCkTQ7NMeP6ExS3NQ0o4yDERY6wYZBdgk0+zDOwnOHFXI8yfjEFiSLj5BxVhl6KKxeA9MaP21Rx0GXvMs1PJmZMj/iLo7Jg0dcRUp2xAlkStvI06kE72V1xycWNV9iYTrZBVCUWotjQZbSujSucoag1CGFPFu8eHGYJJ8Vplk3mVLQsuDkzthIUwf66i1cmKwreE3wX5mgX1EOjCD1REdNWs8W5CvBk105aKVtI8/Z8cjkAFHeqPEEvQdcMrxdyLQZiHZx2iNHIg8ks0rJIZHNZVihEyOPFumFak6R5rtarJb2EmSEIVEiL36mH221oWi1L1PRrsrk6lvoejzXSuMjK4/f3V3rkn3uHiTXKCBVTxJ8l+funhLlnSfdOO9R5Ct3D0VtmqBSdw/oZOY0o5CC39w9cFTNEmzqaYL3heTWlgjq9UxClm5ivEFV/sDTpOiiiwJTMjdKkfc8LeCTDlLXPK0k8pynSfHw0DDBKKFYd4uuE3y+4x4CEwAzazP1EvuvriFbUWuPzANi76PIIZHgFzXQph8+YAt+jQJOYzMu+FiuVmj1vdCzBTxz4NvnaFXcA07H8BJMGXm0UBy35xL8ezjNeMCRpZFHxlnoCZHM2DvgCEWwfJUXPxMWra5cQ0VFmzo+tw7BDdPTUjwXXfb09PQMkqA+wV/TsYCLmhF5qZwszJInVyUJ3N1DsVfp0z3qbERdW5D2Qpl1pdhD8Ja7e0BGJUE9XhL8tHfB0yJ/qgGEBGUEsuW/BJ/q+4giaNyjgC/DZK9hSXMPgpfc3YVczAjK1umYzCtiIkiVocy6IsWsiAJ+3dhLB/goTLOCR4KSZ3Dk7pQmGuScK3753gHDF8l8/feKv87d3aCyVjceBbKPJOvT59HMHpgkqDiSktsYVvBI8GYUSrawNpHmyJffXCQYGHXGRdQjkT+C0vXIyOHyH5JIceogsWoRdWopuYfHdPfNDelIGAmLuEefcxckGchC94A3z3m18QY19aQkyYRM8iU7kpW7+8qINhLsVFp529BIytmKzt4BowFHshZtGrmGGo22Mbb3BZqku/tIWUTJ7iQBj4RUaYRdfBQJjoi6uK70MlQJ8i8FOT6LL+ruLkXBJKejgL43Nc3ELK02rqhSVCo08aVkfTLPgvrwSQrNsSTKuNUfCotkT/mrOor9VDAuBNeIsqBsYdZJCs6IPXEzgnrKyfZMkoLXo65cQb5jFPD61zciHLk9kpK25D1K8Y56IGkYVnAhZyMhV/N4b9E1Rl3lXCS4m5lyRC6Il1jI/7IEJZXk7BY9/YdvUcie6zuyHvLCOBTGRNHq6moXV1S3f/vFfqB7zXGTq3qXgAob7pIZROZ0jgTfP3IY70lEvlXH3/pOMuCGgKcOLRJ8+7fk8a+IZLI1k0TKjKT4qkLAkeU/o+OOQlECyU8TcizpkbO7LEztRsjmp/ZIJjeQ8Y3XII+4Top3RyYz9w4E+/5eK1r9Gru8JSDJWfWKcY3jbjfn7oHm0ynN2t0Denzk2tIOTbSYkZRpJi49cUrkWHc/yQoBBbr7iuTSBbVokh/vSS9fR9pTj+iOiCTZ2QjjzFzXxXdhTJKeU7T6xtLs3YA7ngLZM132mHki38VOtJlDKyfTg/xjJPjwsyJRK2BTIueFl5KEJHcs+DwSloiUlGxz92usILgkEnSSHPaDlJu32eFbiMRuY++cJ/ipK7u9PJOG5ic2QSlCbqtRrqjH9fguyvD2gcyThjcLTRNB2uvig0jkKqoE97v7Sc64lwTayPaR4hkjwZ15I0qioLyKAq6PuuT/0Q6i7jizBBxpJvJH9Ow1dwl42t3P5CSYC8O3EIHZWPBjFNDKQfkocrcm8iSbeOdQZgXPHOefzd39ZB+pJBL9PajnHlmbGG9QpbjVo51GQjq6uwcWBzXp8OZI45EUx9b0BYLL3F3wQ5gfqbR7VUsZkSojQVsT7HJ70/2FUaqxF60WRhuX0+xZEzKlnCF5SeAPtItshoKq3X1F51Hyq38+pjoSd3HaOZxDKJndJe886uLVe0zJtmmJmla3OPzZPboVkrzb93D3zQnpP6QJmexOTwJnX87cKaJO/cudx842tSpJcH/uvoN7LA0N/8Psfe+3TQ7fP+IvjEQ5NGFwOscpQ8IIwY/a5l4NiEWtS+NiPNfEuXV0fk2sDQ0TTCjeLQV0fBENDZcV/8/dXdCRelR0ZJmv9mybk9GsFWvicjr9bDjIlq667G25evJcd038BZRifXf3gFNLw8jO3Y/7Gi/Wox+dKAbzrQzGt9XGg7xewcfqpVrR6tIaBkUOLYkyhg2xi0zc3QPq/nqSPLWAfnNEvu8UKbKSKHcH1AUE8FzT318fRepxd+8yG5NcmLs3hPvGmwC1gnkDv0dWjeTsi0G9aLV7jWILXfzsvuKRG2Mgu9zdRRmmRhHE05UnEo/zDO/AKicTSMBwOSIx7VNF3knstlvstiU2MFwWmuN2970MPzIzGbDDNSYEjy5hT4D5gGPPyVrIOeeT0Jw62dQz6Pf7MjdZZc/92NkqMqVgv9+Xs0ZJ8vj7STvVkvnSZm5WTLLDUT2d4YOY9KLl5UgNq2n1+/1HzlqSXMol5agyS3PmcICiaj9dEtDF/0Q5t3dRtodJ3qdKajNeWjH7qjA3nVNd5fEDArO9/E5/NyjH9h7wVJCyAzbWr0OSd9tPO9tItMj2+/0ZG9GSlElC5SBBR16ScrVCd6ZZKeCMY967kDMBp5/QUvYGuHAwqw28Z9MTluFIRbZPj4BOPbZGSL7CrPhZmP0aEhtsj2CckVhJZzq4YLc+Nz5ckjMHdxswBB80LL1460MmYB6RRHJSg+E3wSbRt6RbnY/rzyAT87eqmkzBCM3Y6larbFWHb7awCn7Z4SDCCAt8EEU2P81kAqcQQg+JiinV7Die4iYXrcqT/RNMTyTckR1nAt++ghjHwgLkrHtBUOM80OmM054vdy1NJtdDeoFwE5iDCTV6UTU2U68Yx3YH2jVHz69xZr50wNzE7g/Y7OsMMAM1JNsmGDoLzQzmL4KdWN6hUF7JVA+WwIHkhg6ZlC2vAnPOVLdXQlAfySczQ2IKvwYBieMW13RI9CUQrIPZkzis5Hd1IyQLTHWAvO+AkQfzU30cAkFJBStUzMxgbMFhn/hFJDOXqZlOUEN0toYoiQrMMbvVCH1Pama2HBkRUxMiV9Hq51irT8V+ME3Nfb5CFm3sOKb1fnFhlzxUFJgD6DuaiQNzC4E+OM4MxiHiBE87l0EMRyomHsPg6G0Cxlw5IRbwRsiO6oUMa1TCcIO5YIiojAYDGFOG5N1ggECCtsDmwYVRQ7BlMID5ZA81eCUF5lI5MHro5rdenL05AkVYwxHBIBiLNg+mk/bmAyQWzZBhpGAB1u3YmyOj8JNOHh39ZlgRUhPMr1dCcAjBH0MyckLkK/bVNjV39wfsNVzDSm9+b7PMVHAhUpcOtzuSnDkXI/VYHWQzFe3AXgtuaVoFp9AhYdbbp2joxZS5FuzbDAGGBv6eSQjaGgKVJBbAIBExXw0Bk0dt1eDINbtLJuH3Lexh2SSpYCmqrAq/fwb5fwazS11ziHBcBkcH7jZgyimSiDA2GGMlfHYBhcCIXdO7kyRMRRjnhlPo1nMuJE57apjPMF++IQuG+UQbfTrEILiuIWFYbazWxNyco3W0ruNJYX4carWjNJjpdSARZ7djzzQ+kGxW81SDezJE3CBjH8FbmN/fMR5gGBiC25NUITqFb2WKb24lnGBgMDefjKpzMjhupuoizHHDXyd4Od84Dx18zeH/C6i9YgF9E0WtlT+rIRHZxGith6u3CasOJIYNiZRqSAQbogA1rEzYXewXFfzSI8E8WfaNMO/v7snq65cTTpK8XZjv9kqIXqwWJKMMJhDBKEMirI6dlAOfUM4/2NswLQMLKD4A5loJRr9hCSsmwZw3ZKjVtV0krwx+DSEHGcWGZH1zxwgjZLNvfQtRtFrWQNHq1nqOEarBHGhitI0JrHSXF/dCZvZCMGc+OwcrA9BD/ogfYd97y+4yrSBgaQgWEMFIw0pAw13WIclpGIdmMJaQEKmGb08RD//ZkT3+JX0AzNtXrZb8p5qDwL7NL73qD8RuSUFy7hQQYfUxdvKltQ2/nOOksCDYEAir5cJ397TIGDYYw0wgGbTtNzczGK+3c3bNoHfySLay2I+Aa2hg+xu6/kReu5NXra9o9Xe0TYTV8Psp4rWqUX8K334LkT+ZvQAcJtRgdBxaTN2ua8E8sa0Sv/T4x3n491IbAsXlhFjfJSdJTsGwgLlshhV2lU7eEMwnYZbag9XwSuXAt5qztn1rCYEOMzN0ZqYnMwRit1u6QsPvryCmzsOuue7J7C+2mhrArFWDwDFyX83AKJo/52nl3EpVY63KZIy2elfU8W37qz/7R3PfpkIUyvpG29jIGuG0x4B5Gl3rgDkvbEi+4tgxkdWbT9D+YtGiRYjYMCRdGmzONkCUIDv87Vb41l3OQ6fNokUnbye1VvPN6NwxeEtbQjJj29tGxpVtWbm5czEkw6mCuWvrZG4C+xTlJSscPjpCbwK9ExwwE6434LcTIWMDa4fCca/ifbCL0+DQre/86piC8RYhYqNiM4IZhoiOGraLjEXTIbk21dh2cSgcJAnz0HDckVQ4bEvCCpnmHsOQAaIORqmdud4M9+Lz9r49BYFU23ICh3fRXsBwE7QROizsahV0LhhOPXOyS51j4UtzvAWkKnOjrABHmnZVlZbe/thlpW3gofeNYPVZYEXD8ufOm9q2nXk1GJp2LtspOxc73KbWgnFrhxrBvLDvqABzx2DUlGP/vyHZ1xyy55x36ietfLCd+iMmu8CMsTO8/hJ6CP7H62OluoL/3oaDo95gdjNCFgFDxNk3ROg9zSPAfMXNG/D1bHc5jPbnvAOYP/jnGdJ4+7w/qIAF5tqvViKvuAHcnpCcDsl1Nl9xMrhwGMzHA2pnni5YkTFluydJ/qbtRysXsnnT6Zp4if0GPgXMcyP7ILs35r2Gui7IdWFezjv/Skg4VK+JP9+eHSviv4NT9wHz2g7AxLpwrCebYNjZqSMjFS7YHOC3XgDJ8fST/BdkSJZ/GHF4l/x27LVZz6GeBUkcCuMjTjBEsGh3Fw+WfzRuSJLVZ7QTQ3JnsmJNDBf+5LbhdmHe2KVFeq1bc038g2vbqcN4sb2fbYWbN0SvTdV5G8yanNprYhgRH2C29nIzBOJyZ4Qk6/cYbiGtpkAvga9jhuTd9Zo91ILk4X0utu83n2f723+qXhPs8L4k86vE++dEeTkE+tBDkLx+RCkf7J4kTMBgkKyJ0SN0gA5D6tCL8wBB70jNg0BCDsxCPeE6JHmJCDRe13XB+AfvhKnsTQ93wMETTGnwOdEARu8PlI598A3Kp+iBb5b5vvG1Lw7Bx8M69kVUTkGNjqDL4A5wvYKrMXALCiSTEFxG8g7mOcxBBIyejkkLsDL93t78ho/m8KgMttOLiI4pDabXZGzWs39Eizqe1XLQXz1pO9ryN499/Vit4W0RDF/LtsEP3+cuWn1oieA9R95pF3VMbokOL2/5Jt//gvtNWhkML8F2c6oJJPapO1PLtoei1cpW5s8eiEjWmO5ptCfI+5JVn/8q2MZIcUi3OAcu2E9giVN/aAUdIZYPhn3Rxu4WRmimW3qzyUxTyroL4KB9PXjPsWjRKUy/ze3d3mu8xtsU9blc9T9aXtOTWylaXYu1SdnXbra/Sr3ELo2dX3K3TNdwFbP3A+uaa47VK/6i1YvWqOIzma3RaKu9dRT7CdD2IJiINUJmXh4wv63aaKslM186wLc9+HYDgWQdone9v6LVmSqjtVaw/TUFcwDu7XZdtHEmb7SNeffHFti3why9vdV2N6jFRc0dq7UhU9HGSLbD/vwJ3owH7zACRVhJRroAAABFeGlmAABJSSoACAAAAAYAEgEDAAEAAAABAAAAGgEFAAEAAABWAAAAGwEFAAEAAABeAAAAKAEDAAEAAAACAAAAEwIDAAEAAAABAAAAaYcEAAEAAABmAAAAAAAAAEkZAQDoAwAASRkBAOgDAAAGAACQBwAEAAAAMDIxMAGRBwAEAAAAAQIDAACgBwAEAAAAMDEwMAGgAwABAAAA//8AAAKgBAABAAAAVAEAAAOgBAABAAAAWgAAAAAAAAA=" alt="The Levi Rodgers Real Estate Group" class="logo">
    <a href="https://lrgrealty.com" class="exit">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12" stroke-linecap="round"/></svg>
      Exit
    </a>
  </div>
</header>

<!-- ============ PROGRESS ============ -->
<div class="progress-bar"><div class="progress-fill" id="progress-fill"></div></div>

<!-- ============ STAGE ============ -->
<main class="stage" id="stage">

  <!-- INTRO -->
  <section class="screen active" data-screen="intro">
    <div class="screen-inner intro-inner">
      <div class="intro-eyebrow"><span class="dot"></span> Texas real estate &middot; personalized</div>
      <h1 class="q-title">Tell us what you\'re <em>looking for.</em></h1>
      <p class="q-help">A few quick questions, then an LRG specialist reaches out with a plan built for your situation.</p>
      <div class="paths-grid">
        <button class="path" data-path="buyer">
          <div class="path-title">I want to buy</div>
          <div class="path-desc">First home, move-up, or investment in Central Texas.</div>
        </button>
        <button class="path" data-path="seller">
          <div class="path-title">I want to sell</div>
          <div class="path-desc">Free valuation and 2026 selling strategy.</div>
        </button>
        <button class="path" data-path="va">
          <div class="path-title">VA loan / Veteran</div>
          <div class="path-desc">Active duty, Veteran, PCS &mdash; we know the process.</div>
        </button>
        <button class="path" data-path="market">
          <div class="path-title">Market updates</div>
          <div class="path-desc">Free monthly Texas market reports.</div>
        </button>
        <button class="path" data-path="neighborhood">
          <div class="path-title">Neighborhood alerts</div>
          <div class="path-desc">Weekly listings from areas you care about.</div>
        </button>
        <button class="path" data-path="other">
          <div class="path-title">Just have a question</div>
          <div class="path-desc">Anything else &mdash; we\'ll route you.</div>
        </button>
      </div>
    </div>
  </section>

  <!-- ============ BUYER PATH ============ -->
  <section class="screen" data-screen="buyer-1" data-path="buyer">
    <div class="screen-inner">
      <div class="q-label"><span class="num">01</span> Timeline</div>
      <h2 class="q-title">When are you <em>looking to buy?</em></h2>
      <div class="answers">
        <button class="ans" data-value="0-3" data-auto data-next="buyer-2"><div class="ans-key">A</div><div class="ans-content"><div class="ans-title">In the next 3 months</div><div class="ans-desc">Actively looking, pre-approved or close.</div></div></button>
        <button class="ans" data-value="3-6" data-auto data-next="buyer-2"><div class="ans-key">B</div><div class="ans-content"><div class="ans-title">3&ndash;6 months out</div><div class="ans-desc">Getting serious. Need a plan.</div></div></button>
        <button class="ans" data-value="6-12" data-auto data-next="buyer-2"><div class="ans-key">C</div><div class="ans-content"><div class="ans-title">6&ndash;12 months out</div><div class="ans-desc">Researching, want to be ready.</div></div></button>
        <button class="ans" data-value="just-looking" data-auto data-next="buyer-2"><div class="ans-key">D</div><div class="ans-content"><div class="ans-title">Just looking</div><div class="ans-desc">No pressure &mdash; happy to learn.</div></div></button>
      </div>
      <div class="foot"><div class="foot-meta">Pick one to continue &mdash; or press A, B, C, D</div><div class="foot-secondary"><button class="btn btn-back" data-back>&larr; Back</button></div></div>
    </div>
  </section>

  <section class="screen" data-screen="buyer-2" data-path="buyer">
    <div class="screen-inner">
      <div class="q-label"><span class="num">02</span> Area</div>
      <h2 class="q-title">Which area are you <em>considering?</em></h2>
      <p class="q-help">Pick one or more.</p>
      <div class="chips" data-multi="buyer-area">
        <button class="chip" data-value="san-antonio">San Antonio</button>
        <button class="chip" data-value="austin">Austin</button>
        <button class="chip" data-value="killeen">Killeen / Fort Cavazos</button>
        <button class="chip" data-value="round-rock">Round Rock / Pflugerville</button>
        <button class="chip" data-value="new-braunfels">New Braunfels</button>
        <button class="chip" data-value="not-sure">Not sure yet</button>
      </div>
      <div class="foot"><div class="foot-primary"><button class="btn btn-primary" data-next="contact" disabled>Continue &rarr;</button></div><div class="foot-secondary"><button class="btn btn-back" data-back>&larr; Back</button></div></div>
    </div>
  </section>

  <!-- ============ SELLER PATH ============ -->
  <section class="screen" data-screen="seller-1" data-path="seller">
    <div class="screen-inner">
      <div class="q-label"><span class="num">01</span> Property</div>
      <h2 class="q-title">What\'s your <em>property address?</em></h2>
      <p class="q-help">We use this to send you a free professional valuation. We won\'t share it.</p>
      <div class="input-group"><div class="form-field"><label for="rss-lf-seller-address">Property address</label><input class="input" id="rss-lf-seller-address" type="text" name="seller-address" placeholder="123 Main St, San Antonio, TX 78201" autocomplete="street-address"></div></div>
      <div class="foot"><div class="foot-primary"><button class="btn btn-primary" data-next="seller-2" data-require="seller-address" disabled>Continue &rarr;</button></div><div class="foot-meta">Press <kbd>Enter</kbd> to continue</div><div class="foot-secondary"><button class="btn btn-back" data-back>&larr; Back</button></div></div>
    </div>
  </section>

  <section class="screen" data-screen="seller-2" data-path="seller">
    <div class="screen-inner">
      <div class="q-label"><span class="num">02</span> Timing</div>
      <h2 class="q-title">When are you thinking of <em>selling?</em></h2>
      <div class="answers">
        <button class="ans" data-value="now" data-auto data-next="seller-3"><div class="ans-key">A</div><div class="ans-content"><div class="ans-title">Soon as possible</div><div class="ans-desc">Ready to list now or in the next few weeks.</div></div></button>
        <button class="ans" data-value="3-6" data-auto data-next="seller-3"><div class="ans-key">B</div><div class="ans-content"><div class="ans-title">3&ndash;6 months</div><div class="ans-desc">Planning ahead. Want to get strategy right.</div></div></button>
        <button class="ans" data-value="6-12" data-auto data-next="seller-3"><div class="ans-key">C</div><div class="ans-content"><div class="ans-title">6&ndash;12 months</div><div class="ans-desc">Just starting to think about it.</div></div></button>
        <button class="ans" data-value="curious" data-auto data-next="seller-3"><div class="ans-key">D</div><div class="ans-content"><div class="ans-title">Just curious about value</div><div class="ans-desc">No timeline. Want to know what it\'s worth.</div></div></button>
      </div>
      <div class="foot"><div class="foot-meta">Pick one to continue &mdash; or press A, B, C, D</div><div class="foot-secondary"><button class="btn btn-back" data-back>&larr; Back</button></div></div>
    </div>
  </section>

  <section class="screen" data-screen="seller-3" data-path="seller">
    <div class="screen-inner">
      <div class="q-label"><span class="num">03</span> Buying too?</div>
      <h2 class="q-title">Will you also be <em>buying?</em></h2>
      <div class="answers">
        <button class="ans" data-value="yes" data-auto data-next="contact"><div class="ans-key">A</div><div class="ans-content"><div class="ans-title">Yes, also buying</div><div class="ans-desc">Ask us about LRG\'s Move-Up Program.</div></div></button>
        <button class="ans" data-value="no" data-auto data-next="contact"><div class="ans-key">B</div><div class="ans-content"><div class="ans-title">No, just selling</div></div></button>
        <button class="ans" data-value="maybe" data-auto data-next="contact"><div class="ans-key">C</div><div class="ans-content"><div class="ans-title">Not sure yet</div></div></button>
      </div>
      <div class="foot"><div class="foot-meta">Pick one to continue &mdash; or press A, B, C, D</div><div class="foot-secondary"><button class="btn btn-back" data-back>&larr; Back</button></div></div>
    </div>
  </section>

  <!-- ============ VA PATH ============ -->
  <section class="screen" data-screen="va-1" data-path="va">
    <div class="screen-inner">
      <div class="q-label"><span class="num">01</span> Status</div>
      <h2 class="q-title">What\'s your <em>situation?</em></h2>
      <div class="answers">
        <button class="ans" data-value="active-duty" data-auto data-next="va-2"><div class="ans-key">A</div><div class="ans-content"><div class="ans-title">Active duty</div><div class="ans-desc">Currently serving.</div></div></button>
        <button class="ans" data-value="veteran" data-auto data-next="va-2"><div class="ans-key">B</div><div class="ans-content"><div class="ans-title">Veteran</div><div class="ans-desc">Separated or retired.</div></div></button>
        <button class="ans" data-value="spouse" data-auto data-next="va-2"><div class="ans-key">C</div><div class="ans-content"><div class="ans-title">Military spouse / family</div></div></button>
        <button class="ans" data-value="pcs" data-auto data-next="va-2"><div class="ans-key">D</div><div class="ans-content"><div class="ans-title">PCS relocation</div><div class="ans-desc">Time-sensitive. Moving on orders.</div></div></button>
      </div>
      <div class="foot"><div class="foot-meta">Pick one to continue &mdash; or press A, B, C, D</div><div class="foot-secondary"><button class="btn btn-back" data-back>&larr; Back</button></div></div>
    </div>
  </section>

  <section class="screen" data-screen="va-2" data-path="va">
    <div class="screen-inner">
      <div class="q-label"><span class="num">02</span> Need</div>
      <h2 class="q-title">Buying, selling, or <em>both?</em></h2>
      <div class="answers">
        <button class="ans" data-value="buying" data-auto data-next="contact"><div class="ans-key">A</div><div class="ans-content"><div class="ans-title">Buying</div></div></button>
        <button class="ans" data-value="selling" data-auto data-next="contact"><div class="ans-key">B</div><div class="ans-content"><div class="ans-title">Selling</div></div></button>
        <button class="ans" data-value="both" data-auto data-next="contact"><div class="ans-key">C</div><div class="ans-content"><div class="ans-title">Both</div><div class="ans-desc">Need a Move-Up plan.</div></div></button>
      </div>
      <div class="foot"><div class="foot-meta">Pick one to continue &mdash; or press A, B, C, D</div><div class="foot-secondary"><button class="btn btn-back" data-back>&larr; Back</button></div></div>
    </div>
  </section>

  <!-- ============ MARKET PATH ============ -->
  <section class="screen" data-screen="market-1" data-path="market">
    <div class="screen-inner">
      <div class="q-label"><span class="num">01</span> Email</div>
      <h2 class="q-title">Where should we <em>send updates?</em></h2>
      <p class="q-help">Just an email. No calls, no spam, unsubscribe anytime.</p>
      <div class="input-group"><div class="form-field"><label for="rss-lf-market-email">Your email</label><input class="input" id="rss-lf-market-email" type="email" name="market-email" placeholder="you@email.com" autocomplete="email" inputmode="email"></div></div>
      <div class="foot"><div class="foot-primary"><button class="btn btn-primary" data-next="market-2" data-require="market-email" disabled>Continue &rarr;</button></div><div class="foot-meta">Press <kbd>Enter</kbd> to continue</div><div class="foot-secondary"><button class="btn btn-back" data-back>&larr; Back</button></div></div>
    </div>
  </section>

  <section class="screen" data-screen="market-2" data-path="market">
    <div class="screen-inner">
      <div class="q-label"><span class="num">02</span> Area</div>
      <h2 class="q-title">Which Texas area do you <em>care about?</em></h2>
      <p class="q-help">ZIP code or city &mdash; we\'ll send hyperlocal data.</p>
      <div class="input-group"><div class="form-field"><label for="rss-lf-market-zip">ZIP code or city</label><input class="input" id="rss-lf-market-zip" type="text" name="market-zip" placeholder="78201 or Austin" autocomplete="postal-code"></div></div>
      <div class="foot"><div class="foot-primary"><button class="btn btn-primary" data-submit="market" data-require="market-zip" disabled>Send me the report &rarr;</button></div><div class="foot-meta">Press <kbd>Enter</kbd> to continue</div><div class="foot-secondary"><button class="btn btn-back" data-back>&larr; Back</button></div></div>
    </div>
  </section>

  <!-- ============ NEIGHBORHOOD PATH ============ -->
  <section class="screen" data-screen="hood-1" data-path="neighborhood">
    <div class="screen-inner">
      <div class="q-label"><span class="num">01</span> Areas</div>
      <h2 class="q-title">Which neighborhoods are <em>on your list?</em></h2>
      <p class="q-help">Pick one or more.</p>
      <div class="chips" data-multi="hood-area">
        <button class="chip" data-value="alamo-heights">Alamo Heights</button>
        <button class="chip" data-value="stone-oak">Stone Oak</button>
        <button class="chip" data-value="boerne">Boerne</button>
        <button class="chip" data-value="helotes">Helotes</button>
        <button class="chip" data-value="austin-central">Austin (central)</button>
        <button class="chip" data-value="round-rock">Round Rock</button>
        <button class="chip" data-value="pflugerville">Pflugerville</button>
        <button class="chip" data-value="other">Other</button>
      </div>
      <div class="foot"><div class="foot-primary"><button class="btn btn-primary" data-next="contact" disabled>Continue &rarr;</button></div><div class="foot-secondary"><button class="btn btn-back" data-back>&larr; Back</button></div></div>
    </div>
  </section>

  <!-- ============ OTHER PATH ============ -->
  <section class="screen" data-screen="other-1" data-path="other">
    <div class="screen-inner">
      <div class="q-label"><span class="num">01</span> Question</div>
      <h2 class="q-title">What\'s <em>on your mind?</em></h2>
      <p class="q-help">Tell us a bit and we\'ll route you to the right specialist.</p>
      <div class="input-group"><div class="form-field"><label for="rss-lf-other-message">Your question</label><textarea class="textarea" id="rss-lf-other-message" name="other-message" placeholder="e.g., Relocating from California, need to understand Texas property taxes..."></textarea></div></div>
      <div class="foot"><div class="foot-primary"><button class="btn btn-primary" data-next="contact" data-require="other-message" disabled>Continue &rarr;</button></div><div class="foot-secondary"><button class="btn btn-back" data-back>&larr; Back</button></div></div>
    </div>
  </section>

  <!-- ============ CONTACT (universal) ============ -->
  <section class="screen" data-screen="contact">
    <div class="screen-inner">
      <div class="q-label"><span class="num">&#9658;</span> Almost done</div>
      <h2 class="q-title">Where can we <em>reach you?</em></h2>
      <p class="q-help">A specialist personally reviews your info &mdash; no auto-responder spam.</p>
      <div class="input-group">
        <div class="form-row-two-up">
          <div class="form-field"><label for="rss-lf-firstname">First name</label><input class="input" id="rss-lf-firstname" type="text" name="firstname" placeholder="John" autocomplete="given-name"></div>
          <div class="form-field"><label for="rss-lf-lastname">Last name</label><input class="input" id="rss-lf-lastname" type="text" name="lastname" placeholder="Smith" autocomplete="family-name"></div>
        </div>
        <div class="form-field"><label for="rss-lf-email">Email</label><input class="input" id="rss-lf-email" type="email" name="email" placeholder="you@email.com" autocomplete="email" inputmode="email"></div>
        <div class="form-field"><label for="rss-lf-phone">Phone</label><input class="input" id="rss-lf-phone" type="tel" name="phone" placeholder="(210) 555-1234" autocomplete="tel" inputmode="tel"></div>
        <input class="rss-lf-honeypot" type="text" name="website" autocomplete="off" tabindex="-1" aria-hidden="true">
      </div>
      <div class="rss-lf-error" role="alert"></div>
      <div class="foot">
        <div class="foot-primary">
          <button class="btn btn-primary" data-submit="primary" data-require-all="firstname,lastname,email,phone" disabled id="contact-submit-btn">Send my request &rarr;</button>
        </div>
        <div class="foot-secondary"><button class="btn btn-back" data-back>&larr; Back</button></div>
      </div>
    </div>
  </section>

  <!-- ============ CONFIRMATION ============ -->
  <section class="screen" data-screen="confirmation">
    <div class="screen-inner confirm">
      <div class="confirm-icon">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"><path d="M5 13l4 4L19 7" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </div>
      <h2 id="confirm-title">You\'re <em>all set.</em></h2>
      <p class="confirm-msg" id="confirm-msg">Thanks &mdash; we got your info.</p>
      <div class="confirm-card">
        <div class="confirm-card-label">What happens next</div>
        <div class="confirm-card-text" id="confirm-next">An LRG specialist will reach out within one business day.</div>
      </div>
      <a href="https://lrgrealty.com" class="btn btn-primary">Back to LRG Realty</a>
    </div>
  </section>

</main>';
    }

    /* =========================================================
     * AJAX Submission Handler
     * ========================================================= */

    public static function handle_submit() {
        // Verify nonce
        if ( ! check_ajax_referer( 'rss_lead_form_submit', '_ajax_nonce', false ) ) {
            wp_send_json_error( array( 'message' => 'Invalid security token.' ), 403 );
        }

        $raw = isset( $_POST['payload'] ) ? wp_unslash( $_POST['payload'] ) : '';
        $data = json_decode( $raw, true );
        if ( ! is_array( $data ) ) {
            wp_send_json_error( array( 'message' => 'Invalid payload.' ), 400 );
        }

        // Honeypot check — bots fill this, real users don't
        $honeypot = isset( $data['honeypot'] ) ? trim( (string) $data['honeypot'] ) : '';
        if ( $honeypot !== '' ) {
            wp_send_json_success( array( 'success' => true, 'lead_id' => 0 ) );
        }

        // Rate limit: 3 submissions per IP per 10 minutes
        $ip_raw   = isset( $_SERVER['REMOTE_ADDR'] ) ? sanitize_text_field( $_SERVER['REMOTE_ADDR'] ) : '';
        $ip_hash  = hash( 'sha256', $ip_raw . wp_salt() );
        $rate_key = 'rss_lf_rate_' . substr( $ip_hash, 0, 16 );
        $rate_count = (int) get_transient( $rate_key );
        if ( $rate_count >= 3 ) {
            wp_send_json_success( array( 'success' => true, 'lead_id' => 0 ) );
        }
        set_transient( $rate_key, $rate_count + 1, 600 );

        // Extract fields
        $path      = sanitize_text_field( $data['path'] ?? 'unknown' );
        $firstname = sanitize_text_field( $data['firstname'] ?? '' );
        $lastname  = sanitize_text_field( $data['lastname'] ?? '' );
        $email     = sanitize_email( $data['email'] ?? '' );
        $phone     = sanitize_text_field( $data['phone'] ?? '' );
        $answers   = isset( $data['answers'] ) && is_array( $data['answers'] ) ? $data['answers'] : array();
        $referrer  = esc_url_raw( $data['referrer'] ?? '' );
        $ref_param = sanitize_text_field( $data['ref_param'] ?? '' );
        $timestamp = sanitize_text_field( $data['timestamp'] ?? gmdate( 'c' ) );
        $ua        = isset( $_SERVER['HTTP_USER_AGENT'] ) ? sanitize_text_field( $_SERVER['HTTP_USER_AGENT'] ) : '';

        $path_label = self::PATH_LABELS[ $path ] ?? $path;
        $settings   = self::get_settings();
        $lead_id    = 0;

        // Build Message string for FUB
        $message_parts = array( "Path: {$path_label}", '' );
        foreach ( $answers as $q => $a ) {
            $q_clean = sanitize_text_field( $q );
            $a_clean = is_array( $a ) ? implode( ', ', array_map( 'sanitize_text_field', $a ) ) : sanitize_text_field( $a );
            $message_parts[] = "{$q_clean}: {$a_clean}";
        }
        $message_parts[] = '';

        // Formatted submission time in CT
        $dt = new DateTime( $timestamp, new DateTimeZone( 'UTC' ) );
        $dt->setTimezone( new DateTimeZone( 'America/Chicago' ) );
        $message_parts[] = 'Submitted: ' . $dt->format( 'Y-m-d g:i A T' );

        // Page attribution
        $page_source = 'direct';
        if ( $ref_param ) {
            $page_source = '/lrg-blog/' . ltrim( $ref_param, '/' ) . '/';
        } elseif ( $referrer ) {
            $page_source = $referrer;
        }
        $message_parts[] = "Page: {$page_source}";
        $message = implode( "\n", $message_parts );

        // === Save to database ===
        if ( ! empty( $settings['enable_db'] ) ) {
            $post_id = wp_insert_post( array(
                'post_type'   => self::CPT_SLUG,
                'post_title'  => "{$firstname} {$lastname} — {$path_label}",
                'post_status' => 'publish',
            ) );

            if ( $post_id && ! is_wp_error( $post_id ) ) {
                $lead_id = $post_id;
                update_post_meta( $post_id, '_rss_lf_path',         $path );
                update_post_meta( $post_id, '_rss_lf_firstname',    $firstname );
                update_post_meta( $post_id, '_rss_lf_lastname',     $lastname );
                update_post_meta( $post_id, '_rss_lf_email',        $email );
                update_post_meta( $post_id, '_rss_lf_phone',        $phone );
                update_post_meta( $post_id, '_rss_lf_answers',      wp_json_encode( $answers ) );
                update_post_meta( $post_id, '_rss_lf_referrer',     $referrer );
                update_post_meta( $post_id, '_rss_lf_ref_param',    $ref_param );
                update_post_meta( $post_id, '_rss_lf_submitted_at', $timestamp );
                update_post_meta( $post_id, '_rss_lf_user_agent',   $ua );
                update_post_meta( $post_id, '_rss_lf_ip',           $ip_hash );
                update_post_meta( $post_id, '_rss_lf_message',      $message );
            }
        }

        // === Send email ===
        $mail_status = 'skipped';
        if ( ! empty( $settings['enable_email'] ) && ! empty( $settings['fub_email'] ) ) {
            $subject = "New Lead from LRG Blog — {$path_label}";
            $to      = sanitize_email( $settings['fub_email'] );

            $body = "Name: {$firstname} {$lastname}\n"
                  . "Email: {$email}\n"
                  . "Phone: " . ( $phone ?: 'not provided' ) . "\n"
                  . "Source: LRG Blog Lead\n"
                  . "Message:\n{$message}\n";

            $headers = array(
                "From: {$settings['from_name']} <{$settings['from_email']}>",
            );
            if ( $email ) {
                $headers[] = "Reply-To: {$firstname} {$lastname} <{$email}>";
            }

            // CC recipients (one per line)
            $cc_raw = trim( $settings['cc_recipients'] ?? '' );
            if ( $cc_raw ) {
                foreach ( preg_split( '/[\r\n]+/', $cc_raw ) as $cc ) {
                    $cc = trim( $cc );
                    if ( is_email( $cc ) ) {
                        $headers[] = "Cc: {$cc}";
                    }
                }
            }

            $sent = wp_mail( $to, $subject, $body, $headers );
            $mail_status = $sent ? 'success' : 'fail';
        }

        // === Log ===
        $log_line = sprintf(
            "[%s] %s | lead_id=%d | %s | %s | mail=%s\n",
            gmdate( 'Y-m-d H:i:s' ),
            $lead_id ? 'success' : 'db_skip',
            $lead_id,
            $email,
            $path,
            $mail_status
        );
        @file_put_contents( '/tmp/rss-lead-form.log', $log_line, FILE_APPEND );

        wp_send_json_success( array( 'success' => true, 'lead_id' => $lead_id ) );
    }

    /* =========================================================
     * Settings Page
     * ========================================================= */

    public static function add_settings_page() {
        add_options_page(
            'RSS Lead Form',
            'RSS Lead Form',
            'manage_options',
            'rss-lead-form',
            array( __CLASS__, 'render_settings_page' )
        );
    }

    public static function render_settings_page() {
        if ( ! current_user_can( 'manage_options' ) ) {
            return;
        }

        if ( isset( $_POST['rss_lf_nonce'] ) && wp_verify_nonce( sanitize_text_field( wp_unslash( $_POST['rss_lf_nonce'] ) ), 'rss_lf_save' ) ) {
            $opts = array(
                'fub_email'        => sanitize_email( wp_unslash( $_POST['fub_email'] ?? '' ) ),
                'cc_recipients'    => sanitize_textarea_field( wp_unslash( $_POST['cc_recipients'] ?? '' ) ),
                'from_email'       => sanitize_email( wp_unslash( $_POST['from_email'] ?? '' ) ),
                'from_name'        => sanitize_text_field( wp_unslash( $_POST['from_name'] ?? '' ) ),
                'phone_for_errors' => sanitize_text_field( wp_unslash( $_POST['phone_for_errors'] ?? '' ) ),
                'enable_db'        => isset( $_POST['enable_db'] ),
                'enable_email'     => isset( $_POST['enable_email'] ),
            );
            update_option( self::OPTION_KEY, $opts );
            echo '<div class="updated"><p>Settings saved.</p></div>';
        }

        $s = self::get_settings();
        ?>
        <div class="wrap">
            <h1>RSS Lead Form Settings</h1>
            <form method="post">
                <?php wp_nonce_field( 'rss_lf_save', 'rss_lf_nonce' ); ?>
                <table class="form-table">
                    <tr><th>FUB lead email</th><td><input type="email" name="fub_email" value="<?php echo esc_attr( $s['fub_email'] ); ?>" class="regular-text" /><p class="description">Follow Up Boss email-ingestion address.</p></td></tr>
                    <tr><th>CC recipients</th><td><textarea name="cc_recipients" rows="3" class="large-text"><?php echo esc_textarea( $s['cc_recipients'] ); ?></textarea><p class="description">One email per line. Gets a copy of every lead.</p></td></tr>
                    <tr><th>From email</th><td><input type="email" name="from_email" value="<?php echo esc_attr( $s['from_email'] ); ?>" class="regular-text" /></td></tr>
                    <tr><th>From name</th><td><input type="text" name="from_name" value="<?php echo esc_attr( $s['from_name'] ); ?>" class="regular-text" /></td></tr>
                    <tr><th>Phone (error msg)</th><td><input type="text" name="phone_for_errors" value="<?php echo esc_attr( $s['phone_for_errors'] ); ?>" class="regular-text" /><p class="description">Shown in error messages. Leave blank to omit.</p></td></tr>
                    <tr><th>Save to database</th><td><label><input type="checkbox" name="enable_db" <?php checked( $s['enable_db'] ); ?> /> Save leads as custom post type</label></td></tr>
                    <tr><th>Email forwarding</th><td><label><input type="checkbox" name="enable_email" <?php checked( $s['enable_email'] ); ?> /> Forward leads via email</label></td></tr>
                </table>
                <?php submit_button(); ?>
            </form>
        </div>
        <?php
    }
}

RSS_Lead_Form::init();
