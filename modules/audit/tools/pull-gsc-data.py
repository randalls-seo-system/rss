#!/usr/bin/env python3
"""
Pull or parse GSC performance data for audit analysis.

Can either pull via GSC API (requires credentials) or parse a GSC
zip export downloaded from Search Console UI.

Usage:
    # Parse downloaded GSC export:
    python3 pull-gsc-data.py --site lrg --gsc-export ~/Downloads/lrgrealty.com-Performance.zip \
        --output-dir audits/

    # Pull via API (requires GSC credentials configured):
    python3 pull-gsc-data.py --site lrg --output-dir audits/ --days 90
"""

import argparse
import csv
import os
import sys
import zipfile
from datetime import datetime


def parse_gsc_zip(zip_path: str, output_dir: str) -> dict:
    """Parse GSC performance zip export into standardized CSVs.

    Returns dict with paths to pages and queries CSVs.
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    pages_out = os.path.join(output_dir, f"gsc-pages-{date_str}.csv")
    queries_out = os.path.join(output_dir, f"gsc-queries-{date_str}.csv")

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()

        # Find Pages.csv and Queries.csv
        pages_file = next((n for n in names if "Pages" in n and n.endswith(".csv")), None)
        queries_file = next((n for n in names if "Queries" in n and n.endswith(".csv")), None)

        if pages_file:
            with zf.open(pages_file) as f:
                content = f.read().decode("utf-8-sig")
                reader = csv.DictReader(content.splitlines())
                rows = list(reader)

                # Standardize column names
                standardized = []
                for row in rows:
                    std_row = {}
                    for k, v in row.items():
                        key = k.strip().lower().replace(" ", "_")
                        # Map GSC column names to standard names
                        if key in ("top_pages", "page", "url"):
                            key = "url"
                        elif key == "clicks":
                            key = "clicks"
                        elif key == "impressions":
                            key = "impressions"
                        elif key == "ctr":
                            key = "ctr"
                        elif key in ("position", "average_position"):
                            key = "position"
                        std_row[key] = v
                    standardized.append(std_row)

                if standardized:
                    with open(pages_out, "w", newline="") as out:
                        fieldnames = ["url", "clicks", "impressions", "ctr", "position"]
                        writer = csv.DictWriter(out, fieldnames=fieldnames, extrasaction="ignore")
                        writer.writeheader()
                        for row in standardized:
                            # Clean numeric values
                            for field in ["clicks", "impressions", "position"]:
                                if field in row:
                                    row[field] = str(row[field]).replace(",", "")
                            writer.writerow(row)

                    print(f"  Pages: {len(standardized)} URLs → {pages_out}", file=sys.stderr)
                else:
                    print(f"  Pages: empty", file=sys.stderr)
        else:
            print(f"  WARNING: No Pages.csv in zip", file=sys.stderr)

        if queries_file:
            with zf.open(queries_file) as f:
                content = f.read().decode("utf-8-sig")
                reader = csv.DictReader(content.splitlines())
                rows = list(reader)

                standardized = []
                for row in rows:
                    std_row = {}
                    for k, v in row.items():
                        key = k.strip().lower().replace(" ", "_")
                        if key in ("top_queries", "query"):
                            key = "query"
                        elif key == "clicks":
                            key = "clicks"
                        elif key == "impressions":
                            key = "impressions"
                        elif key == "ctr":
                            key = "ctr"
                        elif key in ("position", "average_position"):
                            key = "position"
                        std_row[key] = v
                    standardized.append(std_row)

                if standardized:
                    with open(queries_out, "w", newline="") as out:
                        fieldnames = ["query", "clicks", "impressions", "ctr", "position"]
                        writer = csv.DictWriter(out, fieldnames=fieldnames, extrasaction="ignore")
                        writer.writeheader()
                        for row in standardized:
                            for field in ["clicks", "impressions"]:
                                if field in row:
                                    row[field] = str(row[field]).replace(",", "")
                            writer.writerow(row)

                    print(f"  Queries: {len(standardized)} → {queries_out}", file=sys.stderr)
        else:
            print(f"  WARNING: No Queries.csv in zip", file=sys.stderr)

    return {"pages": pages_out, "queries": queries_out}


def main():
    parser = argparse.ArgumentParser(description="Pull or parse GSC performance data.")
    parser.add_argument("--site", required=True, help="Site slug")
    parser.add_argument("--output-dir", required=True, help="Output directory for CSVs")
    parser.add_argument("--gsc-export", help="Path to GSC zip export (skip API pull)")
    parser.add_argument("--days", type=int, default=90, help="Days of data to pull (API mode)")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    print(f"=== GSC Data ===", file=sys.stderr)
    print(f"Site: {args.site}", file=sys.stderr)

    if args.gsc_export:
        if not os.path.exists(args.gsc_export):
            print(f"ERROR: GSC export not found: {args.gsc_export}", file=sys.stderr)
            sys.exit(1)
        print(f"Parsing GSC export: {args.gsc_export}", file=sys.stderr)
        paths = parse_gsc_zip(args.gsc_export, args.output_dir)
    else:
        print("ERROR: API mode not yet implemented. Use --gsc-export with a downloaded zip.", file=sys.stderr)
        sys.exit(1)

    print(f"\nOutput directory: {args.output_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
