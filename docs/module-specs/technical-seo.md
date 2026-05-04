# Technical SEO Module

## Status: Complete (v1.0)

## What This Module Does

Deploys 6 mu-plugins to a target WordPress site that together provide AI/LLM-optimized infrastructure:

1. **llms-config** — Site-specific URL configuration (curated list of pages organized by topic for AI crawler ingestion)
2. **llms-txt** — Dynamic /llms.txt endpoint following the AI discovery standard
3. **ai-crawler-log** — Database table + tracking for AI crawler visits (ChatGPT-User, PerplexityBot, ClaudeBot, etc.)
4. **markdown-variants** — ?format=md handler that serves clean markdown for AI consumption
5. **llms-full-txt** — Single-file /llms-full.txt export of all site content for AI ingestion
6. **dashboard-ai-crawlers** — WP Admin dashboard page showing crawler activity

## How To Deploy

### New site (full pipeline)

```bash
# 1. Render templates
./modules/technical-seo/render.sh sites/<slug>.conf

# 2. Dry-run to verify pre-flight (SSH, paths, WP-CLI)
./modules/technical-seo/deploy.sh sites/<slug>.conf --dry-run

# 3. Review rendered files manually
ls modules/technical-seo/rendered/<slug>/

# 4. Deploy for real (backs up existing files first)
./modules/technical-seo/deploy.sh sites/<slug>.conf
```

### Via orchestration layer

```bash
# Renders + deploys all enabled modules
./tools/deploy-to-site.sh sites/<slug>.conf
```

### Dry-run mode

```bash
./modules/technical-seo/deploy.sh sites/<slug>.conf --dry-run
```

Runs all pre-flight checks (SSH, paths, WP-CLI, file presence) without uploading or modifying anything. Reports what would be deployed.

## Template Variables

| Variable | Required | Example | Used In |
|---|---|---|---|
| `SITE_PREFIX` | Yes | `valn` | All 6 templates — PHP identifiers and slugs |
| `SITE_NAME` | Yes | `VA Loan Network` | llms-txt, llms-full-txt, llms-config fallback |
| `SITE_URL` | Yes | `https://valoannetwork.com` | markdown-variants, llms-full-txt |
| `SITE_SLUG` | Yes | `valn` | Output directory name |
| `FORM_PAGE_SLUG` | No | `compare-loan-offers` | markdown-variants (empty = disabled) |
| `CONFIG_URLS_FILE` | No | `sites/valn-llms-urls.php` | Companion data file for llms-config |

`SITE_PREFIX_UPPER` is auto-derived from `SITE_PREFIX`.

## URL Config File Format

Each site provides a PHP file (referenced by `CONFIG_URLS_FILE`) that returns an array:

```php
<?php
return [
    'intro'          => 'Site description for AI crawlers...',
    'disclosures'    => 'Legal disclosures...',
    'sections'       => [
        [
            'key'   => 'guides',
            'title' => 'Core Guides',
            'items' => [
                [ 'id' => 123, 'path' => '/guide/', 'title' => 'Guide', 'desc' => '...' ],
            ],
        ],
    ],
    'contact'        => [
        'cta'   => [ 'id' => 456, 'path' => '/get-started/', 'title' => 'Get Started', 'desc' => '...' ],
        'phone' => '1-800-555-0100',
    ],
    'tool_post_ids'  => [ 123, 456 ],
];
```

## Deploy Script Behavior

1. **Pre-flight** — Validates rendered files exist, SSH works, mu-plugins path writable, WP-CLI available
2. **Backup** — Copies existing mu-plugins to `.rss-backups/<timestamp>/` on target
3. **Upload** — SCP each file, verify size matches
4. **Verify** — Check functions exist via `wp eval`
5. **Static files** — Trigger llms.txt and llms-full.txt generation, flush rewrite rules + cache

## Rollback

Deploy creates timestamped backups. To rollback:

```bash
ssh <target> 'cp <backup-dir>/* <mu-plugins-path>/ && rm <mu-plugins-path>/<prefix>-*.php'
```

The exact command is printed at the end of each successful deploy.

## Known Limitations

- WP Engine serves /llms.txt and /llms-full.txt as static files, bypassing PHP. Static file hits don't get logged in crawler table.
- llms-full.txt generation is heavy on large sites; cached to /wp-content/uploads/llms-full-cache.txt and refreshed nightly via cron.
- Static files must be written to doc root, not just uploads, for nginx to serve them.
- Markdown conversion uses regex-based HTML stripping — works well for standard WP content and Divi, but may need tuning for other page builders.

## Validation Notes

- **VALN**: Rendered output matches production (functional code byte-identical, Day 2)
- **TLN**: Dry-run deploy passes all pre-flight checks. TLN has a simpler existing `tln-llms-txt.php` (static heredoc) that RSS would replace with config-driven version. No staging environment — production deploy deferred.

## What's NOT in This Module

- Yoast configuration (separate module, future)
- Schema markup (separate module, future)
- Robots.txt management (separate module, future)
- Content generation or rewriting
