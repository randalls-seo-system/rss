# RSS Blog Home

Custom conversion-focused blog home page. Intercepts the blog index (`is_home()`) and renders a hybrid landing page with hero, featured article, article grid, category navigation, client reviews, and CTA sections. Pure PHP/CSS/JS — no Divi, no Gutenberg.

## Deployment

mu-plugin with subdirectory assets:
- `rss-blog-home.php` → `wp-content/mu-plugins/` (auto-activates)
- `rss-blog-home/assets/` → `wp-content/mu-plugins/rss-blog-home/assets/`

## Configuration

All settings via **WP Admin → Blog Home**. Stored in `rss_blog_home_settings` option.

### Settings reference

| Setting | Default | Purpose |
|---------|---------|---------|
| `enabled` | `1` | Master toggle |
| `hero_headline` | _(client-specific)_ | H1 text in hero |
| `hero_subhead` | _(client-specific)_ | Paragraph below headline |
| `cta_text` | `Connect with LRG` | Primary CTA button text |
| `cta_url` | `/lrg-blog/connect-with-lrg/` | CTA destination (relative) |
| `reviews_rating` | `4.9` | Star rating displayed |
| `reviews_count` | `1,180` | Review count displayed |
| `logo_url` | _(empty)_ | Logo image in hero (optional) |
| `navy` | `#0F1F4A` | Primary dark color |
| `red` | `#C8102E` | CTA/accent color |
| `gold` | `#FBBF24` | Star/trust color |
| `categories` | _(6 defaults)_ | Featured categories, one per line: `Display Name\|slug` |

## Page sections

1. **Hero** — navy gradient, headline (Fraunces serif), subhead, CTA button, trust stars
2. **Featured Article** — latest post or one with `_rss_featured` meta, 60/40 image/text split
3. **Latest Stories** — 3-column grid of 6 recent posts with thumbnails, category pills, read time
4. **Browse by Topic** — 3-column category cards with post counts, pulled from WP term data
5. **What Our Clients Say** — 3 review cards from `rss_reviews_list` option (requires RSS Google Reviews)
6. **Secondary CTA** — navy band with CTA button

## Routing

Hooks into `template_redirect` when `is_home() && !is_paged()`. Calls `get_header()` and `get_footer()` to preserve the active theme's header/footer (Divi Theme Builder compatible).

## Dependencies

- **RSS Google Reviews** (optional): reviews section reads from `rss_reviews_list` option. If empty, section is hidden.
- **Google Fonts**: Fraunces + Inter, loaded conditionally only on the blog home page.

## Fonts

- Headlines: Fraunces (serif, variable weight)
- Body: Inter (sans-serif)
