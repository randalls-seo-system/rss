#!/usr/bin/env python3
"""
Master SERP analyzer. Extracts all features using provider router.

Usage:
    python3 analyze-serp.py --keyword "best neighborhoods in austin" --site lrg
    python3 analyze-serp.py --keywords-csv keywords.csv --site lrg --output-dir serp/
"""

import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
from cache import SerpCache
from provider import SerpProviderRouter


def get_providers(provider_arg: str):
    """Instantiate providers based on --provider flag."""
    providers = []

    if provider_arg in ("auto", "serpdev", "serper"):
        try:
            from serpdev_client import SerperDevClient
            providers.append(SerperDevClient())
        except (ValueError, Exception) as e:
            if provider_arg == "serpdev":
                print(f"ERROR: SerpDev unavailable: {e}", file=sys.stderr)
                sys.exit(1)
            # auto mode: skip unavailable

    if provider_arg in ("auto", "serpapi"):
        try:
            from serpapi_client import SerpAPIClient
            providers.append(SerpAPIClient())
        except (ValueError, Exception) as e:
            if provider_arg == "serpapi":
                print(f"ERROR: SerpAPI unavailable: {e}", file=sys.stderr)
                sys.exit(1)

    if not providers:
        print("ERROR: No SERP providers available. Set SERPAPI_KEY or SERPDEV_API_KEY.", file=sys.stderr)
        sys.exit(1)

    return providers


def analyze_keyword(keyword: str, router: SerpProviderRouter, cache: SerpCache,
                    location: str, device: str, skip_cache: bool) -> dict:
    """Analyze a single keyword."""
    # Check cache (keyed by first provider)
    if not skip_cache:
        cached = cache.get("router", keyword, location, device)
        if cached:
            print(f"  [cache hit]", file=sys.stderr, end="")
            return cached

    result = router.search_and_extract(keyword, location=location, device=device)

    # Add metadata
    result["queried_at"] = datetime.utcnow().isoformat() + "Z"
    result["intent_signals"] = {
        "has_local_pack": result.get("local_pack") is not None,
        "has_ai_overview": result.get("ai_overview") is not None,
        "has_paa": bool(result.get("paa")),
        "has_featured_snippet": result.get("has_featured_snippet", False),
        "has_knowledge_panel": result.get("knowledge_panel") is not None,
    }

    # Cache result
    cache.set("router", keyword, location, device, result)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Master SERP analyzer with multi-provider routing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Output JSON includes: top_results, paa, ai_overview, knowledge_panel,
local_pack, related_searches, intent_signals, providers_used.

Examples:
  %(prog)s --keyword "va loan requirements" --site valn --output-json serp/va-loan-req.json
  %(prog)s --keywords-csv keywords.csv --site lrg --output-dir serp/
        """,
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--keyword", help="Single keyword to analyze")
    input_group.add_argument("--keywords-csv", help="CSV with 'keyword' column")

    parser.add_argument("--site", help="Site slug (for cache directory)")
    parser.add_argument("--output-json", help="Output JSON path (single keyword)")
    parser.add_argument("--output-dir", help="Output directory (batch mode)")
    parser.add_argument("--provider", choices=["auto", "serpdev", "serpapi"], default="auto",
                        help="Provider selection (default: auto)")
    parser.add_argument("--location", default="United States", help="Search location")
    parser.add_argument("--device", choices=["desktop", "mobile"], default="desktop")
    parser.add_argument("--skip-cache", action="store_true", help="Bypass cache")
    args = parser.parse_args()

    # Setup
    providers = get_providers(args.provider)
    router = SerpProviderRouter(providers)
    cache_dir = os.path.expanduser(f"~/{args.site}-rewrite/serp/cache/") if args.site else "/tmp/serp-cache/"
    cache = SerpCache(cache_dir)

    print(f"=== SERP Analyzer ===", file=sys.stderr)
    print(f"Providers: {[p.name for p in providers]}", file=sys.stderr)
    print(f"Cache: {cache_dir}", file=sys.stderr)
    print(file=sys.stderr)

    if args.keyword:
        # Single keyword
        print(f"Analyzing: {args.keyword}", file=sys.stderr, end="")
        result = analyze_keyword(args.keyword, router, cache, args.location, args.device, args.skip_cache)
        print(f" → {len(result.get('top_results', []))} results, "
              f"{len(result.get('paa', []))} PAA, "
              f"AI Overview: {'yes' if result.get('ai_overview') else 'no'}, "
              f"providers: {result.get('providers_used', [])}", file=sys.stderr)

        output = json.dumps(result, indent=2)
        if args.output_json:
            os.makedirs(os.path.dirname(os.path.abspath(args.output_json)), exist_ok=True)
            with open(args.output_json, "w") as f:
                f.write(output)
            print(f"\nOutput: {args.output_json}", file=sys.stderr)
        else:
            print(output)

    elif args.keywords_csv:
        output_dir = args.output_dir or (f"~/{args.site}-rewrite/serp/" if args.site else "/tmp/serp/")
        output_dir = os.path.expanduser(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        with open(args.keywords_csv) as f:
            reader = csv.DictReader(f)
            keywords = [row.get("keyword", row.get("query", "")).strip() for row in reader]
            keywords = [k for k in keywords if k]

        print(f"Processing {len(keywords)} keywords", file=sys.stderr)
        for i, kw in enumerate(keywords):
            slug = re.sub(r"[^a-z0-9]+", "-", kw.lower())[:80]
            print(f"  [{i+1}/{len(keywords)}] {kw}", file=sys.stderr, end="")
            result = analyze_keyword(kw, router, cache, args.location, args.device, args.skip_cache)
            out_path = os.path.join(output_dir, f"{slug}.json")
            with open(out_path, "w") as f:
                json.dump(result, f, indent=2)
            print(f" → {out_path}", file=sys.stderr)

        print(f"\nDone. {len(keywords)} keywords analyzed.", file=sys.stderr)


if __name__ == "__main__":
    main()
