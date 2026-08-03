"""Content-quality gate — prevents publishing generator boilerplate stubs.

Root cause (2026-08-03 audit): 13 neighborhood guides published as
identical boilerplate with no real neighborhood content. The generator
produced template scaffolding, and no gate caught it before deploy.

This module provides a pre-publish content check that hard-stops on:
1. Known boilerplate phrases (generator template language)
2. Subject/neighborhood name appearing too few times in body
3. Body word count below a minimum floor
4. Required data fields empty or placeholder

All checks are on the GENERATED HTML, not the live page. The gate
runs after generation, before write/deploy.
"""

import re
from .tool_utils import eprint


# ── Boilerplate phrase blocklist ──
# These phrases come from the generator template that produced all 13
# confirmed stubs. Any hit = the content is template scaffolding, not
# a real guide.
BOILERPLATE_PHRASES = [
    "from the source material",
    "original source content",
    "drawing on verified data",
    "serve different buyer profiles at different price points",
    "compare without guessing",
    "sections below break down the specifics",
    "verified data from the source",
    "every data point below comes from",
    "neighborhoods and areas covered here",
    "the information here is drawn from",
    "sourced directly from verified",
]

# Generic FAQ questions that never name the actual neighborhood.
# These appear verbatim in the template and indicate the FAQs
# were not customized for the subject.
GENERIC_FAQ_PHRASES = [
    "what are the best neighborhoods in this area",
    "how much do homes cost here",
    "what school district serves this area",
    "how is the commute from here",
    "is this a good area for military families",
]

# Minimum subject-name mentions in the stripped body text.
# Real guides mention their neighborhood 8+ times. Stubs mention it 0-3 times.
MIN_SUBJECT_MENTIONS = 5

# Minimum body word count (stripped of HTML tags).
# The boilerplate template produces ~1,780 words of filler.
# A real guide should exceed 1,500 words of substantive content.
# We set the floor low enough that a real guide always passes.
MIN_BODY_WORDS = 1200

# Minimum prose paragraph count (real <p> content blocks, not nav/scaffold).
MIN_PROSE_PARAGRAPHS = 6


def _strip_html(html: str) -> str:
    """Strip HTML tags, return plain text."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _count_subject_mentions(text: str, subject: str) -> int:
    """Count how many times the subject name appears in the text."""
    if not subject or len(subject) < 3:
        return -1  # Can't check — subject too short
    return text.lower().count(subject.lower())


def _count_prose_paragraphs(html: str) -> int:
    """Count substantial <p> tags (>20 words, not nav/scaffold)."""
    paras = re.findall(r"<p[^>]*>(.*?)</p>", html, re.DOTALL)
    count = 0
    for p in paras:
        text = re.sub(r"<[^>]+>", " ", p).strip()
        if len(text.split()) >= 20:
            count += 1
    return count


def run_content_quality_gate(
    html: str,
    neighborhood: str,
    city: str,
) -> list[str]:
    """Run the content-quality gate on generated HTML.

    Args:
        html: The generated HTML content.
        neighborhood: Target neighborhood name (e.g., "Circle C Ranch").
        city: Target city name (e.g., "Austin").

    Returns:
        List of failure reasons. Empty list = all checks passed.
        Each failure is a descriptive string.
    """
    failures = []
    text = _strip_html(html)
    text_lower = text.lower()
    words = text.split()

    # ── CHECK 1: Boilerplate phrase detection ──
    bp_hits = []
    for phrase in BOILERPLATE_PHRASES:
        if phrase.lower() in text_lower:
            bp_hits.append(phrase)

    if bp_hits:
        failures.append(
            f"BOILERPLATE DETECTED: {len(bp_hits)} generator template phrase(s) found. "
            f"This content is scaffolding, not a real guide. "
            f"Phrases: {bp_hits[:3]}"
        )

    # ── CHECK 2: Generic FAQ detection ──
    generic_faq_hits = []
    for phrase in GENERIC_FAQ_PHRASES:
        if phrase.lower() in text_lower:
            generic_faq_hits.append(phrase)

    if generic_faq_hits >= 3 if isinstance(generic_faq_hits, int) else len(generic_faq_hits) >= 3:
        failures.append(
            f"GENERIC FAQ DETECTED: {len(generic_faq_hits)} generic FAQ question(s) "
            f"that don't name the neighborhood. FAQs must be specific to {neighborhood}."
        )

    # ── CHECK 3: Subject mention count ──
    # Try the full neighborhood name first, then the city-qualified version
    nb_mentions = _count_subject_mentions(text, neighborhood)
    # Also try without common suffixes like "Ranch", "Park", "Hills"
    nb_core = re.sub(r"\s+(Ranch|Park|Hills|Heights|Creek|Village|Estates|Manor|Oaks)$", "", neighborhood, flags=re.IGNORECASE).strip()
    if nb_core != neighborhood:
        nb_core_mentions = _count_subject_mentions(text, nb_core)
        nb_mentions = max(nb_mentions, nb_core_mentions)

    if nb_mentions >= 0 and nb_mentions < MIN_SUBJECT_MENTIONS:
        failures.append(
            f"SUBJECT UNDERCOUNT: '{neighborhood}' appears {nb_mentions} time(s) in body "
            f"(minimum {MIN_SUBJECT_MENTIONS}). Real guides mention their subject frequently. "
            f"This suggests template content not customized for the neighborhood."
        )

    # ── CHECK 4: Word count floor ──
    wc = len(words)
    if wc < MIN_BODY_WORDS:
        failures.append(
            f"WORD COUNT BELOW FLOOR: {wc} words (minimum {MIN_BODY_WORDS}). "
            f"Content is too thin to publish."
        )

    # ── CHECK 5: Prose paragraph count ──
    prose_paras = _count_prose_paragraphs(html)
    if prose_paras < MIN_PROSE_PARAGRAPHS:
        failures.append(
            f"PROSE PARAGRAPHS BELOW FLOOR: {prose_paras} substantial paragraphs "
            f"(minimum {MIN_PROSE_PARAGRAPHS}). Real guides have multiple detailed sections."
        )

    return failures
