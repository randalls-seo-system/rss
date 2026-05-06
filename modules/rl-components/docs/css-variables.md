# CSS Variables — Per-Client Customization Guide

All Rank Logic components use CSS custom properties for theming. Override these in a per-client `rl-theme.css` file to match brand colors.

## How to Customize

Create a theme file that imports the base CSS and overrides variables:

```css
/* sites/<client-slug>/rl-theme.css */
@import url('../../modules/rl-components/css/rl-base.css');

:root {
  --rl-primary: #1a365d;
  --rl-accent: #f97316;
}
```

## Variable Reference

### Brand Colors (always override per client)

| Variable | Default | Purpose |
|----------|---------|---------|
| `--rl-primary` | `#1a365d` | Primary brand color (headings, buttons) |
| `--rl-primary-light` | `#2a4a7f` | Lighter primary (hover states) |
| `--rl-primary-dark` | `#0f2344` | Darker primary (H1, card titles) |
| `--rl-accent` | `#f97316` | Accent/CTA color |
| `--rl-accent-hover` | `#ea680b` | Accent hover state |
| `--rl-accent-soft` | `rgba(249,115,22,0.12)` | Accent background tint |
| `--rl-link` | `#2563eb` | Text link color |
| `--rl-link-hover` | `#1d4ed8` | Link hover color |

### Text Colors

| Variable | Default | Purpose |
|----------|---------|---------|
| `--rl-text` | `#0f172a` | Primary body text |
| `--rl-text-muted` | `#475569` | Secondary/paragraph text |
| `--rl-text-light` | `#94a3b8` | Tertiary (separators, meta) |

### Backgrounds

| Variable | Default | Purpose |
|----------|---------|---------|
| `--rl-bg` | `#ffffff` | Card/component background |
| `--rl-bg-alt` | `#f8fafc` | Alternate background (table headers) |
| `--rl-bg-soft` | `#f5f7ff` | Page-level soft background |
| `--rl-border` | `#e2e8f0` | Default border color |
| `--rl-border-accent` | `rgba(249,115,22,0.45)` | Accent border (eyebrow, CTA pill) |

### Spacing (rarely need to override)

| Variable | Default | Purpose |
|----------|---------|---------|
| `--rl-spacing-xs` | `4px` | Tight spacing |
| `--rl-spacing-sm` | `8px` | Small gaps |
| `--rl-spacing-md` | `16px` | Standard gaps |
| `--rl-spacing-lg` | `24px` | Section spacing |
| `--rl-spacing-xl` | `40px` | Large section spacing |

### Cards (rarely need to override)

| Variable | Default | Purpose |
|----------|---------|---------|
| `--rl-card-radius` | `24px` | Large card radius |
| `--rl-card-radius-sm` | `18px` | Small card radius |
| `--rl-card-radius-xs` | `14px` | Compact element radius |
| `--rl-card-padding` | `22px` | Card inner padding |
| `--rl-card-shadow` | (complex) | Card drop shadow |
| `--rl-card-shadow-sm` | (complex) | Smaller shadow |

### Typography (rarely need to override)

| Variable | Default | Purpose |
|----------|---------|---------|
| `--rl-font-body` | System stack | Body font family |
| `--rl-font-heading` | `"Poppins", system` | Heading font family |
| `--rl-font-mono` | `"Courier New"` | Monospace font |
| `--rl-font-size-base` | `14px` | Base font size |
| `--rl-line-height` | `1.65` | Base line height |
| `--rl-font-weight-normal` | `400` | Normal weight |
| `--rl-font-weight-bold` | `800` | Bold weight |
| `--rl-font-weight-heavy` | `900` | Heavy weight |

## Client Examples

### VA Loan Network (VALN)
```css
:root {
  --rl-primary: #00296B;
  --rl-primary-light: #0B3D91;
  --rl-primary-dark: #001B45;
  --rl-accent: #f97316;
  --rl-link: #0A66C2;
  --rl-link-hover: #084E94;
}
```

### Canopy Insurance (Canopy)
```css
:root {
  --rl-primary: #00296B;
  --rl-primary-light: #0B3D91;
  --rl-primary-dark: #0f2344;
  --rl-accent: #f97316;
}
```

### LRG (Placeholder)
```css
:root {
  --rl-primary: #1a365d;
  --rl-primary-dark: #0f2344;
  --rl-accent: #f97316;
}
```
