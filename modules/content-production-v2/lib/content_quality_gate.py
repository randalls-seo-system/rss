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

    # ── CHECK 0: Editorial marker / placeholder detection (HARD FAIL) ──
    # Bracketed editorial markers in body HTML = content is not ready to
    # deploy. Catches [FLAG, [TODO, [FIXME, [NOTE TO, [REVIEW, [PLACEHOLDER,
    # XXX tokens. Excludes matches inside href attributes.
    _marker_patterns = [
        (r'\[FLAG\b', '[FLAG'),
        (r'\[TODO\b', '[TODO'),
        (r'\[FIXME\b', '[FIXME'),
        (r'\[NOTE\s+TO\b', '[NOTE TO'),
        (r'\[REVIEW\b', '[REVIEW'),
        (r'\[PLACEHOLDER\b', '[PLACEHOLDER'),
        (r'\[INSERT\b', '[INSERT'),
        (r'\[TBD\b', '[TBD'),
    ]
    # Strip href attributes before checking so URLs with random strings
    # don't false-positive (e.g., a slug containing "xxx")
    _text_no_hrefs = re.sub(r'href="[^"]*"', '', html)
    _text_no_hrefs_stripped = _strip_html(_text_no_hrefs)
    marker_hits = []
    for pattern, label in _marker_patterns:
        if re.search(pattern, _text_no_hrefs_stripped, re.IGNORECASE):
            marker_hits.append(label)
    # XXX check: only flag standalone XXX (word boundary), not inside URLs
    if re.search(r'\bXXX\b', _text_no_hrefs_stripped):
        marker_hits.append('XXX')

    if marker_hits:
        failures.append(
            f"EDITORIAL MARKER IN CONTENT: {marker_hits}. "
            f"Review notes, placeholders, and TODO markers must be removed "
            f"before deploy. Move verification notes to the fact-check report."
        )

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

    # ── CHECK 6: Self-contradiction (body asserts X, FAQ denies X) ──
    # Extract FAQ answers and body text separately, look for direct contradictions
    # Works with both nh-faq (neighborhood format) and rl-faq / details (article format)
    faq_section = re.search(r'<div class="(?:nh-faq|rl-faq)">(.*?)</div>', html, re.DOTALL)
    if not faq_section:
        # Fallback: look for any <details> block cluster (FAQ section without wrapper class)
        details_blocks = re.findall(r'<details>.*?</details>', html, re.DOTALL)
        if len(details_blocks) >= 3:
            faq_section = type('obj', (object,), {'group': lambda self, n: ' '.join(details_blocks)})()

    if faq_section:
        faq_text = _strip_html(faq_section.group(1)).lower()
        body_text = text_lower

        # Pattern: body says "X heritage/tradition/founded by" and FAQ says "No... not X"
        contradiction_patterns = [
            # (body_claim_pattern, faq_denial_pattern, description)
            (r'german\s+(?:settlers?|heritage|tradition|immigrants?|founded)',
             r'(?:no|not)\s+.*german', "German heritage claimed in body but denied in FAQ"),
            (r'spanish\s+(?:settlers?|heritage|tradition|founded)',
             r'(?:no|not)\s+.*spanish', "Spanish heritage claimed in body but denied in FAQ"),
            (r'(?:founded|established|settled)\s+(?:by|in)\s+\d{4}',
             r'(?:no|not)\s+.*founded', "Founding narrative in body contradicted in FAQ"),
        ]
        for body_pat, faq_pat, desc in contradiction_patterns:
            if re.search(body_pat, body_text) and re.search(faq_pat, faq_text):
                failures.append(
                    f"SELF-CONTRADICTION: {desc}. "
                    f"The body and FAQ contradict each other on the same topic."
                )

    return failures


def run_ymyl_language_check(html: str) -> list[str]:
    """Advisory check for YMYL language violations in distressed-homeowner content.

    Flags tax, legal, and foreclosure framing that states outcomes as fact
    rather than using required qualified language. Advisory — surfaces in
    the report but does not hard-fail the pipeline.

    Returns:
        List of advisory findings. Empty list = clean.
    """
    text = _strip_html(html)
    text_lower = text.lower()
    findings = []

    # ── TAX LANGUAGE: forgiven debt stated as categorically taxable ──
    # Required framing: "may create taxable income; other exclusions may apply"
    # The insolvency and bankruptcy exclusions are permanent (IRS Topic 431).
    tax_unqualified_patterns = [
        (r'forgiven\s+debt\s+is\s+(?:now\s+)?taxable', "forgiven debt is [now] taxable"),
        (r'now\s+taxable', "now taxable"),
        (r'will\s+owe\s+taxes?\s+on\s+the\s+forgiven', "will owe taxes on the forgiven amount"),
        (r'no\s+longer\s+(?:excluded|applies|available|in\s+effect)', "no longer excluded/applies"),
        (r'(?:the|this)\s+(?:exclusion|exemption)\s+(?:has\s+)?(?:expired|ended|no\s+longer)',
         "the exclusion expired/ended/no longer..."),
        (r'debt\s+is\s+(?:now\s+)?(?:fully\s+)?taxable\s+income', "debt is taxable income"),
        (r'forgiven\s+(?:mortgage\s+)?debt\s+(?:is|will\s+be)\s+treated\s+as\s+(?:ordinary\s+)?income',
         "forgiven debt is/will be treated as income"),
        (r'you\s+(?:will|are\s+going\s+to)\s+owe\s+taxes?\s+on', "you will owe taxes on"),
    ]
    for pattern, desc in tax_unqualified_patterns:
        matches = re.findall(pattern, text_lower)
        if matches:
            # Check if the qualifier phrase appears nearby (within 200 chars)
            qualifier = "may create taxable income"
            qualifier2 = "other exclusions may apply"
            for m in re.finditer(pattern, text_lower):
                start = max(0, m.start() - 200)
                end = min(len(text_lower), m.end() + 200)
                context = text_lower[start:end]
                if qualifier not in context and qualifier2 not in context:
                    findings.append(
                        f"TAX LANGUAGE: '{desc}' stated without qualifier. "
                        f"Required framing: 'may create taxable income; other exclusions may apply.' "
                        f"Insolvency and bankruptcy exclusions are permanent (IRS Topic 431)."
                    )
                    break  # One finding per pattern is enough

    # ── FORECLOSURE FRAMING: Texas leads without raw-count qualifier ──
    fc_patterns = [
        (r'texas\s+leads?\s+(?:the\s+)?(?:nation|country|u\.?s\.?)\s+in\s+foreclosures?',
         "Texas leads the nation in foreclosures"),
        (r'texas\s+(?:has|had)\s+the\s+(?:most|highest)\s+foreclosures?',
         "Texas has the most/highest foreclosures"),
        (r'texas\s+is\s+(?:#\s*1|number\s+one|first)\s+(?:in|for)\s+foreclosures?',
         "Texas is #1 in foreclosures"),
    ]
    for pattern, desc in fc_patterns:
        if re.search(pattern, text_lower):
            # Check for qualifier within 200 chars
            qualifiers = ["raw count", "by count", "by volume", "by raw",
                          "not.*rate", "rate was"]
            match = re.search(pattern, text_lower)
            if match:
                start = max(0, match.start() - 100)
                end = min(len(text_lower), match.end() + 200)
                context = text_lower[start:end]
                has_qualifier = any(q in context for q in qualifiers[:4])
                if not has_qualifier:
                    findings.append(
                        f"FORECLOSURE FRAMING: '{desc}' without raw-count qualifier. "
                        f"Texas had the most REOs by raw count (3,322, H1 2026 ATTOM) but "
                        f"its rate (0.18%) is not in the top 5. Must qualify."
                    )
                    break

    return findings


def check_thin_data_risk(serp_results_count: int, neighborhood: str) -> dict:
    """Flag guides generated from sparse SERP data as confabulation risk.

    Returns a risk assessment dict. Called by the pipeline after generation
    to tag guides that need full human read, not just correction-clearing.
    """
    if serp_results_count <= 5:
        return {
            "risk_level": "HIGH",
            "flag": f"THIN-DATA: Only {serp_results_count} SERP results for '{neighborhood}'. "
                    f"READ FULLY — confabulation risk. Heritage/history sections, specific "
                    f"amenity claims, and cultural narratives may be invented.",
            "action": "full_human_read",
        }
    elif serp_results_count <= 7:
        return {
            "risk_level": "MODERATE",
            "flag": f"MODERATE-DATA: {serp_results_count} SERP results for '{neighborhood}'. "
                    f"Spot-check heritage and cultural claims.",
            "action": "spot_check",
        }
    else:
        return {
            "risk_level": "LOW",
            "flag": "",
            "action": "corrections_only",
        }
