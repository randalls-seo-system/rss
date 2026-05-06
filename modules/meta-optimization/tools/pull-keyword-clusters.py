#!/usr/bin/env python3
"""Pull GSC keyword clusters per page URL.

Reads a candidates CSV (must have 'url' column), queries GSC for
each page's top N queries, and saves the full cluster data as JSON.
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add parent dir so we can import lib
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.gsc_client import GSCClient


def load_site_conf(site_slug):
    conf_path = Path(__file__).resolve().parent.parent.parent.parent / 'sites' / f'{site_slug}.conf'
    if not conf_path.exists():
        sys.exit(f"Site config not found: {conf_path}")
    conf = {}
    with open(conf_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                conf[key.strip()] = val.strip().strip('"')
    return conf


def main():
    parser = argparse.ArgumentParser(description='Pull GSC keyword clusters per page')
    parser.add_argument('--site', required=True, help='Site slug (reads sites/<slug>.conf)')
    parser.add_argument('--candidates-csv', required=True, help='CSV with url column')
    parser.add_argument('--output-json', help='Output path (default: auto)')
    parser.add_argument('--days', type=int, default=90, help='Lookback days (default: 90)')
    parser.add_argument('--rows-per-page', type=int, default=100, help='Max queries per page (default: 100)')
    parser.add_argument('--service-account', help='Path to service account JSON')
    parser.add_argument('--dry-run', action='store_true', help='Validate inputs only')
    args = parser.parse_args()

    conf = load_site_conf(args.site)
    gsc_property = conf.get('GSC_PROPERTY', f"sc-domain:{conf.get('SITE_DOMAIN', '')}")
    sa_path = args.service_account or conf.get('GSC_SERVICE_ACCOUNT', '')
    if not sa_path:
        sa_path = os.path.expanduser('~/valn-rewrite/.gsc-credentials.json')

    output_path = args.output_json or os.path.expanduser(
        f'~/{args.site}-rewrite/audits/keyword-clusters.json')

    # Load candidates
    with open(args.candidates_csv) as f:
        candidates = list(csv.DictReader(f))
    urls = [c['url'] for c in candidates if 'url' in c]

    print(f"Site: {args.site} ({gsc_property})")
    print(f"Candidates: {len(urls)}")
    print(f"Lookback: {args.days} days")
    print(f"Output: {output_path}")

    if args.dry_run:
        print("Dry run — skipping API calls.")
        return

    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=args.days)).strftime('%Y-%m-%d')

    client = GSCClient(sa_path)
    results = {}
    total_queries = 0

    for i, url in enumerate(urls):
        try:
            rows = client.get_queries_for_page(
                gsc_property, url, start_date, end_date,
                row_limit=args.rows_per_page
            )
            results[url] = [
                {
                    'query': r['keys'][0],
                    'clicks': r['clicks'],
                    'impressions': r['impressions'],
                    'ctr': round(r['ctr'], 4),
                    'position': round(r['position'], 1),
                }
                for r in rows
            ]
            total_queries += len(rows)
        except Exception as e:
            results[url] = []
            print(f"  ERROR {url}: {e}")

        if (i + 1) % 50 == 0:
            print(f"  {i+1}/{len(urls)} done | {total_queries} queries")

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)

    pages_with_data = sum(1 for v in results.values() if v)
    print(f"\nDone. {pages_with_data} pages with data, {total_queries} total queries.")
    print(f"Saved to {output_path}")


if __name__ == '__main__':
    main()
