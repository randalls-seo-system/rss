#!/usr/bin/env python3
"""Build the Explore Resources hub box (spec §7.5).

Reads the anchor pool, finds cluster-related pages for the target keyword,
and renders a deterministic hub box HTML block. Uses a lightweight LLM call
(gpt-5.4-mini) for the 1-2 sentence intro line only.

Usage:
    python3 build-hub-box.py \\
        --site valn \\
        --target-keyword "VA funding fee" \\
        --post-id 833 \\
        --output /path/to/hub-box.html
"""

import argparse
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
MODULE_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(MODULE_DIR))

from lib.anchor_pool import AnchorPool
from lib.llm_client import LLMClient
from lib.site_config import load_site_config
from lib.tool_utils import eprint, extract_html, write_output

# Pages to exclude from hub box (utility/legal, not content)
_SKIP_SLUGS = frozenset({
    "home", "", "privacy-policy", "terms", "legal", "disclaimer",
    "advertising-disclosures", "compare-loan-offers", "contact",
    "va-loan-network-editorial-team", "apply", "confirmation",
    "about-us", "about", "scholarship", "editorial-team",
})

# Mechanical model for intro line generation
MECHANICAL_PROVIDER = "openai"
MECHANICAL_MODEL = "gpt-5.4-mini"


def _slug_from_url(url: str) -> str:
    """Extract slug from URL path."""
    path = url.rstrip("/").split("/")
    return path[-1] if path else ""


def _build_intro_line(keyword: str, site_slug: str) -> str:
    """Generate a 1-2 sentence cluster description via gpt-5.4-mini."""
    prompt = (
        f'Write a single sentence (15-25 words) describing a collection of articles '
        f'about "{keyword}" for a mortgage/lending website. The sentence introduces '
        f'a list of related resource links. Do NOT use "discover", "explore", "dive into", '
        f'"navigate", or any filler. Write like a loan officer pointing to related pages. '
        f'Return ONLY the sentence, no quotes, no HTML.'
    )
    try:
        client = LLMClient(provider=MECHANICAL_PROVIDER, model=MECHANICAL_MODEL)
        cache_key = f"{site_slug}|{keyword}|hub-box-intro"
        response = client.call(prompt, cache_key=cache_key, max_tokens=100)
        text = response.text.strip().strip('"').strip("'")
        if text and len(text.split()) >= 8:
            return text
    except Exception as e:
        eprint(f"[build-hub-box] Intro generation failed: {e}")
    # Fallback: generic intro
    return f"These articles cover key topics related to {keyword}."


def _build_link_description(title: str, keyword: str) -> str:
    """Generate a 6-12 word description for a hub box link via gpt-5.4-mini."""
    prompt = (
        f'Write a 6-10 word description for a page titled "{title}" in the context '
        f'of "{keyword}". The description appears after a dash in a link list. '
        f'Be specific and factual. No filler. Return ONLY the description, no quotes.'
    )
    try:
        client = LLMClient(provider=MECHANICAL_PROVIDER, model=MECHANICAL_MODEL)
        cache_key = f"hub-desc|{title[:40]}"
        response = client.call(prompt, cache_key=cache_key, max_tokens=50)
        text = response.text.strip().strip('"').strip("'").rstrip(".")
        if text and 4 <= len(text.split()) <= 15:
            return text
    except Exception:
        pass
    # Fallback: use title as description
    return title


def main():
    parser = argparse.ArgumentParser(
        description="Build Explore Resources hub box (spec §7.5)"
    )
    parser.add_argument("--site", required=True, help="Site slug")
    parser.add_argument("--target-keyword", required=True, help="Target keyword")
    parser.add_argument("--post-id", required=True, type=int, help="Current post ID (excluded from hub box)")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    args = parser.parse_args()

    eprint(f"[build-hub-box] Building hub box for: {args.target_keyword}")

    # Load anchor pool
    pool = AnchorPool(args.site)
    candidates = pool.candidates_for_topic(
        args.target_keyword,
        max=15,
        exclude_post_id=args.post_id,
    )

    # Filter out utility pages
    candidates = [
        c for c in candidates
        if _slug_from_url(c.url) not in _SKIP_SLUGS
    ]

    # Need at least 3 cluster siblings per spec §7.5.2.4
    if len(candidates) < 3:
        eprint(f"[build-hub-box] Only {len(candidates)} candidates found (need ≥3). Omitting hub box.")
        write_output("", args.output)
        return

    # Cap at 7 links per spec §7.5.2.1
    candidates = candidates[:7]

    eprint(f"[build-hub-box] Found {len(candidates)} cluster pages")

    # Load site config for title lookup
    config = load_site_config(args.site)

    # Build the hub box title from keyword
    # Capitalize first letter of each significant word
    topic_title = args.target_keyword.title()

    # Generate intro line
    intro = _build_intro_line(args.target_keyword, args.site)

    # Build link list items with descriptions
    link_items = []
    for c in candidates:
        # Get page title from anchor pool destinations
        title = ""
        for dest in pool._destinations:
            if pool._normalize_url(dest.get("url", "")) == c.url:
                title = dest.get("title", "")
                break
        if not title:
            title = _slug_from_url(c.url).replace("-", " ").title()

        desc = _build_link_description(title, args.target_keyword)
        link_items.append(f'    <li><a href="{c.url}">{title}</a> — {desc}</li>')

    # Assemble hub box HTML per spec §7.5.1
    html = (
        f'<aside class="rl-cluster-box">\n'
        f'  <h2>Explore {topic_title} Resources</h2>\n'
        f'  <p>{intro}</p>\n'
        f'  <ul>\n'
        + "\n".join(link_items) + "\n"
        f'  </ul>\n'
        f'</aside>'
    )

    eprint(f"[build-hub-box] Hub box built: {len(candidates)} links")
    write_output(html, args.output)


if __name__ == "__main__":
    main()
