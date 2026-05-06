#!/usr/bin/env python3
"""
Generate audit summary report from sub-tool outputs.

Usage:
    python3 generate-summary.py --site lrg --output-dir audits/ \
        --output-md audits/00-AUDIT-SUMMARY.md
"""

import argparse
import csv
import os
import sys
from datetime import datetime


def count_csv(path: str) -> int:
    """Count data rows in a CSV (excluding header)."""
    if not os.path.exists(path):
        return -1
    with open(path) as f:
        return sum(1 for _ in f) - 1


def read_site_name(site_slug: str) -> str:
    """Read SITE_NAME from config."""
    root = os.path.expanduser("~/randalls-seo-system")
    conf = os.path.join(root, "sites", f"{site_slug}.conf")
    if os.path.exists(conf):
        with open(conf) as f:
            for line in f:
                if line.startswith("SITE_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    return site_slug


def main():
    parser = argparse.ArgumentParser(description="Generate audit summary report.")
    parser.add_argument("--site", required=True, help="Site slug")
    parser.add_argument("--output-dir", required=True, help="Directory containing audit outputs")
    parser.add_argument("--output-md", help="Output markdown path (default: <output-dir>/00-AUDIT-SUMMARY.md)")
    args = parser.parse_args()

    output_md = args.output_md or os.path.join(args.output_dir, "00-AUDIT-SUMMARY.md")
    site_name = read_site_name(args.site)
    date_str = datetime.now().strftime("%Y-%m-%d")

    d = args.output_dir

    # Count outputs from each sub-tool
    inventory_count = count_csv(os.path.join(d, "all-posts.csv"))
    gsc_count = count_csv(os.path.join(d, f"gsc-pages-{date_str}.csv"))
    if gsc_count == -1:  # try without date
        for f in os.listdir(d):
            if f.startswith("gsc-pages") and f.endswith(".csv"):
                gsc_count = count_csv(os.path.join(d, f))
                break

    delete_count = count_csv(os.path.join(d, "delete-candidates.csv"))
    slug_count = count_csv(os.path.join(d, "slug-issues.csv"))
    meta_count = count_csv(os.path.join(d, "meta-candidates.csv"))
    rewrite_count = count_csv(os.path.join(d, "priority-rewrites.csv"))
    cannibal_count = count_csv(os.path.join(d, "cannibalization.csv"))
    triage_path = os.path.join(d, "triage.csv")

    tier_a = tier_b = 0
    if os.path.exists(triage_path):
        with open(triage_path) as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("tier") == "A":
                    tier_a += 1
                else:
                    tier_b += 1

    report = f"""# {site_name} Content Audit Summary

**Date:** {date_str}
**Module:** modules/audit/ v1.0

---

## Inventory

| Metric | Count |
|--------|-------|
| Published posts (WP) | {inventory_count if inventory_count >= 0 else 'N/A'} |
| GSC tracked URLs | {gsc_count if gsc_count >= 0 else 'N/A'} |

## Audit Results

| Category | Count | Tool |
|----------|-------|------|
| Delete candidates | {delete_count if delete_count >= 0 else 'N/A'} | identify-deletes.py |
| Slug issues | {slug_count if slug_count >= 0 else 'N/A'} | identify-slug-issues.py |
| Meta refresh candidates | {meta_count if meta_count >= 0 else 'N/A'} | identify-meta-candidates.py |
| Priority rewrites (page 2-3) | {rewrite_count if rewrite_count >= 0 else 'N/A'} | identify-priority-rewrites.py |
| Cannibalization pairs | {cannibal_count if cannibal_count >= 0 else 'N/A'} | identify-cannibalization.py |

## Triage Classification

| Tier | Count | Action |
|------|-------|--------|
| Tier A (modern format) | {tier_a} | Class migration only |
| Tier B (legacy format) | {tier_b} | Full content rewrite |

## Output Files

| File | Description |
|------|-------------|
| all-posts.csv | Full WP inventory |
| gsc-pages-*.csv | GSC page traffic data |
| delete-candidates.csv | Zero-traffic deletion candidates |
| slug-issues.csv | Date-prefix and hash-suffix slug problems |
| meta-candidates.csv | High-impression low-CTR meta refresh targets |
| priority-rewrites.csv | Page 2-3 ranking opportunities |
| cannibalization.csv | Near-duplicate content pairs |
| triage.csv | Tier A/B classification |

## Next Steps

1. Review delete candidates — confirm no valuable content before removal
2. Deploy slug redirects via modules/redirect-management/
3. Prioritize meta refreshes by impression volume
4. Queue priority rewrites for content team
5. Resolve cannibalization pairs (merge, redirect, or differentiate)
"""

    os.makedirs(os.path.dirname(os.path.abspath(output_md)), exist_ok=True)
    with open(output_md, "w") as f:
        f.write(report)

    print(f"=== Audit Summary Generated ===", file=sys.stderr)
    print(f"Output: {output_md}", file=sys.stderr)


if __name__ == "__main__":
    main()
