#!/usr/bin/env python3
"""
Generate redirect map from GSC data.

Analyzes Google Search Console URL data to identify URLs that need redirects
(date-path patterns, hash suffixes, broken slugs) and produces a redirect
map CSV with source → target mappings.

Usage:
    python3 generate-redirect-map.py --site lrg \
        --gsc-csv gsc-urls.csv \
        --output redirects/lrg-redirect-map.csv

Input CSV columns (from GSC export):
    url, clicks, impressions, ctr, position

Output CSV columns:
    old_url, new_url, clicks_90d, impressions_90d, ctr, position, issue_type
"""

import argparse
import csv
import os
import re
import sys
from urllib.parse import urlparse


# ── Issue Detection Patterns ─────────────────────────────────────────────────

# Squarespace date-path: /blog/2024/10/19/slug
DATE_PATH_RE = re.compile(r"(/[a-z-]+/)\d{4}/\d{1,2}/\d{1,2}/(.+?)$")

# Hash suffix from Squarespace: slug-abc123xyz
HASH_SUFFIX_RE = re.compile(r"-[a-z0-9]{10,}$")

# Trailing date stamp: slug-2024 or slug-2025
TRAILING_YEAR_RE = re.compile(r"-20\d{2}$")

# Duplicate slug markers: slug-2, slug-3
DUPE_SUFFIX_RE = re.compile(r"-(\d)$")


def detect_issues(url: str, base_path: str = "") -> list[dict]:
    """Detect redirect-worthy issues in a URL.

    Returns list of {issue_type, suggested_target} dicts.
    """
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    issues = []

    # 1. Date-path pattern
    date_match = DATE_PATH_RE.search(path)
    if date_match:
        prefix = date_match.group(1)
        slug = date_match.group(2)
        # Strip hash suffix from slug too
        clean_slug = HASH_SUFFIX_RE.sub("", slug)
        new_path = f"{prefix}{clean_slug}/"
        issue_type = "date_path"
        if clean_slug != slug:
            issue_type = "date_path+hash"
        issues.append({
            "issue_type": issue_type,
            "suggested_target": f"{parsed.scheme}://{parsed.netloc}{new_path}",
        })
        return issues  # date_path is primary; skip other checks

    # 2. Hash suffix only (no date path)
    slug_part = path.split("/")[-1] if "/" in path else path
    hash_match = HASH_SUFFIX_RE.search(slug_part)
    if hash_match:
        clean_slug = HASH_SUFFIX_RE.sub("", slug_part)
        parent = "/".join(path.split("/")[:-1])
        new_path = f"{parent}/{clean_slug}/"
        issues.append({
            "issue_type": "hash_suffix",
            "suggested_target": f"{parsed.scheme}://{parsed.netloc}{new_path}",
        })

    return issues


def generate_redirect_map(gsc_csv: str, site_domain: str, blog_prefix: str = "") -> list[dict]:
    """Process GSC URL data and generate redirect mappings.

    Args:
        gsc_csv: Path to GSC export CSV
        site_domain: Production domain (e.g., lrgrealty.com)
        blog_prefix: Blog path prefix (e.g., /lrg-blog)

    Returns:
        List of redirect map entries
    """
    redirects = []

    with open(gsc_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("url", row.get("URL", "")).strip()
            if not url:
                continue

            # Only process URLs on the target domain
            parsed = urlparse(url)
            if site_domain not in parsed.netloc:
                continue

            issues = detect_issues(url)
            if not issues:
                continue

            issue = issues[0]  # primary issue
            redirects.append({
                "old_url": url,
                "new_url": issue["suggested_target"],
                "clicks_90d": row.get("clicks", row.get("Clicks", "0")),
                "impressions_90d": row.get("impressions", row.get("Impressions", "0")),
                "ctr": row.get("ctr", row.get("CTR", "0%")),
                "position": row.get("position", row.get("Position", "0")),
                "issue_type": issue["issue_type"],
            })

    # Sort by clicks descending (highest traffic first)
    redirects.sort(key=lambda r: int(str(r["clicks_90d"]).replace(",", "") or 0), reverse=True)

    return redirects


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate redirect map from GSC URL data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Issue types detected:
  date_path       Squarespace date-path URL (/blog/2024/10/19/slug)
  date_path+hash  Date-path + hash suffix
  hash_suffix     Squarespace hash suffix only (slug-abc123xyz)

Examples:
  %(prog)s --site lrg --gsc-csv gsc-export.csv --output lrg-redirect-map.csv
  %(prog)s --site tln --gsc-csv tln-gsc.csv --domain thelendersnetwork.com --output tln-redirects.csv
        """,
    )

    parser.add_argument("--site", required=True, help="Site slug (reads sites/<slug>.conf)")
    parser.add_argument("--gsc-csv", required=True, help="GSC URL export CSV")
    parser.add_argument("--domain", help="Override production domain (default: from site config)")
    parser.add_argument("--output", required=True, help="Output redirect map CSV path")

    args = parser.parse_args()

    # Read domain from config if not overridden
    domain = args.domain
    if not domain:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
        conf_path = os.path.join(root_dir, "sites", f"{args.site}.conf")
        if os.path.exists(conf_path):
            with open(conf_path) as f:
                for line in f:
                    if line.startswith("SITE_DOMAIN="):
                        domain = line.split("=", 1)[1].strip().strip('"')
                        break
        if not domain:
            print(f"ERROR: Could not read SITE_DOMAIN from {conf_path}", file=sys.stderr)
            sys.exit(1)

    print(f"=== Redirect Map Generator ===", file=sys.stderr)
    print(f"Site: {args.site}", file=sys.stderr)
    print(f"Domain: {domain}", file=sys.stderr)
    print(f"GSC input: {args.gsc_csv}", file=sys.stderr)

    redirects = generate_redirect_map(args.gsc_csv, domain)

    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "old_url", "new_url", "clicks_90d", "impressions_90d", "ctr", "position", "issue_type",
        ])
        writer.writeheader()
        writer.writerows(redirects)

    print(f"\nGenerated {len(redirects)} redirects", file=sys.stderr)
    print(f"Output: {args.output}", file=sys.stderr)

    # Issue type summary
    types = {}
    for r in redirects:
        t = r["issue_type"]
        types[t] = types.get(t, 0) + 1
    print("\nIssue distribution:", file=sys.stderr)
    for t, count in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {t}: {count}", file=sys.stderr)


if __name__ == "__main__":
    main()
