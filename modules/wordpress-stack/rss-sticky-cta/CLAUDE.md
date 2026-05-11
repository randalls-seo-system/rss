# RSS Sticky CTA Bar

Fixed bottom bar with star rating display, reviews ticker, and CTA button. Slides up after scroll, with an optional disclosure-only mode for specific pages.

## Deployment

Copy `rss-sticky-cta.php` to the client site's `wp-content/mu-plugins/`. Auto-activates as mu-plugin.

## Configuration

All settings via **WP Admin → Sticky CTA**. Stored in the single `rss_sticky_cta` option.

### Settings reference

| Setting | Default | Purpose |
|---------|---------|---------|
| `rating_value` | `5.0` | Star rating number displayed |
| `rating_tagline` | `by our clients` | Text below the rating |
| `mobile_summary` | `Rated {rating} out of 5 stars` | Mobile one-liner (`{rating}` = placeholder) |
| `cta_url` | _(empty)_ | CTA button destination (relative path). Blank hides the button. |
| `cta_label` | `Get Started` | CTA button text |
| `reviews_url` | _(empty)_ | Reviews button destination (relative path). Blank hides the button. |
| `reviews_label` | `Read Our Reviews` | Reviews button text |
| `bar_bg` | `#0b1e3a` | Bar background color |
| `accent_color` | `#2F7BFF` | Accent color for rating highlight |
| `star_color` | `#FBBF24` | Star icon color |
| `cta_bg` | `#ffd500` | CTA button background |
| `cta_text_color` | `#00296b` | CTA button text color |
| `ticker_shortcode` | `[rss_reviews_ticker ...]` | Shortcode rendered in the ticker area. Requires RSS Google Reviews. |
| `show_after_scroll` | `1` | Bar slides up after 10% viewport scroll |
| `exclude_urls` | `/confirmation` | URL patterns where bar is hidden (one per line) |
| `disclosure_urls` | `/apply` | URL patterns that show disclosure bar instead (one per line) |
| `disclosure_text` | _(empty)_ | HTML for the disclosure mini bar |

### Per-client setup

1. Drop `rss-sticky-cta.php` into mu-plugins
2. Go to WP Admin → Sticky CTA
3. Set CTA URL + label, Reviews URL
4. Adjust brand colors
5. (Optional) Configure disclosure text for apply-type pages

## Three render modes

1. **Full bar** (default): Rating block + ticker + CTA + Reviews button, revealed on scroll
2. **Disclosure bar**: Centered text-only bar, always visible (on URLs matching `disclosure_urls`)
3. **Hidden**: No bar rendered (on URLs matching `exclude_urls`)

## Companion plugin

The ticker area renders a shortcode — typically `[rss_reviews_ticker]` from the RSS Google Reviews plugin. If that plugin isn't installed, the ticker area is blank but the bar still works.

## Origin

Generalized from VALN's `valn-sitebar.php` (541 lines). Reduced to 313 lines by:
- Extracting all hardcoded values into wp_options
- Removing 70+ lines of page-385-specific CSS
- Removing 80-line staging hotfix with duplicate CSS
- Removing VALN-specific CTA text, page IDs, and URL patterns
