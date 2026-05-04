<?php
/**
 * MU Plugin: BASE PURGE 410
 * Returns HTTP 410 Gone for retired content paths.
 *
 * Intent:
 *  - KEEP /pcs-guide/
 *  - 410 everything under /military-bases/
 *  - 410 non-VLG pages ending in -guide (protects /va-loan-guides/*)
 *  - EXCEPTIONS: allow specific -guide URLs that must remain live
 */

add_action('template_redirect', function () {
  $uri = $_SERVER['REQUEST_URI'] ?? '';
  if ($uri === '') return;

  $path = parse_url($uri, PHP_URL_PATH) ?: '/';

  // Normalize trailing slash for comparisons
  $norm = rtrim($path, '/');
  if ($norm === '') $norm = '/';

  // KEEP: PCS guide page must remain live
  if (preg_match('#^/pcs-guide/?$#i', $path)) {
    return;
  }

  // ALLOWLIST: these specific URLs must NOT be 410'd
  // (exact path match, with or without trailing slash)
  $allow = [
    '/2026-va-loan-seller-guide',
    '/calvet-loans-in-california-guide',
    '/category/va-loan-credit-guide',
    '/tla-vs-tle-pcs-lodging-benefit-guide',
    '/va-vendee-financing-guide',
  ];
  foreach ($allow as $keep) {
    if (strcasecmp($norm, $keep) === 0) {
      return;
    }
  }

  // 410 for /military-bases/ and anything under it
  if (preg_match('#^/military-bases(/|$)#i', $path)) {
    status_header(410);
    header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
    header('Pragma: no-cache');
    echo 'Gone';
    exit;
  }

  // 410 for non-VLG *-guide pages (protects /va-loan-guides/*)
  if (preg_match('#^/(?!va-loan-guides/).+-guide/?$#i', $path)) {
    status_header(410);
    header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
    header('Pragma: no-cache');
    echo 'Gone';
    exit;
  }
}, 0);
