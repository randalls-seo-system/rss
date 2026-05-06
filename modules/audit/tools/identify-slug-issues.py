#!/usr/bin/env python3
"""
Identify slug pattern issues: date-prefixed, hash-suffix, archive paths.

Cross-references WP slugs against GSC ground truth to find URLs that
need redirects.

Usage:
    python3 identify-slug-issues.py \
        --inventory-csv audits/all-posts.csv \
        --gsc-pages-csv audits/gsc-pages.csv \
        --output-csv audits/slug-issues.csv
"""

import argparse
import csv
import os
import re
import sys


# Patterns
DATE_PREFIX_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}-")
HASH_SUFFIX_RE = re.compile(r"-[a-z0-9]{10,}$")
DATE_ARCHIVE_RE = re.compile(r"/\d{4}/\d{1,2}/\d{1,2}/")


def classify_slug(slug: str) -> list[str]:
    """Classify a slug's issues."""
    issues = []
    if DATE_PREFIX_RE.match(slug):
        issues.append("date_prefix")
    if HASH_SUFFIX_RE.search(slug):
        issues.append("hash_suffix")
    return issues


def clean_slug(slug: str) -> str:
    """Generate a clean version of a problematic slug."""
    cleaned = slug
    # Remove date prefix
    cleaned = DATE_PREFIX_RE.sub("", cleaned)
    # Remove hash suffix
    cleaned = HASH_SUFFIX_RE.sub("", cleaned)
    return cleaned


def main():
    parser = argparse.ArgumentParser(description="Identify slug pattern issues.")
    parser.add_argument("--inventory-csv", required=True, help="WP content inventory CSV")
    parser.add_argument("--gsc-pages-csv", help="GSC pages CSV (for ground truth cross-ref)")
    parser.add_argument("--output-csv", required=True, help="Output slug issues CSV")
    args = parser.parse_args()

    # Load GSC URLs for ground truth
    gsc_urls = set()
    gsc_slugs = set()
    if args.gsc_pages_csv and os.path.exists(args.gsc_pages_csv):
        with open(args.gsc_pages_csv) as f:
            reader = csv.DictReader(f)
            for row in reader:
                url = row.get("url", "").rstrip("/")
                gsc_urls.add(url)
                slug = url.split("/")[-1]
                gsc_slugs.add(slug)

    issues = []
    with open(args.inventory_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            slug = row.get("post_name", row.get("slug", ""))
            title = row.get("post_title", row.get("title", ""))
            post_id = row.get("ID", row.get("post_id", ""))

            slug_issues = classify_slug(slug)
            if not slug_issues:
                continue

            cleaned = clean_slug(slug)
            in_gsc = slug in gsc_slugs or cleaned in gsc_slugs

            issues.append({
                "post_id": post_id,
                "current_slug": slug,
                "suggested_slug": cleaned,
                "issue_type": "+".join(slug_issues),
                "title": title,
                "in_gsc": "yes" if in_gsc else "no",
            })

    os.makedirs(os.path.dirname(os.path.abspath(args.output_csv)), exist_ok=True)
    with open(args.output_csv, "w", newline="") as f:
        fieldnames = ["post_id", "current_slug", "suggested_slug", "issue_type", "title", "in_gsc"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(issues)

    # Summary
    types = {}
    gsc_count = sum(1 for i in issues if i["in_gsc"] == "yes")
    for i in issues:
        t = i["issue_type"]
        types[t] = types.get(t, 0) + 1

    print(f"=== Slug Issues ===", file=sys.stderr)
    print(f"Total issues: {len(issues)}", file=sys.stderr)
    print(f"With GSC presence: {gsc_count} (need redirects)", file=sys.stderr)
    for t, count in sorted(types.items(), key=lambda x: -x[1]):
        print(f"  {t}: {count}", file=sys.stderr)
    print(f"Output: {args.output_csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
