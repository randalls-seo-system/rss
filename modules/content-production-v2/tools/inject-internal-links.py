#!/usr/bin/env python3
"""Inject internal links from the anchor pool into assembled article HTML.

For each body paragraph (between H2 headings, outside restricted zones):
identifies injection points by matching anchor pool entries against
natural phrases in the text. Applies word-boundary matching, zone guards,
generic-anchor filtering, and per-article/per-paragraph caps.

Usage:
    python3 inject-internal-links.py \\
        --site <slug> \\
        --html-input <path> \\
        --html-output <path> \\
        --pending-links-output <path>

See docs/article-spec.md Section 11 for anchor text rules.
"""

import argparse
import json
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
MODULE_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(MODULE_DIR))

from bs4 import BeautifulSoup, NavigableString, Tag

from lib.anchor_pool import AnchorPool
from lib.linker_core import inject_link_in_paragraph as _inject_link_in_paragraph
from lib.linker_core import is_restricted_zone
from lib.tool_utils import eprint


# ---------------------------------------------------------------------------
# Generic anchor blocklist (shared with the strip classifier — Fix 3)
# These 2-word phrases pass the content-word filter but are too generic
# for internal linking. They produce garbage anchors on every mention.
# ---------------------------------------------------------------------------

_GENERIC_ANCHOR_BLOCKLIST = frozenset({
    "closing costs", "down payment", "credit score", "interest rate",
    "home loan", "home loans", "mortgage insurance", "loan program",
    "loan programs", "loan type", "loan types", "monthly payment",
    "monthly payments", "purchase price", "credit report", "credit reports",
    "loan amount", "loan officer", "real estate", "interest rates",
    "editorial team", "lenders network",
})

# Byline / non-content strings that should never be anchors (Fix 4)
_BYLINE_BLOCKLIST = frozenset({
    "editorial team", "the lenders network team", "lenders network team",
    "tln editorial team", "about us", "contact us",
})


# ---------------------------------------------------------------------------
# Single-word trigger whitelist and drop log (Defect 2 fix)
# ---------------------------------------------------------------------------

_WHITELIST_PATH = TOOLS_DIR / "single-word-whitelist.txt"


def _load_single_word_whitelist() -> frozenset:
    """Load approved single-word triggers from whitelist file.

    File format: one word per line, # comments allowed, blank lines skipped.
    If the file does not exist, returns empty (all single-word triggers blocked).
    """
    if not _WHITELIST_PATH.exists():
        return frozenset()
    lines = _WHITELIST_PATH.read_text().strip().splitlines()
    return frozenset(
        line.strip().lower() for line in lines
        if line.strip() and not line.startswith("#")
    )


_SINGLE_WORD_WHITELIST: frozenset = _load_single_word_whitelist()

# Accumulates dropped triggers during a run for summary logging
_dropped_triggers: list[tuple[str, str, str]] = []


# ---------------------------------------------------------------------------
# Zone guard: unified restricted-zone check (Fix 1 refactor)
# ---------------------------------------------------------------------------

_FAQ_H2_PATTERN = re.compile(
    r"frequently\s+asked|faqs?\b|common\s+questions", re.IGNORECASE
)

_SKIP_H2_PATTERN = re.compile(
    r"bottom\s+line(?!\s+up\s+front)|resources?\s+used|in\s+this\s+article|"
    r"resources\b",
    re.IGNORECASE,
)


def _is_in_restricted_zone(element) -> bool:
    """Delegate to shared lib. Preserves backward-compatible function name."""
    return is_restricted_zone(element, {
        "prefixes": ["tln", "rl-"],
        "extra_classes": ["rl-resources"],
    })


def _is_body_paragraph(para, first_body_h2_offset: int, soup_str: str) -> bool:
    """Return True if a <p> element is in a valid body injection zone."""
    # Must not be in a restricted zone
    if _is_in_restricted_zone(para):
        return False

    # Must be after the first body H2 (not in ATF)
    # Use string position as proxy
    para_str = str(para)
    para_offset = soup_str.find(para_str)
    if para_offset < first_body_h2_offset:
        return False

    # Must not be inside a FAQ-headed section
    # Walk up to find the nearest preceding H2
    prev = para.find_previous(["h2", "h3"])
    if prev:
        h_text = prev.get_text(strip=True)
        if _FAQ_H2_PATTERN.search(h_text):
            return False
        if _SKIP_H2_PATTERN.search(h_text):
            return False

    return True


# ---------------------------------------------------------------------------
# Gate 1: Global per-article link cap
# ---------------------------------------------------------------------------

def _max_links_for_word_count(wc: int) -> int:
    """Cap total injected links by article word count."""
    if wc < 400:
        return 3
    if wc < 800:
        return 5
    if wc < 1500:
        return 8
    if wc < 2500:
        return 11
    return 14


MAX_LINKS_PER_PARAGRAPH = 2

# Stopwords for subphrase quality filter
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "in", "on", "at", "to", "for", "of", "with", "by", "from", "as",
    "and", "or", "but", "not", "no", "if", "it", "its", "do", "does",
    "did", "has", "have", "had", "can", "could", "will", "would", "shall",
    "should", "may", "might", "must", "that", "this", "these", "those",
    "what", "which", "who", "whom", "how", "when", "where", "why",
    "you", "your", "i", "my", "we", "our", "they", "their", "up",
})


def _has_content_words(phrase: str, min_count: int = 2) -> bool:
    """Return True if the phrase has at least min_count non-stopword content words."""
    words = phrase.lower().split()
    content_words = [w for w in words if w not in _STOPWORDS]
    return len(content_words) >= min_count


def _is_generic_anchor(anchor: str) -> bool:
    """Return True if anchor text is in the generic blocklist or is a byline string."""
    lower = anchor.lower().strip()
    if lower in _GENERIC_ANCHOR_BLOCKLIST:
        return True
    if lower in _BYLINE_BLOCKLIST:
        return True
    return False


# _inject_link_in_paragraph is now imported from lib.linker_core
# _SKIP_PARENT_TAGS is defined there as well


# ---------------------------------------------------------------------------
# URL normalization (Fix 5)
# ---------------------------------------------------------------------------

_WPE_STAGING_DOMAINS = frozenset({
    "lrgrealtyblogs.wpenginepowered.com",
    "lrgrealtyblogs.wpengine.com",
})


def _normalize_link_url(url: str, site_domain: str) -> str:
    """Convert absolute URLs to relative paths for the target site."""
    if not url:
        return url
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.netloc.lower().lstrip("www.")

    # Match site domain or known staging domains
    if host == site_domain.lower().lstrip("www.") or host in _WPE_STAGING_DOMAINS:
        return parsed.path or "/"
    return url


# ---------------------------------------------------------------------------
# Candidate matching
# ---------------------------------------------------------------------------

def _find_matching_candidates(
    text: str,
    pool: AnchorPool,
    topic: str,
    used_urls: set[str],
    internal_keywords: set[str],
    max_candidates: int = 2,
    exclude_post_id: int | None = None,
    used_anchors_global: set[str] | None = None,
    site_domain: str = "",
) -> list[dict]:
    """Find anchor pool candidates whose anchor text appears in the text."""
    matches = []

    for dest in pool._destinations:
        if exclude_post_id is not None and dest.get("id") == exclude_post_id:
            continue

        raw_url = dest.get("url", "")
        url = _normalize_link_url(raw_url, site_domain)
        if url in used_urls:
            continue

        anchors = dest.get("anchors", [])
        primary_kw = dest.get("primary_keyword", "")

        anchor_options = []
        seen = set()
        for a in anchors:
            al = a.lower()
            if al in seen:
                continue
            wc = len(a.split())
            if wc < 2:
                if al not in _SINGLE_WORD_WHITELIST:
                    _dropped_triggers.append((a, raw_url, "single-word"))
                    continue
            if wc > 5:
                continue
            anchor_options.append(a)
            seen.add(al)
        if primary_kw and primary_kw.lower() not in seen:
            pk_wc = len(primary_kw.split())
            if pk_wc < 2 and primary_kw.lower() not in _SINGLE_WORD_WHITELIST:
                _dropped_triggers.append((primary_kw, raw_url, "single-word-primary"))
            elif 2 <= pk_wc <= 5:
                anchor_options.append(primary_kw)

        if not anchor_options:
            continue

        best_match = None
        for opt in anchor_options:
            if not _has_content_words(opt, min_count=2):
                continue
            if _is_generic_anchor(opt):
                continue
            if used_anchors_global and opt.lower() in used_anchors_global:
                continue
            pattern = re.compile(r"\b" + re.escape(opt) + r"\b", re.IGNORECASE)
            if pattern.search(text):
                content_count = len([w for w in opt.lower().split() if w not in _STOPWORDS])
                if best_match is None or content_count > best_match[0] or (content_count == best_match[0] and len(opt) > best_match[1]):
                    best_match = (content_count, len(opt), opt)

        if best_match is None:
            continue

        is_primary = best_match[2].lower() == primary_kw.lower()
        score = best_match[0] + (10 if is_primary else 0)

        matches.append({
            "anchor_text": best_match[2],
            "url": url,
            "score": score,
        })

    matches.sort(key=lambda m: (-m["score"], -len(m["anchor_text"])))

    seen_urls: set[str] = set()
    seen_anchors: set[str] = set()
    deduped = []
    for m in matches:
        if m["url"] in seen_urls:
            continue
        if m["anchor_text"].lower() in seen_anchors:
            continue
        deduped.append(m)
        seen_urls.add(m["url"])
        seen_anchors.add(m["anchor_text"].lower())
        if len(deduped) >= max_candidates:
            break

    return deduped


# ---------------------------------------------------------------------------
# Find first body H2 position (for ATF detection)
# ---------------------------------------------------------------------------

def _find_first_body_h2_offset(soup, soup_str: str) -> int:
    """Find the string offset of the first body H2 (not BLUF/FAQ/resources)."""
    for h2 in soup.find_all("h2"):
        h2_text = h2.get_text(strip=True)
        # Skip BLUF
        if "bottom line up front" in h2_text.lower():
            continue
        # Skip FAQ
        if _FAQ_H2_PATTERN.search(h2_text):
            continue
        # Skip resources/closing
        if _SKIP_H2_PATTERN.search(h2_text):
            continue
        # This is a body H2
        h2_str = str(h2)
        offset = soup_str.find(h2_str)
        if offset >= 0:
            return offset
    # Fallback: treat everything as body (conservative — may inject in ATF)
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Inject internal links from anchor pool into article HTML (spec Section 11)"
    )
    parser.add_argument("--site", required=True, help="Site slug (e.g., lrg, valn)")
    parser.add_argument("--html-input", required=True, help="Path to assembled article HTML")
    parser.add_argument("--html-output", required=True, help="Path to write linked HTML")
    parser.add_argument("--pending-links-output", required=True, help="Path to write pending-links JSON")
    parser.add_argument("--target-keyword", default="", help="Article target keyword (broadens candidate matching)")
    parser.add_argument("--article-url", default="", help="Article URL for pending-links context")
    parser.add_argument("--exclude-post-id", type=int, default=None, help="Exclude this post ID from anchor pool (self-link prevention)")
    args = parser.parse_args()

    # Load input HTML
    input_path = Path(args.html_input)
    if not input_path.exists():
        eprint(f"Error: HTML input file not found: {input_path}")
        sys.exit(1)

    input_html = input_path.read_text()
    if not input_html.strip():
        eprint("Error: HTML input file is empty")
        sys.exit(1)

    # Load anchor pool
    pool = AnchorPool(args.site)
    if not pool._destinations:
        eprint(f"Anchor pool empty for site {args.site}; no links injected")
        Path(args.html_output).write_text(input_html)
        Path(args.pending_links_output).write_text("[]")
        sys.exit(0)

    # Load site domain for URL normalization
    try:
        from lib.site_config import load_site_config
        site_config = load_site_config(args.site)
        site_domain = site_config.get("SITE_DOMAIN", "")
    except Exception:
        site_domain = ""

    internal_keywords = pool.get_internal_keywords_set()
    eprint(f"[inject-links] Loaded anchor pool: {len(pool._destinations)} destinations, "
           f"{len(internal_keywords)} internal keywords")

    # Parse HTML
    soup = BeautifulSoup(input_html, "html.parser")
    soup_str = str(soup)

    total_injected = 0
    used_urls_global: set[str] = set()
    used_anchors_global: set[str] = set()
    target_keyword = args.target_keyword
    exclude_post_id = args.exclude_post_id

    # DUP_TARGET prevention: pre-populate used_urls with existing internal links
    for existing_a in soup.find_all("a", href=True):
        href = existing_a["href"]
        if href.startswith("/") and not href.startswith("//"):
            used_urls_global.add(href.rstrip("/") + "/")
            used_urls_global.add(href.rstrip("/"))
        elif "thelendersnetwork.com" in href:
            from urllib.parse import urlparse
            path = urlparse(href).path
            used_urls_global.add(path.rstrip("/") + "/")
            used_urls_global.add(path.rstrip("/"))
    eprint(f"[inject-links] Pre-existing internal link targets: {len(used_urls_global)}")

    # Gate 1: compute article word count and cap
    article_wc = len(soup.get_text(separator=" ").split())
    max_links = _max_links_for_word_count(article_wc)
    eprint(f"[inject-links] Article word count: {article_wc}, link cap: {max_links}")

    # Find first body H2 offset for ATF detection
    first_body_h2_offset = _find_first_body_h2_offset(soup, soup_str)
    eprint(f"[inject-links] First body H2 at offset: {first_body_h2_offset}")

    # ---------------------------------------------------------------------------
    # Fix 1: Unified paragraph scanning (works with or without <section> wrappers)
    # Find ALL <p> tags in the document, filter by zone guard, inject into valid ones.
    # ---------------------------------------------------------------------------

    all_paragraphs = soup.find_all("p")
    body_paragraphs = [
        p for p in all_paragraphs
        if _is_body_paragraph(p, first_body_h2_offset, soup_str)
    ]
    eprint(f"[inject-links] Found {len(body_paragraphs)} valid body paragraphs "
           f"(of {len(all_paragraphs)} total)")

    for para in body_paragraphs:
        if total_injected >= max_links:
            eprint(f"[inject-links] Link cap ({max_links}) reached, stopping")
            break

        paragraph_text = para.get_text()

        # Skip very short paragraphs
        if len(paragraph_text.split()) < 10:
            continue

        # Gate 2: per-paragraph cap
        remaining_budget = max_links - total_injected
        candidates_limit = min(MAX_LINKS_PER_PARAGRAPH, remaining_budget)

        # Find the nearest preceding H2 for topic context
        prev_h2 = para.find_previous("h2")
        h2_text = prev_h2.get_text(strip=True) if prev_h2 else ""
        pool_topic = target_keyword if target_keyword else h2_text

        matches = _find_matching_candidates(
            paragraph_text, pool, pool_topic,
            used_urls_global,
            internal_keywords,
            max_candidates=candidates_limit,
            exclude_post_id=exclude_post_id,
            used_anchors_global=used_anchors_global,
            site_domain=site_domain,
        )

        para_injected = 0
        injected_matches = []
        for m in matches:
            was_injected = _inject_link_in_paragraph(
                para, m["anchor_text"], m["url"]
            )
            if was_injected:
                used_urls_global.add(m["url"])
                para_injected += 1
                injected_matches.append(m)
                eprint(f"[inject-links]   [{h2_text[:30]}] '{m['anchor_text']}' → {m['url']}")

        if para_injected > 0:
            total_injected += para_injected
            for m in injected_matches:
                used_anchors_global.add(m["anchor_text"].lower())

    eprint(f"[inject-links] Done: {total_injected} links injected")

    if _dropped_triggers:
        unique_drops = {}
        for trigger, dest_url, reason in _dropped_triggers:
            key = (trigger.lower(), dest_url)
            if key not in unique_drops:
                unique_drops[key] = (trigger, dest_url, reason)
        eprint(f"[inject-links] Dropped {len(unique_drops)} unique single-word trigger(s) "
               f"({len(_dropped_triggers)} evaluations):")
        for trigger, dest_url, reason in unique_drops.values():
            eprint(f"[inject-links]   DROPPED '{trigger}' ({dest_url}): {reason}")

    # Write outputs
    Path(args.html_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.html_output).write_text(str(soup))

    Path(args.pending_links_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.pending_links_output).write_text("[]")


if __name__ == "__main__":
    main()
