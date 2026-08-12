"""post_assembly.py — Shared post-assembly cleanup passes.

Six passes that run on generated HTML AFTER assembly and BEFORE file write.
Extracted from generate-roundup.py so both generators share the same backstops.

Usage:
    from lib.post_assembly import run_all_passes

    html, report = run_all_passes(html, site_config=config, target_keyword=kw)
    for entry in report:
        eprint(f"  {entry}")
"""

import csv
import re
from pathlib import Path

# Shared regex: split HTML into tag vs text-node segments.
# Preserves <style> and <script> blocks as single tokens so text-node
# passes don't corrupt JSON-LD or inline CSS.
_TAG_SPLIT = re.compile(
    r'(<style[^>]*>.*?</style>|<script[^>]*>.*?</script>|<[^>]+>)',
    re.DOTALL,
)


# ── Pass 1: Fair Housing phrase scan ──

_FH_REPLACEMENTS = [
    # ── Demographic targeting: familial status ──
    ("young families", "first-time buyers"),
    ("Young families", "First-time buyers"),
    ("family-friendly", "community-oriented"),
    ("Family-friendly", "Community-oriented"),
    ("Family-Friendly", "Community-Oriented"),
    ("family-oriented", "community-oriented"),
    ("Family-oriented", "Community-oriented"),
    ("best for families", "best for larger lots and community amenities"),
    ("Best for families", "Best for larger lots and community amenities"),
    ("ideal for families", "ideal for community amenities and school access"),
    ("Ideal for families", "Ideal for community amenities and school access"),
    ("draw families", "draw buyers"),
    ("Draw families", "Draw buyers"),
    ("draws families", "draws buyers"),
    ("attract families", "attract buyers"),
    ("Attract families", "Attract buyers"),
    ("Families benefit", "Buyers benefit"),
    ("families benefit", "buyers benefit"),
    ("Families draw", "Buyers draw"),
    ("families draw", "buyers draw"),
    ("Families access", "Buyers access"),
    ("families access", "buyers access"),
    ("Families served", "Buyers served"),
    ("families served", "buyers served"),
    ("Family-Focused", "Community-Focused"),
    ("Family-focused", "Community-focused"),
    ("family-focused", "community-focused"),
    ("for families", "for buyers"),
    # ── Socioeconomic framing ──
    ("budget-conscious", "value-focused"),
    ("Budget-conscious", "Value-focused"),
    # ── Age-based targeting ──
    ("attract retirees", "attract long-term owners"),
]

# Safety claims: DELETE, don't substitute. Replacing fabricates a
# different unsourced claim. Strip the phrase and surrounding connectors.
_SAFETY_DELETE_PATTERNS = [
    # "X and low crime rates" → "X"
    # "low crime rates and X" → "X"
    # "X, low crime rates, and Y" → "X and Y"
    # Standalone "low crime rates" → flag for human review
    re.compile(r',?\s*and\s+(?:low[- ]crime\s+rates?|safest\s+\w+|crime[- ]free)', re.IGNORECASE),
    re.compile(r'(?:low[- ]crime\s+rates?|safest\s+\w+|crime[- ]free)\s*(?:,\s*and|and)\s+', re.IGNORECASE),
    re.compile(r',\s*(?:low[- ]crime\s+rates?|safest\s+\w+|crime[- ]free)\s*,', re.IGNORECASE),
    re.compile(r';\s*(?:low[- ]crime\s+rates?|safest\s+\w+|crime[- ]free)\s*', re.IGNORECASE),
]
# Standalone pattern — if the phrase is the whole clause, flag instead of silently deleting
_SAFETY_STANDALONE = re.compile(
    r'\b(?:low[- ]crime\s+rates?|safest\s+\w+|crime[- ]free|low[- ]crime)\b', re.IGNORECASE
)


def fh_scan(html: str) -> tuple[str, list[str]]:
    """Mechanical FH phrase replacement.

    This is a FLOOR, not a detector — it catches only exact-match phrases.
    Semantic FH review (demographic targeting, safety claims, socioeconomic
    framing) requires a full read and is not automated here.
    """
    log = []
    total = 0
    for old, new in _FH_REPLACEMENTS:
        c = html.count(old)
        if c:
            html = html.replace(old, new)
            total += c
    log.append(f"FH scan: {total} replacements")

    # Safety claims: delete (not substitute) with connector cleanup
    safety_deletes = 0
    safety_flags = []
    # First pass: delete safety phrases with surrounding connectors
    for pattern in _SAFETY_DELETE_PATTERNS:
        html, n = pattern.subn(' ', html)
        safety_deletes += n
    # Second pass: flag any remaining standalone safety phrases
    remaining = _SAFETY_STANDALONE.findall(html)
    if remaining:
        for phrase in remaining:
            safety_flags.append(f"SAFETY FLAG (needs human review): '{phrase}' remains after connector cleanup")
    # Clean up double spaces from deletions
    if safety_deletes:
        html = re.sub(r'  +', ' ', html)
    log.append(f"Safety deletions: {safety_deletes} stripped, {len(safety_flags)} flagged for review")
    log.extend(safety_flags)

    return html, log


# ── Pass 2: Em dash strip ──

def strip_em_dashes(html: str) -> tuple[str, list[str]]:
    """Replace em dashes in text nodes with commas.

    Skips <style>, <script>, and HTML tags so JSON-LD is untouched.
    """
    parts = _TAG_SPLIT.split(html)
    count = 0
    for idx, part in enumerate(parts):
        if part.startswith('<'):
            continue
        c = part.count('\u2014')
        if c:
            parts[idx] = part.replace(' \u2014 ', ', ').replace('\u2014', ', ')
            count += c
    html = ''.join(parts)
    return html, [f"Em dash strip: {count} removed"]


# ── Pass 3: Markdown bold → <strong> ──

def fix_markdown_bold(html: str) -> tuple[str, list[str]]:
    """Convert **text** to <strong>text</strong> and strip orphaned **."""
    html = re.sub(r'\*\*([^*]+?)\*\*', r'<strong>\1</strong>', html)
    parts = _TAG_SPLIT.split(html)
    orphans = 0
    for idx, part in enumerate(parts):
        if part.startswith('<'):
            continue
        if '**' in part:
            orphans += part.count('**')
            parts[idx] = part.replace('**', '')
    html = ''.join(parts)
    return html, [f"Markdown fix: {orphans} orphaned ** stripped"]


# ── Pass 4: Whitespace collapse ──

def collapse_whitespace(html: str) -> tuple[str, list[str]]:
    """Fix camelCase joins and missing spaces after punctuation in text nodes.

    Common after link removal leaves "wordWord" or "word.Word" artifacts.
    """
    parts = _TAG_SPLIT.split(html)
    fixes = 0
    for idx, part in enumerate(parts):
        if part.startswith('<'):
            continue
        before = part
        part = re.sub(r'([a-z])([A-Z])', lambda m: m.group(1) + ' ' + m.group(2), part)
        part = re.sub(r'([,;.!?])([A-Z])', lambda m: m.group(1) + ' ' + m.group(2), part)
        if part != before:
            fixes += 1
            parts[idx] = part
    html = ''.join(parts)
    return html, [f"Whitespace fix: {fixes} nodes repaired"]


# ── Pass 5: Link validation ──

_DEFAULT_SLUG_CACHES = ['/tmp/lrg-all-posts.csv', '/tmp/lrg-all-pages.csv']


def validate_links(html: str, slug_cache_paths: list[str] | None = None,
                   blog_prefix: str = '/lrg-blog/', skip_slugs: set[str] | None = None
                   ) -> tuple[str, list[str]]:
    """Drop internal links whose slugs don't exist in the live slug cache.

    Skips CTA links (connect-with-lrg) and any slugs in skip_slugs.
    Returns unchanged html if no slug cache files are found.
    """
    cache_paths = slug_cache_paths or _DEFAULT_SLUG_CACHES
    skip = skip_slugs or set()

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return html, ["Link validation: skipped (bs4 not available)"]

    live_slugs = set()
    for csvf in cache_paths:
        try:
            with open(csvf) as fh:
                for row in csv.DictReader(fh):
                    live_slugs.add(row['post_name'])
        except (FileNotFoundError, KeyError):
            pass

    if not live_slugs:
        return html, ["Link validation: skipped (no slug cache)"]

    soup = BeautifulSoup(html, 'html.parser')
    drops = 0
    for a in soup.find_all('a', href=True):
        href = a['href']
        if not href.startswith(blog_prefix) or 'connect-with-lrg' in href:
            continue
        slug = href.replace(blog_prefix, '').rstrip('/')
        if slug in skip:
            continue
        if slug not in live_slugs:
            a.replace_with(a.get_text())
            drops += 1

    if drops:
        html = str(soup)
    return html, [f"Link validation: {drops} 404 links dropped"]


# ── Pass 6: Unsourced number flag ──

_DOLLAR_PATTERN = re.compile(r'\$\d[\d,]*K?')
_MINUTE_PATTERN = re.compile(r'\b\d{1,3}\s*(?:min(?:ute)?s?|min\.)\b', re.IGNORECASE)
_TAX_PERCENT_PATTERN = re.compile(r'\b\d+\.?\d*\s*%', re.IGNORECASE)


def flag_unsourced_numbers(html: str, verified_numbers: set[str] | None = None,
                           hard_fail: bool = False
                           ) -> tuple[str, list[str]]:
    """Flag dollar amounts and drive times in prose that aren't in verified data.

    Does NOT modify html — returns it unchanged. The log entries are
    warnings for human review. Pass verified_numbers as a set of strings
    that ARE sourced (e.g. {"$350K", "$600K", "25 min"}) to suppress
    false positives on those values.

    When hard_fail=True, raises SystemExit if any unsourced numbers are
    found. Use this when price/commute data is null and numbers in the
    output are necessarily fabricated.
    """
    verified = verified_numbers or set()
    # Build a flat set of all numbers that appear inside any verified value,
    # so "25-30 min to downtown Austin" suppresses "30 min", "25 min", etc.
    verified_nums = set()
    for v in verified:
        for d in _DOLLAR_PATTERN.findall(str(v)):
            verified_nums.add(d)
        for t in _MINUTE_PATTERN.findall(str(v)):
            verified_nums.add(t)
        # Also extract bare integers from ranges like "25-30"
        for n in re.findall(r'\b(\d{1,3})\b', str(v)):
            verified_nums.add(n)

    # Strip HTML tags for text-only scan
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)

    def _is_verified(val):
        """Check if a matched number appears in any verified value."""
        if val in verified:
            return True
        # Extract the bare number and check
        num = re.search(r'\d+', val)
        if num and num.group(0) in verified_nums:
            return True
        return False

    flags = []
    for m in _DOLLAR_PATTERN.finditer(text):
        val = m.group(0)
        if not _is_verified(val):
            ctx_start = max(0, m.start() - 30)
            ctx_end = min(len(text), m.end() + 30)
            flags.append(f"UNSOURCED $: {val} in: ...{text[ctx_start:ctx_end].strip()}...")

    for m in _MINUTE_PATTERN.finditer(text):
        val = m.group(0)
        if not _is_verified(val):
            ctx_start = max(0, m.start() - 30)
            ctx_end = min(len(text), m.end() + 30)
            flags.append(f"UNSOURCED TIME: {val} in: ...{text[ctx_start:ctx_end].strip()}...")

    # Tax-rate percentages: flag X.X% when "tax" or "rate" appears within 60 chars
    for m in _TAX_PERCENT_PATTERN.finditer(text):
        val = m.group(0)
        if _is_verified(val):
            continue
        window_start = max(0, m.start() - 60)
        window_end = min(len(text), m.end() + 60)
        window = text[window_start:window_end].lower()
        if 'tax' in window or 'rate' in window:
            ctx_start = max(0, m.start() - 30)
            ctx_end = min(len(text), m.end() + 30)
            flags.append(f"UNSOURCED TAX%: {val} in: ...{text[ctx_start:ctx_end].strip()}...")

    summary = f"Unsourced number check: {len(flags)} flags"
    if hard_fail and flags:
        import sys
        print(f"\nHARD FAIL: {len(flags)} unsourced numbers in output.", file=sys.stderr)
        for f in flags:
            print(f"  {f}", file=sys.stderr)
        print("\nThe LLM fabricated dollar amounts or drive times despite", file=sys.stderr)
        print("no price/commute data in the input. Output not written.", file=sys.stderr)
        sys.exit(1)
    return html, [summary] + flags


# ── Pass 7: Geography and district consistency check ──

def check_geography(html: str, target_city: str, districts: list[str],
                    adjacent_cities: list[str] | None = None
                    ) -> tuple[str, list[str]]:
    """Flag geography errors: wrong city names, wrong corridor, ISD contradictions.

    Does NOT modify html. Returns flags for human review.
    """
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    flags = []

    # Check for "multiple ISDs/districts" when data has only one
    if len(set(districts)) == 1:
        for pattern in [r'multiple ISDs', r'multiple districts', r'several districts',
                        r'across.*ISDs', r'vary by.*district']:
            for m in re.finditer(pattern, text, re.IGNORECASE):
                ctx_start = max(0, m.start() - 20)
                ctx_end = min(len(text), m.end() + 40)
                flags.append(f"DISTRICT CONTRADICTION: '{m.group(0)}' but data has only {districts[0]}. "
                             f"Context: ...{text[ctx_start:ctx_end].strip()}...")

    return html, flags


# ── Pass 8: Author resolution ──

def resolve_author(site_config: dict, target_keyword: str = "",
                   override_id: int | None = None) -> tuple[int, str]:
    """Resolve author ID from lane map or override.

    Returns (author_id, reason_string).
    """
    if override_id:
        return override_id, f"override (user {override_id})"

    lane_map_raw = site_config.get("AUTHOR_LANE_MAP", "")
    fallback_id = int(site_config.get("AUTHOR_FALLBACK_ID", 1))
    fallback_name = site_config.get("AUTHOR_FALLBACK_NAME", "default")

    kw_lower = target_keyword.lower()
    for line in lane_map_raw.strip().splitlines():
        line = line.strip()
        if not line or '|' not in line:
            continue
        parts = line.split('|')
        if len(parts) < 3:
            continue
        keywords_csv, uid_str, display_name = parts[0], parts[1], parts[2]
        keywords = [k.strip().lower() for k in keywords_csv.split(',')]
        if any(k in kw_lower for k in keywords if k):
            return int(uid_str), f"lane map: {display_name.strip()} ({keywords_csv.strip()})"

    return fallback_id, f"fallback: {fallback_name}"


# ── Convenience: run all 6 HTML passes ──

def run_all_passes(html: str, site_config: dict | None = None,
                   target_keyword: str = "",
                   slug_cache_paths: list[str] | None = None,
                   verified_numbers: set[str] | None = None,
                   target_city: str = "",
                   districts: list[str] | None = None,
                   ) -> tuple[str, list[str]]:
    """Run passes 1-7 on html. Returns (cleaned_html, log_entries).

    Pass 8 (author resolution) is not included here — it doesn't modify
    HTML, it resolves a metadata field. Call resolve_author() separately.
    """
    all_log = []

    html, log = fh_scan(html)
    all_log.extend(log)

    html, log = strip_em_dashes(html)
    all_log.extend(log)

    html, log = fix_markdown_bold(html)
    all_log.extend(log)

    html, log = collapse_whitespace(html)
    all_log.extend(log)

    html, log = validate_links(html, slug_cache_paths)
    all_log.extend(log)

    # Hard-fail on unsourced numbers when no verified data exists
    # (meaning price/commute are null — any numbers are fabricated)
    numbers_hard_fail = verified_numbers is not None and len(verified_numbers) == 0
    html, log = flag_unsourced_numbers(html, verified_numbers,
                                       hard_fail=numbers_hard_fail)
    all_log.extend(log)

    # Geography and district consistency
    if target_city and districts:
        html, log = check_geography(html, target_city, districts)
        all_log.extend(log)

    return html, all_log
