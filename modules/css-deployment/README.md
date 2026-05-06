# CSS Deployment Module

Deploy rl-components CSS framework to WordPress sites via mu-plugin.

Handles the full lifecycle: source CSS porting, bundle building, deployment
via SCP, cache flushing, and rendering verification.

## Quick Start: New Client CSS in 3 Commands

```bash
# 1. Build the bundle
python3 modules/css-deployment/tools/build-css-bundle.py --site <slug>

# 2. Deploy to staging
bash modules/css-deployment/tools/deploy-css.sh --site <slug> --target staging

# 3. Verify it rendered
python3 modules/css-deployment/tools/verify-css-rendered.py \
    --site <slug> --sample-url "https://<staging-url>/?p=<post-id>"
```

## When to Use

- **New client onboarding:** Port existing CSS to rl-* namespace, deploy mu-plugin
- **CSS updates:** Rebuild bundle with updated rl-base.css, redeploy
- **Brand refresh:** Update site theme CSS, rebuild and deploy
- **Class-name divergence:** Add aliases instead of modifying article HTML

## Workflow

```
Source CSS (vln-pages.css, lrg-styles.css, etc.)
    │
    ▼
port-source-css.py ──→ rl-base.css (rl-* namespace)
    │
    ├── add-css-aliases.py ──→ aliases appended (if needed)
    │
    ▼
build-css-bundle.py ──→ deploy bundle:
    │                      rl-base.css
    │                      rl-<slug>-theme.css
    │                      rl-css-loader.php
    │                      manifest.json
    ▼
deploy-css.sh ──→ SCP to WPE + cache flush
    │
    ▼
verify-css-rendered.py ──→ pass/fail report
```

## Tools

| Tool | Purpose | SSH Required |
|------|---------|-------------|
| build-css-bundle.py | Combine base + theme CSS, generate loader | No |
| deploy-css.sh | SCP to WPE, version bump, cache flush | Yes |
| verify-css-rendered.py | Post-deploy rendering assertions | No |
| port-source-css.py | Convert proprietary classes to rl-* | No |
| add-css-aliases.py | Add class aliases for HTML divergence | No |

## Site Config Requirements

`sites/<slug>.conf` must have:
- `SSH_HOST`, `SSH_USER`, `SSH_KEY_PATH` — for deployment
- `SITE_NAME`, `SITE_DOMAIN` — for loader and verification
- `WP_PATH` — WordPress installation path
- `PRIMARY_COLOR`, `SECONDARY_COLOR` — for auto-generated theme stub

## Deployed Structure on WP Engine

```
wp-content/mu-plugins/
├── rl-css-loader.php              mu-plugin loader (enqueues CSS at priority 9999)
└── rl-css-loader/
    └── css/
        ├── rl-base.css            rl-components base (shared across sites)
        └── rl-<slug>-theme.css    site-specific brand overrides
```

## Troubleshooting

**CSS not applying:**
1. Check mu-plugin is loaded: `wp eval 'print_r(wp_get_mu_plugins());'`
2. Check CSS files return HTTP 200: `curl -sI <css-url>`
3. Check priority (9999 should beat most themes)
4. Check for Cloudflare/Varnish cache: add `?v=<timestamp>` to CSS URL

**Wrong source CSS:**
- Don't assume theme directory. Check actual enqueued CSS on a live page:
  `curl -s <page-url> | grep -oP 'href="[^"]*\.css[^"]*"'`
- VALN's real CSS is in `/wp-content/plugins/vln-interactive-pages/`, not theme

**Class names don't match:**
- Use `add-css-aliases.py` to add aliases instead of renaming HTML classes
- Common pattern: CamelCase vs kebab-case (vlnNextPill vs rl-next-pill)

## Rollback

Backups are created automatically in `<bundle-dir>/backups/<timestamp>/`.

```bash
# Restore previous version
BACKUP=~/lrg-rewrite/css-deploy/backups/20260506-193300/
scp -i ~/.ssh/wpengine_valn $BACKUP/rl-base.css lrgrealtyblog@lrgrealtyblog.ssh.wpengine.net:/sites/lrgrealtyblog/wp-content/mu-plugins/rl-css-loader/css/
```

## File Structure

```
modules/css-deployment/
├── README.md
├── tools/
│   ├── build-css-bundle.py
│   ├── deploy-css.sh
│   ├── verify-css-rendered.py
│   ├── port-source-css.py
│   └── add-css-aliases.py
├── templates/
│   └── rl-css-loader.php.template
├── lib/
│   ├── __init__.py
│   └── css_validator.py
└── examples/
    └── lrg-deployment-2026-05-06.md
```
