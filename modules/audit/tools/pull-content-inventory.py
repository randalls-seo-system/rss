#!/usr/bin/env python3
"""
Pull content inventory from WordPress via WP-CLI.

Extracts all published posts with metadata into a CSV for audit analysis.

Usage:
    python3 pull-content-inventory.py --site lrg --output-csv audits/all-posts.csv
    python3 pull-content-inventory.py --site lrg --output-csv audits/all-posts.csv --include-meta
"""

import argparse
import csv
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
from wp_cli_client import WPCLIClient


def pull_inventory(client: WPCLIClient, post_types: str, post_status: str,
                   include_meta: bool) -> list[dict]:
    """Pull post inventory via WP-CLI eval-file for rich metadata."""
    php = f"""<?php
$posts = get_posts([
    'post_type'      => explode(',', '{post_types}'),
    'posts_per_page' => -1,
    'post_status'    => '{post_status}',
]);
$results = [];
foreach ($posts as $p) {{
    $content_text = wp_strip_all_tags($p->post_content);
    $word_count = str_word_count($content_text);
    $row = [
        'ID'            => $p->ID,
        'post_title'    => $p->post_title,
        'post_name'     => $p->post_name,
        'post_date'     => $p->post_modified,
        'post_status'   => $p->post_status,
        'post_author'   => $p->post_author,
        'word_count'    => $word_count,
        'post_type'     => $p->post_type,
    ];
    {'$row["has_yoast_title"] = get_post_meta($p->ID, "_yoast_wpseo_title", true) ? "1" : "0";' if include_meta else ''}
    {'$row["has_yoast_meta"] = get_post_meta($p->ID, "_yoast_wpseo_metadesc", true) ? "1" : "0";' if include_meta else ''}
    $results[] = $row;
}}
usort($results, function($a, $b) {{ return $a['ID'] - $b['ID']; }});
echo json_encode($results);
"""
    output = client.eval_file(php, timeout=180)
    return json.loads(output)


def main():
    parser = argparse.ArgumentParser(description="Pull WP content inventory via WP-CLI.")
    parser.add_argument("--site", required=True, help="Site slug")
    parser.add_argument("--output-csv", required=True, help="Output CSV path")
    parser.add_argument("--post-types", default="post", help="Comma-separated post types (default: post)")
    parser.add_argument("--post-status", default="publish", help="Post status (default: publish)")
    parser.add_argument("--include-meta", action="store_true", help="Include Yoast title/meta flags")
    args = parser.parse_args()

    print(f"=== Content Inventory ===", file=sys.stderr)
    print(f"Site: {args.site}", file=sys.stderr)

    client = WPCLIClient.from_site_config(args.site)

    if not client.test_connection():
        print("ERROR: SSH connection failed", file=sys.stderr)
        sys.exit(1)

    posts = pull_inventory(client, args.post_types, args.post_status, args.include_meta)
    print(f"Pulled {len(posts)} posts", file=sys.stderr)

    os.makedirs(os.path.dirname(os.path.abspath(args.output_csv)), exist_ok=True)
    fieldnames = list(posts[0].keys()) if posts else ["ID", "post_title", "post_name", "post_date"]
    with open(args.output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(posts)

    print(f"Output: {args.output_csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
