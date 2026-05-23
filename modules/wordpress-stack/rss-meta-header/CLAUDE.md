# RSS Meta Header

EEAT meta header block for WordPress posts and pages. Renders a "Written by / Reviewed by / Updated" credibility strip at the top of every article.

## What it does

Outputs a styled block showing:
- **Author** (name, avatar, role, NMLS if applicable)
- **Reviewer** (configurable per-site default, editorial team option, or per-post custom)
- **Updated date** (post modified date)

Hooks into `the_content` filter (injects after first `</h1>`). Bottom placement uses `et_after_main_content` (Divi) or `wp_footer` (non-Divi fallback). Integrates with Yoast for `reviewedBy` schema; emits standalone JSON-LD when Yoast is absent.

## Why this matters for SEO

Google's E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness) signals are a core ranking factor for YMYL content. This plugin makes authorship and editorial review visible to both users and crawlers via structured data.

## Configuration

### Default reviewer (Settings > RSS Meta Header)

Set once per site. Fields: name, profile URL, role, image, NMLS, type (Person/Organization). Leave name empty to hide the reviewer line by default.

### Editorial team (Settings > RSS Meta Header)

Optional second reviewer choice. Always typed as Organization in schema. Fields: team name, short mobile name, page URL, image.

### Author identity (WordPress user meta)

Author data comes from the WP user profile. Customize per-user with these meta keys:

| User Meta Key | Purpose |
|---|---|
| `rss_mh_avatar` | Custom avatar URL (overrides gravatar) |
| `rss_mh_profile_url` | Profile page URL (overrides author archive URL) |
| `rss_mh_role` | Role/title shown on desktop |
| `rss_mh_role_mobile` | Shorter role for mobile (optional) |
| `rss_mh_name_mobile` | Shorter display name for mobile (optional) |
| `rss_mh_nmls` | NMLS number |
| `rss_mh_nmls_url` | NMLS lookup URL |

Set via WP-CLI: `wp user meta update <user_id> rss_mh_role "Loan Officer"`

### Per-post overrides (post/page meta box)

Each post has a sidebar meta box with:
- **Enable/disable** the meta header
- **Content type**: Article (Written by) or Tool (Created by)
- **Placement**: Top (below hero) or Bottom (after content)
- **Hide reviewer**: checkbox to suppress reviewer line
- **Reviewer selection**: Default (from Settings), Editorial Team, or Custom
- **Spacing override**: per-post gap in px (overrides global)
- **Label overrides**: custom text for author/reviewer/date labels

### Post meta keys reference

| Meta Key | Values |
|---|---|
| `_rss_enable_block` | `1` (enabled, default) / `0` (disabled) |
| `_rss_reviewer_select` | `default` / `editorial_team` / `custom` |
| `_rss_reviewer_override` | Array: `{name, role, nmls, url, img}` |
| `_rss_eeat_mode` | `article` / `tool` |
| `_rss_eeat_position` | `top` / `bottom` |
| `_rss_eeat_hide_reviewer` | `0` / `1` |
| `_rss_eeat_label_author` | Custom label string |
| `_rss_eeat_label_reviewer` | Custom label string |
| `_rss_eeat_label_updated` | Custom label string |
| `_rss_gap_override` | Integer px value (-60 to 120), blank = global |

## Deployment

Install as mu-plugin: copy `rss-meta-header.php` to `wp-content/mu-plugins/`.

After activation, go to Settings > RSS Meta Header to configure the default reviewer and editorial team for the site.
