#!/usr/bin/env python3
"""
Port proprietary CSS class systems to rl-* namespace.

Converts site-specific class prefixes (vln-, valn-, lrg-, cnp-) to the
universal rl-* prefix used by rl-components.

Usage:
    python3 port-source-css.py --source-css ~/css/vln-pages.css \
        --source-prefix vln --output-css ~/css/rl-base-ported.css

    python3 port-source-css.py --source-css ~/css/vln-pages.css \
        --source-prefix vln --output-css /dev/null --dry-run
"""

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
from css_validator import parse_css, detect_class_prefixes


def camel_to_kebab(name: str) -> str:
    """Convert CamelCase to kebab-case: vlnNextPill → vln-next-pill."""
    s = re.sub(r"([A-Z])", r"-\1", name).lower()
    return s.lstrip("-")


def build_default_mappings(source_prefix: str) -> list[tuple]:
    """Build default prefix-to-rl transformation rules.

    Returns list of (pattern, replacement) tuples applied in order.
    """
    p = source_prefix
    P = p[0].upper() + p[1:]  # Capitalized version

    return [
        # CamelCase class names: vlnNextPill → rl-next-pill
        # Applied via function, not simple regex
        ("camelcase", None),
        # Hyphenated: vln-hero → rl-hero
        (rf"\.{p}-", ".rl-"),
        # Exact prefix class: .vlnPage → .rl-page (after camelcase conversion)
        (rf"\.{p}([A-Z])", lambda m: f".rl-{m.group(1).lower()}"),
    ]


def convert_css(css_text: str, source_prefix: str, explicit_mappings: dict = None) -> tuple[str, dict]:
    """Convert CSS from source prefix to rl-* prefix.

    Returns (converted_css, stats_dict).
    """
    p = source_prefix
    result = css_text
    stats = {"total_replacements": 0, "camelcase_conversions": 0, "prefix_swaps": 0}

    # Apply explicit mappings first (highest priority)
    if explicit_mappings:
        for old, new in explicit_mappings.items():
            count = result.count(old)
            if count > 0:
                result = result.replace(old, new)
                stats["total_replacements"] += count

    # Convert CamelCase: .vlnNextPill → .rl-next-pill
    def camel_replacer(match):
        full = match.group(0)
        cls_name = match.group(1)
        kebab = camel_to_kebab(cls_name)
        # Remove the source prefix from the kebab version
        if kebab.startswith(f"{p}-"):
            kebab = kebab[len(p) + 1:]
        elif kebab.startswith(p):
            kebab = kebab[len(p):]
        stats["camelcase_conversions"] += 1
        stats["total_replacements"] += 1
        return f".rl-{kebab}"

    # Match .vlnCamelCase patterns
    camel_pattern = rf"\.({p}[A-Z][a-zA-Z]*)"
    result = re.sub(camel_pattern, camel_replacer, result)

    # Convert hyphenated: .vln-hero → .rl-hero
    count = len(re.findall(rf"\.{p}-", result))
    result = re.sub(rf"\.{p}-", ".rl-", result)
    stats["prefix_swaps"] += count
    stats["total_replacements"] += count

    # Convert bare prefix references in selectors: .vln → .rl (less common)
    # Only if followed by space, comma, {, or end of selector
    count2 = len(re.findall(rf"\.{p}(?=[\s,{{>+~:])", result))
    result = re.sub(rf"\.{p}(?=[\s,{{>+~:])", ".rl", result)
    stats["prefix_swaps"] += count2
    stats["total_replacements"] += count2

    return result, stats


def main():
    parser = argparse.ArgumentParser(
        description="Port CSS from proprietary class system to rl-* namespace.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Transformations applied:
  .vlnNextPill     → .rl-next-pill      (CamelCase to kebab)
  .vln-hero        → .rl-hero           (prefix swap)
  .vlnCallout      → .rl-callout        (CamelCase to kebab)

Explicit mappings (via --mapping-file) override automatic rules.

Examples:
  %(prog)s --source-css vln-pages.css --source-prefix vln --output-css rl-base.css
  %(prog)s --source-css lrg-styles.css --source-prefix lrg --output-css rl-base.css --dry-run
        """,
    )

    parser.add_argument("--source-css", required=True, help="Source CSS file path")
    parser.add_argument("--source-prefix", required=True, help="Source class prefix (e.g., vln, lrg)")
    parser.add_argument("--output-css", required=True, help="Output CSS file path")
    parser.add_argument("--mapping-file", help="JSON file with explicit class mappings (old→new)")
    parser.add_argument("--dry-run", action="store_true", help="Show stats without writing output")
    args = parser.parse_args()

    if not os.path.exists(args.source_css):
        print(f"ERROR: Source CSS not found: {args.source_css}", file=sys.stderr)
        sys.exit(1)

    with open(args.source_css) as f:
        source = f.read()

    # Load explicit mappings
    explicit = {}
    if args.mapping_file and os.path.exists(args.mapping_file):
        with open(args.mapping_file) as f:
            explicit = json.load(f)

    print(f"=== CSS Port: {args.source_prefix} → rl-* ===", file=sys.stderr)
    print(f"Source: {args.source_css}", file=sys.stderr)

    source_stats = parse_css(source, args.source_css)
    print(f"Source: {source_stats.file_size:,} bytes, {source_stats.selector_count} selectors", file=sys.stderr)

    # Detect prefix usage before conversion
    prefixes_before = detect_class_prefixes(source, [args.source_prefix, "rl"])
    source_classes = len(prefixes_before.get(args.source_prefix, []))
    print(f"Source prefix classes: {source_classes}", file=sys.stderr)

    # Convert
    converted, stats = convert_css(source, args.source_prefix, explicit)

    output_stats = parse_css(converted)
    print(f"\nOutput: {output_stats.file_size:,} bytes, {output_stats.selector_count} selectors", file=sys.stderr)
    print(f"Replacements: {stats['total_replacements']}", file=sys.stderr)
    print(f"  CamelCase conversions: {stats['camelcase_conversions']}", file=sys.stderr)
    print(f"  Prefix swaps: {stats['prefix_swaps']}", file=sys.stderr)

    # Check for remnants
    prefixes_after = detect_class_prefixes(converted, [args.source_prefix])
    remnants = prefixes_after.get(args.source_prefix, [])
    if remnants:
        print(f"\nWARNING: {len(remnants)} source-prefix remnants:", file=sys.stderr)
        for r in remnants[:10]:
            print(f"  .{r}", file=sys.stderr)
    else:
        print(f"\nZero {args.source_prefix}-* remnants in output", file=sys.stderr)

    if args.dry_run:
        print(f"\n[DRY RUN] Would write {output_stats.file_size:,} bytes to {args.output_css}", file=sys.stderr)
    else:
        os.makedirs(os.path.dirname(os.path.abspath(args.output_css)), exist_ok=True)
        with open(args.output_css, "w") as f:
            f.write(converted)
        print(f"\nOutput: {args.output_css}", file=sys.stderr)


if __name__ == "__main__":
    main()
