"""Shared page-fetching and caching utilities.

Used by extract-subtopic-gaps.py (heading extraction) and evidence.py
(passage extraction). Single implementation — no duplication.
"""

import hashlib
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

PAGE_CACHE_DIR = Path.home() / ".cache" / "rss-serp-pages"
CACHE_TTL_DAYS = 7
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)
FETCH_TIMEOUT = 15

KNOWN_BLOCKED_DOMAINS = {
    "bungalow.com",
    "zillow.com",
    "apartments.com",
    "realtor.com",
    "reddit.com",
    "forbes.com",
    "wsj.com",
    "nytimes.com",
    "bloomberg.com",
}


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _cache_path(url: str) -> Path:
    h = hashlib.sha256(url.encode()).hexdigest()
    return PAGE_CACHE_DIR / f"{h}.html"


def cache_get(url: str) -> str | None:
    """Return cached HTML for url, or None if missing/expired."""
    path = _cache_path(url)
    if not path.exists():
        return None
    age_days = (time.time() - path.stat().st_mtime) / 86400
    if age_days > CACHE_TTL_DAYS:
        return None
    return path.read_text(errors="replace")


def cache_set(url: str, html: str) -> None:
    """Write HTML to disk cache."""
    PAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(url).write_text(html)


def is_blocked_domain(url: str) -> bool:
    """Check if URL belongs to a known-blocked domain."""
    domain = urlparse(url).netloc.lower().lstrip("www.")
    return any(domain == d or domain.endswith("." + d) for d in KNOWN_BLOCKED_DOMAINS)


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_page(url: str) -> str | None:
    """Fetch a page, using disk cache. Returns HTML or None on failure."""
    if is_blocked_domain(url):
        _log(f"  Skipping known-blocked domain: {url[:80]}")
        return None
    cached = cache_get(url)
    if cached is not None:
        return cached
    try:
        import requests

        resp = requests.get(
            url, headers={"User-Agent": USER_AGENT}, timeout=FETCH_TIMEOUT
        )
        resp.raise_for_status()
        html = resp.text
        cache_set(url, html)
        return html
    except Exception as e:
        _log(f"  WARN: failed to fetch {url[:80]}: {e}")
        return None


# ---------------------------------------------------------------------------
# Body-text extraction (shared between gap extraction and evidence)
# ---------------------------------------------------------------------------

def strip_boilerplate(soup) -> None:
    """Remove nav, footer, aside, script, style, header, noscript in-place.

    Accepts a BeautifulSoup instance. Mutates it.
    """
    for tag in soup.find_all(
        ["nav", "footer", "aside", "script", "style", "header", "noscript"]
    ):
        tag.decompose()
