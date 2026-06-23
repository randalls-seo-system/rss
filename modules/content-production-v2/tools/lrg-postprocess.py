#!/usr/bin/env python3
"""LRG Postprocessor — maps pipeline output HTML to the rl-page CSS framework.

The pipeline (assemble-article.py) outputs a generic HTML class vocabulary.
The LRG site's CSS injector (lrg-article-styles.php) scopes ALL styling
under `.rl-page`. This script bridges the gap:

  1. Wraps content in <div class="rl-page rl-page-lrg"><div class="rl-wrap">
  2. Wraps consecutive quick-cards in <div class="rl-quick-grid">
  3. Adds class="rl-table" to bare <table> elements
  4. Wraps body <section> lists in alternating bullet-section-* colors
  5. Adds class="rl-section" to bare body <section> elements

Usage:
    python3 lrg-postprocess.py --html-file /path/to/article.html [--in-place]
    python3 lrg-postprocess.py --post-id 7442 --site lrg  (reads from WP, writes back)
"""

import argparse
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString

BULLET_COLORS = ["bullet-section-green", "bullet-section-blue",
                 "bullet-section-gray", "bullet-section-green",
                 "bullet-section-blue", "bullet-section-gray"]

# Sections that are NOT body content (skip bullet-color wrapping)
SKIP_SECTIONS = {"rl-bluf", "rl-faq", "rl-resources", "rl-section"}


def postprocess(html: str) -> str:
    """Apply all LRG postprocessing transforms to pipeline HTML."""
    soup = BeautifulSoup(html, "html.parser")

    # ── 1. Wrap consecutive <article class="rl-quick-card"> in rl-quick-grid ──
    cards = soup.find_all("article", class_="rl-quick-card")
    if cards:
        # Find the first card and group consecutive siblings
        first_card = cards[0]
        card_group = [first_card]
        node = first_card.next_sibling
        while node:
            if isinstance(node, NavigableString) and not node.strip():
                node = node.next_sibling
                continue
            if hasattr(node, "get") and node.get("class") and "rl-quick-card" in node.get("class", []):
                card_group.append(node)
                node = node.next_sibling
                continue
            break

        if len(card_group) > 1:
            grid_div = soup.new_tag("div", **{"class": "rl-quick-grid"})
            first_card.insert_before(grid_div)
            for card in card_group:
                card.extract()
                grid_div.append(card)

    # ── 2. Add rl-table to bare <table> elements ──
    for table in soup.find_all("table"):
        existing = table.get("class", [])
        if "rl-table" not in existing:
            table["class"] = existing + ["rl-table"]

    # ── 3. Add bullet-section colors to body <section> UL content ──
    color_idx = 0
    for section in soup.find_all("section"):
        classes = section.get("class", [])
        # Skip non-body sections (BLUF, FAQ, resources, already-classed)
        if any(c in SKIP_SECTIONS for c in classes):
            continue
        if classes:
            continue  # already has a class, don't override

        # This is a bare body <section>. Add rl-section class.
        section["class"] = ["rl-section"]

        # If section contains a <ul>, wrap the UL in a bullet-section div
        ul = section.find("ul")
        if ul:
            color_class = BULLET_COLORS[color_idx % len(BULLET_COLORS)]
            color_idx += 1
            wrapper = soup.new_tag("div", **{"class": color_class})
            ul.wrap(wrapper)

    # ── 4. Wrap BLUF section UL in bullet-section-gray ──
    bluf = soup.find("section", class_="rl-bluf")
    if bluf:
        bluf_ul = bluf.find("ul")
        if bluf_ul and not bluf_ul.parent.get("class"):
            wrapper = soup.new_tag("div", **{"class": "bullet-section-gray"})
            bluf_ul.wrap(wrapper)

    # ── 5. Outer rl-page wrapper ──
    # SKIP for nh-* neighborhood guides — they use their own CSS vocabulary
    # and the rl-page wrapper conflicts with nh-* styles. Stone Oak (gold
    # standard) renders with nh-hero as the top-level element, no rl-page.
    inner_html = str(soup)

    if 'nh-hero' in inner_html:
        # Neighborhood guide — return as-is, no rl-page wrapper
        return inner_html

    wrapped = (
        '<div class="rl-page rl-page-lrg">\n'
        '<div class="rl-wrap">\n'
        f'{inner_html}\n'
        '</div>\n'
        '</div>'
    )

    return wrapped


def main():
    parser = argparse.ArgumentParser(description="LRG Postprocessor")
    parser.add_argument("--html-file", help="Local HTML file to process")
    parser.add_argument("--in-place", action="store_true", help="Overwrite the file")
    parser.add_argument("--post-id", type=int, help="WordPress post ID (reads/writes via SSH)")
    parser.add_argument("--site", default="lrg", help="Site slug")
    args = parser.parse_args()

    if args.html_file:
        path = Path(args.html_file)
        html = path.read_text()
        result = postprocess(html)
        if args.in_place:
            path.write_text(result)
            print(f"OK: {path} ({len(html)} -> {len(result)} bytes)")
        else:
            print(result)
    elif args.post_id:
        print(f"Use --html-file for local processing. For WP batch, use the PHP deploy script.", file=sys.stderr)
        sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
