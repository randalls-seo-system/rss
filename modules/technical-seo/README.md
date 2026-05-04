# Technical SEO Infrastructure Module

Status: Complete (v1.0)

6 mu-plugins templated from VALN production, with config-driven rendering and automated deployment to any WordPress site.

## Quick Start

```bash
# Render templates for a site
./render.sh ../../sites/<slug>.conf

# Dry-run deploy (pre-flight checks only)
./deploy.sh ../../sites/<slug>.conf --dry-run

# Real deploy (backup + upload + verify)
./deploy.sh ../../sites/<slug>.conf
```

## Contents

- `source-from-valn/` — Original production mu-plugins (reference)
- `templates/` — 6 `.template.php` files with `{{VAR}}` placeholders
- `render.sh` — Renders templates into deployable mu-plugins
- `deploy.sh` — Deploys rendered files to target via SSH/SCP
- `rendered/` — Output directory per site (gitignored)
- `REPLACEMENTS.md` — Discovery doc of all template substitutions

See `docs/module-specs/technical-seo.md` for full spec.
