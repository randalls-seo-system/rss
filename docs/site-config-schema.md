# Site Config Schema — `sites/<site>/config.json`

Canonical configuration for every RSS-managed site. One JSON file per site
replaces the scattered `.conf`, `-linker.json`, and `-reference.md` files.

## Migration

Existing `*-linker.json` files remain valid — `link-injector.py` reads its
current `--site-config` path. The `linking` section of this schema is a
strict superset: every field in a `-linker.json` has a home here. Tools
will be updated to read from `sites/<site>/config.json` in a separate
migration session. Until then, both formats coexist.

## Schema

### `identity` (required)

| Field | Type | Req | Description | Read by |
|-------|------|-----|-------------|---------|
| `site_id` | string | Y | Short slug: valn, tln, lrg, gfp, canopy | all tools |
| `name` | string | Y | Display name | reporting, schema markup |
| `public_url` | string | Y | Production URL with scheme | deploy, sitemap |
| `platform` | string | N | "wpe", "wpe-worker", "cloudflare-pages" | deploy scripts |
| `platform_notes` | string | N | Reverse proxy, Worker routing, etc. | human reference |

### `access` (required)

| Field | Type | Req | Description |
|-------|------|-----|-------------|
| `ssh_host` | string | Y | SSH hostname |
| `ssh_user` | string | Y | SSH username (production) |
| `ssh_key_path` | string | Y | Path to SSH key |
| `wp_path` | string | Y | Absolute WP install path on server |
| `mu_plugins_path` | string | N | Absolute mu-plugins path |
| `staging.url` | string | N | Staging URL |
| `staging.ssh_user` | string | N | Staging SSH user |
| `staging.ssh_key_path` | string | N | Staging SSH key |
| `staging.wp_path` | string | N | Staging WP path |

### `content` (required)

| Field | Type | Req | Description |
|-------|------|-----|-------------|
| `css_prefix` | string[] | Y | CSS class prefixes for this site's components |
| `brand_voice_archetype` | string | N | Key into `modules/brand-voice/archetypes/` |
| `primary_color` | string | N | Hex color |
| `secondary_color` | string | N | Hex color |
| `logo_url` | string | N | Logo image URL |
| `phone` | string | N | Site phone number |
| `cta_url` | string | N | Universal CTA destination (e.g., /compare-loan-offers/) |
| `cta_text` | string | N | CTA button text |
| `form_page_slug` | string | N | Lead form page slug |
| `claims_policy` | string | N | Path to the site's authoritative claims/voice rules file. Contains closed-set factual positions, attribution requirements, and content guardrails that all content for this site must follow. Examples: VALN messaging standard (Matt's AUS corrections), AHN Shariah attribution block, TLN program-specific underwriting rules. |
| `article_min_words` | int | N | Pipeline minimum |
| `article_max_words` | int | N | Pipeline maximum |
| `default_post_status` | string | N | "draft" or "publish" |

### `authors` (required)

| Field | Type | Req | Description |
|-------|------|-----|-------------|
| `author_map` | object | Y | Role → `{wp_user_id, name, scope}` |
| `byline_mode` | string | N | "single", "multi", "team" |
| `never_author` | int[] | N | WP user IDs that must never appear as post_author |

Example:
```json
"author_map": {
  "primary_sme": {"wp_user_id": 941, "name": "Matt Schwartz", "scope": "mortgage-operational"},
  "secondary": {"wp_user_id": 234, "name": "Levi Rodgers", "scope": "benefits-lifestyle"}
}
```

### `linking` (required for linker tools)

| Field | Type | Req | Description | Read by |
|-------|------|-----|-------------|---------|
| `zone_suffixes` | string[] | Y | Hero, callout, faq, etc. | link-injector, inject-internal-links |
| `extra_zone_classes` | string[] | N | Additional full class names to block | link-injector |
| `skip_slugs` | string[] | Y | Slugs excluded from injection as sources | link-injector |
| `protected_slugs` | string[] | N | Never modified as source AND never used as destination | link-injector |
| `excluded_destinations` | string[] | N | URL prefixes that are never link targets | link-injector |
| `pool_path` | string | N | Path to anchor-pool JSON relative to repo root | link-injector, inject-internal-links |
| `inbound_min` | int | N | Inbound-priority threshold (default 3) | link-injector |
| `per_run_dest_cap` | int | N | Hard cap per destination per run (default 10) | link-injector |
| `max_links_per_para` | int | N | Default 1 | link-injector |
| `max_links_per_section` | int | N | Default 3 | link-injector |
| `max_links_per_post` | int | N | Default 10 | link-injector |
| `pages_as_sources` | bool | N | Default false | link-injector |
| `url_transform` | string|null | N | "lrg_blog_prefix" or null | link-injector |
| `canonical_formats` | object | N | URL patterns per post type | link-injector |
| `source_dest_language_match` | bool | N | Enforce language matching | link-injector |
| `language_prefixes` | object | N | Language → URL prefix map | link-injector |

### `protected` (recommended)

| Field | Type | Description |
|-------|------|-------------|
| `do_not_touch_pages` | object[] | `{post_id, slug, reason}` — never modify without explicit approval |
| `theme_builder_layouts` | int[] | Divi Theme Builder layout post IDs |
| `frozen_subsystems` | object[] | `{name, path, status, notes}` |
| `known_traps` | object[] | `{name, description}` — WPCode gotchas, cache behavior, etc. |

### `integrations` (optional)

| Field | Type | Description |
|-------|------|-------------|
| `gsc_property` | string | Google Search Console property |
| `ga4_measurement_id` | string | GA4 measurement ID |
| `ga4_property_id` | string | GA4 property number |
| `clarity_project_id` | string | Microsoft Clarity ID |
| `gtm_container_id` | string | Google Tag Manager |
| `meta_pixel_id` | string | Meta Pixel ID |
| `cdn_notes` | string | Varnish, Cloudflare, purge behavior |
| `lead_form_notes` | string | Form ID, CRM integration |
| `nmls_number` | string | For mortgage sites |
| `license_disclaimer` | string | Compliance disclaimer |

### `ops` (optional)

| Field | Type | Description |
|-------|------|-------------|
| `work_log` | object | `{table, method, categories, metric_types}` |
| `backup_dir` | string | Server path convention for backups |
| `persistent_ops_dir` | string | For sites where ~ is ephemeral |
| `service_tier` | string | "Premium", "Pro", "Starter" |
| `reference_files` | object | Key → local path for content spec, voice file, etc. |

## File Organization

```
sites/
  valn/
    config.json          ← canonical config (this schema)
  tln/
    config.json
  lrg/
    config.json
  valn.conf              ← legacy, read by site_config.py (migration pending)
  valn-linker.json       ← legacy, read by link-injector.py (migration pending)
  valn-anchor-pools.json ← anchor pool data (stays here)
  valn-reference.md      ← migrates into config.json protected/ops sections
```
