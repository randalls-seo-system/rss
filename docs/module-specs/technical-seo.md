# Technical SEO Module

## What This Module Does

Deploys 6 mu-plugins to a target WordPress site that together provide AI/LLM-optimized infrastructure:

1. **llms-config** — Site-specific URL configuration (curated list of pages organized by topic for AI crawler ingestion)
2. **llms-txt** — Dynamic /llms.txt endpoint following the AI discovery standard
3. **ai-crawler-log** — Database table + tracking for AI crawler visits (ChatGPT-User, PerplexityBot, ClaudeBot, etc.)
4. **markdown-variants** — ?format=md handler that serves clean markdown for AI consumption
5. **llms-full-txt** — Single-file /llms-full.txt export of all site content for AI ingestion
6. **dashboard-ai-crawlers** — WP Admin dashboard page showing crawler activity

## How To Deploy

1. Ensure site config exists at `sites/<slug>.conf`
2. Ensure URL config exists at path specified in `CONFIG_URLS_FILE`
3. Run: `./modules/technical-seo/render.sh sites/<slug>.conf`
4. Verify rendered files in `modules/technical-seo/rendered/<slug>/`
5. Deploy via: `./tools/deploy-to-site.sh sites/<slug>.conf` (Day 5 task)

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

## Known Limitations

- WP Engine serves /llms.txt and /llms-full.txt as static files, bypassing PHP. Static file hits don't get logged in crawler table.
- llms-full.txt generation is heavy on large sites; cached to /wp-content/uploads/llms-full-cache.txt and refreshed nightly via cron.
- Static files must be written to doc root, not just uploads, for nginx to serve them.
- Markdown conversion uses regex-based HTML stripping — works well for standard WP content and Divi, but may need tuning for other page builders.

## What's NOT in This Module

- Yoast configuration (separate module, future)
- Schema markup (separate module, future)
- Robots.txt management (separate module, future)
- Content generation or rewriting
