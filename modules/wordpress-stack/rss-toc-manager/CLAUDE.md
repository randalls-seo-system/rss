# RSS TOC Manager

Version: 1.0.0
Generalized from: VALN TOC Manager v1.12.0

## What it does

Sticky Table of Contents plugin for WordPress with:
- Auto-generated TOC from H2 headings
- Configurable CTA block (or no CTA if cta_url is empty)
- Per-post on/off override via post meta
- Per-post CTA copy override
- Sidebar widget (sticky)
- Shortcode: `[rss_toc]` (primary), `[ez-toc]` (legacy alias)
- Sticky CTA bar on scroll (auto-generated from inline CTA)
- Mobile hide option with configurable breakpoint
- Heading exclusion patterns
- Color picker for links and buttons
- Bulk enable/disable via admin list columns

## Deploying to a new client site

1. Copy the plugin file to mu-plugins:
   ```
   cat rss-toc-manager.php | ssh <user>@<host> 'cat > /nas/content/live/<install>/wp-content/mu-plugins/rss-toc-manager.php'
   ```

2. Verify activation (mu-plugins are auto-active):
   ```
   ssh <user>@<host> 'wp plugin list --status=must-use --format=csv'
   ```

3. Configure per-site CTA (skip if no CTA wanted):
   ```
   ssh <user>@<host> "wp option update rss_toc_settings '{\"cta_url\":\"/connect/\",\"cta_text\":\"Talk to Us\",\"cta_line1\":\"Ready to\",\"cta_line2\":\"Get Started?\",\"cta_line3\":\"Connect Today\"}' --format=json"
   ```

4. Or configure via WP Admin: Settings > RSS TOC

## Per-site CTA configuration

| Setting | Description | Default |
|---------|-------------|---------|
| cta_url | CTA button destination URL | (empty — no CTA shown) |
| cta_text | CTA button text | (empty) |
| cta_line1 | CTA heading line 1 | (empty) |
| cta_line2 | CTA heading line 2 (large) | (empty) |
| cta_line3 | CTA heading line 3 | (empty) |

When `cta_url` is empty, the entire CTA section is hidden (no empty wrapper rendered).

## Per-post override via post meta

| Meta key | Values | Effect |
|----------|--------|--------|
| `_rss_toc_enabled` | `on` / `off` / (empty) | Force on, force off, or use global default |
| `_rss_toc_cta_line1` | text | Override CTA heading line 1 for this post |
| `_rss_toc_cta_line2` | text | Override CTA heading line 2 for this post |
| `_rss_toc_cta_line3` | text | Override CTA heading line 3 for this post |
| `_rss_toc_cta_button` | text | Override CTA button text for this post |

## What was generalized

- Class: `VALN_TOC_Manager` -> `RSS_TOC_Manager`
- Option key: `valn_toc_settings` -> `rss_toc_settings`
- All meta keys: `_valn_toc_*` -> `_rss_toc_*`
- All CSS classes: `.valn-toc-*` -> `.rss-toc-*`
- All CSS variables: `--valn-toc-*` -> `--rss-toc-*`
- JS config: `valnTocConfig` -> `rssTocConfig`
- Shortcode: `[valn_toc]` -> `[rss_toc]` (`[ez-toc]` kept as legacy alias)
- Settings page: `valn-toc-manager` -> `rss-toc-manager`
- Default CTA values: cleared (was VALN-specific URLs/copy)
- New behavior: empty cta_url = CTA section not rendered at all
