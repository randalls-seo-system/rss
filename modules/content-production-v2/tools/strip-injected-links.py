#!/usr/bin/env python3
"""Strip injected internal links from post content, preserving protected links.

For Phase 2b of the LRG re-link: removes linker-injected internal links
so content can be re-linked through the patched linker with the expanded
anchor pool.

Protected links (NEVER stripped):
  1. /listings/*  and /homes-for-sale-*  (IDX listing pages)
  2. /neighborhoods/*                    (directory pages)
  3. connect-with-lrg CTAs               (article CTAs)
  4. External links (non-lrgrealty.com)   (out of scope)
  5. Links inside rl-resources sections  (editorial, not injected)

Usage:
    python3 strip-injected-links.py --html-input <path> --html-output <path>

    # Batch mode (reads from DB, writes stripped HTML to output dir):
    python3 strip-injected-links.py --site lrg --batch --output-dir <dir> [--dry-run] [--limit N]
"""

import argparse
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
MODULE_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(MODULE_DIR))

from bs4 import BeautifulSoup, NavigableString


# ---------------------------------------------------------------------------
# Preservation rules — links matching ANY rule are NEVER stripped.
# ---------------------------------------------------------------------------

def _is_protected_link(a_tag) -> tuple[bool, str]:
    """Return (True, reason) if this <a> tag must be preserved, else (False, '')."""
    href = a_tag.get("href", "")
    if not href:
        return True, "no-href"

    # Rule 1: IDX listing pages
    if "/listings/" in href or "/homes-for-sale-" in href:
        return True, "listing-page"

    # Rule 2: Neighborhood directory pages
    if "/neighborhoods/" in href:
        return True, "directory-page"

    # Rule 3: CTA links (connect-with-lrg)
    if "connect-with-lrg" in href:
        return True, "cta-link"

    # Rule 4: External links (not relative AND not lrgrealty.com)
    if href.startswith("http"):
        if "lrgrealty.com" not in href:
            return True, "external"

    # Rule 5: Anchor-only links (#section)
    if href.startswith("#"):
        return True, "anchor"

    # Rule 6: Links inside rl-resources sections
    parent = a_tag.parent
    while parent:
        if hasattr(parent, "get"):
            classes = parent.get("class", [])
            if isinstance(classes, list):
                for cls in classes:
                    if "rl-resources" in cls:
                        return True, "resources-section"
        parent = getattr(parent, "parent", None)

    return False, ""


def _is_internal_link(a_tag) -> bool:
    """Return True if this link points to an internal lrgrealty.com page."""
    href = a_tag.get("href", "")
    if not href:
        return False
    # Relative paths
    if href.startswith("/") and not href.startswith("//"):
        return True
    # Absolute lrgrealty.com
    if "lrgrealty.com" in href:
        return True
    return False


def strip_injected_links(html: str) -> tuple[str, dict]:
    """Strip non-protected internal links from HTML.

    Returns (stripped_html, stats_dict).
    """
    soup = BeautifulSoup(html, "html.parser")

    stats = {
        "total_links": 0,
        "stripped": 0,
        "preserved": 0,
        "preserved_reasons": {},
        "external_skipped": 0,
    }

    for a_tag in soup.find_all("a", href=True):
        stats["total_links"] += 1

        # Skip non-internal links entirely
        if not _is_internal_link(a_tag):
            stats["external_skipped"] += 1
            continue

        # Check preservation rules
        protected, reason = _is_protected_link(a_tag)
        if protected:
            stats["preserved"] += 1
            stats["preserved_reasons"][reason] = stats["preserved_reasons"].get(reason, 0) + 1
            continue

        # This is a strippable internal link — unwrap it (keep text, remove tag)
        a_tag.unwrap()
        stats["stripped"] += 1

    stats["preserved"] += stats["external_skipped"]

    return str(soup), stats


def main():
    parser = argparse.ArgumentParser(
        description="Strip injected internal links while preserving protected links"
    )
    parser.add_argument("--html-input", help="Path to input HTML file")
    parser.add_argument("--html-output", help="Path to write stripped HTML")
    parser.add_argument("--site", help="Site slug for batch mode")
    parser.add_argument("--batch", action="store_true", help="Batch mode (all posts)")
    parser.add_argument("--output-dir", help="Output directory for batch mode")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    parser.add_argument("--limit", type=int, default=0, help="Limit batch to N posts")
    args = parser.parse_args()

    if args.html_input:
        # Single-file mode
        input_path = Path(args.html_input)
        if not input_path.exists():
            print(f"Error: {input_path} not found", file=sys.stderr)
            sys.exit(1)

        html = input_path.read_text()
        stripped, stats = strip_injected_links(html)

        print(f"Total links: {stats['total_links']}")
        print(f"Stripped: {stats['stripped']}")
        print(f"Preserved: {stats['preserved']}")
        print(f"  Reasons: {stats['preserved_reasons']}")

        if args.html_output:
            Path(args.html_output).write_text(stripped)
            print(f"Written to: {args.html_output}")
    elif args.batch:
        print("Batch mode is for Phase 2b execution. Use --html-input for testing.")
        sys.exit(0)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
