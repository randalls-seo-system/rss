# LRG CSS Deployment — 2026-05-06

First production use of rl-components CSS on Levi Rodgers Real Estate Group.

## Iteration History

| Version | Change | Result |
|---------|--------|--------|
| v1.0.0 | rl-base.css (3,830 bytes, CSS variables only) | Unstyled — variables without rules |
| v1.0.1 | Added !important + priority 9999 | Still unstyled — specificity wasn't the issue |
| v1.0.2 | Ported vln-ui.css from Divi child theme (37K) | Still unstyled — wrong source file |
| v1.0.3 | Ported vln-pages.css from vln-interactive-pages plugin (76K) | ATF styled, body sections working |
| v1.0.4 | Added 8 CSS aliases for LRG-variant class names | Fully working |

## Key Lesson

VALN's real CSS lives in `/wp-content/plugins/vln-interactive-pages/`, NOT
in the Divi child theme. The theme's `vln-ui.css` is a small subset.

**How to find the right source CSS for any site:**
```bash
curl -s https://site.com/page-with-styled-content/ | \
    grep -oP 'href="[^"]*\.css[^"]*"' | sort -u
```
Then check which CSS file contains the classes used in the HTML.

## Deployed Structure

```
/sites/lrgrealtyblog/wp-content/mu-plugins/
├── rl-css-loader.php           (mu-plugin loader, v1.0.4)
└── rl-css-loader/
    └── css/
        ├── rl-base.css         (81,526 bytes — ported from vln-pages.css)
        └── rl-lrg-theme.css    (1,971 bytes — brand colors + overrides)
```

## CSS Aliases Added (v1.0.4)

LRG's HTML uses class names that differ slightly from VALN's originals.
Instead of modifying the HTML (which would break during content migration),
aliases were added to the CSS:

| LRG class | Mirrors | Reason |
|-----------|---------|--------|
| `bullet-section-green` | `rl-bullet-section--green` | Missing `rl-` prefix + double-dash |
| `bullet-section-blue` | `rl-bullet-section--blue` | Same pattern |
| `bullet-section-gray` | `rl-bullet-section--gray` | Same pattern |
| `bullet-section-yellow` | `rl-bullet-section--yellow` | Same pattern |
| `bullet-section-red` | `rl-bullet-section--red` | Same pattern |
| `rl-quick-head` | `rl-hero-quick-head` | Shorter alias |
| `rl-text-muted` | custom rules | Utility class |
| `rl-compact-answer` | custom rules | FAQ answer spacing |

## Commands Used

```bash
# Build bundle
python3 modules/css-deployment/tools/build-css-bundle.py --site lrg --version 1.0.4

# Port source CSS
python3 modules/css-deployment/tools/port-source-css.py \
    --source-css ~/lrg-rewrite/css/valn-source-v2/vln-pages.css \
    --source-prefix vln \
    --output-css ~/lrg-rewrite/css-deploy/rl-base.css

# Add aliases
python3 modules/css-deployment/tools/add-css-aliases.py \
    --target-css ~/lrg-rewrite/css-deploy/rl-base.css \
    --aliases-yaml ~/lrg-rewrite/css/lrg-aliases.json

# Deploy to staging
bash modules/css-deployment/tools/deploy-css.sh --site lrg --target staging

# Verify
python3 modules/css-deployment/tools/verify-css-rendered.py \
    --site lrg \
    --sample-url "https://lrgrealtyblog.wpenginepowered.com/?p=2662" \
    --expected-classes "rl-page,rl-quick-grid,rl-faq,rl-hero"
```
