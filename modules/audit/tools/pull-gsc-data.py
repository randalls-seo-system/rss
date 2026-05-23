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
import re
import sys
import zipfile
from datetime import datetime, timedelta
from pathlib import Path


def load_site_config(site_slug: str) -> dict:
    """Load site config from sites/<slug>.conf, return as dict."""
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent.parent  # modules/audit/tools -> repo root
    conf_path = repo_root / "sites" / f"{site_slug}.conf"
    if not conf_path.exists():
        print(f"ERROR: Site config not found: {conf_path}", file=sys.stderr)
        sys.exit(1)
    config = {}
    with open(conf_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("["):
                continue
            m = re.match(r'^([A-Z_]+)="?(.*?)"?\s*$', line)
            if m:
                config[m.group(1)] = m.group(2)
    return config


def find_credentials() -> str:
    """Find GSC service account credentials file.

    Checks (in order):
      1. ~/randalls-seo-system/.gsc-credentials.json
      2. ~/valn-rewrite/.gsc-credentials.json  (legacy fallback)
    """
    home = Path.home()
    primary = home / "randalls-seo-system" / ".gsc-credentials.json"
    fallback = home / "valn-rewrite" / ".gsc-credentials.json"
    if primary.exists():
        return str(primary)
    if fallback.exists():
        return str(fallback)
    print(
        "ERROR: GSC credentials not found.\n"
        f"  Checked: {primary}\n"
        f"  Checked: {fallback}\n"
        "  Place service account JSON at: {primary}",
        file=sys.stderr,
    )
    sys.exit(1)


def pull_gsc_api(site_slug: str, days: int, output_dir: str) -> dict:
    """Pull GSC data via Search Analytics API.

    Returns dict with paths to pages and queries CSVs.
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        print(
            "ERROR: Google API packages not installed.\n"
            "  Run: pip install google-api-python-client google-auth",
            file=sys.stderr,
        )
        sys.exit(1)

    config = load_site_config(site_slug)
    gsc_property = config.get("GSC_PROPERTY")
    if not gsc_property:
        print(
            f"ERROR: GSC_PROPERTY not set in sites/{site_slug}.conf\n"
            f"  Add: GSC_PROPERTY=\"sc-domain:yourdomain.com\"",
            file=sys.stderr,
        )
        sys.exit(1)

    creds_path = find_credentials()
    print(f"Credentials: {creds_path}", file=sys.stderr)
    print(f"GSC Property: {gsc_property}", file=sys.stderr)

    credentials = service_account.Credentials.from_service_account_file(
        creds_path, scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
    )
    service = build("searchconsole", "v1", credentials=credentials)

    end_date = datetime.now() - timedelta(days=3)  # GSC data lags ~3 days
    start_date = end_date - timedelta(days=days)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    print(f"Date range: {start_str} to {end_str} ({days} days)", file=sys.stderr)

    date_str = datetime.now().strftime("%Y-%m-%d")
    pages_out = os.path.join(output_dir, f"gsc-pages-{date_str}.csv")
    queries_out = os.path.join(output_dir, f"gsc-queries-{date_str}.csv")

    # --- Pages (top 1000 by impressions) ---
    print("Pulling page-level data...", file=sys.stderr)
    page_response = service.searchanalytics().query(
        siteUrl=gsc_property,
        body={
            "startDate": start_str,
            "endDate": end_str,
            "dimensions": ["page"],
            "rowLimit": 1000,
            "dataState": "final",
        },
    ).execute()

    page_rows = page_response.get("rows", [])
    with open(pages_out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "clicks", "impressions", "ctr", "position"])
        writer.writeheader()
        for row in page_rows:
            writer.writerow({
                "url": row["keys"][0],
                "clicks": int(row["clicks"]),
                "impressions": int(row["impressions"]),
                "ctr": round(row["ctr"], 4),
                "position": round(row["position"], 1),
            })
    print(f"  Pages: {len(page_rows)} URLs → {pages_out}", file=sys.stderr)

    # --- Queries (top 5000 by impressions) ---
    print("Pulling query-level data...", file=sys.stderr)
    query_response = service.searchanalytics().query(
        siteUrl=gsc_property,
        body={
            "startDate": start_str,
            "endDate": end_str,
            "dimensions": ["query"],
            "rowLimit": 5000,
            "dataState": "final",
        },
    ).execute()

    query_rows = query_response.get("rows", [])
    with open(queries_out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["query", "clicks", "impressions", "ctr", "position"])
        writer.writeheader()
        for row in query_rows:
            writer.writerow({
                "query": row["keys"][0],
                "clicks": int(row["clicks"]),
                "impressions": int(row["impressions"]),
                "ctr": round(row["ctr"], 4),
                "position": round(row["position"], 1),
            })
    print(f"  Queries: {len(query_rows)} → {queries_out}", file=sys.stderr)

    return {"pages": pages_out, "queries": queries_out}


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
        print(f"Pulling via GSC API (last {args.days} days)", file=sys.stderr)
        paths = pull_gsc_api(args.site, args.days, args.output_dir)

    print(f"\nOutput directory: {args.output_dir}", file=sys.stderr)


if __name__ == "__main__":
    main()
