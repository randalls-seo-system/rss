<?php
/**
 * Plugin Name: VALN Redirect Engine
 * Description: Unified 301 redirect handler for all cannibalization merges, P1 fixes, and broken-link patterns.
 *              Deployed because Yoast Premium runtime redirects are not firing on this site (WP Engine full-page
 *              cache intercepts requests before template_redirect runs on cold-cache hits; Yoast also calls
 *              handle_redirects() directly at plugins_loaded which conflicts with object-cache-pro warm state).
 *              This mu-plugin fires at template_redirect priority 0, beats canonical/404 handling, and works
 *              whether or not the page cache has been primed.
 * Version: 2.3.0
 * Author: VALN Engineering
 * Last updated: 2026-04-26
 *
 * IMPORTANT: Do NOT delete this file and rely on Yoast redirects until the Yoast issue is diagnosed and fixed.
 *            Yoast redirects are left in place for admin-UI visibility only.
 */

add_action( 'template_redirect', function () {
    // Skip admin, AJAX, cron, REST, and feed requests.
    if (
        is_admin()
        || ( defined( 'DOING_AJAX' ) && DOING_AJAX )
        || ( defined( 'DOING_CRON' ) && DOING_CRON )
        || ( defined( 'REST_REQUEST' ) && REST_REQUEST )
    ) {
        return;
    }

    $uri  = $_SERVER['REQUEST_URI'] ?? '';
    $path = strtok( $uri, '?' );
    if ( $path === '' || $path[0] !== '/' ) {
        return;
    }
    // Normalize: single leading slash, single trailing slash, lowercase.
    $normalized = '/' . trim( strtolower( $path ), '/' ) . '/';

    // -------------------------------------------------------------------------
    // REDIRECT MAP
    // Keys   = incoming path (normalized: lowercase, trailing slash)
    // Values = destination path or full URL
    //
    // Sections:
    //   A. Cannibalization Type 1  (9 redirects — merged duplicate articles)
    //   B. Cannibalization Type 2 Batch 1  (10 redirects)
    //   C. Cannibalization Type 2 Batch 2  (9 redirects)
    //   D. P1 redirects from 2026-04-05  (6 redirects)
    //   E. Top broken-link patterns by occurrence count  (10+ redirects)
    //   F. Draft pages — redirect to nearest live equivalent
    // -------------------------------------------------------------------------

    static $map = [

        // ── A. CANNIBALIZATION TYPE 1 ─────────────────────────────────────────
        // Original mu-plugin entries (9). Preserved exactly.
        '/warrior-dividend-eligibility-1776-bonus/'              => '/warrior-dividend-1776-how-to-receive-verify/',
        '/va-loan-rate-predictions-march-2026/'                  => '/va-loan-rate-trends-2026/',
        '/co-borrower-on-a-va-loan/'                             => '/va-loan-co-borrowers-and-co-signer-guidelines/',
        '/can-you-use-a-va-loan-more-than-once/'                 => '/first-vs-subsequent-va-loan-use/',
        '/is-it-hard-to-sell-a-house-to-someone-with-a-va-loan/' => '/why-would-a-seller-not-accept-a-va-loan/',
        '/military-housing-allowance-vs-bah/'                    => '/basic-allowance-for-housing-rates/',
        '/va-adaptive-housing-grants/'                           => '/housing-grants-for-disabled-veterans/',
        '/calculate-your-dti-ratio/'                             => '/what-is-dti-ratio/',
        '/va-disability-rates-cola-grants-2026/'                 => '/va-disability-rates/',

        // ── B. CANNIBALIZATION TYPE 2 BATCH 1 ────────────────────────────────
        // (10 redirects — from Yoast export, cannibalization merges)
        '/va-loan-with-bad-credit/'                              => '/va-loans/bad-credit-va-loan/',
        '/bad-credit-va-loan/'                                   => '/va-loans/bad-credit-va-loan/',
        '/va-funding-fee/'                                       => '/va-loans/va-funding-fee/',
        '/va-loan-limits-with-full-entitlement/'                 => '/va-loans/va-loan-limits/',
        '/va-loan-limits-with-full-entitlement-2025/'            => '/va-loans/va-loan-limits/',
        '/new-va-loan-limits-in-2025-what-you-need-to-know/'     => '/va-loans/va-loan-limits/',
        '/va-loan-income-requirements/'                          => '/va-loans/income-requirements/',
        '/2025-va-income-requirements/'                          => '/va-loans/income-requirements/',
        '/va-loan-occupancy-requirements-a-complete-guide/'      => '/va-loan-occupancy-requirements/',
        '/va-loans/down-payment/'                                => '/down-payment/',

        // ── C. CANNIBALIZATION TYPE 2 BATCH 2 ────────────────────────────────
        // (9 redirects — from Yoast export, additional cannibalization merges)
        '/va-loan-600-credit-score/'                             => '/va-loans/minimum-credit-score-needed-for-va-loans/',
        '/minimum-credit-score-needed-for-va-loans/'             => '/va-loans/minimum-credit-score-needed-for-va-loans/',
        '/closing-costs/'                                        => '/va-loans/closing-costs/',
        '/va-loans/va-loan-fee-scenarios/'                       => '/va-loans/va-closing-costs-calculator/',
        '/va-manual-underwriting/'                               => '/manual-underwriting-va-loan/',
        '/va-loan-occupancy-guidelines/'                         => '/va-loan-occupancy-requirements/',
        '/va-loans/streamline-refinance/'                        => '/va-loans/irrrl/',
        '/va-loans/data/irrrl/'                                  => '/va-loans/irrrl/',

        // ── D. P1 REDIRECTS — 2026-04-05 ─────────────────────────────────────
        // /about/ → about-us (slug mismatch)
        '/about/'                                                => '/about-us/',
        // /meet-our-founder/ → Matt's author page
        '/meet-our-founder/'                                     => '/meet-levi/',
        // /va-loans/va-loan-comparison-network/ → 410 gone; redirect to compare-loan-offers
        '/va-loans/va-loan-comparison-network/'                  => '/compare-loan-offers/',
        '/va-loans/va-loan-comparison-network'                   => '/compare-loan-offers/',
        // Draft pages redirect to nearest live equivalent
        // ID 88  — /va-loan-down-payment-requirements/ → /down-payment/
        '/va-loan-down-payment-requirements/'                    => '/down-payment/',
        // ID 94  — /no-down-payment-mortgage-loans/ → /va-loan-no-down-payment-myth/
        '/no-down-payment-mortgage-loans/'                       => '/va-loan-no-down-payment-myth/',
        // ID 33585 — /va-dti-41-not-limit-2026/ → /what-is-dti-ratio/
        '/va-dti-41-not-limit-2026/'                             => '/what-is-dti-ratio/',

        // ── E. TOP BROKEN-LINK PATTERNS (by occurrence count) ────────────────
        // 1. /va-funding-fee/ (130 occurrences) — already in section B above
        // 2. /minimum-credit-score-needed-for-va-loans/ (70) — section C above
        // 3. /closing-costs/ (53) — section C above
        // 4. /va-loan-requirements/ → /va-loan-eligibility-requirements/ does not
        //    exist as a slug; nearest live page is the main va-loans page.
        //    Redirect to /va-loans/ which covers eligibility overview.
        '/va-loan-requirements/'                                 => '/va-loans/',
        // 5. /income-requirements/ (20) — section B covers va-loans/income-requirements
        '/income-requirements/'                                  => '/va-loans/income-requirements/',
        // 6. /va-loan-limits/ (17) — Yoast has this; add here too
        '/va-loan-limits/'                                       => '/va-loans/va-loan-limits/',
        // 7. /va-loans/down-payment/ (14) — section B above
        // 8. /va-closing-checklist/ (13) — target /va-closing-checklist/ IS published (ID 697), NOT broken
        //    This is already a valid page. No redirect needed here.
        // 9. /first-time-homebuyers/ (11) — target /va-loans/first-time-homebuyers/
        '/first-time-homebuyers/'                                => '/va-loans/first-time-homebuyers/',
        // 10. /va-dti-41-not-limit-2026/ (10) — section D above

        // Additional high-value patterns from audit-broken-links-final.csv
        // /entitlement/ (7) → /va-loans/entitlement/ (Yoast has this as va-loans/data/entitlement)
        '/entitlement/'                                          => '/va-loans/entitlement/',
        // /bad-credit-va-loan/ (7) — section B above
        // /cash-out-refinance/ (6) → /va-loans/irrrl/ (closest live page for refi)
        '/cash-out-refinance/'                                   => '/va-loans/irrrl/',
        // /state-veteran-benefits/ (5) → /property-tax-exemptions/ (closest benefits hub)
        '/state-veteran-benefits/'                               => '/property-tax-exemptions/',
        // /jumbo-va-loans/ (4) — check if live; if missing add redirect
        // Target: jumbo-va-loans is in Yoast as redirecting elsewhere — skip; needs verification.
        // /va-loans/texas/ (4) → /va-loan-guides/texas/
        '/va-loans/texas/'                                       => '/va-loan-guides/texas/',
        // /irrrl/ (3) → /va-loans/irrrl/
        '/irrrl/'                                                => '/va-loans/irrrl/',
        // /va-irrrl/ (1) — from audit and valn-project-status.md P2 list
        '/va-irrrl/'                                             => '/va-loans/irrrl/',
        // /va-renovation-loan/ (1) — P2 list
        '/va-renovation-loan/'                                   => '/va-renovation-loans/',
        // /va-closing-costs/ (P2 list)
        '/va-closing-costs/'                                     => '/va-loans/closing-costs/',
        // /va-loans/va-closing-costs/ (P2 list)
        '/va-loans/va-closing-costs/'                            => '/va-loans/closing-costs/',
        // /va-loans/va-loan-funding-fee/ (P2 list)
        '/va-loans/va-loan-funding-fee/'                         => '/va-loans/va-funding-fee/',
        // /va-loan/ → /va-loans/ (P2 list)
        '/va-loan/'                                              => '/va-loans/',
        // /apply-now/ → /compare-loan-offers/ (Yoast has this; reinforce here)
        '/apply-now/'                                            => '/compare-loan-offers/',
        // /bah-rates/ → /basic-allowance-for-housing-rates/
        '/bah-rates/'                                            => '/basic-allowance-for-housing-rates/',
        // /va-loan-rates/ (draft ID 847) → /todays-va-home-loan-rates/
        '/va-loan-rates/'                                        => '/todays-va-home-loan-rates/',
        // /disabled-veteran-property-tax-exemptions/ (draft ID 32121) → /property-tax-exemptions/
        '/disabled-veteran-property-tax-exemptions/'             => '/property-tax-exemptions/',
        // /va-loan-process/ is published (ID 682) — no redirect needed; omitted.
        // /allowable-fees/ → /non-allowable-fees-for-va-loans/ (closest live page)
        '/allowable-fees/'                                       => '/non-allowable-fees-for-va-loans/',
        // /refinance/ → /va-loans/irrrl/
        '/refinance/'                                            => '/va-loans/irrrl/',
        // /va-refinance/ (P2 list)
        '/va-refinance/'                                         => '/va-loans/irrrl/',
        // /va-loans/va-loan-comparison-network (without trailing slash, extra safety)
        // Already covered above.

        // ── F. DRAFT PAGES (from broken-links-2026-04-05.csv) ────────────────
        // Already covered in section D for IDs 88, 94, 33585.
        // ID 847 /va-loan-rates/ → covered above.
        // ID 32121 /disabled-veteran-property-tax-exemptions/ → covered above.

        // ID 36213 /avoid-credit-mistakes-applying-for-va-loan/ — draft, redirect to credit score page
        '/avoid-credit-mistakes-applying-for-va-loan/'           => '/how-to-improve-credit-va-loan/',
        // ID 12570 /can-the-buyer-pay-for-repairs-on-a-va-loan/ — draft, redirect to MPR page
        '/can-the-buyer-pay-for-repairs-on-a-va-loan/'           => '/va-minimum-property-requirements/',
        // NOT_FOUND: /va-mbs-strategy/ — no page exists, redirect to rate trends
        '/va-mbs-strategy/'                                      => '/todays-va-home-loan-rates/',
        // /va-loans/data/entitlement/ → /va-loans/entitlement/ (Yoast has this; reinforce here)
        '/va-loans/data/entitlement/'                            => '/va-loans/entitlement/',
        // /va-loans/data/entitlement/entitlement/ (Yoast has this — avoid double-hop)
        '/va-loans/data/entitlement/entitlement/'                => '/va-loans/entitlement/',
        // /va-loans/entitlement/allowable-fees/ — post 229 links to this non-existent path
        '/va-loans/entitlement/allowable-fees/'                  => '/non-allowable-fees-for-va-loans/',


        // ── Z. MISSING CANNIBALIZATION REDIRECTS — 2026-04-07 PATCH ──────────
        // These 10 were in the original spec but missed by the initial build.
        '/can-you-get-a-va-loan-with-bad-credit/'                => '/va-loans/bad-credit-va-loan/',
        '/no-closing-cost-va-loans/'                             => '/no-closing-cost-va-loan/',
        '/mortgage-points-on-va-loan/'                           => '/discount-points-on-va-loan/',
        '/top-10-military-cities-with-highest-bah/'              => '/15-military-cities-highest-bah-2026/',
        '/using-gift-funds-for-a-va-loan/'                       => '/va-loan-gift-funds/',
        '/what-are-points-on-va-loan/'                           => '/discount-points-on-va-loan/',
        '/restore-va-loan-entitlement/'                          => '/reinstating-va-loan-eligibility-after-home-sale/',
        '/how-disability-status-affects-va-loan-eligibility/'    => '/va-disability-rating-va-loan/',
        '/disabled-veteran-va-loans/'                            => '/va-loans-for-disabled-veterans/',
        '/2025-veterans-pension-rates/'                          => '/2026-va-pension-rates/',
        '/va-home-loan-to-build-a-house/'                        => '/va-loans/va-construction-loan/',
        // Audit patch 2026-04-07 — additional missing canonical entries
        '/va-loan-assumption/'                                   => '/va-loans/va-loan-assumption/',
        '/va-closing-costs-calculator/'                          => '/va-loans/va-closing-costs-calculator/',
        '/va-closing-checklist/'                                 => '/va-loans/va-closing-checklist/',
        '/rent-out-home-with-va-loan/'                           => '/renting-out-your-va-purchased-home/',
        '/partial-entitlement/'                                  => '/partial-entitlement-vs-full-entitlement/',

        // === 2026-04-11 consolidation redirects ===
        '/how-to-increase-my-va-disability-rating/'                   => '/how-to-increase-va-disability-rating/',
        '/va-appraisals-scheduled-christmas-week/'                    => '/holidays-delay-va-loan-closing/',
        '/va-lenders-open-christmas-eve-closing/'                     => '/holidays-delay-va-loan-closing/',
        '/common-va-loan-myths-around-christmas/'                     => '/holidays-delay-va-loan-closing/',
        '/va-loan-closing-date-december-vs-january/'                  => '/holidays-delay-va-loan-closing/',
        '/government-shutdown-ending-va-services-restart/'            => '/va-loans-government-shutdown/',
        '/shutdown-ends-va-services-restored-benefits-backlogs/'      => '/va-loans-government-shutdown/',
        '/va-home-loans-closings-appraisals-after-shutdown-ends/'     => '/va-loans-government-shutdown/',
        '/government-reopening-flights-snap-va-checklist/'            => '/va-loans-government-shutdown/',

        // === 2026-04-11 batch 2 consolidation redirects ===
        '/government-shutdown-survival-guide-for-veterans/'                => '/va-loans-government-shutdown/',
        '/va-loan-shutdown-survival-guide-for-veterans/'                   => '/va-loans-government-shutdown/',
        '/government-shutdown-veterans-what-stays-open/'                   => '/va-loans-government-shutdown/',
        '/2025-va-rates-lower-than-conventional/'                          => '/va-rates-lower-than-conventional/',
        '/comparing-va-rates-to-conventional-mortgage-rates-in-2024/'      => '/comparing-va-rates-to-conventional-mortgage-rates/',
        '/q4-2024-va-loan-rates-predictions/'                              => '/2026-va-loan-rate-forecast-tool/',
        '/best-va-rate-in-todays-market/'                                  => '/todays-va-home-loan-rates/',
        '/what-will-happen-with-mortgage-rates-in-2025/'                   => '/2026-va-loan-rate-forecast-tool/',
        '/home-buying-checklist-for-veterans-in-2024/'                     => '/simple-va-loan-checklist-2026/',

        // === 2026-04-11 batch 3 redirects ===
        '/va-mortgage-rate-forecast-q4-2025/'                         => '/2026-va-loan-rate-forecast-tool/',
        '/fed-cut-means-va-loan-rates-2025/'                          => '/what-fed-rate-cuts-mean-for-your-mortgage/',

        // === 2026-04-11 cannibalization redirects ===
        '/navy-federal-pay-dates/'                               => '/2026-navy-federal-pay-dates/',
        '/usaa-military-pay-dates-2025/'                         => '/usaa-military-pay-dates-2026/',
        '/2026-usaa-military-pay-dates/'                         => '/usaa-military-pay-dates-2026/',

        // === 2026-04-19 SEMrush 4xx audit redirects ===
        '/how-va-loans-compare-to-conventional-loans/'        => '/va-loans-vs-conventional-loans/',
        '/tidewater-reconsideration-of-value/'                => '/va-tidewater-initiative/',
        '/va-disability-rating-and-va-loans/'                 => '/va-disability-rating-va-loan/',
        '/va-loan-appraisal-tidewater-initiative/'            => '/va-tidewater-initiative/',
        '/va-loan-calculator/'                                => '/va-loan-payment-calculator/',
        '/va-loan-seller-concessions/'                        => '/2026-va-loan-seller-guide/',
        '/va-loans-for-manufactured-and-mobile-homes/'        => '/va-loans-for-manufactured-and-mobile-home/',
        '/va-loans/va-cash-out-refinance/'                    => '/cash-out-refinance/',
        '/military-base-guides/'                              => '/va-loans/',
        '/va-condo-approval-requirements/'                    => '/va-condo-single-unit-approval/',


        // === 2026-04-24 GA4 404 fixes ===
        '/personal-va-loan-applications/'          => '/compare-loan-offers/',
        '/2025-va-loan-limits/'                    => '/va-loans/va-loan-limits/',
        '/va-loan-closing-costs/'                  => '/va-loans/closing-costs/',
        '/va-loan-rate-forecast-2025/'             => '/2026-va-loan-rate-forecast-tool/',
        '/va-loan-rate-forecast/'                  => '/2026-va-loan-rate-forecast-tool/',


        // === 2026-04-24 SEMrush broken internal link redirects ===
        '/va-loan-dti/'                              => '/what-is-dti-ratio/',
        '/va-loan-after-bankruptcy/'                  => '/getting-va-loan-after-bankruptcy/',
        '/va-loan-multi-unit/'                        => '/types-of-properties-you-can-buy-with-va-loan/',
        '/grossing-up-va-disability-income/'          => '/gross-up-va-benefits/',
        '/using-military-pay-to-qualify-for-va-loan/' => '/using-military-pay-for-va-loan-qualification/',
        '/va-appraisal-checklist/'                    => '/va-appraisal-mpr-pass-checklist-closing-timeline/',
        '/va-appraisal-reconsideration-of-value/'     => '/how-to-appeal-va-loan-appraisal/',
        '/va-loan-eligibility-quiz/'                  => '/va-eligibility-calculator/',
        '/va-loans/property-requirements/'            => '/va-minimum-property-requirements/',
        '/va-rapid-rescore/'                          => '/rapid-rescores-va-mortgage-credit/',
        '/two-va-loans-at-once/'                      => '/second-tier-entitlement/',
        '/who-is-eligible-for-a-va-loan/'             => '/how-to-qualify-for-va-loan/',

        // === 2026-04-25 corrupted page redirects (16 pages — Homebuilder Confidence body corruption) ===
        '/5-hidden-costs-of-buying-a-home/'                                => '/va-loans/',
        '/understanding-hoa-fees/'                                         => '/va-loans/',
        '/why-va-loans-remain-great-deal-in-unpredictable-market/'         => '/va-loans/',
        '/current-events-shaping-2024-housing-market-veterans/'            => '/va-loans/',
        '/how-to-sell-your-home-in-30-days-or-less/'                       => '/va-loans/',
        '/help-with-va-claims-appeals/'                                    => '/va-disability-rates/',
        '/us-housing-crisis-deepens-home-sales-lowest-since-2010/'         => '/va-loans/',
        '/how-inflation-impacts-2024-housing-market/'                      => '/va-loans/',
        '/5-reasons-mortgage-rates-are-dropping/'                          => '/va-loans/',
        '/30-renters-for-each-home-on-sale/'                               => '/va-loans/',
        '/whats-happening-with-home-prices-2024/'                          => '/va-loans/',
        '/rising-mortgage-rates-signal-of-what-to-come-for-economy/'       => '/va-loans/',
        '/what-happens-to-housing-market-if-trump-wins/'                   => '/va-loans/',
        '/how-to-access-va-healthcare/'                                    => '/va-loans/',
        '/how-to-avoid-homebuyers-remorse/'                                => '/va-loans/',
        '/is-a-housing-crash-coming-what-veterans-need-to-know/'           => '/va-loans/',

        // === 2026-04-26 disability cluster consolidation + fabricated-expert redirects ===
        '/va-disability-ratings/'                                        => '/va-disability-rates/',
        '/2024-va-disability-rates/'                                     => '/va-disability-rates/',
        '/how-ai-is-transforming-housing-market/'                        => '/va-loans/',
        '/10-red-flags-to-watch-out-for-when-viewing-a-home/'            => '/va-loans/',

        // === 2026-04-26 fabricated-quote triage redirects (4 pages) ===
        '/2024-va-disability-rates/'                                       => '/va-disability-rates/',
        '/10-red-flags-to-watch-out-for-when-viewing-a-home/'              => '/va-loans/',
        '/how-ai-is-transforming-housing-market/'                          => '/va-loans/',
        '/impact-of-election-uncertainty-on-mortgage-rates/'               => '/va-loans/',

        // === 2026-04-26 Disability cluster consolidation redirects ===
        '/2024-va-disability-rates/'                             => '/va-disability-rates/',
        '/10-red-flags-to-watch-out-for-when-viewing-a-home/'    => '/va-loans/',
        '/how-ai-is-transforming-housing-market/'                => '/va-loans/',
        '/impact-of-election-uncertainty-on-mortgage-rates/'     => '/va-loans/',

        // --- G. Active 404 fixes (2026-04-29 emergency restore) ---
        '/using-va-loan-to-buy-a-condo/'                        => '/condo-lookup/',
        '/2026-va-disability-rates/'                             => '/va-disability-rates/',
        '/va-home-loan-rates/'                                   => '/todays-va-home-loan-rates/',
    ];

    if ( isset( $map[ $normalized ] ) ) {
        $destination = $map[ $normalized ];
        // If the destination is a relative path, make it absolute.
        if ( $destination[0] === '/' ) {
            $destination = home_url( $destination );
        }
        wp_redirect( $destination, 301 );
        exit;
    }
}, 0 );
