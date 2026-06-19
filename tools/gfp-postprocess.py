#!/usr/bin/env python3
"""Post-process RSS v2 article output into GFP's gfp* class system.

Transforms pipeline rl-* HTML into GFP's gfpPage / gfpHero / gfpBluf /
gfpCallout / gfpFaq class system. GFP uses Divi theme builder for layout
(no shortcode wrapping needed) — only class remapping + structural wraps.

Complete rl- → gfp- class map:
    rl-hero             → gfpHero
    rl-eyebrow          → gfpHero__subtitle
    rl-cta-primary      → gfpCta
    rl-quick-card       → gfpQuickCard (wrapped in gfpQuickGrid)
    rl-jump-nav         → gfpJumpNav
    rl-atf-lede         → gfpLede
    rl-bluf             → gfpBluf
    rl-callout          → gfpCallout
    rl-callout--*       → gfpCallout (all variants)
    rl-faq              → gfpFaq
    rl-resources        → gfpCallout gfpCallout--resources
    rl-closing          → (class removed, plain section)
    rl-cta-mid          → gfpCta-wrap
    <table>             → gfpTableScroll wrapper + gfpTable class
    <details>           → styled by .gfpFaq details (CSS handles it)

Usage:
    python3 tools/gfp-postprocess.py \\
        --input <path> \\
        --output <path>
"""

import argparse
import sys
from bs4 import BeautifulSoup, NavigableString


# ---------------------------------------------------------------------------
# A. Class renames (complete rl- → gfp- map)
# ---------------------------------------------------------------------------

_CLASS_MAP = {
    "rl-hero": "gfpHero",
    "rl-eyebrow": "gfpHero__subtitle",
    "rl-cta-primary": "gfpCta",
    "rl-quick-card": "gfpQuickCard",
    "rl-jump-nav": "gfpJumpNav",
    "rl-atf-lede": "gfpLede",
    "rl-bluf": "gfpBluf",
    "rl-callout": "gfpCallout",
    "rl-faq": "gfpFaq",
    "rl-closing": "",  # remove class, keep element
    "rl-cta-mid": "gfpCta-wrap",
    "rl-cta-pill": "gfpCta",
    "rl-cluster-box": "",  # not used on GFP
}

# All callout variants map to gfpCallout
_CALLOUT_VARIANTS = [
    "rl-callout--deal_math",
    "rl-callout--file_guidance",
    "rl-callout--approval_watchpoint",
    "rl-callout--cost_surprise",
    "rl-callout--operator_note",
    "rl-callout--common_mistake",
    "rl-callout--common_confusion",
    "rl-callout--clear_definition",
    "rl-callout--disqualifier",
    "rl-callout--key_insight",
    "rl-callout--when_each_wins",
]


def _rename_classes(soup: BeautifulSoup) -> None:
    """Rename all rl-* classes to gfp* equivalents."""
    for el in soup.find_all(True):
        classes = el.get("class", [])
        if not classes:
            continue
        if isinstance(classes, str):
            classes = classes.split()

        new_classes = []
        for cls in classes:
            if cls in _CLASS_MAP:
                replacement = _CLASS_MAP[cls]
                if replacement:
                    new_classes.extend(replacement.split())
            elif cls in _CALLOUT_VARIANTS:
                pass  # variant modifier removed, base gfpCallout handles it
            elif cls == "rl-resources":
                new_classes.extend(["gfpCallout", "gfpCallout--resources"])
            elif cls.startswith("rl-"):
                # Unmapped rl- class — warn and keep
                print(f"WARNING: unmapped rl- class: {cls}", file=sys.stderr)
                new_classes.append(cls)
            else:
                new_classes.append(cls)

        if new_classes:
            el["class"] = new_classes
        elif "class" in el.attrs:
            del el["class"]


# ---------------------------------------------------------------------------
# B. Structural transforms
# ---------------------------------------------------------------------------

def _wrap_quick_cards(soup: BeautifulSoup) -> None:
    """Wrap consecutive gfpQuickCard elements in a gfpQuickGrid section."""
    cards = soup.find_all("article", class_="gfpQuickCard")
    if not cards:
        return

    # Group consecutive cards
    groups = []
    current_group = [cards[0]]
    for card in cards[1:]:
        prev = current_group[-1]
        # Check if this card immediately follows the previous one
        between = prev.next_siblings
        is_consecutive = False
        for sib in between:
            if sib == card:
                is_consecutive = True
                break
            if isinstance(sib, NavigableString) and sib.strip() == "":
                continue
            break
        if is_consecutive:
            current_group.append(card)
        else:
            groups.append(current_group)
            current_group = [card]
    groups.append(current_group)

    for group in groups:
        grid = soup.new_tag("div", attrs={"class": "gfpQuickGrid"})
        group[0].insert_before(grid)
        for card in group:
            grid.append(card.extract())


def _wrap_tables(soup: BeautifulSoup) -> None:
    """Wrap bare <table> elements in gfpTableScroll + add gfpTable class."""
    for table in soup.find_all("table"):
        parent = table.parent
        if parent and hasattr(parent, "get") and "gfpTableScroll" in (parent.get("class") or []):
            continue
        existing = table.get("class", [])
        if isinstance(existing, str):
            existing = existing.split()
        if "gfpTable" not in existing:
            table["class"] = existing + ["gfpTable"]
        wrapper = soup.new_tag("div", attrs={"class": "gfpTableScroll"})
        table.wrap(wrapper)


def _wrap_page(soup: BeautifulSoup) -> None:
    """Wrap entire content in <div class='gfpPage'>."""
    # Check if already wrapped
    if soup.find("div", class_="gfpPage"):
        return

    page_div = soup.new_tag("div", attrs={"class": "gfpPage"})
    children = list(soup.children)
    if children:
        children[0].insert_before(page_div)
    for child in children:
        page_div.append(child.extract())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def postprocess(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    _rename_classes(soup)
    _wrap_quick_cards(soup)
    _wrap_tables(soup)
    _wrap_page(soup)

    return str(soup)


def main():
    parser = argparse.ArgumentParser(
        description="Post-process RSS article into GFP gfp* class system"
    )
    parser.add_argument("--input", required=True, help="Input HTML file (pipeline output)")
    parser.add_argument("--output", required=True, help="Output HTML file (GFP class system)")

    args = parser.parse_args()

    with open(args.input) as f:
        html = f.read()

    result = postprocess(html)

    with open(args.output, "w") as f:
        f.write(result)

    print(f"Postprocessed: {args.output} ({len(result):,} bytes)")


if __name__ == "__main__":
    main()
