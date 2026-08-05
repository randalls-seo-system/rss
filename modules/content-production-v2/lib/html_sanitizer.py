"""Post-assembly HTML sanitizer for the article pipeline.

Runs after Phase H step 24 (assembly) and before step 25 (link injection).
Catches structural defects from ANY upstream phase — Opus reasoning leakage,
tag imbalance, <p> nesting, FAQ duplication, stray angle brackets.

Hard-stops the pipeline on failure. Does NOT auto-fix — reports what's wrong
so the upstream prompt or section builder can be corrected.

Wired into assemble-article.py phase_h() between assembly and link injection.
"""

import re
from collections import Counter

from bs4 import BeautifulSoup

from .tool_utils import eprint


# ---------------------------------------------------------------------------
# Meta-commentary detection
# ---------------------------------------------------------------------------

# Patterns that indicate LLM reasoning leaked into output.
# Each is (compiled regex, description).
# IMPORTANT: these must NOT match legitimate editorial content like
# "price correction", "cultural correction", "market correction".
_META_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Self-referential reasoning ("Wait, I used an en dash")
    (re.compile(
        r"(?:^|\n)\s*(?:Wait|Hmm|Actually|Oh|Oops),?\s+I\s+"
        r"(?:used|should|need|forgot|made|noticed|see|realize)",
        re.IGNORECASE,
    ), "LLM self-correction reasoning"),

    # Instruction echo ("Let me fix/check/rewrite/revise")
    (re.compile(
        r"(?:^|\n)\s*Let me\s+(?:fix|check|rewrite|revise|correct|redo|try|rethink)",
        re.IGNORECASE,
    ), "LLM instruction echo"),

    # Output preamble ("Here is the article/HTML/complete")
    (re.compile(
        r"(?:^|\n)\s*Here\s+(?:is|are)\s+the\s+"
        r"(?:article|HTML|complete|final|corrected|updated|revised)",
        re.IGNORECASE,
    ), "LLM output preamble"),

    # Thinking tags that leaked
    (re.compile(r"</?(?:thinking|reflection|scratchpad)>", re.IGNORECASE),
     "LLM thinking tag leaked"),

    # Bare "I" statements outside any HTML tag (reasoning bleed)
    # Anchored to line start to avoid matching "I" inside sentences/quotes.
    (re.compile(
        r"(?:^|\n)\s*I\s+(?:apologize|accidentally|notice that|should have|"
        r"need to|will now|realize|made an error)",
        re.IGNORECASE,
    ), "LLM apology/reasoning"),
]


def _strip_meta_commentary(html: str) -> tuple[str, list[str]]:
    """Remove meta-commentary lines, return (cleaned_html, list of stripped items).

    Only strips LINES that match meta-commentary patterns and contain no HTML tags.
    This prevents stripping legitimate content that happens to contain trigger words
    inside paragraphs or list items.
    """
    stripped = []
    clean_lines = []

    for line in html.split("\n"):
        line_stripped = line.strip()
        # Skip empty lines — pass through
        if not line_stripped:
            clean_lines.append(line)
            continue
        # Only check lines that have NO HTML tags (pure text = likely commentary)
        if "<" in line_stripped and ">" in line_stripped:
            clean_lines.append(line)
            continue
        # Check against meta patterns
        matched = False
        for pattern, desc in _META_PATTERNS:
            if pattern.search(line_stripped):
                stripped.append(f"{desc}: {line_stripped[:120]}")
                matched = True
                break
        if not matched:
            clean_lines.append(line)

    return "\n".join(clean_lines), stripped


# ---------------------------------------------------------------------------
# Tag balance check
# ---------------------------------------------------------------------------

_PAIRED_TAGS = ["div", "section", "details", "ul", "ol", "table", "tr", "td",
                "th", "thead", "tbody", "summary", "nav", "article", "aside",
                "header", "footer", "figure", "figcaption", "blockquote"]


def _check_tag_balance(html: str) -> list[str]:
    """Check that paired HTML tags have matching open/close counts."""
    errors = []
    html_lower = html.lower()
    for tag in _PAIRED_TAGS:
        opens = len(re.findall(rf"<{tag}[\s>]", html_lower))
        closes = html_lower.count(f"</{tag}>")
        if opens != closes:
            errors.append(
                f"Tag imbalance: <{tag}> opens={opens} closes={closes} "
                f"(delta={opens - closes:+d})"
            )
    return errors


# ---------------------------------------------------------------------------
# <p> nesting check
# ---------------------------------------------------------------------------

def _check_p_nesting(html: str) -> list[str]:
    """Detect <p> tags nested inside other unclosed <p> tags."""
    errors = []
    depth = 0
    for m in re.finditer(r"<(/?)p[\s>/]", html, re.IGNORECASE):
        if m.group(1) == "/":
            depth = max(0, depth - 1)
        else:
            depth += 1
            if depth > 1:
                # Find approximate line number
                line_num = html[:m.start()].count("\n") + 1
                errors.append(f"Nested <p> at ~line {line_num} (depth {depth})")
                break  # One report is enough
    return errors


# ---------------------------------------------------------------------------
# FAQ dedup check
# ---------------------------------------------------------------------------

def _check_faq_dedup(html: str) -> list[str]:
    """Detect duplicate <summary> text (FAQ questions asked twice)."""
    errors = []
    soup = BeautifulSoup(html, "html.parser")
    summaries = [s.get_text(strip=True) for s in soup.find_all("summary")]
    counts = Counter(summaries)
    for text, count in counts.items():
        if count > 1:
            errors.append(
                f"Duplicate FAQ question ({count}x): "
                f"{text[:80]}{'...' if len(text) > 80 else ''}"
            )
    return errors


# ---------------------------------------------------------------------------
# Stray angle bracket check
# ---------------------------------------------------------------------------

def _check_stray_angles(html: str) -> list[str]:
    """Detect unescaped < that aren't part of an HTML tag.

    Looks for < followed by something that doesn't look like a tag name,
    closing slash, or !-- comment. Common in LLM output: "rates < 5%".
    """
    errors = []
    # Match < NOT followed by: tag name, /tag, !--, !DOCTYPE
    stray = re.findall(
        r"<(?![a-zA-Z/!])",
        html,
    )
    if stray:
        errors.append(
            f"Stray unescaped '<' ({len(stray)} occurrence(s)) — "
            f"may render as broken HTML"
        )
    return errors


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _check_placeholder_tokens(html: str) -> list[str]:
    """PUBLISH GATE: detect unfilled placeholders and LLM refusal text.

    Any match is a hard-stop — content with these tokens must NEVER
    reach the live site. This catches:
    - Scaffold placeholders from generate-neighborhood-guide.py defaults
    - LLM refusal text when CLAUDE.md rules block content generation
    - Unfilled bracket tokens from any template
    """
    errors: list[str] = []
    text = html  # Check raw HTML, not stripped text, to catch attribute values too

    # Scaffold placeholders (from build_default_data)
    scaffold_tokens = [
        ("[REASON ",    "Unfilled good-fit/think-twice scaffold"),
        ("[EXPLANATION", "Unfilled explanation scaffold"),
        ("[ANSWER]",    "Unfilled FAQ answer scaffold"),
        ("[CONCERN ",   "Unfilled think-twice scaffold"),
        ("[REPLACE",    "Unfilled replace-me scaffold"),
        ("[INSERT",     "Unfilled insert scaffold"),
        ("[TODO",       "Unfilled TODO scaffold"),
        ("[TBD",        "Unfilled TBD scaffold"),
        ("[FILL",       "Unfilled fill scaffold"),
        ("[TYPE]",      "Unfilled type scaffold"),
        ("[YEARS AND TYPES]", "Unfilled housing stock scaffold"),
        ("[RANGE]",     "Unfilled range scaffold"),
        ("[NEAREST]",   "Unfilled nearest scaffold"),
        ("[ROUTE]",     "Unfilled route scaffold"),
    ]
    for token, desc in scaffold_tokens:
        if token in text:
            count = text.count(token)
            errors.append(f"PLACEHOLDER: '{token}' found {count}x — {desc}")

    # Numeric placeholders
    numeric_tokens = [
        ("XXXXX",       "Unfilled ZIP code"),
        ("XX min",      "Unfilled commute time"),
        ("$XXX to $XXX", "Unfilled price range"),
        ("$XXXK",       "Unfilled median price"),
    ]
    for token, desc in numeric_tokens:
        if token in text:
            errors.append(f"PLACEHOLDER: '{token}' — {desc}")

    # LLM refusal text (from CLAUDE.md content generation rule)
    refusal_patterns = [
        "I can't write this section freehand",
        "I can't write this",
        "Per the project's CLAUDE.md",
        "writing section prose freehand",
        "assemble-article.py`. Writing section",
        "CONTENT GENERATION RULE",
    ]
    for pat in refusal_patterns:
        if pat in text:
            errors.append(f"LLM REFUSAL: '{pat[:50]}' found — model refused to generate content")

    return errors


def _postprocess_structure(html: str, site: str = "") -> tuple[str, list[str]]:
    """Postprocessor: add missing structural wrappers to assembled HTML.

    Fixes that run on every article before deploy:
    1. rl-page wrapper — wraps entire content in <div class="rl-page rl-page-{site}">
    2. rl-quick-grid — wraps consecutive rl-quick-card elements in a grid container
    3. H1 removal — removes any <h1> tag from post_content (WP renders title separately)
    4. rl-cta-primary removal — removes ATF CTA link (hidden by CSS, cleaner to strip)
    5. bullet-section wrappers — wraps bare <ul> in body <section> blocks

    Returns (html, list_of_fixes_applied).
    """
    import re as _re
    fixes = []

    # 1. rl-page wrapper
    if 'rl-page' not in html[:100]:
        site_cls = f" rl-page-{site}" if site else ""
        html = f'<div class="rl-page{site_cls}">\n<div class="rl-wrap">\n{html}\n</div>\n</div>'
        fixes.append("rl-page wrapper added")

    # 2. rl-quick-grid wrapper
    if 'rl-quick-card' in html and 'rl-quick-grid' not in html:
        first = html.find('<article class="rl-quick-card">')
        if first != -1:
            pos = first
            last_end = first
            for _ in range(4):
                end = html.find('</article>', pos)
                if end == -1:
                    break
                last_end = end + 10
                pos = end + 10
            cards = html[first:last_end]
            html = html[:first] + '<div class="rl-quick-grid">' + cards + '</div>' + html[last_end:]
            fixes.append("rl-quick-grid wrapper added")

    # 2b. ATF FAQ heading — insert "Asked First" heading before the first ATF <details>
    if 'rl-atf-faqhead' not in html and '<details>' in html:
        # Find the first <details> that appears BEFORE any <section> (ATF area)
        first_details = html.find('<details>')
        first_section = html.find('<section')
        if first_details != -1 and (first_section == -1 or first_details < first_section):
            faq_heading = '<div class="rl-atf-faqhead"><span class="rl-kicker">Asked First</span>Top questions before you dig in</div>\n'
            html = html[:first_details] + faq_heading + html[first_details:]
            fixes.append("ATF FAQ heading added")

    # 3. H1 removal
    h1_match = _re.search(r'<h1[^>]*>.*?</h1>', html, _re.DOTALL)
    if h1_match:
        html = html[:h1_match.start()] + html[h1_match.end():]
        fixes.append("H1 removed from content")

    # 4. rl-cta-primary removal
    if 'rl-cta-primary' in html:
        html = _re.sub(r'<a[^>]*class="rl-cta-primary"[^>]*>[^<]*</a>\s*', '', html)
        fixes.append("rl-cta-primary removed")

    # 5. bullet-section wrappers for bare <ul> in body sections
    body_start = html.find('<section>')
    if body_start == -1:
        body_start = html.find('<section ')
    if body_start != -1:
        head = html[:body_start]
        body = html[body_start:]
        colors = ['gray', 'blue', 'green', 'beige']
        idx = [0]

        def _wrap_ul(match):
            color = colors[idx[0] % len(colors)]
            idx[0] += 1
            return f'<div class="bullet-section-{color}"><ul>\n<li>'

        body = _re.sub(r'<ul>\s*\n?\s*<li>', _wrap_ul, body)
        body = _re.sub(r'</ul>(?!\s*</div>)', '</ul></div>', body)
        html = head + body
        if idx[0] > 0:
            fixes.append(f"{idx[0]} bullet-section wrappers added")

    return html, fixes


def sanitize_assembled_html(html: str, site: str = "") -> tuple[str, list[str]]:
    """Run all sanitization checks and structural postprocessing on assembled article HTML.

    Args:
        html: The assembled article HTML (post step H.24, pre link injection).
        site: Site slug (e.g., 'lrg') for site-specific wrapper classes.

    Returns:
        (cleaned_html, errors) — cleaned_html has meta-commentary stripped
        and structural postprocessing applied.
        errors is a list of structural issues found. If non-empty, the caller
        should hard-stop the pipeline.
    """
    all_errors: list[str] = []

    # 1. Strip meta-commentary (the only mutation — everything else is check-only)
    cleaned, stripped_items = _strip_meta_commentary(html)
    if stripped_items:
        for item in stripped_items:
            eprint(f"  [Sanitizer] Stripped: {item}")

    # 2. Structural postprocessing (rl-page wrapper, rl-quick-grid, bullet-sections, H1/CTA removal)
    cleaned, pp_fixes = _postprocess_structure(cleaned, site)
    if pp_fixes:
        for fix in pp_fixes:
            eprint(f"  [Postprocessor] {fix}")

    # 3. Structural checks (on the cleaned + postprocessed HTML)
    all_errors.extend(_check_tag_balance(cleaned))
    all_errors.extend(_check_p_nesting(cleaned))
    all_errors.extend(_check_faq_dedup(cleaned))
    all_errors.extend(_check_stray_angles(cleaned))

    # 4. PUBLISH GATE: placeholder tokens and LLM refusal text
    all_errors.extend(_check_placeholder_tokens(cleaned))

    return cleaned, all_errors
