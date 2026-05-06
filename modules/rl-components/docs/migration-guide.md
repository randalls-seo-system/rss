# Migration Guide — Legacy Prefixes to rl-*

How to convert existing client sites (Canopy cnp-*, VALN vln-*) to the universal rl-* component library.

## Approach

Migration happens **organically with new content**, not as a bulk rewrite. Existing pages keep their current prefixes. New pages use rl-* classes exclusively.

## Class Mapping

### Canopy (cnp*) to Rank Logic (rl-*)

| Canopy Class | RL Class | CSS File |
|-------------|----------|----------|
| `.cnpPage` | `.rl-page` | rl-layout.css |
| `.cnpWrap` | `.rl-wrap` | rl-layout.css |
| `.cnpCard` | `.rl-card` | rl-cards.css |
| `.cnpCard-inner` | `.rl-card-inner` | rl-cards.css |
| `.cnpHero` | `.rl-hero` | rl-hero.css |
| `.cnpHeroLead` | `.rl-hero-lead` | rl-hero.css |
| `.cnpBreadcrumb` | `.rl-breadcrumb` | rl-hero.css |
| `.cnpEyebrow` | `.rl-eyebrow` | rl-hero.css |
| `.cnpMeta` | `.rl-meta` | rl-hero.css |
| `.cnpPills` | `.rl-pills` | rl-hero.css |
| `.cnpPill` | `.rl-pill` | rl-hero.css |
| `.cnpNextPill` | `.rl-next-pill` | rl-hero.css |
| `.cnpNextLabel` | `.rl-next-label` | rl-hero.css |
| `.cnpNextLink` | `.rl-next-link` | rl-hero.css |
| `.cnpQuickGrid` | `.rl-quick-grid` | rl-cards.css |
| `.cnpQuickCard` | `.rl-quick-card` | rl-cards.css |
| `.cnpFaq` | `.rl-faq` | rl-faq.css |
| `.cnpTableScroll` | `.rl-table-scroll` | rl-tables.css |
| `.cnpTable` | `.rl-table` | rl-tables.css |
| `.cnpCallout` | `.rl-callout` | rl-callouts.css |
| `.cnpCallout-warn` | `.rl-callout--warning` | rl-callouts.css |
| `.cnpCallout-blue` | `.rl-callout--info` | rl-callouts.css |
| `.cnpDisclosure` | `.rl-disclosure` | rl-callouts.css |
| `.cnpSection` | `.rl-section` | rl-layout.css |
| `.cnpSectionHead` | `.rl-section-head` | rl-layout.css |
| `.cnpGrid2` | `.rl-grid-2` | rl-layout.css |
| `.cnpGrid3` | `.rl-grid-3` | rl-layout.css |
| `.cnpBtn` | `.rl-btn` | rl-utility.css |
| `.cnpBtn-primary` | `.rl-btn--primary` | rl-utility.css |
| `.cnpBtn-secondary` | `.rl-btn--secondary` | rl-utility.css |
| `.cnpPane` | `.rl-pane` | rl-cards.css |
| `.cnpPaneTitle` | `.rl-pane-title` | rl-cards.css |
| `.bullet-section-green` | `.rl-bullet-section--green` | rl-bullet-sections.css |
| `.bullet-section-yellow` | `.rl-bullet-section--yellow` | rl-bullet-sections.css |
| `.bullet-section-red` | `.rl-bullet-section--red` | rl-bullet-sections.css |
| `.bullet-section-blue` | `.rl-bullet-section--blue` | rl-bullet-sections.css |
| `.bullet-section-gray` | `.rl-bullet-section--gray` | rl-bullet-sections.css |

### VALN (vln*) to Rank Logic (rl-*)

Same mapping as Canopy, replacing `vln` prefix:

| VALN Class | RL Class |
|-----------|----------|
| `.vlnPage` | `.rl-page` |
| `.vlnWrap` | `.rl-wrap` |
| `.vlnCard` | `.rl-card` |
| `.vlnHero` | `.rl-hero` |
| `.vlnHeroLead` | `.rl-hero-lead` |
| `.vlnEyebrow` | `.rl-eyebrow` |
| `.vlnNextPill` | `.rl-next-pill` |
| `.vlnNextLabel` | `.rl-next-label` |
| `.vlnNextLink` | `.rl-next-link` |
| `.vlnQuickGrid` | `.rl-quick-grid` |
| `.vlnQuickCard` | `.rl-quick-card` |
| `.vlnFaq` | `.rl-faq` |
| `.vlnTableScroll` | `.rl-table-scroll` |
| `.vlnTable` | `.rl-table` |
| `.vlnCallout` | `.rl-callout` |
| `.vlnDisclosure` | `.rl-disclosure` |

## Migration Steps (per page)

1. **Load rl-* CSS** alongside existing CSS (no conflicts — different prefixes)
2. **New content** uses rl-* classes
3. **When rewriting** an existing page, swap class names using the mapping above
4. **Set client theme** in rl-theme.css to match existing brand colors
5. **Test** — verify visual parity with the original

## Data Attribute Changes

| Legacy | RL |
|--------|-----|
| `data-vln-page` | `data-rl-page` |
| `data-cnp-table` | `data-rl-table` |

## Coexistence

Both legacy and rl-* CSS can load simultaneously. The prefixes are different, so there are zero selector conflicts. This allows gradual migration without a "big bang" cutover.
