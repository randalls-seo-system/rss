<?php
/**
 * Plugin Name: LRG Article Styles
 * Description: Inlines rl-base.css + rl-cards.css on single posts for V3 article styling. LRG red/navy palette.
 * Version: 1.0.1
 * Author: VALN Team
 */

if ( ! defined( 'ABSPATH' ) ) {
    exit;
}

add_action( 'wp_head', function () {
    if ( ! is_singular( 'post' ) ) {
        return;
    }
    ?>
<style id="lrg-article-styles">
.rl-page {
  --rl-bg: #ffffff;
  --rl-border: #e2e8f0;
  --rl-card-radius: 24px;
  --rl-card-radius-sm: 18px;
  --rl-card-padding: 22px;
  --rl-card-shadow: 0 12px 34px rgba(15, 23, 42, 0.10), 0 2px 10px rgba(15, 23, 42, 0.06);
  --rl-card-shadow-sm: 0 12px 30px rgba(15, 23, 42, 0.08);
  --rl-primary-dark: #0F1F4A;
  --rl-text-muted: #475569;
  --rl-font-weight-heavy: 900;
}

/* VALN Interactive Pages — Shared CSS
   - Scoped to .rl-page (recommended).
   - Backward compatible with .rl-page.
   - No CSS variables / :where() so WP's built-in editor linter won't block saves.
*/

/* Root wrapper */
.rl-page{
  font-family: system-ui,-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  color:#0f172a;

  background:
    radial-gradient(1200px 600px at 12% 0, rgba(200,16,46,.12), transparent 55%),
    radial-gradient(900px 500px at 88% 12%, rgba(200,16,46,.10), transparent 60%),
    #f8f9fa;

  padding:28px 16px 72px;
}

@media (max-width:640px){
  .rl-page{ padding:20px 12px 64px; }
}

.rl-page,
.rl-page *{ box-sizing:border-box; }

/* Focus */
.rl-page a:focus,
.rl-page button:focus,
.rl-page input:focus,
.rl-page select:focus,
.rl-page summary:focus,
.rl-page textarea:focus{
  outline:3px solid rgba(200,16,46,.35);
  outline-offset:2px;
  border-radius:10px;
}

.rl-page a{ color:#C8102E; text-decoration:none; }
.rl-page a:hover{ text-decoration:underline; }

/* Wrap */
.rl-page .rl-wrap{ max-width:1120px; margin:0 auto; }

/* Hide helper (JS can override with inline style when needed) */
.rl-page .rl-hide{ display:none; }

/* Honeypot wrapper for forms */
.rl-page .rl-hp-wrap{ position:absolute; left:-9999px; width:1px; height:1px; overflow:hidden; }

/* Defensive typography against theme overrides */
.rl-page p,
.rl-page li,
.rl-page td,
.rl-page th,
.rl-page dt,
.rl-page dd,
.rl-page label,
.rl-page input,
.rl-page select,
.rl-page button,
.rl-page summary{
  font-size:14px;
  line-height:1.65;
}

.rl-page h1,
.rl-page h2,
.rl-page h3,
.rl-page h4{
  color:#0F1F4A !important;
  letter-spacing:-.01em;
  margin:0;
}

/* Headings (avoid clamp() so WP linter won't complain) */
.rl-page h1{
  font-size:36px;
  font-weight:900;
  line-height:1.12;
}
@media (max-width:640px){
  .rl-page h1{ font-size:30px; }
}

.rl-page h2{
  font-size:26px;
  font-weight:850;
  line-height:1.22;
}
@media (max-width:640px){
  .rl-page h2{ font-size:22px; }
}

.rl-page h3{
  font-size:16px;
  font-weight:850;
  line-height:1.22;
}

.rl-page h4{
  font-size:15px;
  font-weight:850;
  line-height:1.25;
}

.rl-page p{
  margin:0 0 10px;
  color:#475569;
  max-width:100% !important;
}
.rl-page p:last-child{ margin-bottom:0; }

/* Skip link */
.rl-page .rl-skip{
  position:absolute;
  left:-9999px;
  top:10px;
  z-index:9999;
  background:#fff;
  color:#0f172a;
  border:2px solid #C8102E;
  border-radius:12px;
  padding:10px 12px;
  font-weight:850;
}
.rl-page .rl-skip:focus{ left:12px; }

/* Cards */
.rl-page .rl-card{
  background:#ffffff;
  border:1px solid #e2e8f0;
  border-radius:24px;
  box-shadow:0 12px 34px rgba(15,23,42,.10), 0 2px 10px rgba(15,23,42,.06);
}
.rl-page .rl-card-inner{ padding:22px 22px 20px; }
@media (max-width:640px){
  .rl-page .rl-card-inner{ padding:16px 14px; }
}

/* Hero */
.rl-page .rl-hero{ margin-bottom:18px; }

.rl-page .rl-breadcrumb{
  display:flex;
  flex-wrap:wrap;
  gap:8px;
  align-items:center;
  color:#475569;
  font-size:12.5px;
}
.rl-page .rl-breadcrumb a{ font-weight:800; }
.rl-page .rl-breadcrumb .sep,
.rl-page .rl-breadcrumb span[aria-hidden="true"]{ color:#94a3b8; }

.rl-page .rl-eyebrow,
.rl-page .rl-hero-eyebrow{
  display:inline-flex;
  align-items:center;
  gap:8px;
  padding:6px 12px;
  border-radius:999px;
  background:#fff;
  border:1px solid rgba(22,163,74,.45);
  color:#475569;
  font-size:11.5px;
  text-transform:uppercase;
  letter-spacing:.06em;
  margin-top:10px;
}

.rl-page .rl-eyebrow .dot,
.rl-page .rl-hero-dot{
  width:9px; height:9px; border-radius:999px;
  background:#16a34a;
  box-shadow:0 0 0 5px rgba(22,163,74,.22);
}

.rl-page .rl-eyebrow strong,
.rl-page .rl-accent-word{ color:#16a34a; font-weight:900; }

.rl-page .rl-meta,
.rl-page .rl-hero-meta{
  display:flex;
  flex-wrap:wrap;
  gap:8px;
  align-items:center;
  margin-top:8px;
  color:#475569;
  font-size:12.5px;
  width:100%;
}

.rl-page .rl-meta strong{ color:#0f172a; font-weight:800; }
.rl-page .rl-meta .sep{ color:#94a3b8; }

.rl-page .rl-hero-lead,
.rl-page .rl-hero-lead{
  margin-top:10px;
  color:#475569;
  width:100%;
  max-width:100% !important;
}

/* Pills */
.rl-page .rl-pills,
.rl-page .rl-hero-jumps{
  display:flex;
  flex-wrap:wrap;
  gap:10px;
  margin-top:12px;
  padding:0;
}

@media (max-width:760px){
  .rl-page .rl-pills,
  .rl-page .rl-hero-jumps{
    flex-wrap:nowrap;
    overflow-x:auto;
    padding-bottom:6px;
    -webkit-overflow-scrolling:touch;
  }
  .rl-page .rl-pills::-webkit-scrollbar,
  .rl-page .rl-hero-jumps::-webkit-scrollbar{ display:none; }
}

.rl-page .rl-pill,
.rl-page .rl-pill{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  padding:8px 12px;
  border-radius:999px;
  border:1px solid #cbd5e1;
  background:#fff;
  color:#0F1F4A;
  font-weight:850;
  font-size:12.5px;
  white-space:nowrap;
  text-decoration:none !important;
  user-select:none;
}

.rl-page .rl-pill:hover,
.rl-page .rl-pill:hover{ background:#f1f5f9; text-decoration:none !important; }

/* Buttons */
.rl-page .rl-ctas,
.rl-page .rl-hero-ctas,
.rl-page .rl-form-actions,
.rl-page .rl-ctas{
  display:flex;
  flex-wrap:wrap;
  gap:10px;
  margin-top:14px;
  align-items:center;
}

.rl-page .rl-btn{
  display:inline-flex;
  align-items:center;
  justify-content:center;
  gap:8px;
  border-radius:999px;
  border:1px solid transparent;
  padding:11px 18px;
  font-weight:900;
  font-size:14px;
  cursor:pointer;
  text-decoration:none !important;
  line-height:1.2;
  user-select:none;
}

@media (max-width:640px){
  .rl-page .rl-btn{ padding:10px 14px; font-size:13.5px; }
}

.rl-page .rl-btn--primary,
.rl-page .rl-lead-pill{
  background:#0F1F4A;
  border-color:#0F1F4A;
  color:#fff !important;
}
.rl-page .rl-btn--primary:hover,
.rl-page .rl-lead-pill:hover{ background:#0F1F4A; border-color:#0F1F4A; }

.rl-page .rl-btn--secondary,
.rl-page .rl-btn--ghost{
  background:#fff;
  border-color:#cbd5e1;
  color:#0F1F4A !important;
}
.rl-page .rl-btn--secondary:hover,
.rl-page .rl-btn--ghost:hover{ background:#f1f5ff; }

.rl-page .rl-btn--success,
.rl-page .rl-btn--success-pill{
  background:#0F1F4A;
  border-color:#0F1F4A;
  color:#fff !important;
}
.rl-page .rl-btn--success:hover,
.rl-page .rl-btn--success-pill:hover{ background:#0F1F4A; border-color:#0F1F4A; }

/* Optional green filled button (use intentionally; not the default primary CTA) */
.rl-page .rl-btn--green{
  background:#16a34a;
  border-color:#16a34a;
  color:#fff !important;
}
.rl-page .rl-btn--green:hover{ background:#15803d; border-color:#15803d; }

/* Compare/Offer buttons: white with green border + green text */
.rl-page .rl-btn--compare,
.rl-page a.rl-btn--compare{
  background:#fff !important;
  border-color:rgba(22,163,74,.55) !important;
  color:#15803d !important;
  text-decoration:none !important;
}
.rl-page .rl-btn--compare:hover,
.rl-page a.rl-btn--compare:hover{
  background:#ecfdf5 !important;
  border-color:rgba(22,163,74,.65) !important;
  color:#15803d !important;
  text-decoration:none !important;
}

/* Reset: red text, no pill */
.rl-page .rl-btn--reset-link,
.rl-page button.rl-btn--reset-link{
  background:transparent !important;
  border:0 !important;
  padding:0 !important;
  border-radius:0 !important;
  color:#dc2626 !important;
  font-weight:900;
}
.rl-page .rl-btn--reset-link:hover{ text-decoration:underline !important; background:transparent !important; }

/* Small button */
.rl-page .rl-btn--small{ padding:8px 14px; font-size:13px; }

/* Quick cards */
.rl-page .rl-quick-grid{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:12px;
  margin-top:14px;
}
@media (max-width:860px){ .rl-page .rl-quick-grid{ grid-template-columns:minmax(0,1fr); } }

.rl-page .rl-quick-card{
  border-radius:18px;
  border:1px solid #fecaca;
  background:linear-gradient(180deg, rgba(239,246,255,.96) 0%, rgba(255,255,255,.98) 100%);
  padding:14px 14px 12px;
  box-shadow:0 12px 30px rgba(15,23,42,.08);
}
.rl-page .rl-quick-card h3{ font-size:15px; font-weight:900; margin-bottom:8px; color:#0F1F4A; }

.rl-page .rl-quick-card ul,
.rl-page .rl-result-body ul,
.rl-page .rl-callout ul{
  margin:0 !important;
  padding-left:18px !important;
  list-style-type:disc !important;
  list-style-position:outside !important;
  color:#475569;
}
.rl-page .rl-quick-card li,
.rl-page .rl-result-body li,
.rl-page .rl-callout li{ margin:8px 0; display:list-item !important; }

/* Sections */
.rl-page .rl-section{ margin-top:26px; }
.rl-page .rl-section-head,
.rl-page .rl-section-head{ margin-bottom:10px; }
.rl-page .rl-section-head p,
.rl-page .rl-section-head p{ margin:6px 0 0; color:#475569; max-width:100% !important; }

/* Tables */
.rl-page .rl-table-scroll{
  width:100%;
  overflow-x:auto;
  -webkit-overflow-scrolling:touch;
  border-radius:18px;
  border:1px solid #e2e8f0;
  background:#fff;
}

/* If a theme sets tables to display:block, force table layout inside RL wrapper */
.rl-page table{ display:table; border-collapse:collapse; }

.rl-page .rl-table,
.rl-page .rl-compare-table{
  width:100%;
  border-collapse:collapse;
  table-layout:auto;
  font-size:13px;
}

/* Default: allow tables to shrink on mobile without forcing huge min-width.
   If you need horizontal scroll, add data-vln-table="scroll" on the table. */
.rl-page .rl-table[data-vln-table="scroll"],
.rl-page .rl-compare-table[data-vln-table="scroll"]{
  min-width:640px;
}

.rl-page .rl-table th,
.rl-page .rl-table td,
.rl-page .rl-compare-table th,
.rl-page .rl-compare-table td{
  border-bottom:1px solid #e2e8f0;
  padding:10px 10px;
  text-align:left;
  vertical-align:top;
}

@media (max-width:640px){
  .rl-page .rl-table th,
  .rl-page .rl-table td,
  .rl-page .rl-compare-table th,
  .rl-page .rl-compare-table td{
    padding:8px 8px;
  }
}

.rl-page .rl-table thead th,
.rl-page .rl-compare-table thead th{
  background:#f8fafc;
  color:#0f172a;
  font-weight:850;
}

/* Keep key cells (like “30-year fixed”) on one line */
.rl-page .rl-table th:first-child,
.rl-page .rl-table td:first-child{
  white-space:nowrap;
  width:46%;
}
.rl-page .rl-table th:not(:first-child),
.rl-page .rl-table td:not(:first-child){
  white-space:nowrap;
}

/* Tool shell */
.rl-page .rl-tool-shell{
  border-radius:24px;
  border:1px solid #e2e8f0;
  background:rgba(248,250,252,.92);
  padding:16px;
  box-shadow:0 12px 34px rgba(15,23,42,.10), 0 2px 10px rgba(15,23,42,.06);
}
@media (max-width:640px){ .rl-page .rl-tool-shell{ padding:12px; } }

/*
  vlnToolGrid is used for BOTH:
  - Tool shells (inputs + results) where the left column should be slightly wider.
  - General two-column content (like the VA Rates snapshot panes) where columns should be equal.
  
  Base (outside tool shells): equal columns.
  Tool shells override: slight left-column bias.
*/
.rl-page .rl-tool-grid{
  display:grid;
  grid-template-columns:minmax(0,1fr) minmax(0,1fr);
  gap:16px;
}
.rl-page .rl-tool-grid > *{ min-width:0; }
.rl-page .rl-tool-shell .rl-tool-grid{
  grid-template-columns:minmax(0,1.15fr) minmax(0,1.1fr);
}
@media (max-width:900px){
  .rl-page .rl-tool-grid{ grid-template-columns:minmax(0,1fr); }
  .rl-page .rl-tool-shell .rl-tool-grid{ grid-template-columns:minmax(0,1fr); }
}

.rl-page .rl-pane,
.rl-page .rl-form,
.rl-page .rl-result{
  border-radius:18px;
  border:1px solid #e2e8f0;
  background:#fff;
  padding:18px 18px 16px;
  box-shadow:0 12px 30px rgba(15,23,42,.08);
  min-width:0;
}
@media (max-width:640px){
  .rl-page .rl-pane,
  .rl-page .rl-form,
  .rl-page .rl-result{
    padding:14px 14px 12px;
  }
}

.rl-page .rl-pane-title{
  font-size:15px;
  font-weight:950;
  margin:0 0 10px;
  color:#0F1F4A;
}

/* Form fields */
.rl-page .rl-row-2,
.rl-page .rl-form-row{
  display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr));
  gap:12px;
}
@media (max-width:640px){
  .rl-page .rl-row-2,
  .rl-page .rl-form-row{ grid-template-columns:minmax(0,1fr); }
}

.rl-page .rl-field,
.rl-page .rl-form-group{ display:flex; flex-direction:column; min-width:0; margin-bottom:12px; }

.rl-page .rl-field label,
.rl-page .rl-form-label{ font-weight:850; margin-bottom:6px; color:#0f172a; display:block; }

.rl-page .rl-field input,
.rl-page .rl-field select,
.rl-page .rl-form-input,
.rl-page .rl-form-select{
  border-radius:12px;
  border:1px solid #e2e8f0;
  padding:10px 10px;
  background:#fff;
  color:#0f172a;
  font-size:14px;
  width:100%;
}

.rl-page .rl-field input:focus,
.rl-page .rl-field select:focus,
.rl-page .rl-form-input:focus,
.rl-page .rl-form-select:focus{
  outline:none;
  border-color:#C8102E;
  box-shadow:0 0 0 1px rgba(200,16,46,.35);
}

.rl-page .rl-field input[type="range"]{ width:100%; }

.rl-page .rl-range-row{
  display:flex;
  justify-content:space-between;
  gap:8px;
  margin-top:6px;
  color:#475569;
  font-size:12.5px;
}

.rl-page .rl-help,
.rl-page .rl-form-help{ margin-top:6px; color:#475569; font-size:12.5px; line-height:1.55; }

.rl-page .rl-error,
.rl-page .rl-form-error{ margin-top:10px; color:#dc2626; font-weight:750; }

/* Callouts */
.rl-page .rl-callout{
  border-radius:18px;
  border:1px solid #e2e8f0;
  background:#fff;
  padding:12px 12px 10px;
  box-shadow:0 12px 30px rgba(15,23,42,.08);
  margin-top:12px;
}
.rl-page .rl-callout h3{ font-size:15px; margin:0 0 6px; }
.rl-page .rl-callout p{ margin:0; color:#475569; font-size:13px; line-height:1.6; }

.rl-page .rl-callout--warn{ border-color:#fed7aa; background:linear-gradient(180deg,#fffbeb 0%, #fff 100%); }
.rl-page .rl-callout--blue{ border-color:#fecaca; background:linear-gradient(180deg,#fef2f2 0%, #fff 100%); }

/* Results */
.rl-page .rl-result-main{
  border-radius:18px;
  border:1px solid #e2e8f0;
  background:linear-gradient(180deg,#f8fafc 0%, #fff 100%);
  padding:16px 16px 14px;
  margin-bottom:12px;
}

.rl-page .rl-result-top{
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:10px;
  flex-wrap:wrap;
  margin-bottom:10px;
}

.rl-page .rl-tag{
  display:inline-flex;
  align-items:center;
  padding:6px 10px;
  border-radius:999px;
  background:#f1f5f9;
  border:1px solid #cbd5e1;
  color:#0F1F4A;
  font-weight:950;
  font-size:12.5px;
  white-space:nowrap;
}

.rl-page .rl-note{ color:#475569; font-size:12.5px; }

.rl-page .rl-metrics{ display:grid; grid-template-columns:1fr; gap:12px; margin-top:10px; }

.rl-page .rl-metric .label{ color:#475569; font-size:12.5px; line-height:1.2; }
.rl-page .rl-metric .value{ margin-top:4px; color:#0f172a; font-size:26px; font-weight:950; line-height:1.15; }
.rl-page .rl-metric .value.small{ font-size:20px; font-weight:950; }

.rl-page .rl-stack{ display:grid; grid-template-columns:1fr; gap:12px; }
.rl-page .rl-mini-card{
  border-radius:18px;
  border:1px solid #e2e8f0;
  background:linear-gradient(180deg,#fff 0%, #f8fafc 100%);
  padding:12px 12px 10px;
  box-shadow:0 12px 30px rgba(15,23,42,.08);
}

.rl-page .rl-mini-card h3{ font-size:15px; margin:0 0 8px; }

.rl-page .rl-kv-list{ list-style:none; padding:0; margin:0 0 8px; color:#475569; }
.rl-page .rl-kv-list li{ display:flex; justify-content:space-between; gap:10px; margin-bottom:6px; }
.rl-page .rl-kv-list span:last-child{ font-weight:850; color:#0f172a; white-space:nowrap; }

.rl-page .rl-stats{ margin:0; }
.rl-page .rl-stats div{ display:flex; justify-content:space-between; gap:10px; margin-bottom:6px; color:#475569; }
.rl-page .rl-stats dt{ font-weight:700; }
.rl-page .rl-stats dd{ margin:0; font-weight:850; color:#0f172a; white-space:nowrap; }

/* Traffic cards */
.rl-page .rl-traffic-grid{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }
@media (max-width:960px){ .rl-page .rl-traffic-grid{ grid-template-columns:minmax(0,1fr); } }

.rl-page .rl-traffic-card{
  border-radius:18px;
  background:#fff;
  padding:12px 12px 10px;
  box-shadow:0 12px 30px rgba(15,23,42,.08);
  min-width:0;
  border:1px solid #e2e8f0;
}
.rl-page .rl-traffic-card[data-tone="green"]{ border-color:rgba(22,163,74,.35); }
.rl-page .rl-traffic-card[data-tone="yellow"]{ border-color:rgba(202,138,4,.35); }
.rl-page .rl-traffic-card[data-tone="red"]{ border-color:rgba(220,38,38,.30); }

.rl-page .rl-traffic-title{ margin:0 0 6px; font-size:16px; font-weight:950; line-height:1.22; }
.rl-page .rl-traffic-title.green{ color:#16a34a; }
.rl-page .rl-traffic-title.yellow{ color:#ca8a04; }
.rl-page .rl-traffic-title.red{ color:#dc2626; }

/* FAQ */
.rl-page .rl-faq,
.rl-page .rl-faq-list{
  margin-top:12px;
  border:1px solid #e2e8f0;
  border-radius:24px;
  background:#fff;
  overflow:hidden;
  box-shadow:0 18px 45px rgba(15,23,42,.10);
}

.rl-page .rl-faq details,
.rl-page .rl-faq-item{ border:0; }

.rl-page .rl-faq details:not(:first-child),
.rl-page .rl-faq-item:not(:first-child){ border-top:1px solid #e2e8f0; }

.rl-page .rl-faq summary,
.rl-page .rl-faq-item summary{
  cursor:pointer;
  list-style:none;
  padding:16px 16px;
  font-weight:950;
  color:#0f172a;
  display:flex;
  align-items:center;
  justify-content:space-between;
  gap:10px;
}

.rl-page .rl-faq summary::-webkit-details-marker,
.rl-page .rl-faq-item summary::-webkit-details-marker{ display:none; }

/* Default +/- icon if page doesn't provide custom icon */
.rl-page .rl-faq summary:after{
  content:"+";
  width:28px; height:28px;
  display:inline-flex;
  align-items:center;
  justify-content:center;
  border-radius:999px;
  border:1px solid #cbd5e1;
  background:#f8fafc;
  color:#64748b;
  font-weight:950;
  flex:0 0 auto;
}

.rl-page .rl-faq details[open] summary:after{ content:"–"; }

.rl-page .rl-faq .ans,
.rl-page .rl-faqBody{
  border-top:1px solid #e2e8f0;
  padding:12px 16px 16px;
}

.rl-page .rl-faq .ans p{ margin:0; color:#475569; }

/* References */
.rl-page .rl-refs,
.rl-page .rl-sources{
  margin-top:12px;
  border:1px solid #e2e8f0;
  border-radius:24px;
  background:#fff;
  box-shadow:0 18px 45px rgba(15,23,42,.10);
  overflow:hidden;
}

.rl-page .rl-refs-inner{ padding:16px 16px 14px; }
.rl-page .rl-refs-label{ margin:0 0 10px; color:#475569; font-weight:850; font-size:12.5px; }

.rl-page .rl-refs ul,
.rl-page .rl-sources-list{
  margin:0 !important;
  padding-left:18px !important;
  list-style-type:disc !important;
  list-style-position:outside !important;
  color:#475569;
}

.rl-page .rl-refs li,
.rl-page .rl-sources-list li{ margin:8px 0; display:list-item !important; }

/* Utility: visually hidden */
.rl-page .rl-sr-only{
  position:absolute !important;
  left:-9999px !important;
  width:1px !important;
  height:1px !important;
  overflow:hidden !important;
}


/* Compare table best row highlight */
.rl-page .rl-best-row td{
  background:linear-gradient(90deg, rgba(22,163,74,.10) 0%, rgba(22,163,74,.04) 100%);
}
.rl-page .rl-best-row td:first-child{
  position:relative;
}
.rl-page .rl-best-row td:first-child:before{
  content:"";
  position:absolute;
  left:0; top:0; bottom:0;
  width:4px;
  background:#16a34a;
}

/* Level pill (readiness/service/property) */
.rl-page .rl-level-pill,
.rl-page #vaReadyLevelPill,
.rl-page #serviceLevelPill,
.rl-page #propertyLevelPill{
  display:inline-flex;
  align-items:center;
  gap:8px;
  padding:6px 10px;
  border-radius:999px;
  border:1px solid #cbd5e1;
  background:#f1f5f9;
  color:#0F1F4A;
  font-weight:950;
  font-size:12.5px;
  white-space:nowrap;
}

.rl-page .rl-level-pill[data-level="ready"],
.rl-page #vaReadyLevelPill[data-level="ready"],
.rl-page #serviceLevelPill[data-level="ready"],
.rl-page #propertyLevelPill[data-level="ready"]{
  background:rgba(22,163,74,.10);
  border-color:rgba(22,163,74,.35);
  color:#15803d;
}

.rl-page .rl-level-pill[data-level="close"],
.rl-page #vaReadyLevelPill[data-level="close"],
.rl-page #serviceLevelPill[data-level="close"],
.rl-page #propertyLevelPill[data-level="close"]{
  background:rgba(202,138,4,.10);
  border-color:rgba(202,138,4,.35);
  color:#a16207;
}

.rl-page .rl-level-pill[data-level="prep"],
.rl-page #vaReadyLevelPill[data-level="prep"],
.rl-page #serviceLevelPill[data-level="prep"],
.rl-page #propertyLevelPill[data-level="prep"]{
  background:rgba(220,38,38,.08);
  border-color:rgba(220,38,38,.28);
  color:#b91c1c;
}

/* Score bar (optional) */
.rl-page .rl-score-track{
  height:10px;
  border-radius:999px;
  background:#e2e8f0;
  overflow:hidden;
}
.rl-page .rl-score-bar,
.rl-page #vaReadyScoreBar,
.rl-page #serviceScoreBar,
.rl-page #propertyScoreBar{
  height:10px;
  border-radius:999px;
  width:0%;
  background:#0F1F4A;
  transition:width .25s ease;
}


/* ===== Builder/Divi safety nets ===== */

/* Divi sometimes injects <br> between pill links and inside paragraphs */
.rl-page .rl-pills br,
.rl-page .rl-pills br,
.rl-page .rl-hero-lead br,
.rl-page .rl-hero-lead br { display:none !important; }

/* Divi sometimes injects <p>&nbsp;</p> into grid wrappers (breaks layout) */
.rl-page .rl-tool-grid > p,
.rl-page .rl-tool-grid > p,
.rl-page .rl-tool-grid > br,
.rl-page .rl-tool-grid > br,
.rl-page .rl-row-2 > p,
.rl-page .rl-row-2 > p,
.rl-page .rl-row-2 > br,
.rl-page .rl-row-2 > br,
.rl-page .rl-ctas > p,
.rl-page .rl-ctas > p,
.rl-page .rl-ctas > br,
.rl-page .rl-ctas > br,
.rl-page .rl-result-top > p,
.rl-page .rl-result-top > p,
.rl-page .rl-result-top > br,
.rl-page .rl-result-top > br { display:none !important; margin:0 !important; padding:0 !important; }

/* Force primary/success button text to white (Divi can override link colors) */
.rl-page a.rl-btn.rl-btn--primary,
.rl-page a.rl-btn.rl-btn--primary,
.rl-page a.rl-btn.rl-btn--success,
.rl-page a.rl-btn.rl-btn--success { color:#fff !important; -webkit-text-fill-color:#fff !important; }

/* Force compare button text to green (Divi can override link colors via -webkit-text-fill-color) */
.rl-page a.rl-btn.rl-btn--compare,
.rl-page a.rl-btn.rl-btn--compare,
.rl-page button.rl-btn.rl-btn--compare,
.rl-page button.rl-btn.rl-btn--compare {
  color:#15803d !important;
  -webkit-text-fill-color:#15803d !important;
}

/* Lane tones */
.rl-page .rl-lane-green,
.rl-page .rl-lane-green { color:#15803d !important; }
.rl-page .rl-lane-yellow,
.rl-page .rl-lane-yellow { color:#ca8a04 !important; }
.rl-page .rl-lane-red,
.rl-page .rl-lane-red { color:#dc2626 !important; }

/* ============================================================
   Mobile-only unboxing (Desktop stays identical)

   Why this exists:
   - On mobile, the gradient wrapper + stacked cards/pills makes
     the content column too narrow and wastes above-the-fold space.
   - We keep the desktop design untouched.

   What this does (<=760px):
   - Plain white wrapper background (no gradient)
   - Remove borders/shadows/radius on “card” containers
   - Remove extra padding (wrapper + card-inner)
   - Hide breadcrumb / eyebrow pill / sources-at-top / jump pills
   ============================================================ */

@media (max-width: 760px){
  /* 1) Wrapper: no gradient, no extra padding */
  .rl-page,
  .rl-page{
    background: #ffffff !important;
    padding: 0 !important;
  }

  .rl-page .rl-wrap,
  .rl-page .rl-wrap{
    padding: 0 !important;
  }

  /* 2) Remove boxed containers (keep structure, lose the chrome) */
  .rl-page .rl-card,
  .rl-page .rl-card,
  .rl-page .rl-section,
  .rl-page .rl-section,
  .rl-page .rl-hero-quick,
  .rl-page .rl-hero-quick,
  .rl-page .rl-hero-quickCard,
  .rl-page .rl-hero-quickCard,
  .rl-page .rl-quick-card,
  .rl-page .rl-quick-card,
  .rl-page .rl-tool-shell,
  .rl-page .rl-tool-shell,
  .rl-page .rl-pane,
  .rl-page .rl-pane,
  .rl-page .rl-form,
  .rl-page .rl-form,
  .rl-page .rl-result,
  .rl-page .rl-result,
  .rl-page .rl-types-grid,
  .rl-page .rl-types-grid,
  .rl-page .rl-type-tabs,
  .rl-page .rl-type-tabs,
  .rl-page .rl-type-detail,
  .rl-page .rl-type-detail,
  .rl-page .rl-faq-list,
  .rl-page .rl-faq-list,
  .rl-page .rl-faq-item,
  .rl-page .rl-faq-item,
  .rl-page .rl-refs,
  .rl-page .rl-refs,
  .rl-page .rl-sources,
  .rl-page .rl-sources,
  .rl-page .rl-mini-card,
  .rl-page .rl-mini-card{
    background: transparent !important;
    border: 0 !important;
    box-shadow: none !important;
    border-radius: 0 !important;
	    padding: 0 !important;
  }

  /* 3) Remove the inner padding that makes the text column skinny */
  .rl-page .rl-card-inner,
  .rl-page .rl-card-inner,
  .rl-page .rl-section-head,
  .rl-page .rl-section-head,
  .rl-page .rl-section-head,
  .rl-page .rl-section-head{
    padding: 0 !important;
  }

  /* 4) Hide above-the-fold “chrome” that wastes space */
  .rl-page .rl-breadcrumb,
  .rl-page .rl-breadcrumb,
  .rl-page .rl-hero-eyebrow,
  .rl-page .rl-hero-eyebrow,
  .rl-page .rl-eyebrow,
  .rl-page .rl-eyebrow,
  .rl-page .rl-hero-meta,
  .rl-page .rl-hero-meta,
  .rl-page .rl-hero .rl-meta,
  .rl-page .rl-hero .rl-meta,
  .rl-page .rl-hero-jumps,
  .rl-page .rl-hero-jumps,
  .rl-page .rl-pills,
  .rl-page .rl-pills{
    display: none !important;
  }

  /* 5) Keep things readable when we remove cards */
  .rl-page .rl-section,
  .rl-page .rl-section{
    margin: 18px 0 !important;
  }

  .rl-page .rl-hero,
  .rl-page .rl-hero{
    margin-bottom: 18px !important;
  }
}

/* =======================================================================
   DESKTOP CONSISTENCY PATCH
   -----------------------------------------------------------------------
   Some themes/builders apply navigation typography (uppercase + letter
   spacing) to <nav> elements and their links. That can leak into VLN
   breadcrumbs and make them look “more spaced” vs other pages.

   Also, if a builder wraps hero content in a flex column with the default
   align-items: stretch, inline-flex “pills” can be blockified and expand to
   full width. These rules harden the layout so the pill stays shrink-to-fit.

   Finally, earlier templates use vlnHero-* class variants; ensure their
   <strong> styles match the newer vln* classes.
   ======================================================================= */

/* Breadcrumbs: force normal casing and tight tracking */
.rl-page .rl-breadcrumb,
.rl-page .rl-breadcrumb a,
.rl-page .rl-breadcrumb span,
.rl-page .rl-breadcrumb,
.rl-page .rl-breadcrumb a,
.rl-page .rl-breadcrumb span{
  text-transform: none !important;
  letter-spacing: normal !important;
}

/* Eyebrow pill: keep shrink-to-fit even inside flex wrappers */
.rl-page .rl-eyebrow,
.rl-page .rl-hero-eyebrow,
.rl-page .rl-eyebrow,
.rl-page .rl-hero-eyebrow{
  width: fit-content;
  max-width: 100%;
  align-self: flex-start;
  white-space: normal;
}

/* Legacy hero variants: match strong styling to newer classes */
.rl-page .rl-hero-eyebrow strong,
.rl-page .rl-hero-eyebrow strong{
  color: var(--vlnGood);
  font-weight: 950;
}

.rl-page .rl-hero-meta strong,
.rl-page .rl-hero-meta strong{
  color: var(--vlnInk);
  font-weight: 900;
}

/* =======================================================================
   RL MOBILE FIXES
   1) Stop iOS/mobile horizontal “page drift” (text sliding off-screen)
   2) Keep the light-blue bullet/quick cards on mobile (requested)
   ======================================================================= */

/* Skip-link: hide without pushing content far off-canvas (prevents x-overflow on some mobile browsers) */
.rl-page .rl-skip,
.rl-page .rl-skip{
  left: 0 !important;
  top: 0 !important;
  width: 1px !important;
  height: 1px !important;
  margin: -1px !important;
  padding: 0 !important;
  overflow: hidden !important;
  border: 0 !important;
  clip: rect(0 0 0 0) !important;
  clip-path: inset(50%) !important;
  white-space: nowrap !important;
}

.rl-page .rl-skip:focus,
.rl-page .rl-skip:focus{
  width: auto !important;
  height: auto !important;
  margin: 0 !important;
  padding: 10px 12px !important;
  overflow: visible !important;
  clip: auto !important;
  clip-path: none !important;
  left: 12px !important;
  top: 12px !important;
  background: #ffffff !important;
  color: var(--ink) !important;
  border: 2px solid var(--brand) !important;
  border-radius: 12px !important;
  font-weight: 900 !important;
  z-index: 9999 !important;
}

@media (max-width: 760px){
  /* Prevent any child overflow from turning into page-level horizontal scroll */
  .rl-page,
  .rl-page{
    overflow-x: hidden !important;
  }

  /* Keep the “bullet section” cards (Quick Answers / takeaways) on mobile */
  .rl-page .rl-quick-card,
  .rl-page .rl-quick-card,
  .rl-page .rl-hero-quickCard,
  .rl-page .rl-hero-quickCard{
    background: #ffffff !important;
    border: 1px solid #fecaca !important; /* light blue */
    border-radius: 18px !important;
    padding: 14px 14px 12px !important;
    box-shadow: none !important;
  }

  /* Keep normal bullets inside those cards */
  .rl-page .rl-quick-card ul,
  .rl-page .rl-quick-card ul,
  .rl-page .rl-hero-quickCard ul,
  .rl-page .rl-hero-quickCard ul{
    padding-left: 20px !important;
    list-style: disc !important;
  }

  /* Reduce scroll-chaining into the page when swiping horizontally in a table/pill scroller */
  .rl-page .rl-table-scroll,
  .rl-page .rl-table-scroll,
  .rl-page .rl-pills,
  .rl-page .rl-pills{
    overscroll-behavior-x: contain;
  }
}

/* ==========================================================
   Builder-proof overrides
   Some page builders (ex: Divi) inject module CSS late and
   can override link colors, fonts, and display properties.
   These rules keep the RL design consistent across pages.
   ========================================================== */

.rl-page{
  background: linear-gradient(180deg, #eaf2ff 0%, #f6f9ff 42%, #ffffff 100%) !important;
  padding: 44px 0 !important;
}

.rl-page :is(h1,h2,h3,h4,h5,h6,p,ul,ol,li,a,span,strong,em,small,button,input,select,textarea,label,summary,dt,dd){
  font-family: var(--vlnFont) !important;
}

.rl-page :is(h1,h2,h3,h4,h5,h6){
  color: var(--vlnHeading) !important;
}

/* Breadcrumbs must stay compact + dark (not theme-blue) */
.rl-page .rl-breadcrumb{
  display: flex !important;
  align-items: center !important;
  gap: 8px !important;
  flex-wrap: wrap !important;
}
.rl-page .rl-breadcrumb a{
  color: var(--vlnInk) !important;
  text-decoration: none !important;
}

.rl-page .rl-breadcrumb,
.rl-page .rl-breadcrumb *{
  text-transform: none !important;
  letter-spacing: normal !important;
}
.rl-page .rl-breadcrumb .sep{
  color: var(--vlnMuted) !important;
}

/* Eyebrow pill must hug content (not stretch full width) */
.rl-page .rl-eyebrow,
.rl-page .rl-hero-eyebrow{
  display: inline-flex !important;
  width: auto !important;
  max-width: 100% !important;
  align-self: flex-start !important;
}

.rl-page .rl-eyebrow,
.rl-page .rl-eyebrow *,
.rl-page .rl-hero-eyebrow,
.rl-page .rl-hero-eyebrow *{
  text-transform: none !important;
  letter-spacing: normal !important;
}

/* Default link color inside RL pages (exclude buttons) */
.rl-page a:not(.rl-btn):not(.rl-pill):not(.rl-pill){
  color: var(--vlnHeading) !important;
}

/* Pills should not inherit theme link styles */
.rl-page .rl-pill,
.rl-page .rl-pill{
  color: var(--vlnHeadingSoft, #0b2a6f) !important;
  text-decoration: none !important;
}

.rl-page .rl-pill,
.rl-page .rl-pill{
  text-transform: none !important;
  letter-spacing: normal !important;
}

/* ====================================================================== 
   RL CONSISTENCY OVERRIDES (v1.4.6)
   Purpose: Make every RL page render identically regardless of theme
   link/heading styles or editor-inserted <br> tags.
====================================================================== */

.rl-page,
.rl-page{
  --vlnFont: system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,"Apple Color Emoji","Segoe UI Emoji";
  --vlnInk: #0f172a;
  --vlnHeading: #0F1F4A;
  --vlnMuted: #475569;
  --vlnLine: rgba(200,16,46,.25);
  --vlnHeadingSoft: #0F1F4A;
  --vlnGood: #16a34a;
  --vlnGreenBg: rgba(255,255,255,.85);
  --vlnGreenLine: rgba(22,163,74,.35);
}

/* Force our gradient + typography (beat most theme styles) */
.rl-page,
.rl-page{
  font-family: var(--vlnFont) !important;
  color: var(--vlnInk) !important;
  background: linear-gradient(180deg, #e8f1ff 0%, #ffffff 30%) !important;
}

.rl-page :where(p,li,span,small,strong,em,summary,label,button,input,select,textarea,th,td,dt,dd),
.rl-page :where(p,li,span,small,strong,em,summary,label,button,input,select,textarea,th,td,dt,dd){
  font-family: var(--vlnFont) !important;
}

/* Headings */
.rl-page :where(h1,h2,h3,h4),
.rl-page :where(h1,h2,h3,h4){
  color: var(--vlnHeading) !important;
}

/* Text links (do NOT clobber buttons or pills) */
.rl-page a:not(.rl-btn):not(.rl-pill):not(.rl-pill),
.rl-page a:not(.rl-btn):not(.rl-pill):not(.rl-pill){
  color: var(--vlnHeading) !important;
  text-decoration: none;
}
.rl-page a:not(.rl-btn):not(.rl-pill):not(.rl-pill):hover,
.rl-page a:not(.rl-btn):not(.rl-pill):not(.rl-pill):hover{
  text-decoration: underline;
}

/* Breadcrumb + Primary sources (meta) */
.rl-page .rl-breadcrumb,
.rl-page .rl-breadcrumb,
.rl-page .rl-meta,
.rl-page .rl-meta,
.rl-page .rl-hero-meta,
.rl-page .rl-hero-meta{
  color: var(--vlnMuted) !important;
}

.rl-page .rl-breadcrumb a,
.rl-page .rl-breadcrumb a{
  color: var(--vlnHeading) !important;
  text-decoration: none;
}
.rl-page .rl-breadcrumb a:hover,
.rl-page .rl-breadcrumb a:hover{
  text-decoration: underline;
}

.rl-page .rl-meta a,
.rl-page .rl-meta a,
.rl-page .rl-hero-meta a,
.rl-page .rl-hero-meta a{
  color: var(--vlnHeading) !important;
  font-weight: 800;
  text-decoration: none;
}
.rl-page .rl-meta a:hover,
.rl-page .rl-meta a:hover,
.rl-page .rl-hero-meta a:hover,
.rl-page .rl-hero-meta a:hover{
  text-decoration: underline;
}

/* Fix WP/Divi auto-inserted line breaks inside meta/breadcrumbs */
.rl-page .rl-meta br,
.rl-page .rl-meta br,
.rl-page .rl-hero-meta br,
.rl-page .rl-hero-meta br,
.rl-page .rl-breadcrumb br,
.rl-page .rl-breadcrumb br,
.rl-page .rl-hero-eyebrow br,
.rl-page .rl-hero-eyebrow br,
.rl-page .rl-eyebrow br,
.rl-page .rl-eyebrow br{
  display:none !important;
}

/* If the editor wraps items in <p>, neutralize block behavior */
.rl-page .rl-meta > p,
.rl-page .rl-meta > p,
.rl-page .rl-hero-meta > p,
.rl-page .rl-hero-meta > p{
  margin:0 !important;
  display:inline !important;
}

/* Ensure active pills keep their intended contrast even after link-color normalization */
.rl-page .rl-pill.is-active,
.rl-page .rl-pill.is-active,
.rl-page .rl-pill.is-active,
.rl-page .rl-pill.is-active{
  color:#fff !important;
}


/* === RL consistency fixes (v1.4.7) === */
.rl-page .rl-meta,
.rl-page .rl-meta{
  display:flex !important;
  flex-wrap:wrap !important;
  align-items:center !important;
  gap:8px !important;
}
.rl-page .rl-meta > span,
.rl-page .rl-meta > span,
.rl-page .rl-meta > p,
.rl-page .rl-meta > p{
  display:inline-flex !important;
  flex-wrap:wrap !important;
  align-items:center !important;
  gap:8px !important;
}

/* Normalize card headings even if authors use h2/h3 */
.rl-page .rl-quick-card :is(h2,h3,h4),
.rl-page .rl-quick-card :is(h2,h3,h4){
  font-size:16px !important;
  line-height:1.2 !important;
  font-weight:900 !important;
  margin:0 0 10px !important;
  letter-spacing:-0.01em !important;
}

/* Eyebrow pill should hug content, never stretch full width */
.rl-page .rl-eyebrow,
.rl-page .rl-eyebrow,
.rl-page .rl-hero-eyebrow,
.rl-page .rl-hero-eyebrow{
  width:max-content !important;
  max-width:100% !important;
}

/* =====================================================================
   RL hard-lock styling (v1.4.8)
   Goal: different WordPress templates/builders should still render
   *identical* RL pages.

   Strategy:
   1) Boost selector specificity with ".rl-page.rl-page" so our rules win
      even against theme rules that use !important.
   2) Explicitly set heading, pill, and breadcrumb colors (no inheritance).
   3) Mobile: hide the decorative chrome (gradient/bg + breadcrumb + eyebrow)
      per design requirement.
   ===================================================================== */

/* Base typography + link reset (scoped) */
.rl-page.rl-page,
.rl-page.rl-page{
  font-family: var(--vlnFont, system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif) !important;
  color: var(--vlnInk, #0f172a) !important;
}

/* Headings: always brand navy */
.rl-page.rl-page h1,
.rl-page.rl-page h2,
.rl-page.rl-page h3,
.rl-page.rl-page h4,
.rl-page.rl-page h1,
.rl-page.rl-page h2,
.rl-page.rl-page h3,
.rl-page.rl-page h4{
  color: var(--vlnHeading, #0F1F4A) !important;
}

/* Non-pill/non-button links use brand navy (keeps sources consistent) */
.rl-page.rl-page a:not(.rl-btn):not(.rl-pill):not(.rl-pill),
.rl-page.rl-page a:not(.rl-btn):not(.rl-pill):not(.rl-pill){
  color: var(--vlnHeading, #0F1F4A) !important;
}

/* Breadcrumbs: always muted grey (links included) */
.rl-page.rl-page .rl-breadcrumb,
.rl-page.rl-page .rl-breadcrumb a,
.rl-page.rl-page .rl-breadcrumb,
.rl-page.rl-page .rl-breadcrumb a{
  color: var(--vlnMuted, #475569) !important;
}
.rl-page.rl-page .rl-breadcrumb a:hover,
.rl-page.rl-page .rl-breadcrumb a:hover{
  color: var(--vlnHeading, #0F1F4A) !important;
  text-decoration: underline;
}

/* Pills: always brand navy text */
.rl-page.rl-page .rl-pill,
.rl-page.rl-page .rl-pill,
.rl-page.rl-page .rl-pill,
.rl-page.rl-page .rl-pill{
  color: var(--vlnHeading, #0F1F4A) !important;
  border-color: #bcd3ff !important;
}

/* Ensure themes can't restyle pill text via -webkit-text-fill-color */
.rl-page.rl-page .rl-pill,
.rl-page.rl-page .rl-pill,
.rl-page.rl-page .rl-pill,
.rl-page.rl-page .rl-pill{
  -webkit-text-fill-color: var(--vlnHeading, #0F1F4A) !important;
}

/* Mobile: hide gradient + breadcrumb + eyebrow pill */
@media (max-width: 720px){
  .rl-page.rl-page,
  .rl-page.rl-page{
    background: #fff !important;
  }

  .rl-page.rl-page .rl-breadcrumb,
  .rl-page.rl-page .rl-breadcrumb,
  .rl-page.rl-page .rl-eyebrow,
  .rl-page.rl-page .rl-eyebrow,
  .rl-page.rl-page .rl-hero-eyebrow,
  .rl-page.rl-page .rl-hero-eyebrow{
    display:none !important;
  }
}

/* =======================
   PATCH 1.4.11
   Fixes:
   - Tables with long text columns getting clipped/truncated (wrap text)
   - FAQ focus/active outline getting clipped by the accordion container (use inset ring)
   ======================= */

/* TABLES: allow text wrapping in .rl-table/.rl-table by default.
   Numeric body cells stay non-wrapping via the .num class. */
.rl-page.rl-page .rl-table th,
.rl-page.rl-page .rl-table td,
.rl-page.rl-page .rl-table th,
.rl-page.rl-page .rl-table td{
  white-space: normal !important;
  overflow-wrap: anywhere;
  word-break: normal;
}

/* Keep numeric body cells tidy */
.rl-page.rl-page .rl-table tbody td.num,
.rl-page.rl-page .rl-table tbody td.num{
  white-space: nowrap !important;
}

/* Header labels can wrap even if marked .num (prevents truncated headings like “Points (at cost)”). */
.rl-page.rl-page .rl-table thead th.num,
.rl-page.rl-page .rl-table thead th.num{
  white-space: normal !important;
}

/* FAQ: replace browser outline (which can get clipped) with an inset focus/open ring */
.rl-page.rl-page .rl-faq summary:focus,
.rl-page.rl-page .rl-faq summary:focus-visible,
.rl-page.rl-page .rl-faq summary:focus,
.rl-page.rl-page .rl-faq summary:focus-visible{
  outline: none !important;
}

.rl-page.rl-page .rl-faq summary,
.rl-page.rl-page .rl-faq summary{
  border-radius: 16px;
}

.rl-page.rl-page .rl-faq summary:focus-visible,
.rl-page.rl-page .rl-faq details[open] > summary,
.rl-page.rl-page .rl-faq summary:focus-visible,
.rl-page.rl-page .rl-faq details[open] > summary{
  box-shadow: inset 0 0 0 2px rgba(200,16,46,.45);
}

/* =======================
   PATCH 1.4.12
   Fix:
   - FAQ open/focus ring corners: replace inset box-shadow with a true rounded border drawn inside
     the summary row. This eliminates occasional anti-alias “missing corner” artifacts.
   ======================= */

/* Turn off the inset shadow ring from 1.4.11 */
.rl-page.rl-page .rl-faq summary:focus-visible,
.rl-page.rl-page .rl-faq details[open] > summary,
.rl-page.rl-page .rl-faq summary:focus-visible,
.rl-page.rl-page .rl-faq details[open] > summary{
  box-shadow: none !important;
}

/* Draw a crisp rounded ring *inside* the summary row */
.rl-page.rl-page .rl-faq summary::before,
.rl-page.rl-page .rl-faq summary::before{
  content: "";
  position: absolute;
  inset: 2px;
  border-radius: 14px;
  border: 2px solid rgba(200,16,46,.45);
  opacity: 0;
  pointer-events: none;
  transition: opacity .15s ease;
}

.rl-page.rl-page .rl-faq summary:focus-visible::before,
.rl-page.rl-page .rl-faq details[open] > summary::before,
.rl-page.rl-page .rl-faq summary:focus-visible::before,
.rl-page.rl-page .rl-faq details[open] > summary::before{
  opacity: 1;
}


/* =======================
   1.4.13 PATCH
   - Sticky results column for tool layouts (desktop)
   - Center CTA buttons in result cards
   ======================= */

@media (min-width: 901px){
  /* Make the RIGHT column (results) stay visible while scrolling long tool inputs.
     Scope: only tool grids inside .rl-tool-shell so snapshot grids are unaffected. */
  .rl-page .rl-tool-shell .rl-tool-grid > .rl-pane:nth-child(2),
  .rl-page .rl-tool-shell .rl-tool-grid > .rl-pane:nth-child(2){
    position: sticky;
    top: var(--vlnStickyTop, 12px);
    align-self: start;
  }
}

/* Center CTA buttons inside result cards (e.g., Credit tool snapshot CTAs) */
.rl-page .rl-result-main .rl-ctas,
.rl-page .rl-result-main .rl-ctas{
  justify-content: center;
}

/* Defensive: ensure button label looks centered even if a theme overrides link text-align */
.rl-page .rl-btn,
.rl-page .rl-btn{
  text-align: center;
}

/* -------------------------------------------------------------------------- */
   ================================ */

/* Support cases where the class is applied directly on <details> (details.rl-faq / details.rl-faq)
   and ensure disclosure markers are consistently removed across browsers. */
.rl-faq summary::marker,
.rl-faq summary::marker,
details.rl-faq > summary::marker,
details.rl-faq > summary::marker{
  content: "";
}

.rl-faq summary::-webkit-details-marker,
.rl-faq summary::-webkit-details-marker,
details.rl-faq > summary::-webkit-details-marker,
details.rl-faq > summary::-webkit-details-marker{
  display: none;
}

/* Give the FAQ block breathing room so it cannot visually overlap the author box below. */
.rl-faq,
.rl-faq,
details.rl-faq,
details.rl-faq{
  margin-bottom: 24px !important;
  position: relative;
  z-index: 0;
}

/* Simple Author Box (plugin) sometimes uses negative margins; prevent it from sliding under FAQs. */
.saboxplugin-wrap,
.saboxplugin-authorbox{
  margin-top: 24px !important;
  clear: both;
  position: relative;
  z-index: 1;
}

/* If a FAQ section is built with plain <details> (no .rl-faq wrapper),
   still apply a sane accordion style inside RL wrappers. */
.rl-page details,
.rl-page details{
  background: #fff;
  border: 1px solid #c9d8ff;
  border-radius: 16px;
  overflow: hidden;
}
.rl-page details + details,
.rl-page details + details{
  margin-top: 12px;
}
.rl-page details > summary,
.rl-page details > summary{
  list-style: none;
  cursor: pointer;
  padding: 16px 18px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  outline: none;
}
.rl-page details > summary::after,
.rl-page details > summary::after{
  content: "+";
  font-size: 18px;
  line-height: 1;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #c9d8ff;
  border-radius: 999px;
  flex: 0 0 32px;
  color: #0F1F4A;
}
.rl-page details[open] > summary::after,
.rl-page details[open] > summary::after{
  content: "–";
}
.rl-page details > *:not(summary),
.rl-page details > *:not(summary){
  padding: 0 18px 16px;
  color: #334155;
}
/* ===========================
   RL Traffic-Light Callouts
   Scoped to .rl-page only
   =========================== */

.rl-page .bullet-section-green,
.rl-page .bullet-section-yellow,
.rl-page .bullet-section-red {
  border-radius: 16px;
  padding: 16px 18px;
  margin: 18px 0;
  border: 1px solid;
  box-shadow: none !important; /* hard kill any inherited shadow */
}

/* Backgrounds + borders */
.rl-page .bullet-section-green {
  background: #ecfdf5; /* soft green */
  border-color: rgba(22, 163, 74, 0.35);
}
.rl-page .bullet-section-yellow {
  background: #fffbeb; /* soft amber */
  border-color: rgba(245, 158, 11, 0.40);
}
.rl-page .bullet-section-red {
  background: #fef2f2; /* soft red */
  border-color: rgba(239, 68, 68, 0.38);
}

/* Optional: left accent stripe (adds scan-ability) */
.rl-page .bullet-section-green,
.rl-page .bullet-section-yellow,
.rl-page .bullet-section-red {
  border-left-width: 6px;
}
.rl-page .bullet-section-green { border-left-color: #16a34a; }
.rl-page .bullet-section-yellow { border-left-color: #f59e0b; }
.rl-page .bullet-section-red { border-left-color: #ef4444; }

/* Title row inside a callout */
.rl-page .rl-callout-title {
  font-weight: 800;
  margin: 0 0 10px;
  line-height: 1.25;
}

/* Tighten list spacing inside callouts */
.rl-page .bullet-section-green ul,
.rl-page .bullet-section-yellow ul,
.rl-page .bullet-section-red ul,
.rl-page .bullet-section-green ol,
.rl-page .bullet-section-yellow ol,
.rl-page .bullet-section-red ol {
  margin: 0;
  padding-left: 20px;
}
.rl-page .bullet-section-green li,
.rl-page .bullet-section-yellow li,
.rl-page .bullet-section-red li {
  margin: 6px 0;
}

/* Optional: small “badge” label */
.rl-page .rl-badge {
  display: inline-block;
  font-size: 0.85rem;
  font-weight: 800;
  line-height: 1;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid;
  margin-bottom: 10px;
}
.rl-page .rl-badge--green { background: rgba(22,163,74,0.10); border-color: rgba(22,163,74,0.35); }
.rl-page .rl-badge--yellow { background: rgba(245,158,11,0.12); border-color: rgba(245,158,11,0.40); }
.rl-page .rl-badge--red { background: rgba(239,68,68,0.10); border-color: rgba(239,68,68,0.38); }

/* ===========================
   Layout helpers (2-col / 3-col)
   =========================== */

.rl-page .rl-grid-2,
.rl-page .rl-grid-3 {
  display: grid;
  gap: 16px;
  align-items: start;
}

/* 2 columns on desktop, stack on mobile */
.rl-page .rl-grid-2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
@media (max-width: 900px) {
  .rl-page .rl-grid-2 { grid-template-columns: 1fr; }
}

/* 3 columns on desktop, stack on mobile */
.rl-page .rl-grid-3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
@media (max-width: 980px) {
  .rl-page .rl-grid-3 { grid-template-columns: 1fr; }
}
/* =========================================================
   RL Callouts + 2-column shaded boxes (scoped to .rl-page)
   ========================================================= */

/* 2-column wrapper (auto stacks on mobile) */
.rl-page .rl-callout-grid{
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin: 18px 0 22px;
}

@media (max-width: 820px){
  .rl-page .rl-callout-grid{
    grid-template-columns: 1fr;
    gap: 12px;
  }
}

/* Base callout/card */
.rl-page .rl-callout{
  /* defaults (can be overridden by variants below) */
  --vlnCalloutBg: #ffffff;
  --vlnCalloutBorder: rgba(15, 23, 42, 0.12);
  --vlnCalloutAccent: #f59e0b; /* default accent (amber) */

  background: var(--vlnCalloutBg);
  border: 1px solid var(--vlnCalloutBorder);
  border-radius: 18px;
  padding: 16px 16px 14px;
  box-shadow: none; /* keep it clean & consistent */
  min-width: 0;
}

.rl-page .rl-callout > *:first-child{ margin-top: 0; }
.rl-page .rl-callout > *:last-child{ margin-bottom: 0; }

/* Kicker row (yellow square + label like "Pro Tip", "Disclosure") */
.rl-page .rl-callout-kicker{
  display: flex;
  align-items: center;
  gap: 10px;

  font-weight: 800;
  font-size: 0.90rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;

  color: #0f172a;
  margin: 0 0 10px;
}

.rl-page .rl-callout-kicker::before{
  content: "";
  width: 12px;
  height: 12px;
  border-radius: 4px; /* “square” but slightly softened like your design */
  background: var(--vlnCalloutAccent);
  flex: 0 0 12px;
}

/* Headings inside callouts */
.rl-page .rl-callout h3,
.rl-page .rl-callout h4{
  margin: 0 0 8px;
  line-height: 1.25;
}

/* Body text inside callouts */
.rl-page .rl-callout p,
.rl-page .rl-callout li{
  color: #334155;
}

/* Lists inside callouts */
.rl-page .rl-callout ul,
.rl-page .rl-callout ol{
  margin: 10px 0 0 18px;
  padding: 0;
}
.rl-page .rl-callout li{ margin: 6px 0; }

/* --- Variants --- */

/* PRO TIP (yellow) */
.rl-page .rl-callout--tip{
  --vlnCalloutBg: #fff7e6;          /* soft amber */
  --vlnCalloutBorder: rgba(245, 158, 11, 0.40);
  --vlnCalloutAccent: #f59e0b;
}

/* DISCLOSURE (neutral gray “official looking”) */
.rl-page .rl-callout--disclosure{
  --vlnCalloutBg: #f8fafc;
  --vlnCalloutBorder: rgba(100, 116, 139, 0.28);
  --vlnCalloutAccent: #64748b;
}

/* NOTE (blue-ish) */
.rl-page .rl-callout--note{
  --vlnCalloutBg: #fef2f2;
  --vlnCalloutBorder: rgba(59, 130, 246, 0.35);
  --vlnCalloutAccent: #C8102E;
}

/* WARNING (red-ish) */
.rl-page .rl-callout--warning{
  --vlnCalloutBg: #fff1f2;
  --vlnCalloutBorder: rgba(239, 68, 68, 0.35);
  --vlnCalloutAccent: #ef4444;
}

/* =========================================================
   Optional: compact inline badges (if you want)
   ========================================================= */
.rl-page .rl-badge{
  display: inline-flex;
  align-items: center;
  gap: 8px;

  font-weight: 800;
  font-size: 0.85rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;

  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(15, 23, 42, 0.12);
  background: #fff;
  color: #0f172a;
}

.rl-page .rl-badge::before{
  content: "";
  width: 10px;
  height: 10px;
  border-radius: 3px;
  background: #f59e0b; /* default */
}

.rl-page .rl-badge--tip{
  background: #fff7e6;
  border-color: rgba(245, 158, 11, 0.40);
}
.rl-page .rl-badge--tip::before{ background: #f59e0b; }

.rl-page .rl-badge--disclosure{
  background: #f8fafc;
  border-color: rgba(100, 116, 139, 0.28);
}
.rl-page .rl-badge--disclosure::before{ background: #64748b; }
/* ============================================================
   RL ADD-ON (safe, append-only)
   Paste this at the VERY BOTTOM of your current CSS file
   OR (recommended) in Divi > Theme Options > Custom CSS /
   Appearance > Customize > Additional CSS.

   Purpose:
   - Traffic-light callouts + bullet sections (green/yellow/red)
   - Pro Tip + Disclosure/Resources box (smaller text)
   - Add breathing room for article pages (your "spacing is tight" issue)
   - No CSS variables, no :is/:where, no grid required
   ============================================================ */


/* -----------------------------
   1) ARTICLE SPACING (optional)
   Only applies when wrapper has: class="rl-page main-content"
   ----------------------------- */
.rl-page.main-content h2,
.rl-page.main-content h2{
  margin: 28px 0 12px;
}

.rl-page.main-content h3,
.rl-page.main-content h3{
  margin: 18px 0 10px;
}

.rl-page.main-content p,
.rl-page.main-content p{
  margin: 0 0 12px;
}

/* Keep hero heading from getting big top margins */
.rl-page.main-content .rl-hero h1,
.rl-page.main-content .rl-hero h2,
.rl-page.main-content .rl-hero h1,
.rl-page.main-content .rl-hero h2{
  margin: 0 0 10px;
}

/* Hide empty headings that Divi/wpautop sometimes injects */
.rl-page.main-content h2:empty,
.rl-page.main-content h3:empty,
.rl-page.main-content h2:empty,
.rl-page.main-content h3:empty{
  display: none;
}


/* -----------------------------
   2) BULLET SECTIONS (traffic light)
   Your markup uses:
   .bullet-section-gray / blue / yellow
   Add these too: .bullet-section-green / .bullet-section-red
   ----------------------------- */
.rl-page .bullet-section-gray,
.rl-page .bullet-section-blue,
.rl-page .bullet-section-yellow,
.rl-page .bullet-section-green,
.rl-page .bullet-section-red,
.rl-page .bullet-section-gray,
.rl-page .bullet-section-blue,
.rl-page .bullet-section-yellow,
.rl-page .bullet-section-green,
.rl-page .bullet-section-red{
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  padding: 14px 16px;
  margin: 16px 0;
  background: #ffffff;
  box-shadow: 0 10px 22px rgba(15,23,42,.04);
  color: #334155;
}

/* Bullet section headings inside the box */
.rl-page .bullet-section-gray h3,
.rl-page .bullet-section-blue h3,
.rl-page .bullet-section-yellow h3,
.rl-page .bullet-section-green h3,
.rl-page .bullet-section-red h3,
.rl-page .bullet-section-gray h3,
.rl-page .bullet-section-blue h3,
.rl-page .bullet-section-yellow h3,
.rl-page .bullet-section-green h3,
.rl-page .bullet-section-red h3{
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 900;
  color: #0F1F4A;
}

/* Lists inside bullet sections */
.rl-page .bullet-section-gray ul,
.rl-page .bullet-section-gray ol,
.rl-page .bullet-section-blue ul,
.rl-page .bullet-section-blue ol,
.rl-page .bullet-section-yellow ul,
.rl-page .bullet-section-yellow ol,
.rl-page .bullet-section-green ul,
.rl-page .bullet-section-green ol,
.rl-page .bullet-section-red ul,
.rl-page .bullet-section-red ol,
.rl-page .bullet-section-gray ul,
.rl-page .bullet-section-gray ol,
.rl-page .bullet-section-blue ul,
.rl-page .bullet-section-blue ol,
.rl-page .bullet-section-yellow ul,
.rl-page .bullet-section-yellow ol,
.rl-page .bullet-section-green ul,
.rl-page .bullet-section-green ol,
.rl-page .bullet-section-red ul,
.rl-page .bullet-section-red ol{
  margin: 0;
  padding-left: 20px;
}

.rl-page .bullet-section-gray li,
.rl-page .bullet-section-blue li,
.rl-page .bullet-section-yellow li,
.rl-page .bullet-section-green li,
.rl-page .bullet-section-red li,
.rl-page .bullet-section-gray li,
.rl-page .bullet-section-blue li,
.rl-page .bullet-section-yellow li,
.rl-page .bullet-section-green li,
.rl-page .bullet-section-red li{
  margin: 8px 0;
}

/* Tones */
.rl-page .bullet-section-gray,
.rl-page .bullet-section-gray{
  background: #f8fafc;
  border-color: #e2e8f0;
  border-left: 6px solid #cbd5e1;
}

.rl-page .bullet-section-blue,
.rl-page .bullet-section-blue{
  background: #fef2f2;
  border-color: #fecaca;
  border-left: 6px solid #C8102E;
}

.rl-page .bullet-section-yellow,
.rl-page .bullet-section-yellow{
  background: #fffbeb;
  border-color: #fde68a;
  border-left: 6px solid #f59e0b;
}

.rl-page .bullet-section-green,
.rl-page .bullet-section-green{
  background: #ecfdf5;
  border-color: #bbf7d0;
  border-left: 6px solid #16a34a;
}

.rl-page .bullet-section-red,
.rl-page .bullet-section-red{
  background: #fef2f2;
  border-color: #fecaca;
  border-left: 6px solid #dc2626;
}


/* -----------------------------
   3) CALLOUTS (vlnCallout + modifiers)
   You already have .rl-callout in plugin CSS.
   This adds:
   - bottom margin (fix tight spacing)
   - new modifiers:
     .rl-callout--green / .rl-callout--yellow / .rl-callout--red
   - alias support for your current usage:
     .rl-pro-tip (blue)
     .rl-disclosure (resources/disclosure)
   ----------------------------- */

/* Make callouts breathe (top + bottom) */
.rl-page .rl-callout,
.rl-page .rl-callout{
  margin: 16px 0;
}

/* Normalize callout headings inside the box */
.rl-page .rl-callout h2,
.rl-page .rl-callout h3,
.rl-page .rl-callout h2,
.rl-page .rl-callout h3{
  margin: 0 0 8px;
}

/* ===== Traffic-light callout tones ===== */

/* GREEN */
.rl-page .rl-callout.rl-callout--green,
.rl-page .rl-callout--green,
.rl-page .rl-callout.rl-callout--green,
.rl-page .rl-callout--green{
  background: #ecfdf5;
  border-color: #bbf7d0;
  border-left: 6px solid #16a34a;
}

/* YELLOW */
.rl-page .rl-callout.rl-callout--yellow,
.rl-page .rl-callout--yellow,
.rl-page .rl-callout.rl-callout--yellow,
.rl-page .rl-callout--yellow{
  background: #fffbeb;
  border-color: #fde68a;
  border-left: 6px solid #f59e0b;
}

/* RED */
.rl-page .rl-callout.rl-callout--red,
.rl-page .rl-callout--red,
.rl-page .rl-callout.rl-callout--red,
.rl-page .rl-callout--red{
  background: #fef2f2;
  border-color: #fecaca;
  border-left: 6px solid #dc2626;
}

/* Pro Tip (blue) — your markup: <div class="vlnCallout vlnProTip"> */
.rl-page .rl-callout.rl-pro-tip,
.rl-page .rl-pro-tip,
.rl-page .rl-callout.rl-pro-tip,
.rl-page .rl-pro-tip{
  background: #fef2f2;
  border-color: #fecaca;
  border-left: 6px solid #C8102E;
}

/* Disclosure / Resources (smaller text) — your markup: <div class="vlnCallout vlnDisclosure"> */
.rl-page .rl-callout.rl-disclosure,
.rl-page .rl-disclosure,
.rl-page .rl-callout.rl-disclosure,
.rl-page .rl-disclosure{
  background: #fff7ed;
  border-color: #fed7aa;
  border-left: 6px solid #f59e0b;
  font-size: 13px;
  line-height: 1.55;
  color: #334155;
}

/* Keep Resources title readable but not huge */
.rl-page .rl-disclosure h2,
.rl-page .rl-disclosure h3,
.rl-page .rl-disclosure h2,
.rl-page .rl-disclosure h3{
  font-size: 16px;
  font-weight: 950;
  color: #0F1F4A;
  margin: 0 0 10px;
}

/* Resources list tightening */
.rl-page .rl-disclosure ul,
.rl-page .rl-disclosure ol,
.rl-page .rl-disclosure ul,
.rl-page .rl-disclosure ol{
  margin: 0;
  padding-left: 18px;
}

.rl-page .rl-disclosure li,
.rl-page .rl-disclosure li{
  margin: 6px 0;
}

/* Resources links: make them obviously links even if theme tries to kill underlines */
.rl-page .rl-disclosure a,
.rl-page .rl-disclosure a{
  text-decoration: underline;
  text-underline-offset: 2px;
}
/* ============================================================
   RL ADD-ON (safe, append-only)
   Paste this at the VERY BOTTOM of your current CSS file
   OR (recommended) in Divi > Theme Options > Custom CSS /
   Appearance > Customize > Additional CSS.

   Purpose:
   - Traffic-light callouts + bullet sections (green/yellow/red)
   - Pro Tip + Disclosure/Resources box (smaller text)
   - Add breathing room for article pages (your "spacing is tight" issue)
   - No CSS variables, no :is/:where, no grid required
   ============================================================ */


/* -----------------------------
   1) ARTICLE SPACING (optional)
   Only applies when wrapper has: class="rl-page main-content"
   ----------------------------- */
.rl-page.main-content h2,
.rl-page.main-content h2{
  margin: 28px 0 12px;
}

.rl-page.main-content h3,
.rl-page.main-content h3{
  margin: 18px 0 10px;
}

.rl-page.main-content p,
.rl-page.main-content p{
  margin: 0 0 12px;
}

/* Keep hero heading from getting big top margins */
.rl-page.main-content .rl-hero h1,
.rl-page.main-content .rl-hero h2,
.rl-page.main-content .rl-hero h1,
.rl-page.main-content .rl-hero h2{
  margin: 0 0 10px;
}

/* Hide empty headings that Divi/wpautop sometimes injects */
.rl-page.main-content h2:empty,
.rl-page.main-content h3:empty,
.rl-page.main-content h2:empty,
.rl-page.main-content h3:empty{
  display: none;
}


/* -----------------------------
   2) BULLET SECTIONS (traffic light)
   Your markup uses:
   .bullet-section-gray / blue / yellow
   Add these too: .bullet-section-green / .bullet-section-red
   ----------------------------- */
.rl-page .bullet-section-gray,
.rl-page .bullet-section-blue,
.rl-page .bullet-section-yellow,
.rl-page .bullet-section-green,
.rl-page .bullet-section-red,
.rl-page .bullet-section-gray,
.rl-page .bullet-section-blue,
.rl-page .bullet-section-yellow,
.rl-page .bullet-section-green,
.rl-page .bullet-section-red{
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  padding: 14px 16px;
  margin: 16px 0;
  background: #ffffff;
  box-shadow: 0 10px 22px rgba(15,23,42,.04);
  color: #334155;
}

/* Bullet section headings inside the box */
.rl-page .bullet-section-gray h3,
.rl-page .bullet-section-blue h3,
.rl-page .bullet-section-yellow h3,
.rl-page .bullet-section-green h3,
.rl-page .bullet-section-red h3,
.rl-page .bullet-section-gray h3,
.rl-page .bullet-section-blue h3,
.rl-page .bullet-section-yellow h3,
.rl-page .bullet-section-green h3,
.rl-page .bullet-section-red h3{
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 900;
  color: #0F1F4A;
}

/* Lists inside bullet sections */
.rl-page .bullet-section-gray ul,
.rl-page .bullet-section-gray ol,
.rl-page .bullet-section-blue ul,
.rl-page .bullet-section-blue ol,
.rl-page .bullet-section-yellow ul,
.rl-page .bullet-section-yellow ol,
.rl-page .bullet-section-green ul,
.rl-page .bullet-section-green ol,
.rl-page .bullet-section-red ul,
.rl-page .bullet-section-red ol,
.rl-page .bullet-section-gray ul,
.rl-page .bullet-section-gray ol,
.rl-page .bullet-section-blue ul,
.rl-page .bullet-section-blue ol,
.rl-page .bullet-section-yellow ul,
.rl-page .bullet-section-yellow ol,
.rl-page .bullet-section-green ul,
.rl-page .bullet-section-green ol,
.rl-page .bullet-section-red ul,
.rl-page .bullet-section-red ol{
  margin: 0;
  padding-left: 20px;
}

.rl-page .bullet-section-gray li,
.rl-page .bullet-section-blue li,
.rl-page .bullet-section-yellow li,
.rl-page .bullet-section-green li,
.rl-page .bullet-section-red li,
.rl-page .bullet-section-gray li,
.rl-page .bullet-section-blue li,
.rl-page .bullet-section-yellow li,
.rl-page .bullet-section-green li,
.rl-page .bullet-section-red li{
  margin: 8px 0;
}

/* Tones */
.rl-page .bullet-section-gray,
.rl-page .bullet-section-gray{
  background: #f8fafc;
  border-color: #e2e8f0;
  border-left: 6px solid #cbd5e1;
}

.rl-page .bullet-section-blue,
.rl-page .bullet-section-blue{
  background: #fef2f2;
  border-color: #fecaca;
  border-left: 6px solid #C8102E;
}

.rl-page .bullet-section-yellow,
.rl-page .bullet-section-yellow{
  background: #fffbeb;
  border-color: #fde68a;
  border-left: 6px solid #f59e0b;
}

.rl-page .bullet-section-green,
.rl-page .bullet-section-green{
  background: #ecfdf5;
  border-color: #bbf7d0;
  border-left: 6px solid #16a34a;
}

.rl-page .bullet-section-red,
.rl-page .bullet-section-red{
  background: #fef2f2;
  border-color: #fecaca;
  border-left: 6px solid #dc2626;
}


/* -----------------------------
   3) CALLOUTS (vlnCallout + modifiers)
   You already have .rl-callout in plugin CSS.
   This adds:
   - bottom margin (fix tight spacing)
   - new modifiers:
     .rl-callout--green / .rl-callout--yellow / .rl-callout--red
   - alias support for your current usage:
     .rl-pro-tip (blue)
     .rl-disclosure (resources/disclosure)
   ----------------------------- */

/* Make callouts breathe (top + bottom) */
.rl-page .rl-callout,
.rl-page .rl-callout{
  margin: 16px 0;
}

/* Normalize callout headings inside the box */
.rl-page .rl-callout h2,
.rl-page .rl-callout h3,
.rl-page .rl-callout h2,
.rl-page .rl-callout h3{
  margin: 0 0 8px;
}

/* ===== Traffic-light callout tones ===== */

/* GREEN */
.rl-page .rl-callout.rl-callout--green,
.rl-page .rl-callout--green,
.rl-page .rl-callout.rl-callout--green,
.rl-page .rl-callout--green{
  background: #ecfdf5;
  border-color: #bbf7d0;
  border-left: 6px solid #16a34a;
}

/* YELLOW */
.rl-page .rl-callout.rl-callout--yellow,
.rl-page .rl-callout--yellow,
.rl-page .rl-callout.rl-callout--yellow,
.rl-page .rl-callout--yellow{
  background: #fffbeb;
  border-color: #fde68a;
  border-left: 6px solid #f59e0b;
}

/* RED */
.rl-page .rl-callout.rl-callout--red,
.rl-page .rl-callout--red,
.rl-page .rl-callout.rl-callout--red,
.rl-page .rl-callout--red{
  background: #fef2f2;
  border-color: #fecaca;
  border-left: 6px solid #dc2626;
}

/* Pro Tip (blue) — your markup: <div class="vlnCallout vlnProTip"> */
.rl-page .rl-callout.rl-pro-tip,
.rl-page .rl-pro-tip,
.rl-page .rl-callout.rl-pro-tip,
.rl-page .rl-pro-tip{
  background: #fef2f2;
  border-color: #fecaca;
  border-left: 6px solid #C8102E;
}

/* Disclosure / Resources (smaller text) — your markup: <div class="vlnCallout vlnDisclosure"> */
.rl-page .rl-callout.rl-disclosure,
.rl-page .rl-disclosure,
.rl-page .rl-callout.rl-disclosure,
.rl-page .rl-disclosure{
  background: #fff7ed;
  border-color: #fed7aa;
  border-left: 6px solid #f59e0b;
  font-size: 13px;
  line-height: 1.55;
  color: #334155;
}

/* Keep Resources title readable but not huge */
.rl-page .rl-disclosure h2,
.rl-page .rl-disclosure h3,
.rl-page .rl-disclosure h2,
.rl-page .rl-disclosure h3{
  font-size: 16px;
  font-weight: 950;
  color: #0F1F4A;
  margin: 0 0 10px;
}

/* Resources list tightening */
.rl-page .rl-disclosure ul,
.rl-page .rl-disclosure ol,
.rl-page .rl-disclosure ul,
.rl-page .rl-disclosure ol{
  margin: 0;
  padding-left: 18px;
}

.rl-page .rl-disclosure li,
.rl-page .rl-disclosure li{
  margin: 6px 0;
}

/* Resources links: make them obviously links even if theme tries to kill underlines */
.rl-page .rl-disclosure a,
.rl-page .rl-disclosure a{
  text-decoration: underline;
  text-underline-offset: 2px;
}
/* ==========================================================
   RL shaded callouts + traffic-light bullet boxes
   - Removes the thick left stripe
   - Adds shaded background + thin border (all sides)
   Paste at the VERY BOTTOM of your CSS (or Divi > Custom CSS)
   ========================================================== */

/* ---------- Base: all callouts + bullet sections ---------- */
.rl-callout,
.bullet-section-blue,
.bullet-section-gray,
.bullet-section-yellow,
.bullet-section-green,
.bullet-section-red{
  border: 1px solid #e2e8f0 !important;
  border-left: 1px solid #e2e8f0 !important;   /* kills thick left stripe */
  border-radius: 18px !important;
  background: #f8fafc !important;
  background-image: none !important;          /* kills gradients if any */
  box-shadow: none !important;                /* cleaner “flat” box */
  padding: 16px 18px !important;
  margin: 20px 0 !important;
}

/* If your current stripe is drawn via pseudo-elements, this removes it. */
.rl-callout::before,
.rl-callout::after{
  content: none !important;
  display: none !important;
}

/* ---------- Tone variants (Traffic Light + Pro Tip) ---------- */
.bullet-section-green,
.rl-callout--green{
  background: #ecfdf5 !important;
  border-color: #bbf7d0 !important;
  border-left-color: #bbf7d0 !important;
}

.bullet-section-yellow,
.rl-callout--yellow{
  background: #fffbeb !important;
  border-color: #fde68a !important;
  border-left-color: #fde68a !important;
}

.bullet-section-red,
.rl-callout--red{
  background: #fef2f2 !important;
  border-color: #fecaca !important;
  border-left-color: #fecaca !important;
}

/* Blue tone for bullet sections + Pro Tip callouts */
.bullet-section-blue,
.rl-callout--blue,
.rl-callout.rl-pro-tip{
  background: #fef2f2 !important;
  border-color: #fecaca !important;
  border-left-color: #fecaca !important;
}

/* Gray “neutral” box */
.bullet-section-gray{
  background: #f8fafc !important;
  border-color: #e2e8f0 !important;
  border-left-color: #e2e8f0 !important;
}

/* ---------- Cleaner typography + list spacing inside boxes ---------- */
.rl-callout h2,
.rl-callout h3,
.rl-callout h4,
.bullet-section-blue h2,
.bullet-section-blue h3,
.bullet-section-blue h4,
.bullet-section-gray h2,
.bullet-section-gray h3,
.bullet-section-gray h4,
.bullet-section-green h2,
.bullet-section-green h3,
.bullet-section-green h4,
.bullet-section-yellow h2,
.bullet-section-yellow h3,
.bullet-section-yellow h4,
.bullet-section-red h2,
.bullet-section-red h3,
.bullet-section-red h4{
  margin: 0 0 10px !important;
}

.rl-callout p,
.bullet-section-blue p,
.bullet-section-gray p,
.bullet-section-green p,
.bullet-section-yellow p,
.bullet-section-red p{
  margin: 0 0 10px !important;
}

.rl-callout p:last-child,
.bullet-section-blue p:last-child,
.bullet-section-gray p:last-child,
.bullet-section-green p:last-child,
.bullet-section-yellow p:last-child,
.bullet-section-red p:last-child{
  margin-bottom: 0 !important;
}

.rl-callout ul,
.rl-callout ol,
.bullet-section-blue ul,
.bullet-section-blue ol,
.bullet-section-gray ul,
.bullet-section-gray ol,
.bullet-section-green ul,
.bullet-section-green ol,
.bullet-section-yellow ul,
.bullet-section-yellow ol,
.bullet-section-red ul,
.bullet-section-red ol{
  margin: 0 !important;
  padding-left: 18px !important;
}

.rl-callout li,
.bullet-section-blue li,
.bullet-section-gray li,
.bullet-section-green li,
.bullet-section-yellow li,
.bullet-section-red li{
  margin: 8px 0 !important;
}

/* If you nest a bullet-section inside another, reduce the inner box spacing */
.bullet-section-gray .bullet-section-blue,
.bullet-section-gray .bullet-section-green,
.bullet-section-gray .bullet-section-yellow,
.bullet-section-gray .bullet-section-red{
  margin: 12px 0 0 !important;
}

/* ---------- Resources box: smaller text + tighter bullets ---------- */
.rl-callout.rl-disclosure{
  font-size: 13px !important;
  line-height: 1.55 !important;
}

.rl-callout.rl-disclosure li{
  margin: 6px 0 !important;
}

.rl-callout.rl-disclosure a{
  word-break: break-word;
}

/* ---------- Optional: loosen overall article spacing (scoped) ---------- */
.rl-page h2{ margin: 28px 0 12px !important; }
.rl-page h3{ margin: 18px 0 10px !important; }
.rl-page p{  margin: 0 0 14px !important; }

/* Don’t add extra top margin to the hero title */
.rl-page .rl-hero h2{ margin-top: 0 !important; }
/* ==========================================================
   RL FIX: Badge squares + traffic-light boxes + shaded callouts
   Paste at the VERY BOTTOM of vln-pages.css
   ========================================================== */

/* ---------------------------
   1) BADGE (the pill at top of each traffic-light card)
   Fix: dot stays orange because ::before never gets overridden.
---------------------------- */
.rl-page.rl-page .rl-badge,
.rl-page.rl-page .rl-badge{
  display:inline-flex !important;
  align-items:center !important;
  gap:8px !important;
  padding:6px 12px !important;
  border-radius:999px !important;

  border:1px solid rgba(15,23,42,.14) !important;
  background:#ffffff !important;

  color:#0f172a !important;
  font-weight:900 !important;
  font-size:12px !important;
  line-height:1 !important;
  letter-spacing:.08em !important;
  text-transform:uppercase !important;
  white-space:nowrap !important;

  box-shadow:none !important;
}

.rl-page.rl-page .rl-badge::before,
.rl-page.rl-page .rl-badge::before{
  content:"" !important;
  width:10px !important;
  height:10px !important;
  border-radius:3px !important;
  background:#f59e0b !important; /* fallback */
  flex:0 0 10px !important;
}

/* GREEN badge */
.rl-page.rl-page .rl-badge--green,
.rl-page.rl-page .rl-badge--green{
  background:rgba(22,163,74,.10) !important;
  border-color:rgba(22,163,74,.35) !important;
}
.rl-page.rl-page .rl-badge--green::before,
.rl-page.rl-page .rl-badge--green::before{
  background:#16a34a !important;
}

/* YELLOW badge */
.rl-page.rl-page .rl-badge--yellow,
.rl-page.rl-page .rl-badge--yellow{
  background:rgba(245,158,11,.12) !important;
  border-color:rgba(245,158,11,.40) !important;
}
.rl-page.rl-page .rl-badge--yellow::before,
.rl-page.rl-page .rl-badge--yellow::before{
  background:#f59e0b !important;
}

/* RED badge */
.rl-page.rl-page .rl-badge--red,
.rl-page.rl-page .rl-badge--red{
  background:rgba(239,68,68,.10) !important;
  border-color:rgba(239,68,68,.38) !important;
}
.rl-page.rl-page .rl-badge--red::before,
.rl-page.rl-page .rl-badge--red::before{
  background:#ef4444 !important;
}


/* ---------------------------
   2) TRAFFIC-LIGHT BOXES (your 3-column fit cards + the blue bullet boxes)
   Fix: theme/builder overrides are winning. Force tones with !important.
---------------------------- */
.rl-page.rl-page .bullet-section-green,
.rl-page.rl-page .bullet-section-yellow,
.rl-page.rl-page .bullet-section-red,
.rl-page.rl-page .bullet-section-blue,
.rl-page.rl-page .bullet-section-gray,
.rl-page.rl-page .bullet-section-green,
.rl-page.rl-page .bullet-section-yellow,
.rl-page.rl-page .bullet-section-red,
.rl-page.rl-page .bullet-section-blue,
.rl-page.rl-page .bullet-section-gray{
  border-radius:18px !important;
  padding:16px 18px !important;
  border:1px solid rgba(15,23,42,.12) !important;
  background:#ffffff !important;
  box-shadow:0 10px 24px rgba(15,23,42,.05) !important;
}

/* Tone fills */
.rl-page.rl-page .bullet-section-green,
.rl-page.rl-page .bullet-section-green{
  background:#ecfdf5 !important;
  border-color:rgba(22,163,74,.32) !important;
}

.rl-page.rl-page .bullet-section-yellow,
.rl-page.rl-page .bullet-section-yellow{
  background:#fffbeb !important;
  border-color:rgba(245,158,11,.38) !important;
}

.rl-page.rl-page .bullet-section-red,
.rl-page.rl-page .bullet-section-red{
  background:#fef2f2 !important;
  border-color:rgba(239,68,68,.35) !important;
}

.rl-page.rl-page .bullet-section-blue,
.rl-page.rl-page .bullet-section-blue{
  background:#fef2f2 !important;
  border-color:rgba(200,16,46,.35) !important;
}

.rl-page.rl-page .bullet-section-gray,
.rl-page.rl-page .bullet-section-gray{
  background:#f8fafc !important;
  border-color:rgba(100,116,139,.25) !important;
}

/* Keep the 3-column grid tight (no extra outer margins inside grid) */
.rl-page.rl-page .rl-grid-3 > .bullet-section-green,
.rl-page.rl-page .rl-grid-3 > .bullet-section-yellow,
.rl-page.rl-page .rl-grid-3 > .bullet-section-red,
.rl-page.rl-page .rl-grid-3 > .bullet-section-green,
.rl-page.rl-page .rl-grid-3 > .bullet-section-yellow,
.rl-page.rl-page .rl-grid-3 > .bullet-section-red{
  margin:0 !important;
}

/* List spacing inside these boxes */
.rl-page.rl-page .bullet-section-green ul,
.rl-page.rl-page .bullet-section-yellow ul,
.rl-page.rl-page .bullet-section-red ul,
.rl-page.rl-page .bullet-section-blue ul,
.rl-page.rl-page .bullet-section-gray ul,
.rl-page.rl-page .bullet-section-green ol,
.rl-page.rl-page .bullet-section-yellow ol,
.rl-page.rl-page .bullet-section-red ol,
.rl-page.rl-page .bullet-section-blue ol,
.rl-page.rl-page .bullet-section-gray ol,
.rl-page.rl-page .bullet-section-green ul,
.rl-page.rl-page .bullet-section-yellow ul,
.rl-page.rl-page .bullet-section-red ul,
.rl-page.rl-page .bullet-section-blue ul,
.rl-page.rl-page .bullet-section-gray ul,
.rl-page.rl-page .bullet-section-green ol,
.rl-page.rl-page .bullet-section-yellow ol,
.rl-page.rl-page .bullet-section-red ol,
.rl-page.rl-page .bullet-section-blue ol,
.rl-page.rl-page .bullet-section-gray ol{
  margin:0 !important;
  padding-left:20px !important;
}


/* ---------------------------
   3) CALLOUTS (“Deal Saver”, “Lender Reality Check”, etc.)
   Fix: make them shaded + more “intentional”.
---------------------------- */
.rl-page.rl-page .rl-callout,
.rl-page.rl-page .rl-callout{
  border-radius:18px !important;
  padding:16px 18px !important;
  border:1px solid rgba(15,23,42,.12) !important;
  background:#ffffff !important;
  box-shadow:0 10px 24px rgba(15,23,42,.05) !important;
  margin:20px 0 !important;
}

/* Blue (your existing class: vlnProTip) */
.rl-page.rl-page .rl-callout.rl-pro-tip,
.rl-page.rl-page .rl-callout.rl-pro-tip{
  background:#fef2f2 !important;
  border-color:rgba(200,16,46,.35) !important;
}

/* Resources/Disclosure */
.rl-page.rl-page .rl-callout.rl-disclosure,
.rl-page.rl-page .rl-callout.rl-disclosure{
  background:#fff7ed !important;
  border-color:rgba(245,158,11,.35) !important;
}

/* Optional: if you use these tone classes anywhere */
.rl-page.rl-page .rl-callout.rl-callout--green,
.rl-page.rl-page .rl-callout.rl-callout--green{
  background:#ecfdf5 !important;
  border-color:rgba(22,163,74,.32) !important;
}
.rl-page.rl-page .rl-callout.rl-callout--yellow,
.rl-page.rl-page .rl-callout.rl-callout--yellow{
  background:#fffbeb !important;
  border-color:rgba(245,158,11,.38) !important;
}
.rl-page.rl-page .rl-callout.rl-callout--red,
.rl-page.rl-page .rl-callout.rl-callout--red{
  background:#fef2f2 !important;
  border-color:rgba(239,68,68,.35) !important;
}

/* Make callouts NOT feel full-width on desktop (article pages only).
   If you hate this, delete this block. */
@media (min-width: 980px){
  .rl-page.rl-page.main-content .rl-callout:not(.rl-disclosure),
  .rl-page.rl-page.main-content .rl-callout:not(.rl-disclosure){
    width:100% !important;
    max-width:960px !important;
    margin-left:auto !important;
    margin-right:auto !important;
  }
}


/* ============================================================
   LRG-VARIANT CLASS ALIASES (added 2026-05-06)

   LRG's HTML migration introduced BEM-style and structural class
   names that VALN's CSS doesn't recognize. These aliases map LRG's
   class structure to existing VALN rule sets.

   Future canonical migration script will align LRG output with
   VALN's class names, at which point these aliases can be removed.
   ============================================================ */


/* ----------------------------------------------------------
   1. Bullet sections — base + BEM modifier classes
      Source: vln-pages.css lines 3839-3910
   ---------------------------------------------------------- */

.rl-page .rl-bullet-section{
  border: 1px solid #e2e8f0;
  border-radius: 18px;
  padding: 14px 16px;
  margin: 16px 0;
  background: #ffffff;
  box-shadow: 0 10px 22px rgba(15,23,42,.04);
  color: #334155;
}

.rl-page .rl-bullet-section h3{
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 900;
}

.rl-page .rl-bullet-section ul,
.rl-page .rl-bullet-section ol{
  margin: 0;
  padding-left: 20px;
}

.rl-page .rl-bullet-section li{
  margin: 8px 0;
}

/* Color variants — backgrounds + border accents */
.rl-page .rl-bullet-section--green{
  background: #ecfdf5;
  border-color: rgba(22, 163, 74, 0.35);
  border-left: 6px solid #16a34a;
}

.rl-page .rl-bullet-section--blue{
  background: #fef2f2;
  border-color: #fecaca;
  border-left: 6px solid #C8102E;
}

.rl-page .rl-bullet-section--red{
  background: #fef2f2;
  border-color: rgba(239, 68, 68, 0.38);
  border-left: 6px solid #ef4444;
}

.rl-page .rl-bullet-section--yellow{
  background: #fffbeb;
  border-color: rgba(245, 158, 11, 0.40);
  border-left: 6px solid #f59e0b;
}

.rl-page .rl-bullet-section--gray{
  background: #f8fafc;
  border-color: #e2e8f0;
  border-left: 6px solid #94a3b8;
}


/* ----------------------------------------------------------
   2. Quick Answers wrapper + header
      Source: vln-ui.css .vlnHero-quick / .vlnHero-quickHead
   ---------------------------------------------------------- */

.rl-page .rl-quick{
  margin-top: 14px;
  background: #f1f5f9;
  border-radius: 18px;
  border: 1px solid rgba(191,219,254,.9);
  padding: 12px 12px 10px;
}

.rl-page .rl-quick-head{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.rl-page .rl-quick-head h2{
  margin: 0;
  font-size: 12px;
  font-weight: 950;
  letter-spacing: .08em;
  text-transform: uppercase;
}

.rl-page .rl-quick-head span{
  font-size: 12px;
  color: #64748b;
  font-weight: 800;
}


/* ----------------------------------------------------------
   3. Top FAQ wrapper — mirrors .rl-faq rules
      Source: vln-pages.css lines 657-665
   ---------------------------------------------------------- */

.rl-page .rl-top-faq{
  margin-top: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 24px;
  background: #fff;
  overflow: hidden;
  box-shadow: 0 18px 45px rgba(15,23,42,.10);
}

.rl-page .rl-top-faq details{ border: 0; }
.rl-page .rl-top-faq details:not(:first-child){ border-top: 1px solid #e2e8f0; }

.rl-page .rl-top-faq summary{
  cursor: pointer;
  list-style: none;
  padding: 16px 16px;
  font-weight: 950;
  color: #0f172a;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}
.rl-page .rl-top-faq summary::-webkit-details-marker{ display: none; }

.rl-page .rl-top-faq summary:after{
  content: "+";
  width: 28px; height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  border: 1px solid #cbd5e1;
  background: #f8fafc;
  color: #64748b;
  font-weight: 950;
  flex: 0 0 auto;
}
.rl-page .rl-top-faq details[open] summary:after{ content: "\2013"; }

.rl-page .rl-top-faq .rl-faqBody{
  border-top: 1px solid #e2e8f0;
  padding: 12px 16px 16px;
  color: #475569;
  line-height: 1.75;
}

.rl-page .rl-top-faq .rl-faqBody p{ margin: 0; color: #475569; }


/* ----------------------------------------------------------
   4. Compact table variant (.rl-mini-table)
      Source: vln-pages.css .vlnTable rules (lines 396-445)
      with reduced padding for compact layout
   ---------------------------------------------------------- */

.rl-page .rl-mini-table{
  width: 100%;
  border-collapse: collapse;
  table-layout: auto;
  font-size: 13px;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  margin: 12px 0;
}

.rl-page .rl-mini-table th,
.rl-page .rl-mini-table td{
  border-bottom: 1px solid #e2e8f0;
  padding: 8px 10px;
  text-align: left;
  vertical-align: top;
  color: #334155;
  font-size: 13px;
  line-height: 1.55;
}

.rl-page .rl-mini-table thead th{
  background: #f8fafc;
  color: #0f172a;
  font-weight: 850;
}

.rl-page .rl-mini-table tbody tr:last-child td{ border-bottom: none; }

@media (max-width:640px){
  .rl-page .rl-mini-table{
    display: block;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
  .rl-page .rl-mini-table th,
  .rl-page .rl-mini-table td{
    padding: 6px 8px;
    font-size: 12px;
  }
}


/* ----------------------------------------------------------
   5. Utility: muted text
   ---------------------------------------------------------- */

.rl-page .rl-text-muted{
  color: #475569;
  font-size: 13px;
  line-height: 1.65;
}

/* ==========================================================
   Rank Logic Component Library — Cards
   .rl-card, .rl-card-inner, .rl-quick-grid, .rl-quick-card
   ========================================================== */

/* Base card */
.rl-page .rl-card {
  background: var(--rl-bg);
  border: 1px solid var(--rl-border);
  border-radius: var(--rl-card-radius);
  box-shadow: var(--rl-card-shadow);
}

.rl-page .rl-card-inner {
  padding: var(--rl-card-padding);
}

@media (max-width: 640px) {
  .rl-page .rl-card-inner {
    padding: 16px 14px;
  }
}

/* Quick cards — 2-column overview grid */
.rl-page .rl-quick-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

@media (max-width: 860px) {
  .rl-page .rl-quick-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

.rl-page .rl-quick-card {
  border-radius: var(--rl-card-radius-sm);
  border: 1px solid var(--rl-border);
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.96) 0%, rgba(255, 255, 255, 0.98) 100%);
  padding: 14px 14px 12px;
  box-shadow: var(--rl-card-shadow-sm);
}

.rl-page .rl-quick-card h3 {
  font-size: 15px;
  font-weight: var(--rl-font-weight-heavy);
  margin-bottom: 8px;
  color: var(--rl-primary-dark);
}

.rl-page .rl-quick-card ul {
  margin: 0;
  padding-left: 18px;
  list-style-type: disc;
  list-style-position: outside;
  color: var(--rl-text-muted);
}

.rl-page .rl-quick-card li {
  margin: 8px 0;
  display: list-item;
}

/* Pane — inner content container */
.rl-page .rl-pane {
  border-radius: var(--rl-card-radius-sm);
  border: 1px solid var(--rl-border);
  background: var(--rl-bg);
  padding: 18px 18px 16px;
  box-shadow: var(--rl-card-shadow-sm);
  min-width: 0;
}

@media (max-width: 640px) {
  .rl-page .rl-pane {
    padding: 14px 14px 12px;
  }
}

.rl-page .rl-pane-title {
  font-size: 15px;
  font-weight: 950;
  margin: 0 0 10px;
  color: var(--rl-primary-dark);
}

</style>
    <?php
}, 5 );
