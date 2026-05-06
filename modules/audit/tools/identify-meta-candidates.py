#!/usr/bin/env python3
"""
Identify high-impression, low-CTR pages that need title/meta refresh.

Usage:
    python3 identify-meta-candidates.py \
        --gsc-pages-csv audits/gsc-pages.csv \
        --min-impressions 200 --max-ctr 0.025 \
        --output-csv audits/meta-candidates.csv
"""

import argparse
import csv
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Identify meta refresh candidates.")
    parser.add_argument("--gsc-pages-csv", required=True, help="GSC pages traffic CSV")
    parser.add_argument("--inventory-csv", help="WP inventory CSV (for post_id matching)")
    parser.add_argument("--priority-list-csv", help="Exclude full-rewrite priorities")
    parser.add_argument("--min-impressions", type=int, default=200,
                        help="Minimum impressions to qualify (default: 200)")
    parser.add_argument("--max-ctr", type=float, default=0.025,
                        help="Maximum CTR to qualify as 'low' (default: 0.025 = 2.5%%)")
    parser.add_argument("--output-csv", required=True, help="Output CSV")
    args = parser.parse_args()

    # Load priority list exclusions
    priority_slugs = set()
    if args.priority_list_csv and os.path.exists(args.priority_list_csv):
        with open(args.priority_list_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                slug = row.get("slug", row.get("post_name", ""))
                if slug:
                    priority_slugs.add(slug)

    # Load inventory for post_id lookup
    slug_to_id = {}
    if args.inventory_csv and os.path.exists(args.inventory_csv):
        with open(args.inventory_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                slug = row.get("post_name", row.get("slug", ""))
                pid = row.get("ID", row.get("post_id", ""))
                slug_to_id[slug] = pid

    candidates = []
    with open(args.gsc_pages_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("url", "").rstrip("/")
            clicks = int(str(row.get("clicks", "0")).replace(",", "") or 0)
            impressions = int(str(row.get("impressions", "0")).replace(",", "") or 0)
            position = float(str(row.get("position", "0")).replace(",", "") or 0)

            # Parse CTR (handle both "3.17%" and "0.0317" formats)
            ctr_raw = str(row.get("ctr", "0"))
            if "%" in ctr_raw:
                ctr = float(ctr_raw.replace("%", "")) / 100
            else:
                ctr = float(ctr_raw or 0)

            slug = url.split("/")[-1] if "/" in url else url

            if impressions < args.min_impressions:
                continue
            if ctr > args.max_ctr:
                continue
            if slug in priority_slugs:
                continue

            post_id = slug_to_id.get(slug, "")
            ctr_pct = round(ctr * 100, 2)

            candidates.append({
                "post_id": post_id,
                "url": url,
                "slug": slug,
                "clicks": clicks,
                "impressions": impressions,
                "ctr_pct": ctr_pct,
                "position": position,
            })

    # Sort by impressions descending
    candidates.sort(key=lambda x: x["impressions"], reverse=True)

    os.makedirs(os.path.dirname(os.path.abspath(args.output_csv)), exist_ok=True)
    with open(args.output_csv, "w", newline="") as f:
        fieldnames = ["post_id", "url", "slug", "clicks", "impressions", "ctr_pct", "position"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidates)

    print(f"=== Meta Refresh Candidates ===", file=sys.stderr)
    print(f"Candidates: {len(candidates)}", file=sys.stderr)
    print(f"Criteria: impressions >= {args.min_impressions}, CTR <= {args.max_ctr*100:.1f}%", file=sys.stderr)
    print(f"Output: {args.output_csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
