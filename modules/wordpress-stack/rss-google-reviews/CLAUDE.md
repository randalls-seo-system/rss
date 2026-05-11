# RSS Google Reviews

Google reviews widget with slider, compact slider, full list, ticker, and Google Places API sync.

## Deployment

Copy the entire `rss-google-reviews/` directory to the client site's `wp-content/plugins/` and activate via WP admin or `wp plugin activate rss-google-reviews`.

This is a regular plugin (not mu-plugin) because it uses activation/deactivation hooks for cron scheduling and option seeding.

## Configuration

All settings are managed via **WP Admin → Google Reviews**. No wp-config or code changes needed.

### wp_options keys

| Key | Purpose |
|-----|---------|
| `rss_reviews_business` | Business name, address, rating, review count, colors, UI settings |
| `rss_reviews_list` | Array of review objects (manual + synced from Google) |
| `rss_reviews_google` | Google Places API config (place_id, api_key, auto_sync) |
| `rss_reviews_ticker` | Ticker interval (seconds), snippet length (characters) |

### Per-client setup

1. Activate plugin
2. Go to WP Admin → Google Reviews
3. Set business name + address
4. (Optional) Enter Google Place ID + API key for auto-sync
5. Add reviews manually or click "Sync Now" to pull from Google

## Shortcodes

| Shortcode | Output |
|-----------|--------|
| `[rss_reviews]` | Full-width slider with auto-play |
| `[rss_reviews_compact]` | Compact slider with "Read more" (modal or expand) |
| `[rss_reviews_list]` | Grid list of all reviews |
| `[rss_reviews_both]` | Slider + list combined |
| `[rss_reviews_ticker]` | Ultra-thin single-line rotating ticker |

### Ticker attributes

```
[rss_reviews_ticker interval="8" min_rating="5" length="200" show_source_link="true"]
```

### Backward-compatible aliases

These shortcodes are registered as aliases for sites migrating from the TVLN version:
`[tvln_reviews]`, `[va_reviews]`, `[tvln_reviews_list]`, `[tvln_reviews_both]`, `[tvln_reviews_compact]`, `[tvln_reviews_ticker]`

## External APIs

- **Google Places API**: Used for optional auto-sync of reviews. Requires a Places API key with the `place_id` field. Syncs up to 5 latest reviews per call. Can be scheduled daily via cron or triggered manually.

## File structure

```
rss-google-reviews/
├── rss-google-reviews.php    # Main plugin (545 lines)
├── assets/
│   ├── admin.css             # Admin UI styles
│   ├── admin.js              # Admin review list management
│   ├── frontend.css          # Slider, list, ticker, modal styles
│   └── frontend.js           # Slider, ticker, compact/modal behavior
└── CLAUDE.md
```

## CSS class prefix

Frontend CSS classes use the `tvln-` prefix (inherited from the original implementation). These are internal implementation details and not brand-visible. Do not rename them — the CSS and JS files are tightly coupled to these class names.
