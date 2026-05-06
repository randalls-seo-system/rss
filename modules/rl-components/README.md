# Rank Logic Component Library

Universal CSS component framework for productized content across all Rank Logic client sites.

## Quick Start

Include all CSS files in order:

```html
<link rel="stylesheet" href="css/rl-base.css">
<link rel="stylesheet" href="css/rl-layout.css">
<link rel="stylesheet" href="css/rl-hero.css">
<link rel="stylesheet" href="css/rl-cards.css">
<link rel="stylesheet" href="css/rl-faq.css">
<link rel="stylesheet" href="css/rl-tables.css">
<link rel="stylesheet" href="css/rl-callouts.css">
<link rel="stylesheet" href="css/rl-bullet-sections.css">
<link rel="stylesheet" href="css/rl-utility.css">
```

Override brand colors with CSS custom properties:

```css
:root {
  --rl-primary: #1a365d;
  --rl-accent: #f97316;
}
```

## Structure

```
css/              9 CSS files — base + 8 component layers
templates/        6 HTML templates — canonical + 5 intent variants
docs/             3 documentation files
examples/         3 client-branded examples (Canopy, VALN, LRG)
```

## Documentation

- `docs/component-library.md` — Visual reference of all components with markup
- `docs/css-variables.md` — Per-client customization guide
- `docs/migration-guide.md` — How to convert cnp-*/vln-* to rl-*

## Templates

| Template | Intent | Use Case |
|----------|--------|----------|
| `article-canonical.html` | Authority/info | Full ATF+BTF canonical article |
| `intent-decision.html` | Decision | "Which should I choose?" comparisons |
| `intent-process.html` | Process | "How do I do X?" step-by-step |
| `intent-comparison.html` | Comparison | "Best X" ranked reviews |
| `intent-news.html` | News/update | Time-sensitive rate/regulation changes |
| `intent-definition.html` | Definition | "What is X?" educational content |

## Per-Client Theming

Each client gets a theme file that imports the base and overrides CSS variables. See `docs/css-variables.md` for the full variable reference.

## Migration

Existing sites (Canopy, VALN) keep their current prefixes. New content uses rl-* classes. Both can coexist without conflicts. See `docs/migration-guide.md`.
