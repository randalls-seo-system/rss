# Technical SEO Infrastructure Module

Status: Templates complete (Day 2)

6 mu-plugins templated from VALN production, ready for config-driven rendering to any WordPress site.

## Quick Start

```bash
# Render for a site
./render.sh ../../sites/<slug>.conf

# Output in rendered/<slug>/
```

## Contents

- `source-from-valn/` — Original production mu-plugins (reference only)
- `templates/` — 6 template files with `{{VAR}}` placeholders
- `render.sh` — Renders templates into deployable mu-plugins
- `rendered/` — Output directory (per-site subdirectories)
- `REPLACEMENTS.md` — Discovery doc of all template substitutions

See `docs/module-specs/technical-seo.md` for full spec.
