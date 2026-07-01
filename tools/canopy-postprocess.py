#!/usr/bin/env python3
"""Post-process RL-class article HTML into Canopy canonical structure.

Transforms generic rl- class articles into cnp- class articles matching
the canonical structure used by known-good Canopy posts (e.g. post 30).

CSS backing: cnp-pages.css (140KB, in canopy-interactive-pages plugin)
provides ALL component styling under .cnpPage scope. Verified:
  cnpPage (2449 rules), cnpCallout (136), cnpFaq (80), cnpHero (72),
  cnpTable (35), cnpQuickCard (16), cnpDisclosure (41), etc.

HARD RULES:
  - NEVER touch the hero header. Leave it byte-identical.
  - Only operates on post_content. Template-rendered components
    (author bio, related posts, TOC) are untouched.
  - Do NOT use canopy* classes (different stylesheet, breaks things).

Usage:
    python3 tools/canopy-postprocess.py \\
        --input <path> --output <path> --slug <page-slug>
"""

import argparse
import re
import sys
from bs4 import BeautifulSoup, NavigableString, Tag


# === CLASS MAPPING: rl- → cnp- (backed by cnp-pages.css) ===
CLASS_MAP = {
    "rl-eyebrow": "cnpEyebrow",
    "rl-cta-primary": "cnpNextLink",
    "rl-cta-pill": "cnpNextLink",
    "rl-quick-card": "cnpQuickCard",
    "rl-jump-nav": "__REMOVE__",
    "rl-callout": "cnpCallout",
    "rl-callout--file_guidance": "cnpCallout-blue",
    "rl-callout--deal_saver": "cnpCallout-green",
    "rl-callout--deadline_warning": "cnpCallout-red",
    "rl-callout--math_check": "cnpCallout-yellow",
    "rl-callout--strategy": "cnpCallout-blue",
    "rl-faq": "cnpFaq",
    "rl-resources": "cnpCallout cnpDisclosure",
    "rl-bluf": "cnpHeroLead",
    "rl-cta-mid": "cnpCallout cnpCallout-blue",
    "rl-atf-faqhead": "cnpAtfHead",
}

VALN_CTA_URL = "/compare-loan-offers/"
CANOPY_CTA_URL = "/get-a-quote/"
VALN_CTA_TEXT = "Get Your Rate \u2192"
CANOPY_CTA_TEXT = "Get Your Free Quote \u2192"


def _remap_classes(tag):
    """Replace rl- classes with cnp- equivalents on a single tag."""
    if not tag.get("class"):
        return False
    old_classes = list(tag["class"])
    new_classes = []
    changed = False
    remove_tag = False

    for cls in old_classes:
        if cls in CLASS_MAP:
            mapped = CLASS_MAP[cls]
            if mapped == "__REMOVE__":
                remove_tag = True
                break
            new_classes.extend(mapped.split())
            changed = True
        elif cls.startswith("rl-"):
            new_classes.append(cls.replace("rl-", "cnp", 1))
            changed = True
        else:
            new_classes.append(cls)

    if remove_tag:
        tag.decompose()
        return True
    if changed:
        tag["class"] = new_classes
    return changed


def _fix_valn_ctas(soup):
    """Replace VALN CTA URLs and text with Canopy equivalents."""
    for a in soup.find_all("a", href=True):
        if VALN_CTA_URL in a["href"]:
            a["href"] = CANOPY_CTA_URL
        text = a.get_text(strip=True)
        if text == VALN_CTA_TEXT:
            a.string = CANOPY_CTA_TEXT


def _wrap_quick_cards(soup):
    """Wrap adjacent cnpQuickCard elements in a cnpQuickGrid container."""
    cards = soup.find_all(class_="cnpQuickCard")
    if not cards:
        return

    groups = []
    current_group = [cards[0]]
    for card in cards[1:]:
        prev = card.previous_sibling
        while prev and isinstance(prev, NavigableString) and not prev.strip():
            prev = prev.previous_sibling
        if prev in current_group:
            current_group.append(card)
        else:
            groups.append(current_group)
            current_group = [card]
    groups.append(current_group)

    for group in groups:
        parent = group[0].parent
        if parent and isinstance(parent, Tag) and "cnpQuickGrid" in (parent.get("class") or []):
            continue
        grid = soup.new_tag("div", attrs={"class": "cnpQuickGrid"})
        group[0].insert_before(grid)
        for card in group:
            grid.append(card.extract())


def _style_tables(soup):
    """Wrap bare <table> elements in cnpTableScroll and add cnpTable class."""
    for table in soup.find_all("table"):
        if "cnpTable" in (table.get("class") or []):
            continue
        table["class"] = table.get("class", []) + ["cnpTable"]
        parent = table.parent
        if not (parent and isinstance(parent, Tag) and
                "cnpTableScroll" in (parent.get("class") or [])):
            scroll = soup.new_tag("div", attrs={"class": "cnpTableScroll"})
            table.wrap(scroll)


def _convert_article_to_div(soup):
    """Convert <article> tags (used by rl- for cards) to <div>."""
    for article in soup.find_all("article"):
        article.name = "div"


def _fix_atf_head(soup):
    """Wrap bare text in cnpAtfHead inside <h2> to match restyle v2 CSS."""
    for head in soup.find_all(class_="cnpAtfHead"):
        for child in list(head.children):
            if isinstance(child, NavigableString) and child.strip():
                h2 = soup.new_tag("h2")
                h2.string = child.strip()
                child.replace_with(h2)


def _add_page_wrapper(soup, slug):
    """Wrap all content in cnpPage + cnpWrap, matching post 30 structure."""
    if soup.find("section", class_="cnpPage"):
        return

    section = soup.new_tag("section", attrs={
        "id": slug,
        "class": f"cnpPage cnpPage-{slug}",
    })
    wrap = soup.new_tag("div", attrs={"class": "cnpWrap"})

    children = list(soup.children)
    for child in children:
        wrap.append(child.extract())
    section.append(wrap)
    soup.append(section)


def _ensure_hero_h1(soup, title: str):
    """Insert <h1> in rl-hero if missing. The pipeline assembler omits it;
    the rendered page needs exactly one H1 for SEO and byline placement."""
    if not title:
        return
    hero = soup.find("header", class_="rl-hero")
    if not hero:
        return
    if hero.find("h1"):
        return  # already has one
    h1 = soup.new_tag("h1")
    h1.string = title
    hero.append(h1)


def postprocess(html: str, slug: str, title: str = "") -> str:
    """Full postprocess: rl→cnp conversion. Hero is preserved except for H1 injection."""
    soup = BeautifulSoup(html, "html.parser")

    # 0. Inject H1 into hero if missing (before snapshot, so it's included)
    _ensure_hero_h1(soup, title)

    # 1. Snapshot the hero — we will restore it byte-identical
    header = soup.find("header")
    hero_original = str(header) if header else None

    # 2. Remove jump-nav
    for nav in soup.find_all("nav", class_="rl-jump-nav"):
        nav.decompose()

    # 3. Convert <article> → <div>
    _convert_article_to_div(soup)

    # 4. Remap rl- → cnp- on ALL tags EXCEPT the hero header
    header_after_remap = soup.find("header")
    for tag in soup.find_all(True):
        # Skip anything inside the header
        if header_after_remap and (tag == header_after_remap or
                                    header_after_remap in tag.parents):
            continue
        _remap_classes(tag)

    # 5. Restore the hero to its exact original HTML
    if hero_original and header_after_remap:
        restored = BeautifulSoup(hero_original, "html.parser").find("header")
        if restored:
            header_after_remap.replace_with(restored)

    # 6. Fix VALN CTAs (including any in the hero — URL fix is safe)
    _fix_valn_ctas(soup)

    # 6b. Fix ATF heading: wrap bare text in <h2>
    _fix_atf_head(soup)

    # 7. Wrap quick cards in grid
    _wrap_quick_cards(soup)

    # 8. Style tables
    _style_tables(soup)

    # 9. Add cnpPage + cnpWrap wrapper
    _add_page_wrapper(soup, slug)

    # 10. Add Divi wrapper
    result = str(soup)
    return (
        '[et_pb_section fb_built="1" _builder_version="4.27.6" '
        'global_colors_info="{}"][et_pb_row _builder_version="4.27.6"]'
        '[et_pb_column type="4_4" _builder_version="4.27.6"]'
        '[et_pb_code _builder_version="4.27.6"]'
        + result
        + "[/et_pb_code][/et_pb_column][/et_pb_row][/et_pb_section]"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Post-process RL-class HTML into Canopy canonical structure"
    )
    parser.add_argument("--input", required=True, help="Input HTML file")
    parser.add_argument("--output", required=True, help="Output HTML file")
    parser.add_argument("--slug", required=True, help="Page slug")
    parser.add_argument("--title", default="", help="Post title (for H1 injection)")
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        html = f.read()

    m = re.search(r"\[et_pb_code[^\]]*\](.*?)\[/et_pb_code\]", html, re.DOTALL)
    if m:
        html = m.group(1)

    result = postprocess(html, args.slug, title=args.title)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(result)

    print(f"Postprocessed: {args.slug}")


if __name__ == "__main__":
    main()
