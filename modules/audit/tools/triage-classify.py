#!/usr/bin/env python3
"""
Classify posts as Tier A (class migration only) or Tier B (full rewrite).

Tier A: Posts already using the target HTML class system — only need
CSS class migration, not content rewrite.

Tier B: Posts in legacy format — need full content rewrite.

Usage:
    python3 triage-classify.py \
        --site lrg --inventory-csv audits/all-posts.csv \
        --html-class-marker lrgArticleKit \
        --output-csv audits/triage.csv
"""

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
from wp_cli_client import WPCLIClient


def classify_posts(client: WPCLIClient, post_ids: list[str],
                   class_marker: str) -> dict:
    """Check which posts contain the class marker in their content."""
    # Batch check via PHP
    ids_json = json.dumps([int(pid) for pid in post_ids if pid])
    php = f"""<?php
$ids = json_decode('{ids_json}');
$results = [];
foreach ($ids as $id) {{
    $content = get_post_field('post_content', $id);
    $has_marker = strpos($content, '{class_marker}') !== false;
    $results[$id] = $has_marker ? 'A' : 'B';
}}
echo json_encode($results);
"""
    output = client.eval_file(php, timeout=300)
    return json.loads(output)


def main():
    parser = argparse.ArgumentParser(description="Classify posts into Tier A/B.")
    parser.add_argument("--site", required=True, help="Site slug")
    parser.add_argument("--inventory-csv", required=True, help="WP inventory CSV")
    parser.add_argument("--html-class-marker", required=True,
                        help="CSS class that indicates modern format (e.g., lrgArticleKit, vlnPage)")
    parser.add_argument("--output-csv", required=True, help="Output CSV")
    args = parser.parse_args()

    # Load inventory
    posts = []
    with open(args.inventory_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            posts.append(row)

    post_ids = [p.get("ID", p.get("post_id", "")) for p in posts if p.get("ID") or p.get("post_id")]

    print(f"=== Triage Classification ===", file=sys.stderr)
    print(f"Site: {args.site}", file=sys.stderr)
    print(f"Posts: {len(post_ids)}", file=sys.stderr)
    print(f"Marker: {args.html_class_marker}", file=sys.stderr)

    client = WPCLIClient.from_site_config(args.site)

    # Process in batches to avoid PHP memory limits
    BATCH_SIZE = 200
    all_tiers = {}
    for i in range(0, len(post_ids), BATCH_SIZE):
        batch = post_ids[i:i + BATCH_SIZE]
        print(f"  Batch {i//BATCH_SIZE + 1}: {len(batch)} posts...", file=sys.stderr)
        tiers = classify_posts(client, batch, args.html_class_marker)
        all_tiers.update(tiers)

    # Build output
    results = []
    for post in posts:
        pid = post.get("ID", post.get("post_id", ""))
        tier = all_tiers.get(str(pid), all_tiers.get(int(pid) if pid else 0, "B"))
        results.append({
            "ID": pid,
            "slug": post.get("post_name", post.get("slug", "")),
            "title": post.get("post_title", post.get("title", "")),
            "tier": tier,
            "word_count": post.get("word_count", ""),
        })

    tier_a = sum(1 for r in results if r["tier"] == "A")
    tier_b = sum(1 for r in results if r["tier"] == "B")

    os.makedirs(os.path.dirname(os.path.abspath(args.output_csv)), exist_ok=True)
    with open(args.output_csv, "w", newline="") as f:
        fieldnames = ["ID", "slug", "title", "tier", "word_count"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"\nTier A (class migration): {tier_a}", file=sys.stderr)
    print(f"Tier B (full rewrite): {tier_b}", file=sys.stderr)
    print(f"Output: {args.output_csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
