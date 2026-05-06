#!/usr/bin/env python3
"""
Rank Logic — Tier A Class Migration Tool
Converts lrg* article kit classes to rl-* component classes.

Usage:
    python3 migrate-classes.py <input.html> <output.html> [--site-class rl-page-lrg]
    python3 migrate-classes.py <input.html> <output.html> --canonical

Modes:
    --canonical (default for future Tier A migrations)
        Aligns output with VALN's proven class structure. Bullet sections
        keep VALN's flat names (bullet-section-green), tables use rl-table,
        FAQ body keeps camelCase (rl-faqBody). No extra structural wrappers.
        CSS in rl-base.css already has rules for these class names.

    --no-canonical (legacy mode, used for LRG post 2662)
        BEM-style renaming: bullet-section-green → rl-bullet-section--green,
        rl-mini-table for compact tables, rl-quick wrapper + rl-quick-head.
        Requires CSS alias rules in the LRG-VARIANT section of rl-base.css.

Always wraps output in <div class="rl-page {site-class}">...</div>
if the wrapper is not already present.
"""

import sys
import re
import argparse

# Shared class mappings (same in both modes)
_SHARED = [
    # Wrapper / layout
    ('lrgArticleKit', 'rl-page'),
    ('lrgWrap', 'rl-wrap'),
    ('lrgPage', 'rl-page'),

    # Hero
    ('lrgHero', 'rl-hero'),
    ('lrgHeroLead', 'rl-hero-lead'),
    ('lrgHero-eyebrow', 'rl-eyebrow'),
    ('lrgEyebrow', 'rl-eyebrow'),
    ('lrgMeta', 'rl-meta'),
    ('lrgBreadcrumb', 'rl-breadcrumb'),

    # Cards / sections
    ('lrgCard-inner', 'rl-card-inner'),
    ('lrgCard', 'rl-card'),
    ('lrgSectionHead', 'rl-section-head'),
    ('lrgSection-head', 'rl-section-head'),
    ('lrgSection', 'rl-section'),

    # Callouts / disclosure
    ('lrgDisclosure', 'rl-disclosure'),
    ('lrgCallout', 'rl-callout'),
    ('lrgNote', 'rl-callout'),

    # Buttons (order matters: specific before generic)
    ('lrgBtn-primary', 'rl-btn--primary'),
    ('lrgBtn-secondary', 'rl-btn--secondary'),
    ('lrgBtn-ghost', 'rl-btn--ghost'),
    ('lrgBtn-compare', 'rl-btn--secondary'),
    ('lrgBtn', 'rl-btn'),

    # CTA
    ('lrgNextStep', 'rl-next-pill'),
    ('lrgNextLabel', 'rl-next-label'),
    ('lrgNextLink', 'rl-next-link'),

    # Pills
    ('lrgPills', 'rl-pills'),
    ('lrgJumpPill', 'rl-pill'),
    ('lrgPill', 'rl-pill'),

    # Utility
    ('lrgHelp', 'rl-text-muted'),
    ('lrgHide', 'rl-hide'),
    ('lrgSkip', 'rl-skip'),
    ('lrgCtas', 'rl-ctas'),

    # Grid
    ('lrgGrid2', 'rl-grid-2'),
    ('lrgGrid3', 'rl-grid-3'),

    # Pane
    ('lrgPaneTitle', 'rl-pane-title'),
    ('lrgPane', 'rl-pane'),

    # Refs / Sources
    ('lrgRefs', 'rl-refs'),
    ('lrgSources', 'rl-disclosure'),

    # Nearby / related
    ('lrgNearby', 'rl-nearby'),
    ('lrgRelated', 'rl-related'),
]

# Canonical mode: aligns with VALN's proven class names.
# rl-base.css has rules for all of these directly.
_CANONICAL_ONLY = [
    # Quick cards — no structural wrapper, direct grid
    ('lrgQuickGrid', 'rl-quick-grid'),
    ('lrgQuickCard', 'rl-quick-card'),
    ('lrgQuickHead', 'rl-quick-head'),
    ('lrgQuickTitle', 'rl-quick-title'),
    ('lrgQuick ', 'rl-quick '),

    # FAQ — camelCase body matches CSS selector
    ('lrgFaqBody', 'rl-faqBody'),
    ('lrgFaqItem', 'rl-faq-item'),
    ('lrgFaq', 'rl-faq'),
    ('lrgTopFaq', 'rl-top-faq'),

    # Tables — standard rl-table (no mini variant)
    ('lrgTableScroll', 'rl-table-scroll'),
    ('lrgMiniTable', 'rl-table'),
    ('lrgTable', 'rl-table'),

    # Bullet sections — preserve VALN's flat class names
    ('bullet-section-green', 'bullet-section-green'),
    ('bullet-section-blue', 'bullet-section-blue'),
    ('bullet-section-gray', 'bullet-section-gray'),
    ('bullet-section-red', 'bullet-section-red'),
    ('bullet-section-yellow', 'bullet-section-yellow'),
    ('bullet-section-beige', 'bullet-section-gray'),
]

# Legacy mode: BEM-style renaming (used for LRG post 2662).
# Requires CSS alias rules in the LRG-VARIANT section of rl-base.css.
_LEGACY_ONLY = [
    # Quick cards — adds structural wrappers
    ('lrgQuickGrid', 'rl-quick-grid'),
    ('lrgQuickCard', 'rl-quick-card'),
    ('lrgQuickHead', 'rl-quick-head'),
    ('lrgQuickTitle', 'rl-quick-title'),
    ('lrgQuick ', 'rl-quick '),

    # FAQ
    ('lrgFaqBody', 'rl-faqBody'),
    ('lrgFaqItem', 'rl-faq-item'),
    ('lrgFaq', 'rl-faq'),
    ('lrgTopFaq', 'rl-top-faq'),

    # Tables — compact variant
    ('lrgTableScroll', 'rl-table-scroll'),
    ('lrgMiniTable', 'rl-mini-table'),
    ('lrgTable', 'rl-table'),

    # Bullet sections — BEM modifier classes
    ('bullet-section-green', 'rl-bullet-section rl-bullet-section--green'),
    ('bullet-section-blue', 'rl-bullet-section rl-bullet-section--blue'),
    ('bullet-section-gray', 'rl-bullet-section rl-bullet-section--gray'),
    ('bullet-section-red', 'rl-bullet-section rl-bullet-section--red'),
    ('bullet-section-yellow', 'rl-bullet-section rl-bullet-section--yellow'),
    ('bullet-section-beige', 'rl-bullet-section rl-bullet-section--gray'),
]


def get_replacements(canonical: bool = True) -> list[tuple[str, str]]:
    """Build the full replacement list for the chosen mode."""
    mode_specific = _CANONICAL_ONLY if canonical else _LEGACY_ONLY
    return _SHARED + mode_specific


def migrate(content: str, site_class: str = 'rl-page-lrg',
            canonical: bool = True) -> tuple[str, int]:
    """Apply class replacements and wrap in rl-page. Returns (output, change_count)."""
    replacements = get_replacements(canonical)
    changes = 0
    for old, new in replacements:
        count = content.count(old)
        if count:
            content = content.replace(old, new)
            changes += count

    # Ensure rl-page wrapper exists
    if f'class="rl-page {site_class}"' not in content:
        content = f'<div class="rl-page {site_class}">\n{content.rstrip()}\n</div>'
        changes += 1

    # Verify no lrg* remnants
    remnants = re.findall(r'\blrg[A-Z][a-zA-Z-]*', content)
    if remnants:
        print(f"WARNING: {len(remnants)} unmapped lrg* tokens remain:", file=sys.stderr)
        for r in set(remnants):
            print(f"  {r}", file=sys.stderr)

    return content, changes


def main():
    parser = argparse.ArgumentParser(description='Migrate lrg* classes to rl-*')
    parser.add_argument('input', help='Input HTML file')
    parser.add_argument('output', help='Output HTML file')
    parser.add_argument('--site-class', default='rl-page-lrg',
                        help='Per-site class added to rl-page wrapper (default: rl-page-lrg)')
    parser.add_argument('--canonical', action='store_true', default=True,
                        help='Use VALN-aligned class names (default)')
    parser.add_argument('--no-canonical', dest='canonical', action='store_false',
                        help='Use legacy BEM-style class names (post 2662 compat)')
    args = parser.parse_args()

    with open(args.input, 'r') as f:
        content = f.read()

    result, changes = migrate(content, args.site_class, args.canonical)
    mode = 'canonical' if args.canonical else 'legacy'

    with open(args.output, 'w') as f:
        f.write(result)

    print(f"Mode: {mode}")
    print(f"Migrated: {changes} replacements")
    print(f"Size: {len(content)} → {len(result)} bytes")
    print(f"rl-page wrapper: {'present' if 'rl-page' in result else 'MISSING'}")


if __name__ == '__main__':
    main()
