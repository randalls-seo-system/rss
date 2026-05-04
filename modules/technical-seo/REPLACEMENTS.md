# Template Replacements Discovered

Pulled 2026-05-03 from VALN production. All 6 mu-plugins analyzed.

## Global Replacements (applied to all files)

| Original | Template Variable | Context |
|---|---|---|
| `valn_` | `{{SITE_PREFIX}}_` | PHP function names, option keys, transient keys, table suffixes, query vars, cron hooks |
| `valn-` | `{{SITE_PREFIX}}-` | Filenames, admin page slugs, WP-CLI sub-commands |
| `VALN_` | `{{SITE_PREFIX_UPPER}}_` | PHP class names |
| `VALN` (standalone in headers) | `{{SITE_PREFIX_UPPER}}` | Plugin Name / Author fields |

## Per-File Replacements

### valn-llms-config.php → llms-config.template.php

| Original Value | Replacement | Notes |
|---|---|---|
| Entire 49-URL config array (inline) | Externalized to `{{SITE_PREFIX}}-llms-urls.php` | Per-site PHP file returns the config array; loaded via `require` |
| Hardcoded tool IDs `[11686, 15382, ...]` | Loaded from urls config `tool_post_ids` key | No more hardcoded IDs in template |
| `1-800-230-7201` | In urls config `contact.phone` | Part of externalized data |
| `VA Loan Network is a Veteran-owned...` (intro) | In urls config `intro` key | Part of externalized data |
| `VA Loan Network is a marketing platform...` (disclosures) | In urls config `disclosures` key | Part of externalized data |
| 6 `valn_llms_*` functions | `{{SITE_PREFIX}}_llms_*` | Standard prefix swap |

### valn-llms-txt.php → llms-txt.template.php

| Original Value | Replacement | Notes |
|---|---|---|
| `valn_llms_txt` query var | `{{SITE_PREFIX}}_llms_txt` | |
| `valn_llms_txt_v2` transient | `{{SITE_PREFIX}}_llms_txt_v2` | |
| `valn_llms_txt_daily_write` cron hook | `{{SITE_PREFIX}}_llms_txt_daily_write` | |
| 5 `valn_llms_txt_*` functions | `{{SITE_PREFIX}}_llms_txt_*` | |
| `valn_llms_get_config` cross-ref | `{{SITE_PREFIX}}_llms_get_config` | |
| `valn_llms_get_all_post_ids` cross-ref | `{{SITE_PREFIX}}_llms_get_all_post_ids` | |
| `# VA Loan Network` fallback header | `# {{SITE_NAME}}` | When config not loaded |

### valn-ai-crawler-log.php → ai-crawler-log.template.php

| Original Value | Replacement | Notes |
|---|---|---|
| `valn_ai_crawler_db_version` option | `{{SITE_PREFIX}}_ai_crawler_db_version` | |
| `valn_ai_crawler_log` table name | `{{SITE_PREFIX}}_ai_crawler_log` | Used with $wpdb->prefix |
| `valn_ai_crawler_create_table` function | `{{SITE_PREFIX}}_ai_crawler_create_table` | |
| `valn_ai_crawler_detect` function | `{{SITE_PREFIX}}_ai_crawler_detect` | |
| `valn_ai_crawler_prune` cron hook | `{{SITE_PREFIX}}_ai_crawler_prune` | |
| `valn_ai_crawler_widget` widget ID | `{{SITE_PREFIX}}_ai_crawler_widget` | |
| `valn_ai_crawler_dashboard_render` function | `{{SITE_PREFIX}}_ai_crawler_dashboard_render` | |
| `wp valn ai-crawler` CLI namespace | `wp {{SITE_PREFIX}} ai-crawler` | |
| `VALN_AI_Crawler_CLI` class | `{{SITE_PREFIX_UPPER}}_AI_Crawler_CLI` | |

### valn-markdown-variants.php → markdown-variants.template.php

| Original Value | Replacement | Notes |
|---|---|---|
| `compare-loan-offers` (skip slug) | `{{FORM_PAGE_SLUG}}` | Form page excluded from md — empty string disables |
| `https://valoannetwork.com` (prod URL) | `{{SITE_URL}}` | Hardcoded in str_replace for md output |
| `valn_md_` transient prefix | `{{SITE_PREFIX}}_md_` | |
| `valn_md_render` function | `{{SITE_PREFIX}}_md_render` | |
| `valn_md_html_to_markdown` function | `{{SITE_PREFIX}}_md_html_to_markdown` | |
| `valn_llms_is_tool_page` cross-ref | `{{SITE_PREFIX}}_llms_is_tool_page` | |
| `\[valn_va_\|\[valn_calc\|\[valn_tool` regex | `\[{{SITE_PREFIX}}_` | Generalized — matches any site-prefixed shortcode |
| `\[valn_` in shortcode strip regex | `\[{{SITE_PREFIX}}_` | In html_to_markdown cleanup |

### valn-llms-full-txt.php → llms-full-txt.template.php

| Original Value | Replacement | Notes |
|---|---|---|
| `valn_llms_full` query var | `{{SITE_PREFIX}}_llms_full` | |
| `valn_regenerate_llms_full` cron hook | `{{SITE_PREFIX}}_regenerate_llms_full` | |
| 5 `valn_llms_full_*` functions | `{{SITE_PREFIX}}_llms_full_*` | |
| `valn_llms_get_config` cross-ref | `{{SITE_PREFIX}}_llms_get_config` | |
| `valn_md_html_to_markdown` cross-ref | `{{SITE_PREFIX}}_md_html_to_markdown` | |
| `valn_llms_is_tool_page` cross-ref | `{{SITE_PREFIX}}_llms_is_tool_page` | |
| `# VA Loan Network` content header | `# {{SITE_NAME}}` | Fallback and main header |
| `https://valoannetwork.com` prod URL | `{{SITE_URL}}` | |

### valn-dashboard-ai-crawlers.php → dashboard-ai-crawlers.template.php

| Original Value | Replacement | Notes |
|---|---|---|
| `valn-ai-crawlers` page slug | `{{SITE_PREFIX}}-ai-crawlers` | |
| `valn_ai_crawlers_render` function | `{{SITE_PREFIX}}_ai_crawlers_render` | |
| `valn_ai_crawler_log` table ref | `{{SITE_PREFIX}}_ai_crawler_log` | |
| `valn_ai_refresh` nonce action | `{{SITE_PREFIX}}_ai_refresh` | |
| `valn_ai_crawler_stats` transient | `{{SITE_PREFIX}}_ai_crawler_stats` | |
| 6 `valn_ai_crawlers_*` functions | `{{SITE_PREFIX}}_ai_crawlers_*` | css, cards, two_col, chart, recent, query |
| CSS `vac-` class prefix | **No change** | Internal CSS — no site conflict since each site is a separate WP install |
| `#1e3a8a`, `#3b82f6` dashboard colors | **No change** | Generic UI colors, not brand |

## Template Variables Summary

| Variable | Example (VALN) | Required | Used In |
|---|---|---|---|
| `{{SITE_PREFIX}}` | `valn` | Yes | All 6 templates |
| `{{SITE_PREFIX_UPPER}}` | `VALN` | Auto-derived | ai-crawler-log, all plugin headers |
| `{{SITE_NAME}}` | `VA Loan Network` | Yes | llms-txt, llms-full-txt, llms-config fallback |
| `{{SITE_URL}}` | `https://valoannetwork.com` | Yes | markdown-variants, llms-full-txt |
| `{{FORM_PAGE_SLUG}}` | `compare-loan-offers` | No (empty = disabled) | markdown-variants |

## Externalized Data Files

| File | Source | Purpose |
|---|---|---|
| `{{SITE_PREFIX}}-llms-urls.php` | `CONFIG_URLS_FILE` in site config | PHP `return [...]` with intro, disclosures, sections, contact, tool_post_ids |

## Expected Diff Notes (rendered VALN vs original)

1. **llms-config.php**: Structural change — config loaded via `require` instead of inline. Functionally identical.
2. **markdown-variants.php**: Shortcode detection simplified from 3 specific patterns to 1 general prefix match. Functionally equivalent (catches same shortcodes + more).
3. **markdown-variants.php**: Form page skip has guard for empty slug. No-op difference when slug is set.
4. **All files**: Plugin Name/Author headers updated to template format. No functional impact.
