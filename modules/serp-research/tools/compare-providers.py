#!/usr/bin/env python3
"""
Diagnostic: compare SERP data from both providers side-by-side.

Usage:
    python3 compare-providers.py --keyword "best neighborhoods in austin" --output-md comparison.md
"""

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
from cache import SerpCache
from provider import FeatureNotSupported


def main():
    parser = argparse.ArgumentParser(
        description="Compare SERP data from multiple providers.",
        epilog="Shows which features each provider supports and where they differ.",
    )

    parser.add_argument("--keyword", required=True, help="Keyword to compare")
    parser.add_argument("--output-md", required=True, help="Output markdown comparison")
    parser.add_argument("--location", default="United States")
    parser.add_argument("--device", choices=["desktop", "mobile"], default="desktop")
    parser.add_argument("--site", help="Site slug (for cache)")
    args = parser.parse_args()

    cache_dir = os.path.expanduser(f"~/{args.site}-rewrite/serp/cache/") if args.site else "/tmp/serp-cache/"
    cache = SerpCache(cache_dir)

    # Try both providers
    provider_results = {}

    # SerpAPI
    try:
        from serpapi_client import SerpAPIClient
        client = SerpAPIClient()
        cached = cache.get("serpapi", args.keyword, args.location, args.device)
        if cached:
            response = cached
            print(f"SerpAPI: [cache hit]", file=sys.stderr)
        else:
            response = client.search(args.keyword, location=args.location, device=args.device)
            cache.set("serpapi", args.keyword, args.location, args.device, response)
            print(f"SerpAPI: fetched", file=sys.stderr)

        provider_results["serpapi"] = {
            "top_results": client.get_top_results(response),
            "paa_count": len(client.get_paa(response)),
            "related_count": len(client.get_related_searches(response)),
            "has_ai_overview": client.get_ai_overview(response) is not None,
            "has_knowledge_panel": client.get_knowledge_panel(response) is not None,
            "has_local_pack": client.get_local_pack(response) is not None,
            "has_featured_snippet": client.has_featured_snippet(response),
        }
    except Exception as e:
        provider_results["serpapi"] = {"error": str(e)}
        print(f"SerpAPI: {e}", file=sys.stderr)

    # SerpDev
    try:
        from serpdev_client import SerperDevClient
        client = SerperDevClient()
        cached = cache.get("serpdev", args.keyword, args.location, args.device)
        if cached:
            response = cached
            print(f"SerpDev: [cache hit]", file=sys.stderr)
        else:
            response = client.search(args.keyword, location=args.location, device=args.device)
            cache.set("serpdev", args.keyword, args.location, args.device, response)
            print(f"SerpDev: fetched", file=sys.stderr)

        ai_overview = None
        try:
            ai_overview = client.get_ai_overview(response)
        except FeatureNotSupported:
            ai_overview = "NOT_SUPPORTED"

        provider_results["serpdev"] = {
            "top_results": client.get_top_results(response),
            "paa_count": len(client.get_paa(response)),
            "related_count": len(client.get_related_searches(response)),
            "has_ai_overview": ai_overview if ai_overview == "NOT_SUPPORTED" else ai_overview is not None,
            "has_knowledge_panel": client.get_knowledge_panel(response) is not None,
            "has_local_pack": client.get_local_pack(response) is not None,
            "has_featured_snippet": client.has_featured_snippet(response),
        }
    except Exception as e:
        provider_results["serpdev"] = {"error": str(e)}
        print(f"SerpDev: {e}", file=sys.stderr)

    # Generate comparison markdown
    os.makedirs(os.path.dirname(os.path.abspath(args.output_md)), exist_ok=True)
    with open(args.output_md, "w") as f:
        f.write(f"# Provider Comparison: {args.keyword}\n\n")
        f.write(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")

        f.write("## Feature Support\n\n")
        f.write("| Feature | SerpAPI | SerpDev |\n")
        f.write("|---------|---------|--------|\n")

        features = ["has_ai_overview", "has_knowledge_panel", "has_local_pack",
                     "has_featured_snippet", "paa_count", "related_count"]
        for feat in features:
            sa = provider_results.get("serpapi", {}).get(feat, "N/A")
            sd = provider_results.get("serpdev", {}).get(feat, "N/A")
            if sa == "NOT_SUPPORTED":
                sa = "Not supported"
            if sd == "NOT_SUPPORTED":
                sd = "Not supported"
            f.write(f"| {feat} | {sa} | {sd} |\n")

        # Top results comparison
        sa_results = provider_results.get("serpapi", {}).get("top_results", [])
        sd_results = provider_results.get("serpdev", {}).get("top_results", [])

        if sa_results:
            f.write(f"\n## Top Results (SerpAPI: {len(sa_results)})\n\n")
            f.write("| # | Title | URL |\n|---|-------|-----|\n")
            for r in sa_results[:5]:
                f.write(f"| {r['position']} | {r['title'][:60]} | {r['url'][:60]} |\n")

        if sd_results:
            f.write(f"\n## Top Results (SerpDev: {len(sd_results)})\n\n")
            f.write("| # | Title | URL |\n|---|-------|-----|\n")
            for r in sd_results[:5]:
                f.write(f"| {r['position']} | {r['title'][:60]} | {r['url'][:60]} |\n")

        # Errors
        for name in ["serpapi", "serpdev"]:
            err = provider_results.get(name, {}).get("error")
            if err:
                f.write(f"\n## {name} Error\n\n```\n{err}\n```\n")

    print(f"\nOutput: {args.output_md}", file=sys.stderr)


if __name__ == "__main__":
    main()
