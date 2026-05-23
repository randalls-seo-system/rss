#!/usr/bin/env python3
"""Inject internal links from the anchor pool into assembled article HTML.

For each body H2 section intro paragraph: identifies injection points by
matching anchor pool entries against natural phrases in the text. Picks
1-3 links per section, applies anchor competition rule per spec 11.3,
writes unmatched opportunities to pending-links.json.

Usage:
    python3 inject-internal-links.py \\
        --site <slug> \\
        --html-input <path> \\
        --html-output <path> \\
        --pending-links-output <path>

See docs/article-spec.md Section 11 for anchor text rules.
See docs/v2-module-architecture.md "tools/inject-internal-links.py" for spec.
"""

import argparse
import json
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
MODULE_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(MODULE_DIR))

from bs4 import BeautifulSoup

from lib.anchor_pool import AnchorPool
from lib.tool_utils import eprint


# ---------------------------------------------------------------------------
# Section classification
# ---------------------------------------------------------------------------

# Markers in section id, class, or H2 text that indicate non-body sections.
_SKIP_MARKERS = frozenset({
    "bluf", "bottom-line", "bottomline", "resources", "resources-used",
    "faq", "faqs", "in-this-article", "toc", "jump-nav", "closing",
    "rl-quick-card", "rl-atf-faq",
})


def _is_body_h2_section(section) -> bool:
    """Return True if a <section> tag contains a body H2 (not BLUF, FAQ, etc.)."""
    h2 = section.find("h2")
    if not h2:
        return False

    h2_text = h2.get_text(strip=True).lower()
    section_id = (section.get("id") or "").lower()
    section_classes = " ".join(section.get("class", [])).lower()
    haystack = f"{section_id} {section_classes} {h2_text}"

    for marker in _SKIP_MARKERS:
        if marker in haystack:
            return False

    # Skip the closing "The Bottom Line" section
    if "bottom line" in h2_text:
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


MIN_WORD_GAP = 30  # Gate 2: minimum words between any two injected links


# ---------------------------------------------------------------------------
# HTML-safe link injection
# ---------------------------------------------------------------------------

_LINK_TAG_RE = re.compile(r"(<a\b[^>]*>.*?</a>)", flags=re.DOTALL | re.IGNORECASE)


def _inject_link_in_html(html_str: str, anchor_text: str, url: str) -> tuple[str, bool]:
    """Replace first occurrence of anchor_text with <a href> in html_str.

    Only replaces in text segments OUTSIDE existing <a> tags.
    Uses word-boundary matching (case-insensitive).

    Returns:
        (modified_html, was_injected)
    """
    segments = _LINK_TAG_RE.split(html_str)
    pattern = re.compile(r"\b" + re.escape(anchor_text) + r"\b", re.IGNORECASE)

    replaced = False
    rebuilt = []
    for seg in segments:
        if replaced or _LINK_TAG_RE.match(seg):
            rebuilt.append(seg)
            continue
        match = pattern.search(seg)
        if match:
            matched_text = seg[match.start() : match.end()]
            link = f'<a href="{url}">{matched_text}</a>'
            seg = seg[: match.start()] + link + seg[match.end() :]
            replaced = True
        rebuilt.append(seg)

    return "".join(rebuilt), replaced


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
) -> list[dict]:
    """Find anchor pool candidates whose anchor text appears in the text.

    Applies the competition rule: if anchor_text is in internal_keywords
    but has no matching anchor pool entry, skip it (let the linking
    strategy own that keyword).

    Returns list of {anchor_text, url, score} sorted by score descending.
    """
    candidates = pool.candidates_for_topic(topic, max=15, exclude_post_id=exclude_post_id)
    if not candidates:
        return []

    text_lower = text.lower()
    matches = []

    for cand in candidates:
        if cand.url in used_urls:
            continue

        anchor = cand.anchor_text
        anchor_lower = anchor.lower()

        # Word count check per spec: internal anchors must be 2-5 words
        word_count = len(anchor.split())
        if word_count < 2 or word_count > 5:
            continue

        # Anchor text diversity: same text at most once per article
        if used_anchors_global and anchor_lower in used_anchors_global:
            continue

        # Check if anchor text appears naturally in the paragraph
        pattern = re.compile(r"\b" + re.escape(anchor_lower) + r"\b", re.IGNORECASE)
        if not pattern.search(text):
            continue

        # Competition rule: if this phrase is claimed by a DIFFERENT internal
        # keyword (i.e., it's in internal_keywords_set), allow it only if
        # the anchor pool DID return this candidate (which it did — we're
        # iterating candidates). The competition rule blocks phrases that are
        # in internal_keywords but have NO anchor pool match for this topic.
        # Since we only iterate pool candidates here, competition is satisfied.

        matches.append({
            "anchor_text": anchor,
            "url": cand.url,
            "score": cand.topic_match_score,
        })

    # Prefer higher score, break ties by longer anchor text (more specific)
    matches.sort(key=lambda m: (-m["score"], -len(m["anchor_text"])))

    # Deduplicate by URL
    seen_urls = set()
    deduped = []
    for m in matches:
        if m["url"] not in seen_urls:
            deduped.append(m)
            seen_urls.add(m["url"])
        if len(deduped) >= max_candidates:
            break

    return deduped


def _detect_pending_links(
    h2_text: str,
    paragraph_text: str,
    pool: AnchorPool,
    internal_keywords: set[str],
    injected_count: int,
    article_context: str,
) -> list[dict]:
    """Detect topical phrases that should be linked but have no anchor pool match.

    Checks for internal keywords appearing in the text that weren't linked.
    Also flags sections with zero injected links as potential content gaps.
    """
    pending = []

    # Check internal keywords appearing in text but not linked
    text_lower = paragraph_text.lower()
    for kw in internal_keywords:
        pattern = re.compile(r"\b" + re.escape(kw) + r"\b", re.IGNORECASE)
        if pattern.search(text_lower):
            # This keyword appears in text — check if pool has a candidate
            candidates = pool.candidates_for_topic(kw, max=1)
            if not candidates:
                pending.append({
                    "article_url": article_context,
                    "section_h2": h2_text,
                    "phrase": kw,
                    "needed_destination_topic": kw,
                })

    # If zero links were injected in this section, flag the H2 topic itself
    if injected_count == 0 and h2_text:
        pending.append({
            "article_url": article_context,
            "section_h2": h2_text,
            "phrase": h2_text,
            "needed_destination_topic": f"Content covering: {h2_text}",
        })

    return pending


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
    parser.add_argument("--article-url", default="", help="Article URL for pending-links context")
    parser.add_argument("--exclude-post-id", type=int, default=None, help="Exclude this post ID from anchor pool (self-link prevention)")
    args = parser.parse_args()

    # Load input HTML
    input_path = Path(args.html_input)
    if not input_path.exists():
        eprint(f"Error: HTML input file not found: {input_path}")
        sys.exit(1)

    try:
        input_html = input_path.read_text()
    except Exception as e:
        eprint(f"Error reading HTML input: {e}")
        sys.exit(1)

    if not input_html.strip():
        eprint("Error: HTML input file is empty")
        sys.exit(1)

    # Load anchor pool
    pool = AnchorPool(args.site)
    if not pool._destinations:
        eprint(f"Anchor pool empty for site {args.site}; no links injected")
        Path(args.html_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.html_output).write_text(input_html)
        Path(args.pending_links_output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.pending_links_output).write_text("[]")
        sys.exit(0)

    internal_keywords = pool.get_internal_keywords_set()
    eprint(f"[inject-links] Loaded anchor pool: {len(pool._destinations)} destinations, "
           f"{len(internal_keywords)} internal keywords")

    # Parse HTML
    try:
        soup = BeautifulSoup(input_html, "html.parser")
    except Exception as e:
        eprint(f"Error: Malformed HTML input: {e}")
        sys.exit(1)

    all_pending: list[dict] = []
    total_injected = 0
    used_urls_global: set[str] = set()
    used_anchors_global: set[str] = set()
    article_context = args.article_url
    exclude_post_id = args.exclude_post_id

    # Gate 1: compute article word count and cap
    article_wc = len(soup.get_text(separator=" ").split())
    max_links = _max_links_for_word_count(article_wc)
    eprint(f"[inject-links] Article word count: {article_wc}, link cap: {max_links}")

    # Gate 2: track word position of last injection for spacing
    last_link_word_pos: int | None = None

    # Compute cumulative word offsets per section for spacing checks
    _section_word_offsets: dict[int, int] = {}
    _running_wc = 0
    for sec in soup.find_all("section"):
        _section_word_offsets[id(sec)] = _running_wc
        _running_wc += len(sec.get_text(separator=" ").split())

    # Process each body H2 section
    sections = soup.find_all("section")
    body_sections = [s for s in sections if _is_body_h2_section(s)]
    eprint(f"[inject-links] Found {len(body_sections)} body H2 sections to process")

    for section in body_sections:
        # Gate 1: stop if cap reached
        if total_injected >= max_links:
            eprint(f"[inject-links] Link cap ({max_links}) reached, stopping")
            break

        h2 = section.find("h2")
        h2_text = h2.get_text(strip=True) if h2 else ""

        # Find the intro paragraph (first <p> in section)
        intro_p = section.find("p")
        if not intro_p:
            eprint(f"[inject-links] Skipping section (no <p>): {h2_text[:50]}")
            continue

        paragraph_text = intro_p.get_text()
        paragraph_html = str(intro_p)

        # Gate 1: limit candidates to remaining budget
        remaining_budget = max_links - total_injected
        candidates_limit = min(2, remaining_budget)

        # Find matching candidates
        used_urls_section: set[str] = set()
        matches = _find_matching_candidates(
            paragraph_text, pool, h2_text,
            used_urls_global | used_urls_section,
            internal_keywords,
            max_candidates=candidates_limit,
            exclude_post_id=exclude_post_id,
            used_anchors_global=used_anchors_global,
        )

        # Gate 2: filter candidates by word spacing
        section_offset = _section_word_offsets.get(id(section), 0)
        para_words = paragraph_text.split()
        spaced_matches = []
        local_last_pos = last_link_word_pos
        for m in matches:
            # Find approximate word position of anchor in paragraph
            anchor_lower = m["anchor_text"].lower()
            para_lower = paragraph_text.lower()
            char_pos = para_lower.find(anchor_lower)
            if char_pos < 0:
                spaced_matches.append(m)
                continue
            word_pos_in_para = len(paragraph_text[:char_pos].split())
            global_word_pos = section_offset + word_pos_in_para

            if local_last_pos is not None and (global_word_pos - local_last_pos) < MIN_WORD_GAP:
                eprint(f"[inject-links]   Spacing skip: '{m['anchor_text']}' only {global_word_pos - local_last_pos}w from prev link")
                continue
            spaced_matches.append(m)
            local_last_pos = global_word_pos + len(m["anchor_text"].split())
        matches = spaced_matches

        # Inject links into the paragraph HTML
        section_injected = 0
        modified_html = paragraph_html
        for m in matches:
            new_html, was_injected = _inject_link_in_html(
                modified_html, m["anchor_text"], m["url"]
            )
            if was_injected:
                modified_html = new_html
                used_urls_section.add(m["url"])
                section_injected += 1
                eprint(f"[inject-links]   {h2_text[:40]}: injected '{m['anchor_text']}' → {m['url']}")

        # Replace the paragraph in the soup if we injected anything
        if section_injected > 0:
            new_p = BeautifulSoup(modified_html, "html.parser")
            intro_p.replace_with(new_p)
            used_urls_global |= used_urls_section
            # Track used anchor texts for article-wide diversity
            for m in matches[:section_injected]:
                used_anchors_global.add(m["anchor_text"].lower())
            total_injected += section_injected
            # Gate 2: update last link position
            last_link_word_pos = local_last_pos

        # Detect pending links for this section
        pending = _detect_pending_links(
            h2_text, paragraph_text, pool,
            internal_keywords, section_injected, article_context,
        )
        all_pending.extend(pending)

    eprint(f"[inject-links] Done: {total_injected} links injected, "
           f"{len(all_pending)} pending link opportunities")

    # Write outputs
    Path(args.html_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.html_output).write_text(str(soup))

    Path(args.pending_links_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.pending_links_output).write_text(
        json.dumps(all_pending, indent=2, ensure_ascii=False)
    )


if __name__ == "__main__":
    main()
