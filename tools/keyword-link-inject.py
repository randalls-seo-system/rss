#!/usr/bin/env python3
"""Post-generation keyword-scan link injector.

Scans article body text for primary keywords from the anchor pool and
injects internal links at first-mention positions. Unlike the v2
inject-internal-links.py (which requires verbatim anchor pool phrase
matches), this tool matches on short primary keywords that naturally
appear in body text.

Rules enforced:
- First mention only per destination URL
- One internal link per paragraph max
- No links in restricted zones (headings, callouts, tables, FAQs, bullet-sections)
- Link density capped by word count band (spec 11.4)
- Self-link prevention (--exclude-slug)
- Skip utility/legal pages

Usage:
    python3 tools/keyword-link-inject.py \\
        --site tln \\
        --input article.html \\
        --output article-linked.html \\
        [--exclude-slug current-page-slug] \\
        [--max-links 12] \\
        [--dry-run]
"""

import argparse
import json
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString, Tag

REPO_ROOT = Path(__file__).resolve().parent.parent

# Pages that should never be link targets
SKIP_SLUGS = {
    "home", "privacy-policy", "apply-now", "about-us", "blog",
    "contact-us", "confirmation", "contributor", "realtor-referral-program",
    "high-quality-mortgage-leads", "compare-loan-offers", "scholarship",
    "terms-of-use", "cookie-policy", "do-not-call-policy",
    "contact-preferences", "security-policy", "fair-lending",
    "advertising-disclosures", "copyright-ip-policy",
    "accessibility-statement", "licensing-regulatory-info",
    "service-disclaimer", "ownership-funding", "diversity-inclusion-policy",
    "editorial-team", "publishing-principles", "editorial-ethics-policy",
    "feedback-policy", "about-tln-editorial-team", "is-the-lenders-network-a-lender",
    "partner-transparency", "legal", "loan-comparison-network",
}

# CSS classes that define restricted zones (no links inside)
RESTRICTED_CLASSES = {
    "tlnCallout", "tlnProTip", "tlnDisclosure",
    "tlnTable", "tlnTableScroll",
    "tlnFaq", "tlnFaqQ",
    "tlnQuickCard", "tlnQuickGrid",
    "tlnHeroLead", "tlnHero", "tlnCard",
    "tlnMeta", "tlnBreadcrumb", "tlnPills",
    "bullet-section-blue", "bullet-section-gray",
    "bullet-section-green", "bullet-section-yellow",
    "bullet-section-red",
    "rl-callout", "rl-quick-card", "rl-faq", "rl-resources",
    "rl-hero", "rl-bluf",
}

RESTRICTED_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6", "code", "pre", "summary"}


def _is_in_restricted_zone(element) -> bool:
    """Check if an element is inside a restricted zone."""
    for parent in element.parents:
        if not isinstance(parent, Tag):
            continue
        if parent.name in RESTRICTED_TAGS:
            return True
        classes = parent.get("class", [])
        if isinstance(classes, str):
            classes = [classes]
        for cls in classes:
            if cls in RESTRICTED_CLASSES:
                return True
    return False


def _build_keyword_index(pool_path: str, exclude_slug: str = "") -> list[dict]:
    """Build scan targets from the anchor pool's primary keywords.

    For each destination, extract 1-3 word scan phrases from the
    primary_keyword that are likely to appear in body text.
    """
    with open(pool_path) as f:
        pool = json.load(f)

    destinations = pool.get("destinations", pool)
    targets = []

    for dest in destinations:
        slug = dest.get("slug", "")
        url = dest.get("url", "")
        pk = dest.get("primary_keyword", "")

        # Skip utility pages
        if slug in SKIP_SLUGS or slug == exclude_slug:
            continue

        # Normalize URL to relative
        if url.startswith("http"):
            from urllib.parse import urlparse
            url = urlparse(url).path
        if not url.startswith("/"):
            url = f"/{url}"
        if not url.endswith("/"):
            url = f"{url}/"

        # Generate scan phrases from primary keyword
        # Clean up: remove years, trailing question marks, lowercase
        pk_clean = re.sub(r"\b20\d{2}\b", "", pk).strip()
        pk_clean = pk_clean.rstrip("?").strip()
        pk_words = pk_clean.lower().split()

        # Skip if primary keyword is too generic or too long
        if len(pk_words) < 2 or len(pk_words) > 6:
            continue

        # Primary scan phrase: the full primary keyword (cleaned)
        scan_phrases = [" ".join(pk_words)]

        # For 3-word keywords: also try the first 2 words as sub-phrase
        # (e.g., "closing costs" from "closing costs explained")
        if len(pk_words) == 3:
            scan_phrases.append(" ".join(pk_words[:2]))

        # For 4+ word keywords: try first 3 words only
        # Do NOT generate 2-word fragments from 4+ word keywords —
        # they match too broadly (e.g., "Fannie Mae" from "Fannie Mae approved condos")
        if len(pk_words) >= 4:
            scan_phrases.append(" ".join(pk_words[:3]))

        # Deduplicate, filter out very short (< 2 words)
        seen = set()
        clean_phrases = []
        for phrase in scan_phrases:
            words = phrase.split()
            if len(words) < 2:
                continue
            key = phrase.lower()
            if key not in seen:
                seen.add(key)
                clean_phrases.append(phrase)

        if not clean_phrases:
            continue

        # Use shortest viable phrase as anchor text, longest as scan trigger
        # Sort by length descending for matching (prefer longer match)
        clean_phrases.sort(key=len, reverse=True)

        targets.append({
            "slug": slug,
            "url": url,
            "primary_keyword": pk,
            "scan_phrases": clean_phrases,
            "anchor_text": clean_phrases[-1],  # shortest phrase as anchor
        })

    # Sort targets by primary keyword length descending
    # (match longer/more specific keywords first)
    targets.sort(key=lambda t: len(t["scan_phrases"][0]), reverse=True)
    return targets


def _word_count(soup: BeautifulSoup) -> int:
    """Count words in the article body."""
    text = soup.get_text(separator=" ")
    return len(text.split())


def _max_links_for_word_count(wc: int) -> int:
    """Per-spec link density caps (updated bands)."""
    if wc < 400:
        return 3
    if wc < 800:
        return 5
    if wc < 1500:
        return 8
    if wc < 2500:
        return 11
    return 14


MIN_WORD_GAP = 30  # Gate 2: minimum words between any two injected links


def inject_links(html: str, targets: list[dict], max_links: int = 0,
                 dry_run: bool = False, verbose: bool = False) -> tuple[str, list[dict]]:
    """Scan body paragraphs for keyword matches and inject links.

    Gates enforced:
      - Per-article link cap (word-count bands)
      - 30-word minimum gap between any two injected links (Gate 2)
      - Anchor variety: prefer scan phrases not yet used in this article (Gate 3)

    Returns (modified_html, list_of_injections).
    """
    soup = BeautifulSoup(html, "html.parser")

    if max_links <= 0:
        max_links = _max_links_for_word_count(_word_count(soup))

    used_urls = set()
    used_paragraphs = set()  # track paragraphs that already got a link
    used_anchor_texts = set()  # Gate 3: anchor variety tracking
    injections = []

    # Gate 2: compute word offsets for each paragraph so we can enforce spacing
    paragraphs = soup.find_all("p")
    para_word_offsets: dict[int, int] = {}
    running_offset = 0
    for p_tag in paragraphs:
        para_word_offsets[id(p_tag)] = running_offset
        running_offset += len(p_tag.get_text().split())

    injected_word_ranges: list[tuple[int, int]] = []  # Gate 2: (start, end) word positions of all injections

    for target in targets:
        if len(injections) >= max_links:
            break
        if target["url"] in used_urls:
            continue

        # Gate 3: order scan phrases to prefer unused anchor texts first
        phrases_ordered = sorted(
            target["scan_phrases"],
            key=lambda p: (p.lower() in used_anchor_texts, -len(p)),
        )

        for phrase in phrases_ordered:
            if target["url"] in used_urls:
                break

            pattern = re.compile(
                r"\b(" + re.escape(phrase) + r"(?:s|es|ing|ed)?)\b",
                re.IGNORECASE,
            )

            for p_tag in paragraphs:
                if target["url"] in used_urls:
                    break
                if id(p_tag) in used_paragraphs:
                    continue
                if _is_in_restricted_zone(p_tag):
                    continue

                # Check if paragraph already contains a link
                if p_tag.find("a"):
                    continue

                p_text = p_tag.get_text()
                match = pattern.search(p_text)
                if not match:
                    continue

                matched_text = match.group(1)

                # Gate 2: check 30-word spacing from ALL previously injected links
                words_before_match = len(p_text[:match.start()].split())
                global_word_pos = para_word_offsets.get(id(p_tag), 0) + words_before_match
                anchor_word_len = len(matched_text.split())
                too_close = False
                for prev_start, prev_end in injected_word_ranges:
                    # Check distance from this candidate to any existing link
                    if global_word_pos < prev_start:
                        gap = prev_start - (global_word_pos + anchor_word_len)
                    else:
                        gap = global_word_pos - prev_end
                    if gap < MIN_WORD_GAP:
                        if verbose:
                            print(f"  [spacing] Skipped \"{matched_text}\" — only {gap} words from a nearby link", file=sys.stderr)
                        too_close = True
                        break
                if too_close:
                    continue

                if dry_run:
                    injections.append({
                        "anchor_text": matched_text,
                        "url": target["url"],
                        "primary_keyword": target["primary_keyword"],
                        "context": p_text[:80].strip(),
                        "word_pos": global_word_pos,
                    })
                    used_urls.add(target["url"])
                    used_paragraphs.add(id(p_tag))
                    used_anchor_texts.add(matched_text.lower())
                    injected_word_ranges.append((global_word_pos, global_word_pos + anchor_word_len))
                    break

                # Inject the link into the paragraph HTML
                injected = False
                for child in p_tag.descendants:
                    if not isinstance(child, NavigableString):
                        continue
                    if child.parent.name == "a":
                        continue  # already inside a link

                    child_match = pattern.search(str(child))
                    if not child_match:
                        continue

                    original = str(child)
                    matched = child_match.group(1)
                    start = child_match.start()
                    end = child_match.end()

                    # Build replacement: text before + link + text after
                    before = original[:start]
                    after = original[end:]
                    link_tag = soup.new_tag("a", href=target["url"])
                    link_tag.string = matched

                    parent_el = child.parent
                    idx = list(parent_el.children).index(child)
                    child.extract()
                    if after:
                        parent_el.insert(idx, NavigableString(after))
                    parent_el.insert(idx, link_tag)
                    if before:
                        parent_el.insert(idx, NavigableString(before))

                    injected = True
                    break

                if injected:
                    injections.append({
                        "anchor_text": matched_text,
                        "url": target["url"],
                        "primary_keyword": target["primary_keyword"],
                    })
                    used_urls.add(target["url"])
                    used_paragraphs.add(id(p_tag))
                    used_anchor_texts.add(matched_text.lower())
                    injected_word_ranges.append((global_word_pos, global_word_pos + anchor_word_len))
                    break

    return str(soup), injections


def main():
    parser = argparse.ArgumentParser(
        description="Keyword-scan link injector for post-generation articles"
    )
    parser.add_argument("--site", required=True, help="Site slug (e.g., tln)")
    parser.add_argument("--input", required=True, help="Input HTML file")
    parser.add_argument("--output", required=True, help="Output HTML file")
    parser.add_argument("--exclude-slug", default="", help="Slug to exclude (self-link prevention)")
    parser.add_argument("--max-links", type=int, default=0, help="Max links (0=auto from word count)")
    parser.add_argument("--dry-run", action="store_true", help="Show matches without modifying HTML")
    parser.add_argument("--verbose", action="store_true", help="Print gate decisions (spacing skips, variety rotation)")

    args = parser.parse_args()

    pool_path = REPO_ROOT / "sites" / f"{args.site}-anchor-pools.json"
    if not pool_path.exists():
        print(f"ERROR: Anchor pool not found: {pool_path}", file=sys.stderr)
        sys.exit(1)

    targets = _build_keyword_index(str(pool_path), args.exclude_slug)
    print(f"[keyword-inject] Loaded {len(targets)} linkable destinations")

    with open(args.input) as f:
        html = f.read()

    result_html, injections = inject_links(html, targets, args.max_links, args.dry_run, args.verbose)

    if args.dry_run:
        print(f"\n[DRY RUN] Would inject {len(injections)} links:")
        for inj in injections:
            print(f"  \"{inj['anchor_text']}\" -> {inj['url']}  (pk: {inj['primary_keyword']})")
            print(f"    context: {inj.get('context', '')}")
    else:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            f.write(result_html)
        print(f"[keyword-inject] Injected {len(injections)} internal links")
        for inj in injections:
            print(f"  \"{inj['anchor_text']}\" -> {inj['url']}")

    print(f"[keyword-inject] Output: {args.output}")


if __name__ == "__main__":
    main()
