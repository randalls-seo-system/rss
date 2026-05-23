#!/usr/bin/env python3
"""Post-process RSS v2 article output into canonical VALN structure.

Transforms pipeline rl-* HTML into VALN's vln* class system with Divi
shortcode wrapping. VALN predates the RSS system and uses a legacy
per-site CSS class set (vln*, vlnCallout, vlnTable, bullet-section-*).

Class mapping:
    rl-hero             → vlnCard vlnHero (+ vlnCard-inner wrapper)
    rl-eyebrow          → vlnEyebrow
    rl-quick-card       → vlnQuickCard (wrapped in vlnQuickGrid)
    rl-jump-nav         → vlnPills (links get vlnPill class)
    rl-callout          → vlnCallout
    rl-callout--deal_math     → vlnCallout vlnProTip
    rl-callout--file_guidance → vlnCallout vlnCallout-yellow
    rl-callout--approval_watchpoint → vlnCallout vlnCallout-yellow
    rl-faq              → vlnFaq
    rl-resources        → vlnCallout vlnDisclosure
    rl-bluf             → (class removed, stays as plain section)
    rl-cta-primary      → vlnNextPill + vlnNextLabel + vlnNextLink
    rl-cta-pill         → vlnNextPill + vlnNextLabel + vlnNextLink
    <table>             → vlnTableScroll wrapper + vlnTable class
    <ul> in body        → bullet-section-blue / bullet-section-gray (alternating)

Divi wrapping: two-row section with module_class="vlnPage custom-table".

Usage:
    python3 tools/valn-postprocess.py \\
        --input <path> \\
        --output <path> \\
        --slug <page-slug> \\
        --title-id <h1-id> \\
        --category-slug <slug> \\
        --category-name <name> \\
        --breadcrumb-leaf <short-title>
"""

import argparse
import re
import sys
from bs4 import BeautifulSoup, NavigableString, Tag


# ---------------------------------------------------------------------------
# A. Class renames
# ---------------------------------------------------------------------------

_CLASS_RENAMES = {
    "rl-hero": "vlnCard vlnHero",
    "rl-eyebrow": "vlnEyebrow",
    "rl-quick-card": "vlnQuickCard",
    "rl-jump-nav": "vlnPills",
    "rl-faq": "vlnFaq",
    "rl-cta-mid": "",  # wrapper div, class removed
}

_CALLOUT_VARIANT_MAP = {
    "rl-callout--deal_math": "vlnProTip",
    "rl-callout--file_guidance": "vlnCallout-yellow",
    "rl-callout--approval_watchpoint": "vlnCallout-yellow",
    "rl-callout--cost_surprise": "vlnProTip",
    "rl-callout--operator_note": "vlnCallout-yellow",
    "rl-callout--common_mistake": "vlnCallout-yellow",
    "rl-callout--common_confusion": "vlnCallout-yellow",
    "rl-callout--clear_definition": "vlnProTip",
    "rl-callout--disqualifier": "vlnCallout-yellow",
    "rl-callout--key_insight": "vlnProTip",
    "rl-callout--when_each_wins": "vlnProTip",
}


def _rename_classes(soup: BeautifulSoup) -> None:
    """Rename all rl-* classes to vln* equivalents."""
    for el in soup.find_all(True):
        classes = el.get("class", [])
        if not classes:
            continue
        if isinstance(classes, str):
            classes = classes.split()

        new_classes = []
        for cls in classes:
            if cls in _CLASS_RENAMES:
                replacement = _CLASS_RENAMES[cls]
                if replacement:
                    new_classes.extend(replacement.split())
            elif cls == "rl-callout":
                new_classes.append("vlnCallout")
            elif cls in _CALLOUT_VARIANT_MAP:
                new_classes.append(_CALLOUT_VARIANT_MAP[cls])
            elif cls == "rl-resources":
                new_classes.extend(["vlnCallout", "vlnDisclosure"])
            elif cls == "rl-bluf":
                pass  # Remove rl-bluf, keep as plain section
            elif cls == "rl-cta-primary":
                new_classes.append("vlnNextLink")
            elif cls == "rl-cta-pill":
                new_classes.append("vlnNextLink")
            elif cls == "rl-cluster-box":
                new_classes.append("cluster-box")
            else:
                new_classes.append(cls)

        if new_classes:
            el["class"] = new_classes
        elif "class" in el.attrs:
            del el["class"]


# ---------------------------------------------------------------------------
# C. Header restructure
# ---------------------------------------------------------------------------

def _restructure_header(soup: BeautifulSoup, slug: str, title_id: str,
                        category_slug: str, category_name: str,
                        breadcrumb_leaf: str) -> None:
    """Restructure the hero header into VALN's vlnCard-inner pattern."""
    header = soup.find("header", class_="vlnHero")
    if not header:
        print("WARNING: No <header class='vlnHero'> found after rename", file=sys.stderr)
        return

    # Wrap header children in vlnCard-inner
    card_inner = soup.new_tag("div", attrs={"class": "vlnCard-inner"})
    children = list(header.children)
    for child in children:
        card_inner.append(child.extract())
    header.append(card_inner)

    # Insert skip link
    skip = soup.new_tag("a", attrs={"class": "vlnSkip", "href": "#vln-faqs"})
    skip.string = "Skip to FAQs"
    card_inner.insert(0, skip)

    # Insert breadcrumb
    breadcrumb_nav = soup.new_tag("nav", attrs={
        "aria-label": "Breadcrumb",
        "class": "vlnBreadcrumb",
    })
    home_link = soup.new_tag("a", href="https://valoannetwork.com/")
    home_link.string = "Home"
    breadcrumb_nav.append(home_link)

    sep1 = soup.new_tag("span", attrs={"aria-hidden": "true", "class": "sep"})
    sep1.string = " → "
    breadcrumb_nav.append(sep1)

    cat_link = soup.new_tag("a", href=f"https://valoannetwork.com/{category_slug}/")
    cat_link.string = category_name
    breadcrumb_nav.append(cat_link)

    sep2 = soup.new_tag("span", attrs={"aria-hidden": "true", "class": "sep"})
    sep2.string = " → "
    breadcrumb_nav.append(sep2)

    leaf = soup.new_tag("span", attrs={"aria-current": "page"})
    leaf.string = breadcrumb_leaf
    breadcrumb_nav.append(leaf)

    card_inner.insert(1, breadcrumb_nav)

    # Restructure eyebrow
    eyebrow = card_inner.find("div", class_="vlnEyebrow")
    if eyebrow:
        raw = eyebrow.get_text(strip=True)
        parts = [p.strip() for p in raw.split("·")]
        eyebrow.clear()
        eyebrow["aria-label"] = raw
        if len(parts) >= 1:
            eyebrow.append(NavigableString(parts[0]))
        if len(parts) >= 2:
            sep_eye = soup.new_tag("span", attrs={"aria-hidden": "true", "class": "sep"})
            sep_eye.string = " · "
            eyebrow.append(sep_eye)
            strong = soup.new_tag("strong")
            strong.string = parts[1]
            eyebrow.append(strong)

    # Add id to H1
    h1 = card_inner.find("h1")
    if h1:
        h1["id"] = title_id
        header["aria-labelledby"] = title_id

    # Build vlnMeta from Resources section
    resources = soup.find(class_="vlnDisclosure")
    meta_div = soup.new_tag("div", attrs={
        "aria-label": "Primary sources",
        "class": "vlnMeta",
    })
    strong_label = soup.new_tag("strong")
    strong_label.string = "Primary sources:"
    meta_div.append(strong_label)

    if resources:
        source_links = resources.find_all("a", limit=3)
        for i, link in enumerate(source_links):
            href = link.get("href", "")
            text = link.get_text(strip=True)
            short = text.split("—")[0].split(" — ")[0].strip()
            if not short:
                short = text[:30]

            new_link = soup.new_tag("a", attrs={
                "href": href,
                "rel": "noopener noreferrer",
                "target": "_blank",
            })
            new_link.string = short
            meta_div.append(NavigableString(" "))
            meta_div.append(new_link)
            if i < len(source_links) - 1:
                sep_src = soup.new_tag("span", attrs={
                    "aria-hidden": "true",
                    "class": "sep",
                })
                sep_src.string = " · "
                meta_div.append(sep_src)

    if h1:
        h1.insert_after(meta_div)

    # Move pills nav inside header, add vlnPill class to links
    pills_nav = soup.find("nav", class_="vlnPills")
    if pills_nav:
        pills_nav.extract()
        pills_nav["aria-label"] = "Jump to section"
        meta_div.insert_after(pills_nav)
        for a in pills_nav.find_all("a"):
            existing = a.get("class", [])
            if isinstance(existing, str):
                existing = existing.split()
            if "vlnPill" not in existing:
                a["class"] = existing + ["vlnPill"]

    # Move ATF lede inside header with vlnHeroLead class
    lede_p = None
    for sibling in header.next_siblings:
        if isinstance(sibling, NavigableString) and sibling.strip() == "":
            continue
        if hasattr(sibling, "name") and sibling.name == "p":
            lede_p = sibling
            break
        else:
            break

    if lede_p:
        lede_p["class"] = "vlnHeroLead"
        lede_p.extract()
        if pills_nav:
            pills_nav.insert_after(lede_p)
        else:
            meta_div.insert_after(lede_p)

    # Convert CTA to vlnNextPill structure
    for cta_link in card_inner.find_all("a", class_="vlnNextLink"):
        cta_text = cta_link.get_text(strip=True).replace(" →", "")
        cta_href = cta_link.get("href", "/compare-loan-offers/")

        pill_span = soup.new_tag("span", attrs={"class": "vlnNextPill"})
        label_span = soup.new_tag("span", attrs={"class": "vlnNextLabel"})
        label_span.string = "Next step:"
        new_link = soup.new_tag("a", attrs={
            "class": "vlnNextLink",
            "href": cta_href,
        })
        new_link.string = "Check Your VA Loan Eligibility"
        pill_span.append(label_span)
        pill_span.append(new_link)
        cta_link.replace_with(pill_span)

    # Note: no additional CTA insertion here. The pipeline emits an rl-cta-primary
    # which was already renamed to vlnNextLink and converted to vlnNextPill structure
    # in the loop above. Inserting a second CTA would duplicate it.


# ---------------------------------------------------------------------------
# D-I. Body transformations
# ---------------------------------------------------------------------------

def _wrap_atf_cards(soup: BeautifulSoup, breadcrumb_leaf: str) -> None:
    """Wrap vlnQuickCard elements in vlnQuickGrid section."""
    header = soup.find("header", class_="vlnHero")
    if not header:
        return

    cards = []
    for sibling in list(header.next_siblings):
        if isinstance(sibling, NavigableString) and sibling.strip() == "":
            continue
        if hasattr(sibling, "get") and sibling.name == "article":
            cls = sibling.get("class", [])
            if isinstance(cls, str):
                cls = cls.split()
            if "vlnQuickCard" in cls:
                cards.append(sibling)
            else:
                break
        elif len(cards) > 0:
            break

    if cards:
        grid = soup.new_tag("section", attrs={
            "aria-label": f"{breadcrumb_leaf} overview",
            "class": "vlnQuickGrid",
        })
        cards[0].insert_before(grid)
        for card in cards:
            grid.append(card.extract())


def _wrap_tables(soup: BeautifulSoup) -> None:
    """Wrap bare <table> elements in vlnTableScroll + add vlnTable class."""
    for table in soup.find_all("table"):
        # Skip if already wrapped
        parent = table.parent
        if parent and parent.get("class") and "vlnTableScroll" in parent.get("class", []):
            continue
        table["class"] = table.get("class", []) + ["vlnTable"] if table.get("class") else ["vlnTable"]
        wrapper = soup.new_tag("div", attrs={"class": "vlnTableScroll"})
        table.wrap(wrapper)


def _alternate_bullet_sections(soup: BeautifulSoup) -> None:
    """Alternate <ul> in body between bullet-section-blue and bullet-section-gray."""
    # Find body content (after ATF section)
    # Body starts after the ATF FAQs (the <details> elements after vlnQuickGrid)
    grid = soup.find("section", class_="vlnQuickGrid")
    if not grid:
        return

    # Find all <ul> elements after the grid
    body_uls = []
    in_body = False
    for el in soup.find_all(True):
        if el == grid:
            in_body = True
            continue
        if not in_body:
            continue
        if el.name == "ul":
            # Skip <ul> inside vlnFaq, vlnDisclosure, vlnQuickCard, vlnQuickGrid
            parent_classes = []
            p = el.parent
            while p:
                parent_classes.extend(p.get("class", []) if hasattr(p, "get") else [])
                p = p.parent if hasattr(p, "parent") else None
            skip_parents = {"vlnFaq", "vlnDisclosure", "vlnQuickCard", "vlnQuickGrid", "vlnCallout", "vlnProTip", "vlnCallout-yellow"}
            if skip_parents & set(parent_classes):
                continue
            body_uls.append(el)

    colors = ["bullet-section-blue", "bullet-section-gray"]
    for i, ul in enumerate(body_uls):
        color = colors[i % 2]
        wrapper = soup.new_tag("div", attrs={"class": color})
        ul.wrap(wrapper)


def _wrap_faq_answers(soup: BeautifulSoup) -> None:
    """Wrap FAQ answer paragraphs in <div class='ans'>."""
    for details in soup.find_all("details"):
        for child in list(details.children):
            if hasattr(child, "name") and child.name in ("p", "div") and child.name != "summary":
                cls = child.get("class", [])
                if isinstance(cls, str):
                    cls = cls.split()
                if "ans" not in cls:
                    ans_div = soup.new_tag("div", attrs={"class": "ans"})
                    child.wrap(ans_div)


def _convert_mid_ctas(soup: BeautifulSoup) -> None:
    """Convert mid-article CTA pills to vlnNextPill structure."""
    for cta_div in soup.find_all("div", class_="rl-cta-mid"):
        cta_link = cta_div.find("a")
        if not cta_link:
            continue
        cta_href = cta_link.get("href", "/compare-loan-offers/")

        pill = soup.new_tag("div", attrs={"class": "vlnNextPill"})
        label = soup.new_tag("span", attrs={"class": "vlnNextLabel"})
        label.string = "Next step:"
        link = soup.new_tag("a", attrs={
            "class": "vlnNextLink",
            "href": cta_href,
        })
        link.string = "Check Your VA Loan Eligibility"
        pill.append(label)
        pill.append(link)
        cta_div.replace_with(pill)


def _add_faq_id(soup: BeautifulSoup) -> None:
    """Add id='vln-faqs' to the BTF FAQ section for skip link."""
    btf_faq_h2 = None
    for h2 in soup.find_all("h2"):
        if "frequently asked questions" in h2.get_text(strip=True).lower():
            btf_faq_h2 = h2
    if btf_faq_h2:
        parent_section = btf_faq_h2.find_parent("section")
        if parent_section:
            parent_section["id"] = "vln-faqs"
        else:
            btf_faq_h2["id"] = "vln-faqs"


# ---------------------------------------------------------------------------
# H-I. Outer wrapping
# ---------------------------------------------------------------------------

def _wrap_body_content(soup: BeautifulSoup) -> Tag:
    """Wrap post-ATF content in <div class='vlnPage main-content'>."""
    # Find the boundary: ATF FAQs (last <details> before rl-bluf/first body <section>)
    grid = soup.find("section", class_="vlnQuickGrid")
    if not grid:
        return soup

    # Find ATF FAQs (details elements between grid and first body section)
    atf_faq_details = []
    body_elements = []
    found_body = False

    for sibling in list(grid.next_siblings):
        if isinstance(sibling, NavigableString) and sibling.strip() == "":
            continue
        if not hasattr(sibling, "name"):
            continue

        if not found_body:
            if sibling.name == "details":
                atf_faq_details.append(sibling)
            elif sibling.name == "aside":
                # Hub box — keep in ATF
                atf_faq_details.append(sibling)
            else:
                found_body = True
                body_elements.append(sibling)
        else:
            body_elements.append(sibling)

    if body_elements:
        body_div = soup.new_tag("div", attrs={"class": "vlnPage main-content"})
        body_elements[0].insert_before(body_div)
        for el in body_elements:
            body_div.append(el.extract())

    return soup


def _build_outer_wrap(soup: BeautifulSoup, slug: str, title_id: str) -> str:
    """Build the outer vlnPage + vlnWrap + Divi wrapping."""
    # Find ATF content (header + grid + ATF FAQs) vs body content (main-content div)
    header = soup.find("header", class_="vlnHero")
    grid = soup.find("section", class_="vlnQuickGrid")
    body_div = soup.find("div", class_="main-content")

    # Build ATF section
    atf_parts = []
    if header:
        atf_parts.append(str(header))

    if grid:
        atf_parts.append(str(grid))

    # ATF FAQs (details elements between grid and body_div)
    if grid:
        for sibling in list(grid.next_siblings):
            if isinstance(sibling, NavigableString) and sibling.strip() == "":
                continue
            if sibling == body_div:
                break
            if hasattr(sibling, "name"):
                atf_parts.append(str(sibling))

    atf_html = "\n".join(atf_parts)
    body_html = str(body_div) if body_div else ""

    # Build outer section
    section_id = f"vln{slug.replace('-', ' ').title().replace(' ', '')}"
    atf_section = (
        f'<section id="{section_id}" class="vlnPage vlnPage-{slug}" data-vln-page="{slug}">\n'
        f'  <a class="vlnSkip" href="#vln-faqs">Skip to FAQs</a>\n'
        f'  <div class="vlnWrap">\n'
        f'{atf_html}\n'
        f'  </div>\n'
        f'</section>'
    )

    # Divi wrapping
    divi_attrs = (
        'fb_built="1" module_class="vlnPage custom-table" '
        '_builder_version="4.27.6" _module_preset="default" '
        'custom_padding="0px|4px|0px|4px|true|true" global_colors_info="{}"'
    )
    row_attrs = '_builder_version="4.27.6" _module_preset="default" global_colors_info="{}"'
    col_attrs = 'type="4_4" _builder_version="4.27.6" _module_preset="default" global_colors_info="{}"'
    text_attrs = '_builder_version="4.27.6" _module_preset="default" global_colors_info="{}"'

    result = (
        f'[et_pb_section {divi_attrs}]'
        f'[et_pb_row {row_attrs}]'
        f'[et_pb_column {col_attrs}]'
        f'[et_pb_text {text_attrs}]'
        f'{atf_section}'
        f'[/et_pb_text][/et_pb_column][/et_pb_row]'
        f'[et_pb_row {row_attrs}]'
        f'[et_pb_column {col_attrs}]'
        f'[et_pb_text {text_attrs}]'
        f'{body_html}'
        f'[/et_pb_text][/et_pb_column][/et_pb_row]'
        f'[/et_pb_section]'
    )

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def postprocess(html: str, slug: str, title_id: str,
                category_slug: str, category_name: str,
                breadcrumb_leaf: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # A-B. Class renames + callout variant mapping
    _rename_classes(soup)

    # Convert mid-article CTAs before header restructure
    _convert_mid_ctas(soup)

    # C. Header restructure
    _restructure_header(soup, slug, title_id, category_slug, category_name, breadcrumb_leaf)

    # D. Wrap ATF cards in vlnQuickGrid
    _wrap_atf_cards(soup, breadcrumb_leaf)

    # E. Wrap tables
    _wrap_tables(soup)

    # G. Wrap FAQ answers
    _wrap_faq_answers(soup)

    # Add FAQ id for skip link
    _add_faq_id(soup)

    # H. Wrap body content
    _wrap_body_content(soup)

    # F. Alternate bullet sections (after body wrap so we know what's in body)
    _alternate_bullet_sections(soup)

    # I-J. Outer + Divi wrapping
    return _build_outer_wrap(soup, slug, title_id)


def main():
    parser = argparse.ArgumentParser(
        description="Post-process RSS article into canonical VALN structure + Divi wrapping"
    )
    parser.add_argument("--input", required=True, help="Input HTML file (pipeline output)")
    parser.add_argument("--output", required=True, help="Output HTML file (VALN + Divi wrapped)")
    parser.add_argument("--slug", required=True, help="Page slug")
    parser.add_argument("--title-id", required=True, help="H1 id attribute")
    parser.add_argument("--category-slug", required=True, help="Breadcrumb category slug (e.g., va-loans)")
    parser.add_argument("--category-name", required=True, help="Breadcrumb category label (e.g., VA Loans)")
    parser.add_argument("--breadcrumb-leaf", required=True, help="Breadcrumb leaf text (article title)")

    args = parser.parse_args()

    with open(args.input) as f:
        html = f.read()

    result = postprocess(
        html,
        slug=args.slug,
        title_id=args.title_id,
        category_slug=args.category_slug,
        category_name=args.category_name,
        breadcrumb_leaf=args.breadcrumb_leaf,
    )

    with open(args.output, "w") as f:
        f.write(result)

    print(f"Postprocessed: {args.output} ({len(result):,} bytes)")


if __name__ == "__main__":
    main()
