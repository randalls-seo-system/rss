# WordPress Stack — RSS Standard Plugin Suite

This directory holds the Randall's SEO System standard plugin stack
that gets deployed to every client WordPress site.

## Architecture

Each plugin lives in its own subdirectory with:
- The main `.php` plugin file (mu-plugin format, auto-activates)
- A `CLAUDE.md` with deployment instructions and configuration reference

## Core plugins (every client site)

| Plugin | Directory | Status |
|--------|-----------|--------|
| RSS TOC Manager | `rss-toc-manager/` | v1.0.0 — generalized from VALN TOC Manager |

## Optional add-ons (per-client)

Not every site gets these. Deploy only when the client has the relevant
use case (e.g. strong Google review presence, scroll-triggered CTA need).

| Plugin | Directory | Status | When to deploy |
|--------|-----------|--------|----------------|
| RSS Google Reviews | `rss-google-reviews/` | v1.0.0 | Client has Google Business reviews worth showcasing |
| RSS Sticky CTA | `rss-sticky-cta/` | v1.0.0 | Site needs scroll-triggered conversion bar |
| RSS Blog Home | `rss-blog-home/` | v1.0.0 | Client wants a custom conversion-focused blog home page |

## Future plugins to generalize

These are currently VALN-specific mu-plugins that will be generalized
into the RSS stack when their client-specific logic is extracted:

- Schema manager (Article, FAQ, HowTo JSON-LD)
- Redirect engine (301 redirect map with template_redirect hook)
- FAQ schema generator (vlnFaq details/summary -> FAQPage JSON-LD)
- Form submission guard (idempotent lead form with UUID dedup)
- Cache header manager (per-post-type cache-control)
- AI crawler config (robots meta for AI crawlers)

## Deployment pattern

1. Copy plugin PHP to client site's `wp-content/mu-plugins/`
2. Configure per-site settings via `wp option update`
3. Verify via admin UI or `wp option get`

mu-plugins are auto-activated by WordPress — no `wp plugin activate` needed.

## Rules

- Do NOT modify VALN production mu-plugins directly. Generalize here first,
  test on staging, then deploy the RSS version to replace the VALN version.
- Each plugin must work with zero configuration (sensible defaults).
- Client-specific values (CTA URLs, brand colors, phone numbers) go in
  wp_options, never hardcoded in the plugin.
