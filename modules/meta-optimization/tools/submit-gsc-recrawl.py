#!/usr/bin/env python3
"""Submit URL_UPDATED notifications to GSC Indexing API for fast re-crawl."""

import argparse
import csv
import os
import sys
import time
from pathlib import Path

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
    parser = argparse.ArgumentParser(description='Submit URLs for GSC re-crawl')
    parser.add_argument('--site', required=True, help='Site slug')
    parser.add_argument('--urls-csv', required=True, help='CSV with url column')
    parser.add_argument('--max', type=int, default=50, help='Max URLs to submit')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    conf = load_site_conf(args.site)
    sa_path = conf.get('GSC_SERVICE_ACCOUNT', '')
    if not sa_path:
        sa_path = os.path.expanduser('~/valn-rewrite/.gsc-credentials.json')

    with open(args.urls_csv) as f:
        reader = csv.DictReader(f)
        urls = [row['url'] for row in reader if 'url' in row][:args.max]

    print(f"Submitting {len(urls)} URLs for re-crawl...")

    if args.dry_run:
        for u in urls[:5]:
            print(f"  DRY: {u}")
        print(f"  ... ({len(urls)} total)")
        return

    client = GSCClient(sa_path)
    success = 0
    errors = 0

    for url in urls:
        try:
            client.submit_url_for_indexing(url)
            success += 1
            if success % 10 == 0:
                print(f"  {success}/{len(urls)} submitted")
        except Exception as e:
            errors += 1
            print(f"  ERROR: {url} - {e}")
        time.sleep(1)

    print(f"\nDone. {success} submitted, {errors} errors.")


if __name__ == '__main__':
    main()
