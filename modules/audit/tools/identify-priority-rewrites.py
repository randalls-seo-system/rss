#!/usr/bin/env python3
"""
Identify page 2-3 quick wins: high-impression pages ranking positions 11-30.

Usage:
    python3 identify-priority-rewrites.py \
        --gsc-pages-csv audits/gsc-pages.csv \
        --min-impressions 500 --position-range 11-30 \
        --output-csv audits/priority-rewrites.csv
"""

import argparse
import csv
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Identify page 2-3 ranking opportunities.")
    parser.add_argument("--gsc-pages-csv", required=True, help="GSC pages traffic CSV")
    parser.add_argument("--position-range", default="11-30",
                        help="Position range (default: 11-30)")
    parser.add_argument("--min-impressions", type=int, default=500,
                        help="Minimum impressions (default: 500)")
    parser.add_argument("--output-csv", required=True, help="Output CSV")
    args = parser.parse_args()

    pos_min, pos_max = map(int, args.position_range.split("-"))

    candidates = []
    with open(args.gsc_pages_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("url", "").rstrip("/")
            clicks = int(str(row.get("clicks", "0")).replace(",", "") or 0)
            impressions = int(str(row.get("impressions", "0")).replace(",", "") or 0)
            position = float(str(row.get("position", "0")).replace(",", "") or 0)

            slug = url.split("/")[-1] if "/" in url else url

            if position < pos_min or position > pos_max:
                continue
            if impressions < args.min_impressions:
                continue

            candidates.append({
                "slug": slug,
                "clicks": clicks,
                "impressions": impressions,
                "avg_position": round(position, 1),
            })

    # Sort by impressions descending
    candidates.sort(key=lambda x: x["impressions"], reverse=True)

    os.makedirs(os.path.dirname(os.path.abspath(args.output_csv)), exist_ok=True)
    with open(args.output_csv, "w", newline="") as f:
        fieldnames = ["slug", "clicks", "impressions", "avg_position"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidates)

    print(f"=== Priority Rewrites (Page 2-3) ===", file=sys.stderr)
    print(f"Candidates: {len(candidates)}", file=sys.stderr)
    print(f"Criteria: position {pos_min}-{pos_max}, impressions >= {args.min_impressions}", file=sys.stderr)
    print(f"Output: {args.output_csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
