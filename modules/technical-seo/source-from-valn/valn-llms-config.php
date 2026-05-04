<?php
/**
 * Plugin Name: VALN LLMs Config
 * Description: Shared configuration for VALN AI retrieval infrastructure.
 *              Curated page list with hand-written descriptions.
 * Version: 2.0.0
 * Author: VALN
 */
if ( ! defined( 'ABSPATH' ) ) exit;

/**
 * Return the curated content configuration.
 *
 * Each item: [ 'id' => post_id, 'path' => '/slug/', 'title' => '...', 'desc' => '...' ]
 * Post IDs are used for content retrieval (llms-full.txt, markdown variants).
 * Paths + titles + descriptions are used for llms.txt generation.
 */
function valn_llms_get_config() {
    return [
        'intro' => 'VA Loan Network is a Veteran-owned mortgage resource helping Veterans, active-duty Service Members, and surviving spouses navigate VA home loan benefits. We provide calculators, eligibility tools, educational guides, and connect qualified borrowers with experienced VA loan officers.',

        'disclosures' => 'VA Loan Network is a marketing platform that connects veterans with licensed mortgage professionals. We are not a lender, not a government agency, and do not originate or fund loans. Loans referenced through this site are originated by licensed mortgage professionals at our partner lenders. Equal Housing Opportunity.',

        'sections' => [
            [
                'key'   => 'about',
                'title' => 'About',
                'items' => [
                    [ 'id' => 29888, 'path' => '/va-loan-network-editorial-team/', 'title' => 'Editorial Team', 'desc' => 'Content standards and review process' ],
                    [ 'id' => 35259, 'path' => '/about-matt-schwartz/', 'title' => 'About Matt Schwartz', 'desc' => 'Founder profile' ],
                ],
            ],
            [
                'key'   => 'guides',
                'title' => 'Core VA Loan Guides',
                'items' => [
                    [ 'id' => 602,   'path' => '/va-loans/', 'title' => 'VA Loans Overview', 'desc' => 'Dashboard with eligibility, property, and readiness tools' ],
                    [ 'id' => 648,   'path' => '/va-loans/va-loan-requirements/', 'title' => 'VA Loan Requirements', 'desc' => 'The 3 deal-killers every Veteran should know' ],
                    [ 'id' => 629,   'path' => '/va-loans/va-loan-benefits/', 'title' => 'VA Loan Benefits', 'desc' => 'Zero down, no PMI, competitive rates explained' ],
                    [ 'id' => 31609, 'path' => '/va-loans/va-loan-hub/', 'title' => 'VA Loan Hub', 'desc' => 'Comprehensive guide hub for all VA loan topics' ],
                    [ 'id' => 31373, 'path' => '/va-loans/complex-va-loan-center/', 'title' => 'Complex VA Loan Center', 'desc' => 'Non-standard scenarios — bankruptcy, low credit, self-employment' ],
                    [ 'id' => 32271, 'path' => '/va-loans/data/', 'title' => 'VA Loan Data Hub', 'desc' => 'Tables, lookups, and downloadable reference data' ],
                    [ 'id' => 32430, 'path' => '/va-loans/entitlement/', 'title' => 'VA Entitlement Explained', 'desc' => 'Full and bonus entitlement, restoration rules' ],
                ],
            ],
            [
                'key'   => 'tools',
                'title' => 'Calculators & Interactive Tools',
                'items' => [
                    [ 'id' => 11686, 'path' => '/how-much-va-loan-can-i-afford/', 'title' => 'VA Loan Affordability Calculator', 'desc' => 'Estimate how much home you can afford with a VA loan' ],
                    [ 'id' => 15382, 'path' => '/va-disability-rate-calculator/', 'title' => 'VA Disability Rate Calculator', 'desc' => 'Estimate monthly VA disability compensation by rating' ],
                    [ 'id' => 11034, 'path' => '/bah-pay-calculator/', 'title' => 'BAH Pay Calculator', 'desc' => 'Look up Basic Allowance for Housing by location and pay grade' ],
                    [ 'id' => 232,   'path' => '/va-residual-income-chart/', 'title' => 'VA Residual Income Calculator', 'desc' => 'Check if you meet VA residual income thresholds' ],
                    [ 'id' => 12538, 'path' => '/4-percent-rule-on-va-loan/', 'title' => 'VA Seller Concessions Calculator', 'desc' => 'Calculate the 4% seller concession limit' ],
                    [ 'id' => 70,    'path' => '/va-loans/va-loan-limits/', 'title' => 'VA County Loan Limit Lookup', 'desc' => 'Find 2026 VA loan limits by county' ],
                    [ 'id' => 713,   'path' => '/va-loans/irrrl/', 'title' => 'VA IRRRL Savings Calculator', 'desc' => 'Estimate savings from a VA streamline refinance' ],
                    [ 'id' => 1106,  'path' => '/va-loans/jumbo-va-loans/', 'title' => 'VA Jumbo Loan Calculator', 'desc' => 'Zero-down jumbo loans over the conforming limit' ],
                    [ 'id' => 10668, 'path' => '/property-tax-exemptions/', 'title' => 'Disabled Veteran Property Tax Calculator', 'desc' => 'Estimate property tax savings by state and disability rating' ],
                    [ 'id' => 32944, 'path' => '/2026-military-pay-raise-calculator/', 'title' => 'Military Pay Raise Calculator', 'desc' => '2026 pay raise impact by grade and years of service' ],
                    [ 'id' => 36577, 'path' => '/va-eligibility-calculator/', 'title' => 'VA Eligibility Calculator', 'desc' => 'Quick eligibility check for VA loan benefits' ],
                ],
            ],
            [
                'key'   => 'eligibility',
                'title' => 'Eligibility & Requirements',
                'items' => [
                    [ 'id' => 12314, 'path' => '/va-service-requirements/', 'title' => 'VA Service Requirements', 'desc' => 'Active duty, Reserve, Guard, and surviving spouse eligibility rules' ],
                    [ 'id' => 9283,  'path' => '/va-minimum-property-requirements/', 'title' => 'VA Minimum Property Requirements', 'desc' => 'What the VA appraiser checks before closing' ],
                    [ 'id' => 14283, 'path' => '/va-appraisal-cost/', 'title' => 'VA Appraisal Costs', 'desc' => '2026 official fee schedule by state' ],
                    [ 'id' => 833,   'path' => '/va-loans/va-funding-fee/', 'title' => 'VA Funding Fee', 'desc' => 'Current rates, exemptions, and how to calculate your fee' ],
                    [ 'id' => 32382, 'path' => '/va-loans/data/allowable-fees/', 'title' => 'VA Loan Allowable Fees', 'desc' => 'Complete list of what Veterans can and cannot be charged' ],
                    [ 'id' => 2621,  'path' => '/what-is-dti-ratio/', 'title' => 'DTI Ratio Guide', 'desc' => 'Can your DTI exceed 41% for a VA loan?' ],
                    [ 'id' => 30386, 'path' => '/va-loan-occupancy-exceptions/', 'title' => 'VA Occupancy Exceptions', 'desc' => "When you don't have to move in within 60 days" ],
                    [ 'id' => 12668, 'path' => '/denied-coe-for-va-home-loan/', 'title' => "Denied COE — What's Next", 'desc' => 'Steps after a Certificate of Eligibility denial' ],
                    [ 'id' => 32995, 'path' => '/va-disability-income-mortgage-qualification/', 'title' => 'VA Disability Income for Mortgages', 'desc' => 'How disability pay counts as qualifying income' ],
                    [ 'id' => 36723, 'path' => '/community-property-states-va-loan/', 'title' => 'Community Property States', 'desc' => 'How spouse debt affects VA loan qualification' ],
                ],
            ],
            [
                'key'   => 'refinance',
                'title' => 'Refinance',
                'items' => [
                    [ 'id' => 661, 'path' => '/va-loans/refinance/', 'title' => 'VA Refinance Guide', 'desc' => 'Compare IRRRL, cash-out, and conventional refi options' ],
                    [ 'id' => 713, 'path' => '/va-loans/irrrl/', 'title' => 'VA IRRRL (Streamline)', 'desc' => 'Interest Rate Reduction Refinance Loan requirements and calculator' ],
                    [ 'id' => 721, 'path' => '/va-loans/cash-out-refinance/', 'title' => 'VA Cash-Out Refinance', 'desc' => 'Tap home equity with a VA cash-out loan' ],
                ],
            ],
            [
                'key'   => 'rates',
                'title' => 'Rates & Financial Data',
                'items' => [
                    [ 'id' => 8306,  'path' => '/todays-va-home-loan-rates/', 'title' => "Today's VA Loan Rates", 'desc' => 'Current VA mortgage rate trends' ],
                    [ 'id' => 9595,  'path' => '/va-disability-rates/', 'title' => '2026 VA Disability Rates', 'desc' => 'Monthly compensation amounts by rating percentage' ],
                    [ 'id' => 11040, 'path' => '/basic-allowance-for-housing-rates/', 'title' => '2026 BAH Rates', 'desc' => 'National BAH rate tables with state-by-state breakdowns' ],
                    [ 'id' => 32857, 'path' => '/2026-military-pay-raise-basic-pay-tables/', 'title' => '2026 Military Pay Tables', 'desc' => 'Basic pay by grade and years of service' ],
                    [ 'id' => 12804, 'path' => '/disabled-veterans-exempt-from-va-funding-fee/', 'title' => 'VA Funding Fee Exemptions', 'desc' => 'Who qualifies for a funding fee waiver' ],
                    [ 'id' => 12368, 'path' => '/roll-va-funding-fee-into-loan/', 'title' => 'Roll Funding Fee into Loan', 'desc' => 'How to finance the VA funding fee' ],
                ],
            ],
            [
                'key'   => 'special',
                'title' => 'Special Situations',
                'items' => [
                    [ 'id' => 2204, 'path' => '/getting-va-loan-after-bankruptcy/', 'title' => 'VA Loan After Bankruptcy', 'desc' => 'Chapter 7 and Chapter 13 waiting periods' ],
                    [ 'id' => 8291, 'path' => '/can-non-veteran-assume-va-loan/', 'title' => 'Non-Veteran VA Loan Assumption', 'desc' => 'Rules for assuming a VA loan without military service' ],
                    [ 'id' => 8043, 'path' => '/can-you-buy-land-with-a-va-loan/', 'title' => 'Buying Land with a VA Loan', 'desc' => "What's allowed and construction alternatives" ],
                    [ 'id' => 697,  'path' => '/va-loans/va-closing-checklist/', 'title' => 'VA Closing Checklist', 'desc' => 'Step-by-step guide to closing day' ],
                    [ 'id' => 856,  'path' => '/va-loans/usda-loans-vs-va-loans/', 'title' => 'USDA vs VA Loans', 'desc' => 'Side-by-side comparison of rural and VA loan programs' ],
                    [ 'id' => 4192, 'path' => '/comparing-va-rates-to-conventional-mortgage-rates/', 'title' => 'VA vs Conventional Rates', 'desc' => 'How VA rates compare to conventional mortgages' ],
                ],
            ],
            [
                'key'   => 'disability',
                'title' => 'Disability & Benefits',
                'items' => [
                    [ 'id' => 9692,  'path' => '/concurrent-retirement-and-disability-pay/', 'title' => 'CRDP (Concurrent Pay)', 'desc' => 'Receiving both military retirement and VA disability' ],
                    [ 'id' => 12968, 'path' => '/disability-grants-for-veterans/', 'title' => 'Disability Grants for Veterans', 'desc' => 'SAH, SHA, and TRA grant programs' ],
                    [ 'id' => 19681, 'path' => '/bah-changes-after-pcs/', 'title' => 'BAH After PCS', 'desc' => 'How your housing allowance changes with a permanent change of station' ],
                ],
            ],
        ],

        'contact' => [
            'cta'   => [ 'id' => 385, 'path' => '/compare-loan-offers/', 'title' => 'Get Started', 'desc' => 'Connect with a VA loan specialist — no SSN, no credit pull' ],
            'phone' => '1-800-230-7201',
        ],
    ];
}

/**
 * Get flat array of all unique post IDs in the curated list.
 */
function valn_llms_get_all_post_ids() {
    $config = valn_llms_get_config();
    $ids = [];
    foreach ( $config['sections'] as $section ) {
        foreach ( $section['items'] as $item ) {
            $ids[] = $item['id'];
        }
    }
    $ids[] = $config['contact']['cta']['id'];
    return array_unique( $ids );
}

/**
 * Get post IDs flagged as interactive tools (get description-only markdown fallback).
 */
function valn_llms_get_tool_post_ids() {
    return [ 11686, 15382, 11034, 232, 12538, 70, 713, 1106, 10668, 32944, 36577 ];
}

/**
 * Check if a given post ID is a tool/calculator page.
 */
function valn_llms_is_tool_page( $post_id ) {
    return in_array( (int) $post_id, valn_llms_get_tool_post_ids(), true );
}
