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
    ("young families", "buyers with school-age children"),
    ("Young families", "Buyers with school-age children"),
    ("family-friendly", "community-oriented"),
    ("Family-friendly", "Community-oriented"),
    ("Family-Friendly", "Community-Oriented"),
    ("best for families", "best for larger lots and community amenities"),
    ("Best for families", "Best for larger lots and community amenities"),
    ("ideal for families", "ideal for community amenities and school access"),
]


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


# ── Pass 6: Author resolution ──

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


# ── Convenience: run all 5 HTML passes ──

def run_all_passes(html: str, site_config: dict | None = None,
                   target_keyword: str = "",
                   slug_cache_paths: list[str] | None = None,
                   ) -> tuple[str, list[str]]:
    """Run passes 1-5 on html. Returns (cleaned_html, log_entries).

    Pass 6 (author resolution) is not included here — it doesn't modify
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

    return html, all_log
