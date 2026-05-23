# RSS Lead Form

Version: 1.0.0
Source: Netlify form prototype at source/index.html

## What it does

Multi-step lead capture form for real estate client sites. Renders via
`[lrg_lead_form]` shortcode. Six paths: buyer, seller, VA/veteran,
market updates, neighborhood alerts, general question.

On submission:
1. Saves lead to WordPress as custom post type `rss_lead`
2. Emails lead to Follow Up Boss via email-ingestion address
3. Logs submission to /tmp/rss-lead-form.log

## File structure

```
rss-lead-form.php          — main plugin (shortcode, AJAX, CPT, settings)
assets/rss-lead-form.css   — scoped CSS (.rss-lf-root container)
assets/rss-lead-form.js    — form logic + AJAX submission
CLAUDE.md                  — this file
source/index.html          — original prototype (reference only)
```

## Deploying to a new site

1. Copy plugin files:
   ```
   ssh <host> 'mkdir -p /path/wp-content/plugins/rss-lead-form/assets'
   cat rss-lead-form.php | ssh <host> 'cat > /path/wp-content/plugins/rss-lead-form/rss-lead-form.php'
   cat assets/rss-lead-form.css | ssh <host> 'cat > /path/wp-content/plugins/rss-lead-form/assets/rss-lead-form.css'
   cat assets/rss-lead-form.js | ssh <host> 'cat > /path/wp-content/plugins/rss-lead-form/assets/rss-lead-form.js'
   ```

2. Activate: `wp plugin activate rss-lead-form`

3. Configure settings:
   ```
   wp option update rss_lf_settings --format=json '{"fub_email":"...", ...}'
   ```
   Or via WP Admin → Settings → RSS Lead Form.

4. Create a page with `[lrg_lead_form]` as the content.

## Settings (wp_options key: rss_lf_settings)

| Key | Description | Default |
|-----|-------------|---------|
| fub_email | FUB email-ingestion address | (empty) |
| cc_recipients | CC emails, one per line | (empty) |
| from_email | Sender email | noreply@{domain} |
| from_name | Sender name | Site name |
| phone_for_errors | Phone shown in error messages | (empty) |
| enable_db | Save leads to database | true |
| enable_email | Forward leads via email | true |

## Anti-spam

- **Honeypot field**: Hidden `name="website"` input. If filled, submission
  silently returns success without saving. Position: off-screen via CSS.
- **Rate limiting**: 3 submissions per IP per 10 minutes. Uses WP transients
  keyed on hashed IP. Over-limit submissions silently return success.

## CTA referral tracking

Article CTA links include `?ref=<post-slug>`. The form reads this from
`window.location.search` and includes it in the submission payload as
`ref_param`. The email's Message body shows the referring page.

## Email format (for FUB parsing)

```
Name: {firstname} {lastname}
Email: {email}
Phone: {phone}
Source: LRG Blog Lead
Message:
Path: {path label}

{Question}: {Answer}
...

Submitted: 2026-05-09 2:30 PM CDT
Page: /lrg-blog/cost-of-living-san-antonio/
```

FUB's email parser extracts Name, Email, Phone, and Message from these labels.

## CSS scoping

All CSS is scoped under `.rss-lf-root` to prevent leaking into the host
WordPress theme. CSS variables use `.rss-lf-root` instead of `:root`.
The shortcode wraps all form HTML in `<div class="rss-lf-root">`.

## Known limitations

- WPE may not have outbound SMTP configured. Email forwarding requires
  WP Mail SMTP plugin + SendGrid or similar transport.
- Form copy/paths are LRG-specific. Generalizing to other clients
  requires extracting the HTML template and path definitions.
- No FUB API integration — uses email-based ingestion only.
