#!/usr/bin/env python3
"""
Raw SERP response fetcher. Saves unprocessed provider responses.

Usage:
    python3 pull-serp.py --keyword "va loan requirements" --provider serpapi
    python3 pull-serp.py --keywords-csv keywords.csv --output-dir serp/raw/
"""

import argparse
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
from cache import SerpCache


def get_provider(provider_name: str):
    """Instantiate a specific provider."""
    if provider_name == "serpapi":
        from serpapi_client import SerpAPIClient
        return SerpAPIClient()
    elif provider_name in ("serpdev", "serper"):
        from serpdev_client import SerperDevClient
        return SerperDevClient()
    elif provider_name == "auto":
        try:
            from serpdev_client import SerperDevClient
            return SerperDevClient()
        except ValueError:
            from serpapi_client import SerpAPIClient
            return SerpAPIClient()
    else:
        raise ValueError(f"Unknown provider: {provider_name}")


def main():
    parser = argparse.ArgumentParser(
        description="Raw SERP response fetcher.",
        epilog="Saves raw provider JSON. Use analyze-serp.py for structured extraction.",
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--keyword", help="Single keyword")
    input_group.add_argument("--keywords-csv", help="CSV with 'keyword' column")

    parser.add_argument("--provider", choices=["auto", "serpdev", "serpapi"], default="auto")
    parser.add_argument("--location", default="United States")
    parser.add_argument("--device", choices=["desktop", "mobile"], default="desktop")
    parser.add_argument("--output-dir", help="Output directory for raw JSON")
    parser.add_argument("--site", help="Site slug (for default output path)")
    parser.add_argument("--skip-cache", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    provider = get_provider(args.provider)
    cache_dir = os.path.expanduser(f"~/{args.site}-rewrite/serp/cache/") if args.site else "/tmp/serp-cache/"
    cache = SerpCache(cache_dir)
    output_dir = args.output_dir or os.path.expanduser(f"~/{args.site}-rewrite/serp/raw/" if args.site else "/tmp/serp/raw/")
    os.makedirs(output_dir, exist_ok=True)

    print(f"=== SERP Puller ===", file=sys.stderr)
    print(f"Provider: {provider.name}", file=sys.stderr)

    keywords = []
    if args.keyword:
        keywords = [args.keyword]
    elif args.keywords_csv:
        with open(args.keywords_csv) as f:
            keywords = [row.get("keyword", row.get("query", "")).strip()
                        for row in csv.DictReader(f) if row.get("keyword", row.get("query", ""))]

    for i, kw in enumerate(keywords):
        slug = re.sub(r"[^a-z0-9]+", "-", kw.lower())[:80]
        print(f"  [{i+1}/{len(keywords)}] {kw}", file=sys.stderr, end="")

        if not args.skip_cache:
            cached = cache.get(provider.name, kw, args.location, args.device)
            if cached:
                print(f" [cache hit]", file=sys.stderr)
                continue

        if args.dry_run:
            print(f" [dry run]", file=sys.stderr)
            continue

        response = provider.search(kw, location=args.location, device=args.device)
        cache.set(provider.name, kw, args.location, args.device, response)

        out_path = os.path.join(output_dir, f"{slug}-{provider.name}.json")
        with open(out_path, "w") as f:
            json.dump(response, f, indent=2)
        print(f" → {out_path}", file=sys.stderr)

    print(f"\nDone.", file=sys.stderr)


if __name__ == "__main__":
    main()
