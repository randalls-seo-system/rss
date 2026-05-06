#!/usr/bin/env python3
"""
Identify true delete candidates: zero traffic + zero inbound links.

Cross-references WP inventory against GSC traffic data to find posts
that have no organic traffic and no internal link equity.

Usage:
    python3 identify-deletes.py \
        --inventory-csv audits/all-posts.csv \
        --gsc-pages-csv audits/gsc-pages.csv \
        --output-csv audits/delete-candidates.csv
"""

import argparse
import csv
import os
import re
import sys


DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}-")


def load_gsc_traffic(gsc_path: str) -> dict:
    """Load GSC pages data, keyed by URL slug.

    Builds multiple lookup keys per URL to handle slug variations:
    - Full URL (exact)
    - Slug (last path component)
    - Cleaned slug (date-prefix removed, for Squarespace imports)
    """
    traffic = {}
    with open(gsc_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("url", "").rstrip("/")
            clicks = int(str(row.get("clicks", "0")).replace(",", "") or 0)
            impressions = int(str(row.get("impressions", "0")).replace(",", "") or 0)
            data = {"url": url, "clicks": clicks, "impressions": impressions}

            # Key by slug (last path component)
            slug = url.split("/")[-1] if "/" in url else url
            # Only store if this slug has more traffic than existing entry
            if slug not in traffic or clicks > traffic[slug]["clicks"]:
                traffic[slug] = data
            # Also store by full URL
            traffic[url] = data
    return traffic


def lookup_gsc(traffic: dict, wp_slug: str) -> dict:
    """Look up GSC traffic for a WP slug, trying multiple matching strategies."""
    # 1. Exact slug match
    if wp_slug in traffic:
        return traffic[wp_slug]
    # 2. Date-prefix cleaned match (WP slug has date prefix, GSC URL doesn't)
    cleaned = DATE_PREFIX_RE.sub("", wp_slug)
    if cleaned != wp_slug and cleaned in traffic:
        return traffic[cleaned]
    # 3. Hash-suffix cleaned match
    hash_cleaned = re.sub(r"-[a-z0-9]{10,}$", "", wp_slug)
    if hash_cleaned != wp_slug and hash_cleaned in traffic:
        return traffic[hash_cleaned]
    # 4. Both cleanings combined
    both_cleaned = re.sub(r"-[a-z0-9]{10,}$", "", cleaned)
    if both_cleaned != wp_slug and both_cleaned in traffic:
        return traffic[both_cleaned]
    return {"clicks": 0, "impressions": 0}


def load_priority_list(path: str) -> set:
    """Load priority list slugs to exclude from delete candidates."""
    slugs = set()
    if not path or not os.path.exists(path):
        return slugs
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            slug = row.get("slug", row.get("post_name", ""))
            if slug:
                slugs.add(slug)
    return slugs


def detect_language(title: str, slug: str) -> str:
    """Simple heuristic for Spanish vs English content."""
    spanish_markers = [
        "cómo", "para", "mejor", "guía", "vender", "comprar", "casa",
        "hogar", "barrio", "veterano", "préstamo", "hipoteca",
    ]
    text = f"{title} {slug}".lower()
    for marker in spanish_markers:
        if marker in text:
            return "ES"
    return "EN"


def main():
    parser = argparse.ArgumentParser(description="Identify true delete candidates.")
    parser.add_argument("--inventory-csv", required=True, help="WP content inventory CSV")
    parser.add_argument("--gsc-pages-csv", required=True, help="GSC pages traffic CSV")
    parser.add_argument("--priority-list-csv", help="Exclude these slugs from deletion")
    parser.add_argument("--output-csv", required=True, help="Output delete candidates CSV")
    parser.add_argument("--min-impressions", type=int, default=0,
                        help="Max impressions to qualify as 'zero traffic' (default: 0)")
    parser.add_argument("--include-spanish", action="store_true",
                        help="Include Spanish content (default: skip)")
    args = parser.parse_args()

    traffic = load_gsc_traffic(args.gsc_pages_csv)
    priority_slugs = load_priority_list(args.priority_list_csv)

    candidates = []
    skipped = {"has_traffic": 0, "priority_list": 0, "spanish": 0}

    with open(args.inventory_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            slug = row.get("post_name", row.get("slug", ""))
            title = row.get("post_title", row.get("title", ""))
            post_id = row.get("ID", row.get("post_id", ""))
            word_count = int(row.get("word_count", "0") or 0)
            post_date = row.get("post_date", "")

            # Skip Spanish unless --include-spanish
            lang = detect_language(title, slug)
            if lang == "ES" and not args.include_spanish:
                skipped["spanish"] += 1
                continue

            # Skip if in priority list
            if slug in priority_slugs:
                skipped["priority_list"] += 1
                continue

            # Check GSC traffic (try multiple slug matching strategies)
            gsc = lookup_gsc(traffic, slug)
            if gsc["clicks"] > 0 or gsc["impressions"] > args.min_impressions:
                skipped["has_traffic"] += 1
                continue

            candidates.append({
                "ID": post_id,
                "slug": slug,
                "title": title,
                "word_count": word_count,
                "language": lang,
                "date": post_date,
                "gsc_clicks": gsc["clicks"],
                "gsc_impressions": gsc["impressions"],
            })

    # Sort by date (oldest first)
    candidates.sort(key=lambda x: x.get("date", ""))

    os.makedirs(os.path.dirname(os.path.abspath(args.output_csv)), exist_ok=True)
    with open(args.output_csv, "w", newline="") as f:
        fieldnames = ["ID", "slug", "title", "word_count", "language", "date",
                       "gsc_clicks", "gsc_impressions"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidates)

    print(f"=== Delete Candidates ===", file=sys.stderr)
    print(f"Candidates: {len(candidates)}", file=sys.stderr)
    print(f"Skipped (has traffic): {skipped['has_traffic']}", file=sys.stderr)
    print(f"Skipped (priority list): {skipped['priority_list']}", file=sys.stderr)
    print(f"Skipped (Spanish): {skipped['spanish']}", file=sys.stderr)
    print(f"Output: {args.output_csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
