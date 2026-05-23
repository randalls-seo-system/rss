#!/usr/bin/env python3
"""Build the Resources Used section.

Deterministic formatting — NO LLM call. Hard-fails per spec 15.6 if
SERP unavailable AND no manual --resources-list provided. No placeholder garbage.

Usage:
    python3 build-resources.py \\
        --site lrg \\
        --target-keyword "va funding fee" \\
        --serp-json /path/to/serp.json \\
        [--resources-list /path/to/resources.json] \\
        [--output /path/to/resources.html]
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

TOOLS_DIR = Path(__file__).resolve().parent
MODULE_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(MODULE_DIR))

from lib.serp_adapter import SerpData
from lib.site_config import load_site_config
from lib.tool_utils import eprint, write_output


HARD_FAIL_MESSAGE = (
    "Resources cannot be generated without SERP data or --resources-list.\n"
    "This is a deliberate hard-fail per spec 15.6 to prevent placeholder garbage."
)

# Known domain capitalizations for anchor text formatting
_DOMAIN_DISPLAY: dict[str, str] = {
    "va.gov": "VA.gov",
    "benefits.va.gov": "Benefits.VA.gov",
    "ecfr.gov": "eCFR.gov",
    "fhfa.gov": "FHFA.gov",
    "hud.gov": "HUD.gov",
    "consumerfinance.gov": "ConsumerFinance.gov",
    "freddiemac.com": "FreddieMac.com",
    "fanniemae.com": "FannieMae.com",
    "realtor.org": "Realtor.org",
    "nar.realtor": "NAR.realtor",
    "nmlsconsumeraccess.org": "NMLSConsumerAccess.org",
}


def _domain_display_name(domain: str) -> str:
    """Convert a domain to a display name for anchor text."""
    domain_lower = domain.lower()
    if domain_lower in _DOMAIN_DISPLAY:
        return _DOMAIN_DISPLAY[domain_lower]
    # Generic: capitalize first letter
    return domain[0].upper() + domain[1:] if domain else domain


def format_anchor_text(source: str, title: str) -> str:
    """Format anchor text as '{Source} — {Document Title}' per spec 11.2."""
    source_display = _domain_display_name(source)

    title = title.strip()
    if not title or title.lower() == source.lower():
        title = "Official Resource"

    return f"{source_display} \u2014 {title}"


# Domains to exclude from Resources (aggregators, video, user-generated)
_BLOCKED_DOMAINS = frozenset({
    "apartments.com", "hellolanding.com", "landing.com",
    "youtube.com", "pinterest.com", "reddit.com",
    "medium.com", "quora.com", "facebook.com",
    "tiktok.com", "instagram.com", "twitter.com", "x.com",
})

# Preferred domains (ranked higher, not required)
_PREFERRED_TLDS = {".gov", ".edu", ".mil"}
_PREFERRED_DOMAINS = frozenset({
    "va.gov", "hud.gov", "consumerfinance.gov", "fhfa.gov",
    "freddiemac.com", "fanniemae.com", "realtor.org", "nar.realtor",
    "nytimes.com", "wsj.com", "ap.org", "reuters.com", "bloomberg.com",
    "sanantonioreport.org", "expressnews.com", "statesman.com",
    "mba.org", "nmlsconsumeraccess.org",
})


def _is_blocked_domain(domain: str) -> bool:
    d = domain.lower()
    if d in _BLOCKED_DOMAINS:
        return True
    # Subdomain check (e.g., blog.medium.com)
    for blocked in _BLOCKED_DOMAINS:
        if d.endswith("." + blocked):
            return True
    return False


def _domain_priority(domain: str) -> int:
    """Lower = better. .gov/.edu/preferred get 0, known sources 1, others 2."""
    d = domain.lower()
    for tld in _PREFERRED_TLDS:
        if d.endswith(tld):
            return 0
    if d in _PREFERRED_DOMAINS:
        return 0
    # Known industry/news sources
    if any(d.endswith(t) for t in (".org", ".edu")):
        return 1
    return 2


def build_resources_from_serp(serp: SerpData, site_domain: str = "") -> list[dict]:
    """Extract resource items from SERP data.

    Draws from: primary_sources (authoritative), AI overview references,
    then top organic results as fallback. Filters blocked domains and
    self-citations. Prefers authoritative sources.
    """
    candidates: list[dict] = []
    seen_domains: set[str] = set()
    site_d = site_domain.lower().lstrip("www.") if site_domain else ""

    def _add(url: str, title: str, source: str, domain: str):
        d = domain.lower().lstrip("www.")
        if d in seen_domains or _is_blocked_domain(d):
            return
        # Self-citation filter (Fix F)
        if site_d and d == site_d:
            return
        seen_domains.add(d)
        candidates.append({
            "url": url,
            "anchor": format_anchor_text(source or domain, title),
            "domain": d,
            "priority": _domain_priority(d),
        })

    # Layer 1: Primary authoritative sources (.gov, .edu, etc.)
    for ref in serp.primary_sources(max=8):
        _add(ref.url, ref.title, ref.source or ref.domain, ref.domain)

    # Layer 2: AI overview references
    for ref in serp.ai_overview_references:
        _add(ref.url, ref.title, ref.source or ref.domain, ref.domain)

    # Layer 3: Top organic results (fallback — this was the missing piece)
    for r in serp.top_results:
        _add(r.url, r.title, r.domain, r.domain)

    # Sort by priority (authoritative first), take up to 8
    candidates.sort(key=lambda c: c["priority"])
    return [{"url": c["url"], "anchor": c["anchor"], "domain": c["domain"]}
            for c in candidates[:8]]


def build_resources_from_list(resources_list: list) -> list[dict]:
    """Format manual resources list.

    Each item can be a plain URL string or a dict with url, title, and optional source.
    """
    items: list[dict] = []
    for item in resources_list:
        if isinstance(item, str):
            domain = urlparse(item).netloc.lower().lstrip("www.")
            items.append({
                "url": item,
                "anchor": format_anchor_text(domain, ""),
                "domain": domain,
            })
        elif isinstance(item, dict):
            url = item.get("url", "")
            title = item.get("title", "")
            source = item.get("source", "")
            domain = urlparse(url).netloc.lower().lstrip("www.") if url else ""
            items.append({
                "url": url,
                "anchor": format_anchor_text(source or domain, title),
                "domain": domain,
            })
    return items


def validate_resources(items: list[dict]) -> list[str]:
    """Validate resources per spec Section 15."""
    errors = []

    if len(items) < 3 or len(items) > 8:
        errors.append(f"Resources has {len(items)} items, expected 3-8 (spec 15.1, relaxed from 5)")

    domains = {item["domain"] for item in items if item.get("domain")}
    if len(domains) < 3:
        errors.append(
            f"Resources has {len(domains)} distinct domains, need >=3 (spec 15.2)"
        )

    for item in items:
        anchor = item.get("anchor", "")
        if not re.match(r"^.+\s*[\u2014:\u2013]\s*.+$", anchor):
            errors.append(
                f"Anchor not in source-title format: '{anchor[:60]}' (spec 15.4)"
            )

    return errors


def render_resources_html(items: list[dict]) -> str:
    """Render resources as HTML per spec 15.5."""
    lines = [
        '<footer class="rl-resources">',
        "  <h2>Resources Used</h2>",
        "  <ul>",
    ]
    for item in items:
        url = item["url"]
        anchor = item["anchor"]
        lines.append(
            f'    <li><a href="{url}" target="_blank" '
            f'rel="noopener noreferrer">{anchor}</a></li>'
        )
    lines.append("  </ul>")
    lines.append("</footer>")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Build the Resources Used section (spec Section 15)"
    )
    parser.add_argument("--site", required=True, help="Site slug")
    parser.add_argument("--target-keyword", required=True, help="Target keyword")
    parser.add_argument(
        "--serp-json",
        help="Path to SERP JSON (optional if --resources-list provided)",
    )
    parser.add_argument(
        "--resources-list",
        help="Path to JSON list of resources (manual override)",
    )
    parser.add_argument("--output", help="Output file path (default: stdout)")
    args = parser.parse_args()

    eprint(f"[build-resources] Building resources for: {args.target_keyword}")

    items: list[dict] = []

    # Path 1: Manual resources list
    if args.resources_list:
        eprint(f"[build-resources] Using manual resources list: {args.resources_list}")
        raw = json.loads(Path(args.resources_list).read_text())
        items = build_resources_from_list(raw)

    # Path 2: SERP data
    if not items and args.serp_json:
        eprint("[build-resources] Extracting from SERP data")
        serp = SerpData(Path(args.serp_json))
        config = load_site_config(args.site)
        site_domain = config.get("SITE_DOMAIN", "")
        items = build_resources_from_serp(serp, site_domain=site_domain)

    # Hard fail per spec 15.6: need at least 3 items (relaxed from 5)
    if len(items) < 3:
        print(HARD_FAIL_MESSAGE, file=sys.stderr)
        sys.exit(1)

    # Cap at 8
    items = items[:8]

    # Validate
    errors = validate_resources(items)
    if errors:
        eprint("[build-resources] Validation warnings:")
        for err in errors:
            eprint(f"  - {err}")

    html = render_resources_html(items)
    domains = {i["domain"] for i in items}
    eprint(
        f"[build-resources] Resources built: {len(items)} items, "
        f"{len(domains)} domains"
    )
    write_output(html, args.output)


if __name__ == "__main__":
    main()
