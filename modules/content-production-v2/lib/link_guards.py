"""P5 + P6 boundary guards for link operations.

P5: is_internal() — external links are NEVER touched by strip/dedup/retarget.
P6: same_language() — cross-language linking is NEVER permitted.

These are HARD guards in the mutation path, not filters on reports.
Every tool that mutates links must call these before acting.

Used by:
  - tools/inject-internal-links.py
  - tools/link-injector.py
  - Any future strip/dedup/retarget tool
"""

import re
from urllib.parse import urlparse


# ───────────────────────────────────────────────────────────────────────────
# P5: External-link domain guard
# ───────────────────────────────────────────────────────────────────────────

def is_internal(href: str, site_domain: str, proxy_paths: list[str] | None = None) -> bool:
    """Return True only if href points to the same site.

    Rules:
        - Relative paths (/foo, foo, #anchor) → internal
        - Absolute URLs to site_domain → internal
        - Absolute URLs to a configured proxy domain for a known path → internal
        - Everything else → external → False

    Args:
        href: The link's href attribute.
        site_domain: The site's primary domain (e.g., "lrgrealtyblog.wpenginepowered.com").
        proxy_paths: Optional list of path prefixes that resolve to this site
                     even under a different domain (e.g., ["/lrg-blog/", "/listings/"]).
    """
    if not href or not isinstance(href, str):
        return False

    href = href.strip()

    # Fragment-only or empty
    if href.startswith('#') or not href:
        return True

    # Relative paths (no scheme)
    if not href.startswith(('http://', 'https://', '//')):
        return True

    # Absolute URL — parse and check domain
    parsed = urlparse(href)
    link_domain = (parsed.hostname or '').lower().rstrip('.')
    site_domain_clean = site_domain.lower().rstrip('.')

    if link_domain == site_domain_clean:
        return True

    # Check www variant
    if link_domain == f'www.{site_domain_clean}':
        return True
    if f'www.{link_domain}' == site_domain_clean:
        return True

    # Proxy paths: some sites serve content under a CDN/proxy domain
    # but with known path prefixes (e.g., Cloudflare worker at lrgrealty.com/lrg-blog/
    # proxies to lrgrealtyblog.wpenginepowered.com)
    if proxy_paths:
        path = parsed.path or '/'
        for prefix in proxy_paths:
            if path.startswith(prefix):
                return True

    return False


def count_external_links(html: str, site_domain: str, proxy_paths: list[str] | None = None) -> tuple[int, list[str]]:
    """Count external links in HTML and return (count, list_of_hrefs).

    Used as a pre/post assertion: external count must not change during a mutation.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    externals = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if not is_internal(href, site_domain, proxy_paths):
            externals.append(href)
    return len(externals), externals


def assert_externals_unchanged(before_html: str, after_html: str, site_domain: str,
                                proxy_paths: list[str] | None = None) -> tuple[bool, str]:
    """Post-run assertion: external link count must equal before count.

    Returns (ok: bool, message: str). If not ok, the message lists which
    external links were added or removed.
    """
    before_count, before_links = count_external_links(before_html, site_domain, proxy_paths)
    after_count, after_links = count_external_links(after_html, site_domain, proxy_paths)

    if before_count == after_count and set(before_links) == set(after_links):
        return True, f'External links unchanged ({before_count})'

    added = set(after_links) - set(before_links)
    removed = set(before_links) - set(after_links)

    parts = [f'External link count changed: {before_count} → {after_count}']
    if removed:
        parts.append(f'  REMOVED (VIOLATION): {", ".join(sorted(removed))}')
    if added:
        parts.append(f'  ADDED: {", ".join(sorted(added))}')

    return False, '\n'.join(parts)


# ───────────────────────────────────────────────────────────────────────────
# P6: Language-boundary guard
# ───────────────────────────────────────────────────────────────────────────

# Per-site language detection rules
_LANGUAGE_RULES: dict[str, dict] = {
    'lrg': {
        'default': 'en',
        'path_rules': [
            {'pattern': r'^/spanish-blog/', 'lang': 'es'},
            {'pattern': r'^/blog-en-espanol/', 'lang': 'es'},
        ],
        'slug_rules': [
            {'pattern': r'-en-espanol$', 'lang': 'es'},
            {'pattern': r'-san-antonio-tx$', 'lang': 'en'},  # city names are English
        ],
    },
    'ahn': {
        'default': 'en',
        'path_rules': [
            {'pattern': r'__prs', 'lang': 'prs'},
            {'pattern': r'__ps', 'lang': 'ps'},
        ],
    },
}


def detect_language(url_or_slug: str, site_slug: str) -> str:
    """Detect the language of a post from its URL/slug and site conventions.

    Returns a language code ('en', 'es', 'prs', 'ps', etc.).
    Falls back to the site's default language.
    """
    rules = _LANGUAGE_RULES.get(site_slug, {})
    default_lang = rules.get('default', 'en')
    value = url_or_slug.lower()

    for rule in rules.get('path_rules', []):
        if re.search(rule['pattern'], value):
            return rule['lang']

    for rule in rules.get('slug_rules', []):
        if re.search(rule['pattern'], value):
            return rule['lang']

    return default_lang


def same_language(source_url: str, dest_url: str, site_slug: str) -> bool:
    """Return True if source and destination are the same language.

    This is a HARD gate: cross-language links are never injected.
    """
    src_lang = detect_language(source_url, site_slug)
    dst_lang = detect_language(dest_url, site_slug)
    return src_lang == dst_lang
