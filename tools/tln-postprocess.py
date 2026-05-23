#!/usr/bin/env python3
"""Post-process RSS v2 article output into canonical TLN structure.

Transforms class-migrated article HTML to match the TLN canonical pattern
(post 1417 reference) by adding structural wrappers, breadcrumb, skip link,
primary sources in header, and restructuring the eyebrow/pills/lede.

Usage:
    python3 tools/tln-postprocess.py \\
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
from bs4 import BeautifulSoup, NavigableString


def postprocess(html: str, slug: str, title_id: str,
                category_slug: str, category_name: str,
                breadcrumb_leaf: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    # --- 1. Find the header ---
    header = soup.find("header", class_="tlnCard")
    if not header:
        print("ERROR: No <header class='tlnCard ...'> found", file=sys.stderr)
        sys.exit(1)

    # --- 2. Build tlnCard-inner wrapper for header children ---
    card_inner = soup.new_tag("div", attrs={"class": "tlnCard-inner"})
    children = list(header.children)
    for child in children:
        card_inner.append(child.extract())
    header.append(card_inner)

    # --- 3. Add skip link as first child of tlnCard-inner ---
    skip = soup.new_tag("a", attrs={"class": "tlnSkip", "href": "#tln-faqs"})
    skip.string = "Skip to FAQs"
    card_inner.insert(0, skip)

    # --- 4. Add breadcrumb as second child ---
    breadcrumb_nav = soup.new_tag("nav", attrs={
        "aria-label": "Breadcrumb",
        "class": "tlnBreadcrumb",
    })
    home_link = soup.new_tag("a", href="/")
    home_link.string = "Home"
    breadcrumb_nav.append(home_link)

    sep1 = soup.new_tag("span", attrs={"aria-hidden": "true", "class": "sep"})
    sep1.string = "→"
    breadcrumb_nav.append(sep1)

    cat_link = soup.new_tag("a", href=f"/category/{category_slug}/")
    cat_link.string = category_name
    breadcrumb_nav.append(cat_link)

    sep2 = soup.new_tag("span", attrs={"aria-hidden": "true", "class": "sep"})
    sep2.string = "→"
    breadcrumb_nav.append(sep2)

    leaf = soup.new_tag("span", attrs={"aria-current": "page"})
    leaf.string = breadcrumb_leaf
    breadcrumb_nav.append(leaf)

    card_inner.insert(1, breadcrumb_nav)

    # --- 5. Restructure eyebrow ---
    eyebrow = card_inner.find("div", class_="tlnEyebrow")
    if eyebrow:
        raw = eyebrow.get_text(strip=True)
        parts = [p.strip() for p in raw.split("·")]
        eyebrow.clear()
        if len(parts) >= 1:
            span_topic = soup.new_tag("span")
            span_topic.string = parts[0].upper()
            eyebrow.append(span_topic)
        if len(parts) >= 2:
            sep_eye = soup.new_tag("span", attrs={"aria-hidden": "true", "class": "sep"})
            sep_eye.string = " · "
            eyebrow.append(sep_eye)
            strong = soup.new_tag("strong")
            strong.string = parts[1]
            eyebrow.append(strong)

    # --- 6. Add id to H1 ---
    h1 = card_inner.find("h1")
    if h1:
        h1["id"] = title_id
        header["aria-labelledby"] = title_id

    # --- 7. Inject tlnMeta (primary sources from resources footer) ---
    resources = soup.find("footer", class_=re.compile(r"tlnCallout|tlnDisclosure"))
    if not resources:
        resources = soup.find(class_="tlnDisclosure")

    meta_div = soup.new_tag("div", attrs={
        "aria-label": "Primary sources",
        "class": "tlnMeta",
    })
    strong_label = soup.new_tag("strong")
    strong_label.string = "Primary sources:"
    meta_div.append(strong_label)

    if resources:
        source_links = resources.find_all("a", limit=3)
        for i, link in enumerate(source_links):
            # Shorten anchor text for header: use domain name only
            href = link.get("href", "")
            text = link.get_text(strip=True)
            # Extract short source name (before the em-dash or colon)
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

    # Insert tlnMeta after H1
    if h1:
        h1.insert_after(meta_div)

    # --- 8. Move tlnPills nav inside header (after tlnMeta) ---
    pills_nav = soup.find("nav", class_="tlnPills")
    if pills_nav:
        pills_nav.extract()
        meta_div.insert_after(pills_nav)

    # --- 9. Add class="tlnPill" to each <a> inside pills nav ---
    if pills_nav:
        for a in pills_nav.find_all("a"):
            existing = a.get("class", [])
            if "tlnPill" not in existing:
                a["class"] = (existing if isinstance(existing, list) else [existing]) + ["tlnPill"]

    # --- 10. Add class="tlnHeroLead" to the lede paragraph ---
    # The lede is the <p> that comes right after where pills_nav was,
    # now it's right after the header (since pills moved inside).
    # Find the first <p> that's a direct child after the header.
    lede_p = None
    for sibling in header.next_siblings:
        if isinstance(sibling, NavigableString) and sibling.strip() == "":
            continue
        if sibling.name == "p":
            lede_p = sibling
            break
        else:
            break

    if lede_p:
        lede_p["class"] = "tlnHeroLead"
        # Move lede inside header (after pills_nav)
        lede_p.extract()
        if pills_nav:
            pills_nav.insert_after(lede_p)
        else:
            meta_div.insert_after(lede_p)

    # Move the CTA pill that's currently inside the header to after lede
    # (it should be: pills → lede → CTA, all inside header)
    cta_in_header = card_inner.find("span", class_="tlnNextPill")
    if cta_in_header and lede_p:
        cta_in_header.extract()
        lede_p.insert_after(cta_in_header)

    # --- 11. Wrap the 4 ATF cards in tlnQuickGrid ---
    cards = []
    # Cards are <article class="tlnQuickCard"> after the header
    for sibling in list(header.next_siblings):
        if isinstance(sibling, NavigableString) and sibling.strip() == "":
            continue
        if hasattr(sibling, "get") and sibling.name == "article":
            cls = sibling.get("class", [])
            if "tlnQuickCard" in cls:
                cards.append(sibling)
            else:
                break
        elif len(cards) > 0:
            break

    if cards:
        grid = soup.new_tag("section", attrs={
            "aria-label": f"{breadcrumb_leaf} overview",
            "class": "tlnQuickGrid",
        })
        # Insert grid where the first card was
        cards[0].insert_before(grid)
        for card in cards:
            grid.append(card.extract())

    # --- 12. Add FAQs id anchor for skip link ---
    btf_faq_h2 = None
    for h2 in soup.find_all("h2"):
        if "frequently asked questions" in h2.get_text(strip=True).lower():
            # Use the LAST one (BTF, not ATF)
            btf_faq_h2 = h2
    if btf_faq_h2:
        parent_section = btf_faq_h2.find_parent("section")
        if parent_section:
            parent_section["id"] = "tln-faqs"
        else:
            btf_faq_h2["id"] = "tln-faqs"

    # --- 13. Wrap everything in tlnPage + tlnWrap ---
    page_section = soup.new_tag("section", attrs={
        "class": f"tlnPage tlnPage-{slug}",
        "data-tln-page": slug,
    })
    wrap_div = soup.new_tag("div", attrs={"class": "tlnWrap"})

    # Move all top-level children into the wrap
    top_children = list(soup.children)
    for child in top_children:
        wrap_div.append(child.extract())
    page_section.append(wrap_div)
    soup.append(page_section)

    return str(soup)


def main():
    parser = argparse.ArgumentParser(
        description="Post-process RSS article into canonical TLN structure"
    )
    parser.add_argument("--input", required=True, help="Input HTML file")
    parser.add_argument("--output", required=True, help="Output HTML file")
    parser.add_argument("--slug", required=True, help="Page slug")
    parser.add_argument("--title-id", required=True, help="H1 id attribute")
    parser.add_argument("--category-slug", required=True, help="Breadcrumb category slug")
    parser.add_argument("--category-name", required=True, help="Breadcrumb category display name")
    parser.add_argument("--breadcrumb-leaf", required=True, help="Breadcrumb leaf text")

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
