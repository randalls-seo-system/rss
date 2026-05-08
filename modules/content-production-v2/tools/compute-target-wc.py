#!/usr/bin/env python3
"""Compute target body word count from SERP top-5 average.

Returns target, min, max (average +/-15%) or fallback default
when SERP data is unavailable or pages can't be fetched.

Usage:
    python3 compute-target-wc.py --serp-json /path/to/serp.json
    python3 compute-target-wc.py --serp-json /path/to/serp.json --no-fetch

See docs/article-spec.md Section 17.2 for target word count logic.
See docs/v2-module-architecture.md "tools/compute-target-wc.py" for spec.
"""

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

# Add lib/ to path for sibling imports
TOOL_DIR = Path(__file__).resolve().parent
MODULE_DIR = TOOL_DIR.parent
sys.path.insert(0, str(MODULE_DIR))

from lib.serp_adapter import SerpData

PAGE_CACHE_DIR = Path.home() / ".cache" / "rss-serp-pages"
CACHE_TTL_DAYS = 7
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
FETCH_TIMEOUT = 15

# KNOWN LIMITATION (not a bug):
# When SERP top results contain mixed page types (news article + tool +
# calculator + long-form blog), the simple average word count is not
# meaningful — a 581-word news article can drag the target below the
# fallback range. Future improvement: filter SERP results by structural
# similarity (e.g., presence of multiple H2s, body-to-nav ratio) before
# averaging. For now, the tool reports the raw average and downstream
# code should treat the result as a hint, not a hard constraint.

KNOWN_BLOCKED_DOMAINS = {
    'bungalow.com',
    'zillow.com',
    'apartments.com',
    'realtor.com',
    'reddit.com',
    'forbes.com',
    'wsj.com',
    'nytimes.com',
    'bloomberg.com',
}

FALLBACK_TARGET = 2100
FALLBACK_MIN = 1800
FALLBACK_MAX = 2400


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# Page cache (shared with extract-subtopic-gaps.py)
# ---------------------------------------------------------------------------

def _cache_path(url: str) -> Path:
    h = hashlib.sha256(url.encode()).hexdigest()
    return PAGE_CACHE_DIR / f"{h}.html"


def _cache_get(url: str) -> str | None:
    path = _cache_path(url)
    if not path.exists():
        return None
    age_days = (time.time() - path.stat().st_mtime) / 86400
    if age_days > CACHE_TTL_DAYS:
        return None
    return path.read_text(errors="replace")


def _cache_set(url: str, html: str) -> None:
    PAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(url).write_text(html)


def _is_blocked_domain(url: str) -> bool:
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower().lstrip("www.")
    return any(domain == d or domain.endswith("." + d) for d in KNOWN_BLOCKED_DOMAINS)


def fetch_page(url: str, allow_fetch: bool) -> str | None:
    """Get page HTML from cache or network."""
    if _is_blocked_domain(url):
        log(f"  Skipping known-blocked domain: {url[:80]}")
        return None
    cached = _cache_get(url)
    if cached is not None:
        return cached
    if not allow_fetch:
        return None
    try:
        import requests
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        html = resp.text
        _cache_set(url, html)
        return html
    except Exception as e:
        log(f"  WARN: failed to fetch {url[:80]}: {e}")
        return None


# ---------------------------------------------------------------------------
# Word count extraction
# ---------------------------------------------------------------------------

def extract_article_word_count(html: str) -> int | None:
    """Extract word count from the main article content of a page.

    Heuristic: prefer <article>, then <main>, then <body>.
    Strip nav, footer, sidebar, script, style, header.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content elements
    for tag in soup.find_all(["nav", "footer", "aside", "script", "style",
                              "header", "noscript", "form", "iframe"]):
        tag.decompose()

    # Find main content container
    content = soup.find("article")
    if content is None:
        content = soup.find("main")
    if content is None:
        content = soup.find("body")
    if content is None:
        return None

    text = content.get_text(separator=" ", strip=True)
    words = re.findall(r"\b\w+\b", text)
    wc = len(words)

    # Sanity check: pages with <100 words are likely blocked/broken
    if wc < 100:
        return None
    return wc


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Compute target body word count from SERP top-5 average.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Output: JSON to stdout with target, min, max, source, n_results."
    )
    parser.add_argument("--serp-json", required=True, help="analyze-serp.py output JSON path")
    parser.add_argument("--no-fetch", action="store_true",
                        help="Don't fetch pages from network; use cache only")
    args = parser.parse_args()

    log("=== Compute Target Word Count ===")

    serp = SerpData(Path(args.serp_json))
    results = serp.top_results[:5]
    allow_fetch = not args.no_fetch

    log(f"Keyword: {serp.keyword}")
    log(f"Top results: {len(results)}")
    log(f"Fetch mode: {'cache+network' if allow_fetch else 'cache only'}")

    word_counts: list[int] = []

    for i, result in enumerate(results):
        log(f"  [{i+1}/{len(results)}] {result.url[:70]}...", )
        html = fetch_page(result.url, allow_fetch)
        if html is None:
            log(f"    SKIP: no content available")
            continue

        wc = extract_article_word_count(html)
        if wc is None:
            log(f"    SKIP: could not extract article content")
            continue

        log(f"    {wc:,} words")
        word_counts.append(wc)

    log(f"\nParseable results: {len(word_counts)} of {len(results)}")

    if len(word_counts) >= 3:
        avg = sum(word_counts) // len(word_counts)
        target_min = int(avg * 0.85)
        target_max = int(avg * 1.15)
        output = {
            "target": avg,
            "min": target_min,
            "max": target_max,
            "source": "serp_avg +/-15%",
            "n_results": len(word_counts),
            "word_counts": word_counts,
        }
        log(f"Average: {avg:,} words")
        log(f"Target range: {target_min:,} - {target_max:,}")
    else:
        output = {
            "target": FALLBACK_TARGET,
            "min": FALLBACK_MIN,
            "max": FALLBACK_MAX,
            "source": "fallback_default",
            "n_results": len(word_counts),
            "word_counts": word_counts,
        }
        log(f"Insufficient data ({len(word_counts)} results). Using fallback: {FALLBACK_MIN}-{FALLBACK_MAX}")

    # Output JSON to stdout
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
