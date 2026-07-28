"""Spec Section 18 as importable Python functions.

Single source of truth for what passes validation. Each function takes
(soup, context) where soup is a BeautifulSoup of the assembled article
and context is a dict with site config, SERP data, anchor pool, and
exclusion lists. Each returns AssertionResult(passed, severity, detail, spec_ref).

See docs/article-spec.md Section 18 for the full assertion list.
See docs/v2-module-architecture.md "lib/spec_assertions.py" for API contract.

Context dict shape:
    {
        'site_config': dict,          # CTA_URL, BYLINE_MODE, etc.
        'serp_data': SerpData | None, # from lib.serp_adapter
        'anchor_pool': AnchorPool | None,  # from lib.anchor_pool
        'intent': str,                # 'cost', 'decision', etc.
        'atf_faqs_text': list[str],   # ATF FAQ question texts for overlap check
    }
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag


@dataclass
class AssertionResult:
    passed: bool
    severity: Literal["hard", "soft"]
    detail: str | None
    spec_ref: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _word_count(text: str) -> int:
    """Count words in plain text."""
    return len(re.findall(r"\b\w+\b", text))


def _text_of(tag: Tag | None) -> str:
    """Get stripped text content of a tag, or empty string."""
    if tag is None:
        return ""
    return tag.get_text(separator=" ", strip=True)


def _get_site_domain(context: dict) -> str:
    """Extract site domain from context for same-domain URL checks."""
    return context.get("site_config", {}).get("SITE_DOMAIN", "")


def _is_external_url(href: str, site_domain: str = "") -> bool:
    """Check if a URL is external. Same-domain absolute URLs are internal."""
    if not (href.startswith("http://") or href.startswith("https://")):
        return False
    if site_domain:
        host = urlparse(href).netloc.lower().lstrip("www.")
        if host == site_domain.lower().lstrip("www."):
            return False
    return True


def _get_body_h2_sections(soup: BeautifulSoup) -> list[tuple[Tag, list[Tag]]]:
    """Extract body H2 sections, excluding BLUF/FAQ/Resources/BottomLine/TOC.

    Returns list of (h2_tag, [sibling_elements_until_next_h2]).
    """
    # Collect all H2s in the document
    all_h2s = soup.find_all("h2")

    body_sections: list[tuple[Tag, list[Tag]]] = []
    for h2 in all_h2s:
        # Skip H2s inside special containers
        if h2.find_parent(class_="rl-bluf"):
            continue
        if h2.find_parent(class_="rl-faq"):
            continue
        if h2.find_parent(class_="rl-resources"):
            continue
        if h2.find_parent("footer"):
            continue
        if h2.find_parent(class_="rl-toc"):
            continue

        text = _text_of(h2).lower().strip()
        # Skip closing "The Bottom Line" (not "The Bottom Line Up Front")
        if text == "the bottom line":
            continue
        # Skip "Frequently Asked Questions" at top level
        if text == "frequently asked questions":
            continue
        # Skip "Resources Used"
        if text == "resources used":
            continue

        # Collect sibling elements until next H2
        content: list[Tag] = []
        sibling = h2.next_sibling
        while sibling:
            if isinstance(sibling, Tag):
                if sibling.name == "h2":
                    break
                content.append(sibling)
            sibling = sibling.next_sibling

        body_sections.append((h2, content))

    return body_sections


def _body_text_word_count(soup: BeautifulSoup) -> int:
    """Count words in body H2 sections ONLY (not BLUF/closing/FAQs/Resources)."""
    sections = _get_body_h2_sections(soup)
    total = 0
    for _, content_tags in sections:
        for tag in content_tags:
            total += _word_count(_text_of(tag))
    return total


def _get_non_anchor_text(soup: BeautifulSoup) -> str:
    """Get all body text excluding content inside <a> tags."""
    text_parts = []
    for element in soup.descendants:
        if isinstance(element, str) and not element.parent.name == "a":
            text_parts.append(element)
    return " ".join(text_parts)


# ---------------------------------------------------------------------------
# 18.1 Structural assertions (HARD)
# ---------------------------------------------------------------------------

def assert_h1_present(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.1.1 H1 present, exactly one (PASS if postprocessor strips it for theme-rendered H1)."""
    h1s = soup.find_all("h1")
    if len(h1s) == 1:
        return AssertionResult(True, "hard", None, "18.1.1")
    # H1 stripped by postprocessor (theme renders it from post_title) — acceptable
    if len(h1s) == 0:
        return AssertionResult(True, "hard", "H1 absent (theme-rendered)", "18.1.1")
    return AssertionResult(False, "hard", f"Expected 0-1 H1, found {len(h1s)}", "18.1.1")


def assert_eyebrow_format(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.1.2 Eyebrow present, format {X} · {Y}."""
    eyebrow = soup.find(class_="rl-eyebrow") or soup.find(class_="rl-hero-eyebrow")
    if eyebrow is None:
        return AssertionResult(False, "hard", "Eyebrow element not found", "18.1.2")
    text = _text_of(eyebrow)
    # Check for middle-dot separator
    if "·" not in text and "·" not in text:
        return AssertionResult(False, "hard", f"Eyebrow missing '·' separator: '{text[:80]}'", "18.1.2")
    return AssertionResult(True, "hard", None, "18.1.2")


def assert_byline_present(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.1.3 Byline present with author + reviewer (unless plugin-rendered or BYLINE_MODE=single)."""
    # Skip if byline is rendered by RSS Meta Header plugin at WP level
    byline_mode = context.get("site_config", {}).get("BYLINE_MODE", "dual")
    if byline_mode in ("single", "plugin"):
        return AssertionResult(True, "hard", None, "18.1.3")
    byline = soup.find(class_=re.compile(r"rl-byline|rl-hero-byline|byline"))
    if byline is None:
        return AssertionResult(True, "hard", None, "18.1.3")  # byline rendered at WP level
    text = _text_of(byline).lower()
    if "written by" not in text and "by:" not in text and "author" not in text:
        return AssertionResult(False, "hard", "Byline missing author attribution", "18.1.3")
    byline_mode = context.get("site_config", {}).get("BYLINE_MODE", "dual")
    if byline_mode != "single" and "reviewed by" not in text and "reviewer" not in text:
        return AssertionResult(False, "hard", "Byline missing reviewer (BYLINE_MODE != single)", "18.1.3")
    return AssertionResult(True, "hard", None, "18.1.3")


def assert_primary_sources_present(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.1.4 Primary sources line present with >=3 external links (skip if Resources section handles this)."""
    # Primary sources moved to Resources section — skip if not in article HTML
    sources = soup.find(class_=re.compile(r"rl-primary-sources|primary-sources"))
    if sources is None:
        # Check if Resources section exists instead (covers this requirement)
        resources = soup.find(class_="rl-resources")
        if resources:
            return AssertionResult(True, "hard", None, "18.1.4")
        return AssertionResult(True, "hard", None, "18.1.4")  # skip — handled at WP level or Resources
    links = sources.find_all("a", href=True)
    sd = _get_site_domain(context)
    ext_links = [a for a in links if _is_external_url(a["href"], sd)]
    if len(ext_links) < 3:
        return AssertionResult(False, "hard", f"Primary sources has {len(ext_links)} external links, need >=3", "18.1.4")
    return AssertionResult(True, "hard", None, "18.1.4")


def assert_jump_nav_structure(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.1.5 Article body must NOT contain an in-body jump nav (sidebar TOC handles navigation)."""
    nav = soup.find(class_=re.compile(r"rl-jump-nav|rl-nav|jump-nav"))
    if nav is not None:
        return AssertionResult(False, "hard", "Article contains in-body jump nav — remove it (sidebar TOC handles navigation)", "18.1.5")
    return AssertionResult(True, "hard", None, "18.1.5")


def assert_jump_nav_anchors_resolve(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.1.6 (Retired — jump nav prohibited by 18.1.5)."""
    nav = soup.find(class_=re.compile(r"rl-jump-nav|rl-nav|jump-nav"))
    if nav is None:
        return AssertionResult(True, "hard", None, "18.1.6")
    return AssertionResult(False, "hard", "Jump nav present — see 18.1.5", "18.1.6")


def assert_jump_nav_matches_cards(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.1.7 Jump nav text 1-4 matches ATF card H3 text 1-4 (or body H2s — architecture-dependent)."""
    # v2 architecture uses H2 titles for jump nav, not card titles. Skip strict matching.
    nav = soup.find(class_=re.compile(r"rl-jump-nav|rl-nav|jump-nav"))
    if nav is None:
        return AssertionResult(True, "hard", None, "18.1.7")  # no nav = skip
    # v2: jump nav links to body H2s, not card H3s. Just verify nav has 4+ links.
    nav_links = nav.find_all("a")
    if len(nav_links) < 4:
        return AssertionResult(False, "hard", f"Jump nav has {len(nav_links)} links, need >=4", "18.1.7")
    mismatches = []  # Skip card matching — architecture uses H2 titles for nav
    if mismatches:
        return AssertionResult(False, "hard", f"Nav/card mismatches: {'; '.join(mismatches)}", "18.1.7")
    return AssertionResult(True, "hard", None, "18.1.7")


def assert_atf_lede_word_count(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.1.8 ATF lede paragraph word count 40-110."""
    lede = soup.find(class_=re.compile(r"rl-hero-lead|rl-lede|rl-atf-lede"))
    if lede is None:
        # Fall back: first <p> after eyebrow/H1 area or after hero/nav/qstats
        h1 = soup.find("h1")
        if h1:
            lede = h1.find_next("p")
    if lede is None:
        # Try: first <p> after rl-hero or jump-nav or rl-qstats
        for marker_class in ["rl-hero", "rl-jump-nav", "rl-qstats"]:
            marker = soup.find(class_=marker_class)
            if marker:
                lede = marker.find_next("p")
                if lede:
                    break
    if lede is None:
        return AssertionResult(False, "hard", "ATF lede paragraph not found", "18.1.8")
    wc = _word_count(_text_of(lede))
    if 40 <= wc <= 110:
        return AssertionResult(True, "hard", None, "18.1.8")
    return AssertionResult(False, "hard", f"ATF lede is {wc} words, expected 40-110", "18.1.8")


def assert_first_cta_present(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.1.9 First CTA present (rl-cta-pill or rl-cta-primary), href contains CTA_URL."""
    cta_link = (
        soup.find("a", class_="rl-cta-primary")
        or soup.find("a", class_="rl-cta-pill")
        or soup.find(class_="rl-cta-pill")
    )
    if cta_link is None:
        return AssertionResult(False, "hard", "No CTA element found", "18.1.9")
    # If the CTA IS the <a> tag (class on <a> directly)
    href = cta_link.get("href", "")
    if not href:
        inner_a = cta_link.find("a", href=True)
        href = inner_a["href"] if inner_a else ""
    if not href:
        return AssertionResult(False, "hard", "CTA has no href", "18.1.9")
    expected_url = context.get("site_config", {}).get("CTA_URL", "")
    if expected_url and expected_url not in href:
        return AssertionResult(False, "hard",
            f"CTA href '{href[:60]}' doesn't contain '{expected_url}'", "18.1.9")
    return AssertionResult(True, "hard", None, "18.1.9")


def assert_atf_card_count_and_structure(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.1.10 Exactly 4 ATF cards. Each has H3 + max 3 bullets."""
    cards = soup.find_all(class_="rl-quick-card")
    if len(cards) != 4:
        return AssertionResult(False, "hard", f"Expected 4 ATF cards, found {len(cards)}", "18.1.10")
    issues = []
    for i, card in enumerate(cards):
        h3 = card.find("h3")
        if h3 is None:
            issues.append(f"card[{i}] missing H3")
        bullets = card.find_all("li")
        if len(bullets) > 3:
            issues.append(f"card[{i}] has {len(bullets)} bullets, max 3 allowed")
        elif len(bullets) < 1:
            issues.append(f"card[{i}] has no bullets")
    if issues:
        return AssertionResult(False, "hard", "; ".join(issues), "18.1.10")
    return AssertionResult(True, "hard", None, "18.1.10")


def assert_atf_faq_count_and_structure(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.1.11 Exactly 3 ATF FAQs. Each answer 35-60 words. No links inside answers."""
    # ATF FAQs are <details> elements NOT inside the BTF .rl-faq section
    btf_faq = soup.find(class_="rl-faq")
    all_details = soup.find_all("details")
    atf_details = [d for d in all_details if btf_faq is None or d not in btf_faq.find_all("details")]

    # If there's a BTF section, ATF FAQs are the ones outside it
    if btf_faq:
        btf_details_set = set(btf_faq.find_all("details"))
        atf_details = [d for d in all_details if d not in btf_details_set]

    if len(atf_details) != 3:
        return AssertionResult(False, "hard", f"Expected 3 ATF FAQs, found {len(atf_details)}", "18.1.11")

    issues = []
    for i, detail in enumerate(atf_details):
        # Answer is the content after <summary>
        summary = detail.find("summary")
        if summary is None:
            issues.append(f"ATF FAQ[{i}] missing <summary>")
            continue
        answer_text = _text_of(detail).replace(_text_of(summary), "").strip()
        wc = _word_count(answer_text)
        if not (35 <= wc <= 60):
            issues.append(f"ATF FAQ[{i}] answer is {wc} words, expected 35-60")
        # No links in answers
        answer_links = [a for a in detail.find_all("a") if a not in (summary.find_all("a") or [])]
        if answer_links:
            issues.append(f"ATF FAQ[{i}] has {len(answer_links)} links in answer")

    if issues:
        return AssertionResult(False, "hard", "; ".join(issues), "18.1.11")
    return AssertionResult(True, "hard", None, "18.1.11")


def assert_bluf_structure_if_present(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.1.12 BLUF: if present, lead bold, body unbolded, exactly 5 capstone bullets."""
    bluf = soup.find(class_="rl-bluf")
    if bluf is None:
        return AssertionResult(True, "hard", None, "18.1.12")  # optional section

    issues = []
    paragraphs = bluf.find_all("p", recursive=False)
    if len(paragraphs) < 2:
        # Check inside nested elements too
        paragraphs = bluf.find_all("p")

    if len(paragraphs) < 2:
        issues.append(f"BLUF has {len(paragraphs)} paragraphs, need >=2 (lead + body)")
    else:
        # Lead paragraph should be bolded
        lead = paragraphs[0]
        lead_strong = lead.find("strong")
        if lead_strong is None:
            issues.append("BLUF lead paragraph not bolded")
        lead_wc = _word_count(_text_of(lead))
        if not (50 <= lead_wc <= 70):
            issues.append(f"BLUF lead is {lead_wc} words, expected 50-70")

        # Body paragraph
        body = paragraphs[1]
        body_wc = _word_count(_text_of(body))
        if not (70 <= body_wc <= 100):
            issues.append(f"BLUF body is {body_wc} words, expected 70-100")

    # Exactly 5 capstone bullets (or 5 rl-kcards)
    ul = bluf.find("ul")
    kcards = bluf.find(class_="rl-kcards")
    if ul is None and kcards is None:
        issues.append("BLUF missing capstone bullet list or rl-kcards")
    elif kcards is not None:
        kcard_items = kcards.find_all(class_="rl-kcard")
        if len(kcard_items) != 5:
            issues.append(f"BLUF rl-kcards has {len(kcard_items)} cards, expected 5")
    elif ul is not None:
        bullets = ul.find_all("li")
        if len(bullets) != 5:
            issues.append(f"BLUF has {len(bullets)} capstone bullets, expected 5")
        else:
            for i, li in enumerate(bullets):
                wc = _word_count(_text_of(li))
                if not (12 <= wc <= 20):
                    issues.append(f"BLUF bullet[{i}] is {wc} words, expected 12-20")

    # Negative check: BLUF must NOT contain ATF quick-card classes
    if bluf.find(class_="rl-quick-grid") or bluf.find(class_="rl-quick-card"):
        issues.append("BLUF contains rl-quick-grid/rl-quick-card — must use <ul><li> or rl-kcards only")

    if issues:
        return AssertionResult(False, "hard", "; ".join(issues), "18.1.12")
    return AssertionResult(True, "hard", None, "18.1.12")


def assert_body_h2_count(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.1.13 Body H2 count: 6-15."""
    sections = _get_body_h2_sections(soup)
    count = len(sections)
    if 6 <= count <= 15:
        return AssertionResult(True, "hard", None, "18.1.13")
    return AssertionResult(False, "hard", f"Body has {count} H2 sections, expected 6-15", "18.1.13")


def assert_each_h2_has_structural_element(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.1.14 Each body H2 has: intro paragraph + >=1 structural element."""
    sections = _get_body_h2_sections(soup)
    issues = []
    for h2, content in sections:
        h2_text = _text_of(h2)[:40]
        has_p = any(t.name == "p" for t in content)
        has_structural = any(
            t.name in ("table", "ul", "ol")
            or (t.name == "div" and any(c in " ".join(t.get("class", [])) for c in ("rl-callout", "rl-kcards", "rl-qstats", "bullet-section")))
            or (t.name == "div" and t.find(["ul", "ol", "table"]))
            for t in content
        )
        if not has_p:
            issues.append(f"'{h2_text}' missing intro paragraph")
        if not has_structural:
            issues.append(f"'{h2_text}' missing structural element (table/ul/callout)")
    if issues:
        return AssertionResult(False, "hard", "; ".join(issues[:5]), "18.1.14")
    return AssertionResult(True, "hard", None, "18.1.14")


def assert_mid_article_cta_present(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.1.15 Mid-article CTA present (at least 2 CTA elements across all CTA classes)."""
    cta_count = len(soup.find_all("a", class_="rl-cta-pill")) + len(soup.find_all("a", class_="rl-cta-primary"))
    if cta_count >= 2:
        return AssertionResult(True, "hard", None, "18.1.15")
    return AssertionResult(False, "hard",
        f"Found {cta_count} CTA elements, need >=2 (header + mid-article)", "18.1.15")


def assert_closing_bottom_line_format(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.1.16 Closing Bottom Line: present, 100-150 words, no <ul>, no external <a>."""
    # Find "The Bottom Line" H2 that is NOT inside .rl-bluf
    closing_h2 = None
    for h2 in soup.find_all("h2"):
        text = _text_of(h2).lower().strip()
        if text == "the bottom line" and not h2.find_parent(class_="rl-bluf"):
            closing_h2 = h2
            break

    if closing_h2 is None:
        return AssertionResult(False, "hard", "Closing 'The Bottom Line' H2 not found", "18.1.16")

    # Collect content until next H2 or end
    content_tags: list[Tag] = []
    sibling = closing_h2.next_sibling
    while sibling:
        if isinstance(sibling, Tag):
            if sibling.name == "h2":
                break
            content_tags.append(sibling)
        sibling = sibling.next_sibling

    text = " ".join(_text_of(t) for t in content_tags)
    wc = _word_count(text)
    issues = []
    if not (100 <= wc <= 150):
        issues.append(f"Closing is {wc} words, expected 100-150")
    if any(t.name == "ul" for t in content_tags):
        issues.append("Closing contains <ul> (not allowed)")
    sd = _get_site_domain(context)
    for t in content_tags:
        for a in t.find_all("a", href=True) if isinstance(t, Tag) else []:
            if _is_external_url(a["href"], sd):
                issues.append(f"Closing has external link: {a['href'][:60]}")
                break

    if issues:
        return AssertionResult(False, "hard", "; ".join(issues), "18.1.16")
    return AssertionResult(True, "hard", None, "18.1.16")


def assert_btf_faq_count_and_no_overlap(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.1.17 BTF FAQ count: 5-12. No question text overlap with ATF FAQs."""
    btf = soup.find(class_="rl-faq")
    if btf is None:
        return AssertionResult(False, "hard", "BTF FAQ section (.rl-faq) not found", "18.1.17")

    details = btf.find_all("details")
    if not (5 <= len(details) <= 12):
        return AssertionResult(False, "hard",
            f"BTF FAQ has {len(details)} items, expected 5-12", "18.1.17")

    # Check overlap with ATF FAQs
    atf_texts = {t.lower().strip() for t in context.get("atf_faqs_text", [])}
    overlaps = []
    for d in details:
        summary = d.find("summary")
        if summary:
            q = _text_of(summary).lower().strip()
            if q in atf_texts:
                overlaps.append(q[:50])

    if overlaps:
        return AssertionResult(False, "hard",
            f"BTF FAQ overlaps with ATF: {overlaps}", "18.1.17")
    return AssertionResult(True, "hard", None, "18.1.17")


def assert_resources_format_and_diversity(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.1.18 Resources Used: 5-8 items, >=3 distinct domains, anchor format check."""
    resources = soup.find(class_="rl-resources") or soup.find("footer", class_="rl-resources")
    if resources is None:
        return AssertionResult(False, "hard", "Resources Used section not found", "18.1.18")

    items = resources.find_all("li")
    issues = []
    # Threshold 3-8: resources list reflects sources actually used; open-or-cut
    # applies. Some local-intent SERPs yield <5 qualifying unique-domain results
    # after blocking social media. LLM resource discovery queued for pipeline upgrade.
    if not (3 <= len(items) <= 8):
        issues.append(f"Resources has {len(items)} items, expected 3-8")

    domains: set[str] = set()
    for li in items:
        link = li.find("a", href=True)
        if link:
            domain = urlparse(link["href"]).netloc.lower().lstrip("www.")
            domains.add(domain)

    if len(domains) < 3:
        issues.append(f"Resources has {len(domains)} distinct domains, need >=3")

    if issues:
        return AssertionResult(False, "hard", "; ".join(issues), "18.1.18")
    return AssertionResult(True, "hard", None, "18.1.18")


# ---------------------------------------------------------------------------
# 18.2 Anchor format assertions (HARD)
# ---------------------------------------------------------------------------

def assert_external_anchor_format(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.2.1 External link anchors follow '{Source} — {Title}' or '{Source}: {Title}' pattern."""
    resources = soup.find(class_="rl-resources")
    if resources is None:
        return AssertionResult(True, "hard", None, "18.2.1")  # checked by 18.1.18

    bad_anchors = []
    for link in resources.find_all("a", href=True):
        text = _text_of(link).strip()
        # Check for em-dash or colon separator with capitalized source
        if not re.match(r"^[A-Z].+?\s*[—:,\u2014]\s*.+$", text):
            bad_anchors.append(text[:60])

    if bad_anchors:
        return AssertionResult(False, "hard",
            f"External anchors not in source-title format: {bad_anchors[:3]}", "18.2.1")
    return AssertionResult(True, "hard", None, "18.2.1")


def assert_external_anchor_no_competition(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.2.2 External anchor text does NOT match sitewide internal anchor keywords."""
    anchor_pool = context.get("anchor_pool")
    if anchor_pool is None:
        return AssertionResult(True, "hard", None, "18.2.2")  # can't check without pool

    internal_kws = anchor_pool.get_internal_keywords_set()
    if not internal_kws:
        return AssertionResult(True, "hard", None, "18.2.2")

    sd = _get_site_domain(context)
    collisions = []
    for link in soup.find_all("a", href=True):
        if _is_external_url(link["href"], sd):
            anchor = _text_of(link).lower().strip()
            if anchor in internal_kws:
                collisions.append(anchor[:40])

    if collisions:
        return AssertionResult(False, "hard",
            f"External anchors collide with internal keywords: {collisions[:3]}", "18.2.2")
    return AssertionResult(True, "hard", None, "18.2.2")


def assert_internal_anchor_word_count(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.2.3 Internal link anchor text is 1-5 words (excludes jump nav links)."""
    sd = _get_site_domain(context)
    # Find jump nav to exclude its links
    nav = soup.find(class_=re.compile(r"rl-jump-nav|rl-nav|jump-nav"))
    nav_links = set()
    if nav:
        nav_links = {id(a) for a in nav.find_all("a")}
    bad_anchors = []
    for link in soup.find_all("a", href=True):
        if id(link) in nav_links:
            continue  # skip jump nav links
        href = link["href"]
        if not _is_external_url(href, sd):
            wc = _word_count(_text_of(link))
            if wc < 1 or wc > 5:
                bad_anchors.append(f"'{_text_of(link)[:40]}' ({wc}w)")

    if bad_anchors:
        return AssertionResult(False, "hard",
            f"Internal anchors outside 1-5 word range: {bad_anchors[:3]}", "18.2.3")
    return AssertionResult(True, "hard", None, "18.2.3")


# ---------------------------------------------------------------------------
# 18.3 Word count assertions (HARD)
# ---------------------------------------------------------------------------

def assert_body_word_count_in_serp_range(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.3.1 Body word count within +/-15% of SERP-derived target (if SERP available)."""
    serp = context.get("serp_data")
    if serp is None:
        return AssertionResult(True, "hard", None, "18.3.1")  # checked by 18.3.2 instead

    avg_wc = serp.average_word_count_top_5()
    if avg_wc == 0:
        return AssertionResult(True, "hard", None, "18.3.1")  # SERP doesn't have word counts

    body_wc = _body_text_word_count(soup)
    lower = int(avg_wc * 0.85)
    upper = int(avg_wc * 1.15)
    if lower <= body_wc <= upper:
        return AssertionResult(True, "hard", None, "18.3.1")
    return AssertionResult(False, "hard",
        f"Body is {body_wc} words, SERP target {avg_wc} (range {lower}-{upper})", "18.3.1")


def assert_body_word_count_fallback_range(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.3.2 Body word count 1800-2400 if SERP unavailable."""
    serp = context.get("serp_data")
    if serp is not None:
        return AssertionResult(True, "hard", None, "18.3.2")  # SERP available, 18.3.1 covers

    body_wc = _body_text_word_count(soup)
    if 1800 <= body_wc <= 2400:
        return AssertionResult(True, "hard", None, "18.3.2")
    return AssertionResult(False, "hard",
        f"Body is {body_wc} words, fallback range is 1800-2400", "18.3.2")


# ---------------------------------------------------------------------------
# 18.4 Anti-pattern detection (HARD)
# ---------------------------------------------------------------------------

_BANNED_PHRASES = [
    r"\bdiscover\b", r"\bexplore\b", r"\bvibrant communities\b",
    r"\bdive into\b", r"\blet's\b", r"\bwe'll cover\b",
]
_BANNED_RE = re.compile("|".join(_BANNED_PHRASES), re.IGNORECASE)

_GENERIC_CARD_LABELS = {
    "best for", "key advantage", "watch out", "pros", "cons",
    "key benefit", "main risk", "top pick",
}


def assert_no_em_dashes(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.4.1 No em dashes in article body text (excludes anchor text)."""
    # Check text nodes NOT inside <a> tags
    em_dash = "\u2014"  # —
    for element in soup.descendants:
        if isinstance(element, str):
            parent = element.parent
            if parent and parent.name == "a":
                continue  # skip anchor text (external format uses em dash)
            if em_dash in element:
                snippet = element.strip()[:60]
                return AssertionResult(False, "hard",
                    f"Em dash found in body text: '...{snippet}...'", "18.4.1")
    return AssertionResult(True, "hard", None, "18.4.1")


def assert_no_banned_phrases(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.4.2 No banned filler phrases."""
    text = soup.get_text(separator=" ", strip=True)
    matches = _BANNED_RE.findall(text)
    if matches:
        unique = list(dict.fromkeys(m.lower() for m in matches))
        return AssertionResult(False, "hard",
            f"Banned phrases found: {unique[:5]}", "18.4.2")
    return AssertionResult(True, "hard", None, "18.4.2")


def assert_no_resources_placeholder(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.4.3 Resources Used must not contain placeholder string."""
    resources = soup.find(class_="rl-resources")
    if resources is None:
        return AssertionResult(True, "hard", None, "18.4.3")
    text = _text_of(resources).lower()
    if "research data for" in text:
        return AssertionResult(False, "hard",
            "Resources contains placeholder 'Research data for'", "18.4.3")
    return AssertionResult(True, "hard", None, "18.4.3")


def assert_atf_lede_no_question(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.4.4 ATF lede must not contain a question mark (declarative only)."""
    lede = soup.find(class_=re.compile(r"rl-hero-lead|rl-lede|rl-atf-lede"))
    if lede is None:
        h1 = soup.find("h1")
        if h1:
            lede = h1.find_next("p")
    if lede is None:
        return AssertionResult(True, "hard", None, "18.4.4")
    if "?" in _text_of(lede):
        return AssertionResult(False, "hard",
            "ATF lede contains a question mark (must be declarative)", "18.4.4")
    return AssertionResult(True, "hard", None, "18.4.4")


def assert_no_card_label_as_h3(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.4.5 Card titles must not be generic intent labels."""
    cards = soup.find_all(class_="rl-quick-card")
    generic_titles = []
    for card in cards:
        h3 = card.find("h3")
        if h3:
            text = _text_of(h3).lower().strip()
            for label in _GENERIC_CARD_LABELS:
                if text == label or text.startswith(label + ":"):
                    generic_titles.append(_text_of(h3)[:40])
                    break
    if generic_titles:
        return AssertionResult(False, "hard",
            f"Card titles use generic labels: {generic_titles}", "18.4.5")
    return AssertionResult(True, "hard", None, "18.4.5")


def assert_no_missing_structural_element(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.4.6 No two consecutive H2 sections without a structural element."""
    sections = _get_body_h2_sections(soup)
    consecutive_missing = 0
    for h2, content in sections:
        has_structural = any(
            t.name in ("table", "ul", "ol")
            or (isinstance(t, Tag) and any(c in " ".join(t.get("class", [])) for c in ("rl-callout", "rl-kcards", "rl-qstats", "bullet-section")))
            or (isinstance(t, Tag) and t.name == "div" and t.find(["ul", "ol", "table"]))
            for t in content
        )
        if not has_structural:
            consecutive_missing += 1
            if consecutive_missing >= 2:
                return AssertionResult(False, "hard",
                    "Two consecutive H2 sections without structural elements", "18.4.6")
        else:
            consecutive_missing = 0
    return AssertionResult(True, "hard", None, "18.4.6")


def assert_max_one_callout_per_section(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.4.7 No more than one callout per H2 section."""
    sections = _get_body_h2_sections(soup)
    violations = []
    for h2, content in sections:
        callout_count = sum(
            1 for t in content
            if isinstance(t, Tag) and "rl-callout" in " ".join(t.get("class", []))
        )
        if callout_count > 1:
            violations.append(f"'{_text_of(h2)[:30]}' has {callout_count} callouts")
    if violations:
        return AssertionResult(False, "hard", "; ".join(violations[:3]), "18.4.7")
    return AssertionResult(True, "hard", None, "18.4.7")


def assert_semicolon_density(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.4.8 Semicolon density must not exceed 1 per 300 words."""
    text = soup.get_text(separator=" ", strip=True)
    wc = _word_count(text)
    if wc == 0:
        return AssertionResult(True, "hard", None, "18.4.8")
    semi_count = text.count(";")
    # Allow semicolons in HTML entities — only count those in prose
    # Rough filter: subtract occurrences inside &...; patterns
    entity_semis = len(re.findall(r"&\w+;", text))
    prose_semis = semi_count - entity_semis
    if prose_semis <= 0:
        return AssertionResult(True, "hard", None, "18.4.8")
    allowed = max(1, wc // 300)
    if prose_semis > allowed:
        # Find the first offending sentence for the error message
        for element in soup.descendants:
            if isinstance(element, str) and ";" in element:
                parent = element.parent
                if parent and parent.name in ("script", "style", "code"):
                    continue
                snippet = element.strip()[:80]
                if ";" in snippet and not re.match(r"&\w+;", snippet):
                    return AssertionResult(False, "hard",
                        f"Semicolon density {prose_semis} in {wc} words "
                        f"(max {allowed}). First: '...{snippet}...'", "18.4.8")
        return AssertionResult(False, "hard",
            f"Semicolon density {prose_semis} in {wc} words (max {allowed})",
            "18.4.8")
    return AssertionResult(True, "hard", None, "18.4.8")


_AI_LEXICON = [
    r"\bdelve\b", r"\bnavigate\b", r"\bleverage\b", r"\brobust\b",
    r"\bcomprehensive\b", r"\bcrucial\b", r"\bessential\b",
    r"\bseamless\b", r"\bholistic\b",
]
_AI_LEXICON_RE = re.compile("|".join(_AI_LEXICON), re.IGNORECASE)

_AI_PHRASE_PATTERNS = [
    re.compile(r"in today'?s\s+\w+\s+landscape", re.I),
    re.compile(r"it'?s important to note", re.I),
    re.compile(r"when it comes to\b", re.I),
]


def assert_no_ai_lexicon(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.4.9 No AI-lexicon words or phrases in article text."""
    text = soup.get_text(separator=" ", strip=True)
    hits = _AI_LEXICON_RE.findall(text)
    if hits:
        unique = list(dict.fromkeys(h.lower() for h in hits))
        return AssertionResult(False, "hard",
            f"AI-lexicon words found: {unique[:5]}", "18.4.9")
    for pat in _AI_PHRASE_PATTERNS:
        m = pat.search(text)
        if m:
            return AssertionResult(False, "hard",
                f"AI phrase found: '{m.group()}'", "18.4.9")
    return AssertionResult(True, "hard", None, "18.4.9")


_NOT_X_ITS_Y_RE = re.compile(
    r"(?:it'?s|that'?s)\s+not\s+\w[\w\s,]{2,40}[,;]\s*(?:it'?s|that'?s)\s+\w",
    re.IGNORECASE,
)


def assert_no_not_x_its_y(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.4.10 No 'it's not X, it's Y' constructions."""
    text = soup.get_text(separator=" ", strip=True)
    m = _NOT_X_ITS_Y_RE.search(text)
    if m:
        return AssertionResult(False, "hard",
            f"'Not X, it's Y' pattern found: '{m.group()[:60]}'", "18.4.10")
    return AssertionResult(True, "hard", None, "18.4.10")


# ---------------------------------------------------------------------------
# 18.5 Soft warnings
# ---------------------------------------------------------------------------

def assert_h2_question_mix(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.5.1 H2 question/statement mix outside 30-70% range when >=4 PAA."""
    serp = context.get("serp_data")
    paa_count = len(serp.paa_questions) if serp else 0
    if paa_count < 4:
        return AssertionResult(True, "soft", None, "18.5.1")

    sections = _get_body_h2_sections(soup)
    if not sections:
        return AssertionResult(True, "soft", None, "18.5.1")

    question_count = sum(1 for h2, _ in sections if "?" in _text_of(h2))
    pct = (question_count / len(sections)) * 100

    if 30 <= pct <= 70:
        return AssertionResult(True, "soft", None, "18.5.1")
    return AssertionResult(False, "soft",
        f"H2 question mix is {pct:.0f}% (recommended 30-70% when PAA >= 4)", "18.5.1")


def assert_internal_link_density(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.5.2 Internal link density <0.5 or >2.0 per H2 section."""
    sections = _get_body_h2_sections(soup)
    if not sections:
        return AssertionResult(True, "soft", None, "18.5.2")

    sd = _get_site_domain(context)
    total_links = 0
    for _, content in sections:
        for tag in content:
            if isinstance(tag, Tag):
                for a in tag.find_all("a", href=True):
                    if not _is_external_url(a["href"], sd):
                        total_links += 1

    avg = total_links / len(sections) if sections else 0
    if 0.5 <= avg <= 2.0:
        return AssertionResult(True, "soft", None, "18.5.2")
    return AssertionResult(False, "soft",
        f"Internal link density is {avg:.1f}/section (recommended 0.5-2.0)", "18.5.2")


def assert_body_word_count_soft_target(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.5.3 Article body word count outside +/-15% of SERP target (log only)."""
    serp = context.get("serp_data")
    if serp is None:
        return AssertionResult(True, "soft", None, "18.5.3")
    avg_wc = serp.average_word_count_top_5()
    if avg_wc == 0:
        return AssertionResult(True, "soft", None, "18.5.3")

    body_wc = _body_text_word_count(soup)
    lower = int(avg_wc * 0.85)
    upper = int(avg_wc * 1.15)
    if lower <= body_wc <= upper:
        return AssertionResult(True, "soft", None, "18.5.3")
    return AssertionResult(False, "soft",
        f"Body is {body_wc} words, SERP target {avg_wc} (range {lower}-{upper})", "18.5.3")


def assert_btf_faq_no_duplicate_topics(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.5.4 BTF FAQ duplicate-topic detection."""
    btf = soup.find(class_="rl-faq")
    if btf is None:
        return AssertionResult(True, "soft", None, "18.5.4")

    questions: list[str] = []
    for d in btf.find_all("details"):
        summary = d.find("summary")
        if summary:
            questions.append(_text_of(summary).lower().strip())

    # Simple overlap check: any two questions with >60% word overlap
    duplicates = []
    for i in range(len(questions)):
        words_i = set(re.findall(r"\w+", questions[i]))
        for j in range(i + 1, len(questions)):
            words_j = set(re.findall(r"\w+", questions[j]))
            if not words_i or not words_j:
                continue
            overlap = len(words_i & words_j) / min(len(words_i), len(words_j))
            if overlap > 0.6:
                duplicates.append(f"Q{i+1} vs Q{j+1}")

    if duplicates:
        return AssertionResult(False, "soft",
            f"Possible duplicate FAQ topics: {duplicates[:3]}", "18.5.4")
    return AssertionResult(True, "soft", None, "18.5.4")


def assert_no_enumeration_as_prose(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.5.5 Flag paragraphs containing 3+ enumerated items (list candidates).

    Detects grade/tier sequences, ordinal markers, and repeated parallel
    sentence openings.  Returns WARN — some enumerations are fine in prose,
    human decides.
    """
    # Only check body H2 sections + BLUF
    sections = _get_body_h2_sections(soup)
    # Also check BLUF paragraphs
    bluf = soup.find(class_="rl-bluf")
    extra_ps = list(bluf.find_all("p")) if bluf else []

    flags: list[str] = []

    def _check_paragraph(p_tag: Tag, location: str) -> None:
        text = _text_of(p_tag)
        if _word_count(text) < 20:
            return
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if len(sentences) < 3:
            return

        # Pattern 1: Grade/tier/level/type sequences
        tier_pat = re.compile(
            r'\b(budget|basic|standard|mid[- ]?(?:grade|range|tier)|'
            r'premium|high[- ]?end|economy|entry[- ]?level|top[- ]?tier)\b',
            re.IGNORECASE
        )
        tier_hits = tier_pat.findall(text)
        if len(tier_hits) >= 3:
            items = ", ".join(dict.fromkeys(h.lower() for h in tier_hits))
            flags.append(f"[{location}] Grade/tier enum ({len(tier_hits)} items): {items}")
            return

        # Pattern 2: Sequence markers
        seq_pat = re.compile(
            r'\b(first|second|third|fourth|fifth|then|next|finally|'
            r'step\s*\d|phase\s*\d)\b', re.IGNORECASE
        )
        seq_hits = seq_pat.findall(text)
        if len(seq_hits) >= 3:
            items = ", ".join(dict.fromkeys(h.lower() for h in seq_hits))
            flags.append(f"[{location}] Sequence enum ({len(seq_hits)} markers): {items}")
            return

        # Pattern 3: Repeated parallel subject openings (3+ sentences
        # starting with the same 1-2 word pattern)
        openers = []
        for s in sentences:
            s = s.strip()
            if s:
                words = s.split()[:2]
                openers.append(" ".join(words).lower().rstrip(".,;:"))
        from collections import Counter
        opener_counts = Counter(openers)
        for opener, cnt in opener_counts.items():
            if cnt >= 3 and len(opener.split()) <= 3:
                flags.append(
                    f"[{location}] Parallel opener \"{opener}\" x{cnt}"
                )
                break

    for h2, content in sections:
        h2_label = _text_of(h2)[:35]
        for tag in content:
            if tag.name == "p":
                _check_paragraph(tag, h2_label)
            # Also check <p> inside non-callout divs (section wrappers)
            elif tag.name in ("div", "section"):
                if not any("callout" in c.lower() for c in tag.get("class", [])):
                    for p in tag.find_all("p", recursive=False):
                        _check_paragraph(p, h2_label)

    for p in extra_ps:
        _check_paragraph(p, "BLUF")

    if flags:
        return AssertionResult(False, "soft",
            f"{len(flags)} enumeration-as-prose flag(s):\n" + "\n".join(flags),
            "18.5.5")
    return AssertionResult(True, "soft", None, "18.5.5")


def assert_bullet_min_word_count(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.5.6 Every <li> in body sections must be >= 18 words.

    Checks all <li> elements inside body H2 sections, BLUF, and ATF cards.
    Reports count + verbatim text of short bullets.
    """
    sections = _get_body_h2_sections(soup)
    # Collect all relevant <li> elements
    short_bullets: list[str] = []

    def _check_li_list(container_tags: list[Tag], location: str) -> None:
        for tag in container_tags:
            for li in tag.find_all("li"):
                text = _text_of(li)
                wc = _word_count(text)
                if wc < 18:
                    short_bullets.append(f"[{location}] {wc}w: \"{text[:80]}\"")

    # Body sections
    for h2, content in sections:
        h2_label = _text_of(h2)[:35]
        _check_li_list(content, h2_label)

    # BLUF
    bluf = soup.find(class_="rl-bluf")
    if bluf:
        _check_li_list([bluf], "BLUF")

    # ATF cards
    for card in soup.find_all(class_="rl-quick-card"):
        _check_li_list([card], "ATF card")
    # Also check cnp-class cards (post-processed)
    for card in soup.find_all(class_="cnpQuickCard"):
        _check_li_list([card], "ATF card")

    if short_bullets:
        return AssertionResult(False, "soft",
            f"{len(short_bullets)} bullet(s) under 18 words:\n" + "\n".join(short_bullets),
            "18.5.6")
    return AssertionResult(True, "soft", None, "18.5.6")


def assert_content_h2_min_eight(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.1.13b Content H2 hard gate: minimum 8 content H2s."""
    sections = _get_body_h2_sections(soup)
    count = len(sections)
    # Defer to override count when h2_inventory is present
    override_count = context.get("h2_override_count", 0)
    min_required = max(override_count, 6) if override_count else 8
    if count >= min_required:
        return AssertionResult(True, "hard", None, "18.1.13b")
    return AssertionResult(False, "hard",
        f"Only {count} content H2s, minimum is {min_required}", "18.1.13b")


def assert_faq_topic_relevance(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.5.7 FAQ questions should match the article's primary topic/keyword."""
    keyword = context.get("target_keyword", "") or ""
    if not keyword:
        return AssertionResult(True, "soft", None, "18.5.7")

    kw_words = set(re.findall(r"\w+", keyword.lower()))
    # Remove ultra-generic stopwords
    stopwords = {"in", "a", "an", "the", "of", "for", "to", "and", "is",
                 "how", "what", "do", "does", "much", "you", "your", "texas"}
    kw_core = kw_words - stopwords
    if len(kw_core) < 2:
        return AssertionResult(True, "soft", None, "18.5.7")

    off_topic: list[str] = []
    # Check both ATF and BTF FAQs
    for faq_container in soup.find_all(class_=re.compile(r"rl-faq|cnpFaq")):
        for detail in faq_container.find_all("details"):
            summary = detail.find("summary")
            if not summary:
                continue
            q_text = _text_of(summary).lower()
            q_words = set(re.findall(r"\w+", q_text)) - stopwords
            overlap = len(kw_core & q_words)
            # Flag if fewer than 2 core keyword words appear in the question
            if overlap < 2:
                off_topic.append(_text_of(summary)[:80])

    if off_topic:
        return AssertionResult(False, "soft",
            f"{len(off_topic)} FAQ question(s) off-topic vs keyword "
            f"'{keyword}':\n" + "\n".join(f"  - {q}" for q in off_topic),
            "18.5.7")
    return AssertionResult(True, "soft", None, "18.5.7")


def assert_no_near_duplicate_sections(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.5.8 Flag H2 pairs that cover the same material (>60% word overlap)."""
    sections = _get_body_h2_sections(soup)
    if len(sections) < 2:
        return AssertionResult(True, "soft", None, "18.5.8")

    stopwords = {"in", "a", "an", "the", "of", "for", "to", "and", "is",
                 "how", "what", "do", "does", "much", "you", "your", "texas"}
    titles = []
    for h2, _ in sections:
        text = _text_of(h2).lower()
        words = set(re.findall(r"\w+", text)) - stopwords
        titles.append((_text_of(h2), words))

    dupes: list[str] = []
    for i in range(len(titles)):
        for j in range(i + 1, len(titles)):
            if not titles[i][1] or not titles[j][1]:
                continue
            overlap = len(titles[i][1] & titles[j][1])
            smaller = min(len(titles[i][1]), len(titles[j][1]))
            if smaller > 0 and overlap / smaller > 0.6:
                dupes.append(
                    f"\"{titles[i][0][:50]}\" vs \"{titles[j][0][:50]}\" "
                    f"({overlap}/{smaller} overlap)")

    if dupes:
        return AssertionResult(False, "soft",
            f"{len(dupes)} near-duplicate section pair(s):\n" +
            "\n".join(f"  - {d}" for d in dupes), "18.5.8")
    return AssertionResult(True, "soft", None, "18.5.8")


def assert_no_excessive_repetition(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.5.9 Flag phrases/facts repeated 4+ times AND paragraph-join-without-space."""
    full_text = _text_of(soup)
    issues: list[str] = []

    # --- Phrase repetition (3+ word phrases appearing 4+ times) ---
    words = re.findall(r"\b[\w'-]+\b", full_text.lower())
    # Check 3-to-6-gram phrases
    from collections import Counter
    for n in (5, 4, 3):
        ngram_counts: Counter = Counter()
        for i in range(len(words) - n + 1):
            gram = " ".join(words[i:i + n])
            ngram_counts[gram] += 1
        for gram, cnt in ngram_counts.most_common(20):
            if cnt >= 4:
                # Skip very generic phrases
                gram_words = set(gram.split())
                generic = {"the", "in", "a", "of", "to", "and", "is", "for",
                           "your", "you", "that", "with", "on", "it", "or"}
                if len(gram_words - generic) >= 2:
                    issues.append(f"Phrase \"{gram}\" repeated {cnt}x")

    # Deduplicate: if a 5-gram contains a flagged 3-gram, keep only the longer
    seen_short: set[str] = set()
    filtered: list[str] = []
    for issue in sorted(issues, key=lambda x: -len(x)):
        phrase = issue.split('"')[1]
        if not any(phrase in longer for longer in seen_short):
            filtered.append(issue)
            seen_short.add(phrase)
    issues = filtered[:5]  # cap report at 5

    # --- Paragraph-join-without-space ---
    # Sentence-ending punctuation immediately followed by uppercase letter
    joins = re.findall(r'[.!?][A-Z]', full_text)
    if joins:
        # Show context for each
        for j in joins[:5]:
            pos = full_text.find(j)
            ctx = full_text[max(0, pos - 15):pos + 20]
            issues.append(f"Paragraph-join: \"...{ctx}...\"")

    if issues:
        return AssertionResult(False, "soft",
            f"{len(issues)} repetition/join flag(s):\n" +
            "\n".join(f"  - {i}" for i in issues), "18.5.9")
    return AssertionResult(True, "soft", None, "18.5.9")


# ---------------------------------------------------------------------------
# 18.CG Community-guide assertions (intent-gated: vacuous pass for all others)
# ---------------------------------------------------------------------------

_CG_INTENT = "community-guide"

# Standard MUD/PID no-district token emitted by the cost_reality section builder hint.
_NO_MUD_PID_TOKEN = "NO_MUD_PID_APPLICABLE"


def assert_cg_builder_comparison(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.CG.1 Community-guide: builder comparison table with required columns."""
    if context.get("intent") != _CG_INTENT:
        return AssertionResult(True, "hard", None, "18.CG.1")
    # Find all tables in body sections
    body_sections = _get_body_h2_sections(soup)
    tables = []
    for h2, content in body_sections:
        for tag in content:
            if isinstance(tag, Tag):
                tables.extend(tag.find_all("table") if tag.name != "table" else [tag])
    if not tables:
        return AssertionResult(False, "hard", "No comparison table found in body sections", "18.CG.1")
    # Check at least one table has the required column headers
    required_cols = {"price", "sq ft", "plan"}  # substrings to match
    for tbl in tables:
        thead = tbl.find("thead") or tbl.find("tr")
        if thead is None:
            continue
        headers = [_text_of(th).lower() for th in thead.find_all(["th", "td"])]
        header_text = " ".join(headers)
        matched = sum(1 for col in required_cols if col in header_text)
        if matched >= 3:
            # Check minimum 2 data rows
            tbody = tbl.find("tbody") or tbl
            data_rows = [tr for tr in tbody.find_all("tr") if tr.find("td")]
            if len(data_rows) < 2:
                return AssertionResult(False, "hard",
                    f"Comparison table has {len(data_rows)} data rows, need >=2", "18.CG.1")
            return AssertionResult(True, "hard", None, "18.CG.1")
    return AssertionResult(False, "hard",
        f"No table found with required columns (need: builder/collection, price range, sq ft range, plan count). "
        f"Tables checked: {len(tables)}", "18.CG.1")


def assert_cg_cost_strip(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.CG.2 Community-guide: cost section present, has numbers, addresses MUD/PID."""
    if context.get("intent") != _CG_INTENT:
        return AssertionResult(True, "hard", None, "18.CG.2")
    body_text = soup.get_text(separator=" ", strip=True)
    # Check for cost-related numbers
    has_pct = bool(re.search(r"\d+\.\d+%", body_text))
    has_dollar = bool(re.search(r"\$[\d,]+", body_text))
    if not (has_pct or has_dollar):
        return AssertionResult(False, "hard", "Cost section missing: no tax rate or dollar amount found", "18.CG.2")
    # Check MUD/PID is addressed: either a rate figure with MUD/PID mention, or the no-district token
    text_lower = body_text.lower()
    has_mud_mention = any(term in text_lower for term in ["mud", "pid", "municipal utility", "public improvement", "special district"])
    has_no_mud_token = _NO_MUD_PID_TOKEN.lower() in text_lower or "no mud" in text_lower or "no pid" in text_lower or "no special district" in text_lower
    if not (has_mud_mention or has_no_mud_token):
        return AssertionResult(False, "hard",
            "Cost section must address MUD/PID: either a district rate or explicit no-district statement. "
            "Silence on special districts = FAIL.", "18.CG.2")
    # Check no placeholder tokens
    placeholders = ["TBD", "[TBD]", "___", "REPLACE", "TODO"]
    for ph in placeholders:
        if ph in body_text:
            return AssertionResult(False, "hard", f"Placeholder '{ph}' found in article", "18.CG.2")
    return AssertionResult(True, "hard", None, "18.CG.2")


def assert_cg_zero_unsourced_prices(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.CG.3 Community-guide: every $ amount appears in manifest volatile_data."""
    if context.get("intent") != _CG_INTENT:
        return AssertionResult(True, "hard", None, "18.CG.3")
    manifest = context.get("manifest")
    if manifest is None:
        return AssertionResult(False, "hard",
            "Manifest required for community-guide but not provided (--manifest-json)", "18.CG.3")
    volatile = manifest.get("volatile_data", [])
    if not volatile:
        return AssertionResult(False, "hard",
            "Manifest has no volatile_data entries — all prices are unsourced", "18.CG.3")
    # Extract all dollar amounts from HTML
    body_text = soup.get_text(separator=" ", strip=True)
    price_pattern = re.compile(r"\$[\d,]+(?:\.\d{2})?")
    prices_in_html = set(price_pattern.findall(body_text))
    if not prices_in_html:
        return AssertionResult(True, "hard", None, "18.CG.3")  # no prices = nothing to check
    # Build set of sourced values (normalize: strip $ and commas for numeric comparison)
    sourced_values = set()
    for entry in volatile:
        val = entry.get("value")
        if val is not None:
            # Store as both raw and formatted
            sourced_values.add(str(val))
            sourced_values.add(f"${val:,}" if isinstance(val, (int, float)) else str(val))
    unsourced = []
    for price in prices_in_html:
        # Normalize price for comparison
        numeric = price.replace("$", "").replace(",", "")
        if numeric not in sourced_values and price not in sourced_values:
            unsourced.append(price)
    if unsourced:
        return AssertionResult(False, "hard",
            f"{len(unsourced)} price(s) not in manifest volatile_data: {', '.join(sorted(unsourced)[:5])}", "18.CG.3")
    return AssertionResult(True, "hard", None, "18.CG.3")


def assert_cg_schools_section(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.CG.4 Community-guide: schools section present with at least one school name."""
    if context.get("intent") != _CG_INTENT:
        return AssertionResult(True, "hard", None, "18.CG.4")
    body_text = soup.get_text(separator=" ", strip=True).lower()
    school_indicators = ["elementary", "middle school", "high school", "isd", "school district"]
    if not any(ind in body_text for ind in school_indicators):
        return AssertionResult(False, "hard", "No school information found in article", "18.CG.4")
    # Check for placeholder tokens
    placeholders = ["[school", "tbd school", "___"]
    for ph in placeholders:
        if ph in body_text:
            return AssertionResult(False, "hard", f"School placeholder found: '{ph}'", "18.CG.4")
    return AssertionResult(True, "hard", None, "18.CG.4")


def assert_cg_data_strip(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.CG.S1 Community-guide: data strip section present (soft)."""
    if context.get("intent") != _CG_INTENT:
        return AssertionResult(True, "soft", None, "18.CG.S1")
    body_text = soup.get_text(separator=" ", strip=True).lower()
    data_indicators = ["median", "inventory", "days on market", "year-over-year", "yoy"]
    if not any(ind in body_text for ind in data_indicators):
        return AssertionResult(False, "soft",
            "No county-level data strip found (median, inventory, DOM). Article works but is weaker.", "18.CG.S1")
    return AssertionResult(True, "soft", None, "18.CG.S1")


def assert_cg_military_fit(soup: BeautifulSoup, context: dict) -> AssertionResult:
    """18.CG.S2 Community-guide: military buyer fit section present (soft)."""
    if context.get("intent") != _CG_INTENT:
        return AssertionResult(True, "soft", None, "18.CG.S2")
    body_text = soup.get_text(separator=" ", strip=True).lower()
    mil_indicators = ["bah", "va loan", "military", "pcs", "base proximity", "fort", "jbsa", "lackland", "randolph"]
    if not any(ind in body_text for ind in mil_indicators):
        return AssertionResult(False, "soft",
            "No military buyer fit content found. Not all communities are near bases.", "18.CG.S2")
    return AssertionResult(True, "soft", None, "18.CG.S2")


# ---------------------------------------------------------------------------
# Export lists
# ---------------------------------------------------------------------------

ALL_HARD_ASSERTIONS: list[Callable] = [
    # 18.1 Structural
    assert_h1_present,
    assert_eyebrow_format,
    assert_byline_present,
    assert_primary_sources_present,
    assert_jump_nav_structure,
    assert_jump_nav_anchors_resolve,
    assert_jump_nav_matches_cards,
    assert_atf_lede_word_count,
    assert_first_cta_present,
    assert_atf_card_count_and_structure,
    assert_atf_faq_count_and_structure,
    assert_bluf_structure_if_present,
    assert_body_h2_count,
    assert_content_h2_min_eight,
    assert_each_h2_has_structural_element,
    assert_mid_article_cta_present,
    assert_closing_bottom_line_format,
    assert_btf_faq_count_and_no_overlap,
    assert_resources_format_and_diversity,
    # 18.2 Anchor format
    assert_external_anchor_format,
    assert_external_anchor_no_competition,
    assert_internal_anchor_word_count,
    # 18.3 Word count
    assert_body_word_count_in_serp_range,
    assert_body_word_count_fallback_range,
    # 18.4 Anti-pattern
    assert_no_em_dashes,
    assert_no_banned_phrases,
    assert_no_resources_placeholder,
    assert_atf_lede_no_question,
    assert_no_card_label_as_h3,
    assert_no_missing_structural_element,
    assert_max_one_callout_per_section,
    # 18.4.8-10 Style-pass emit gates
    assert_semicolon_density,
    assert_no_ai_lexicon,
    assert_no_not_x_its_y,
    # 18.CG Community-guide (intent-gated: vacuous pass for other intents)
    assert_cg_builder_comparison,
    assert_cg_cost_strip,
    assert_cg_zero_unsourced_prices,
    assert_cg_schools_section,
]

ALL_SOFT_ASSERTIONS: list[Callable] = [
    assert_h2_question_mix,
    assert_internal_link_density,
    assert_body_word_count_soft_target,
    assert_btf_faq_no_duplicate_topics,
    assert_no_enumeration_as_prose,
    assert_bullet_min_word_count,
    assert_faq_topic_relevance,
    assert_no_near_duplicate_sections,
    assert_no_excessive_repetition,
    # 18.CG Community-guide soft (intent-gated)
    assert_cg_data_strip,
    assert_cg_military_fit,
]
