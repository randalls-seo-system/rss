#!/usr/bin/env python3
"""
Extract top organic results from SERP analysis JSON.

Usage:
    python3 extract-top-results.py --serp-json serp/va-loans.json --output-csv top10.csv
"""

import argparse
import csv
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Extract top organic results from SERP JSON.")
    parser.add_argument("--serp-json", required=True, help="analyze-serp.py output JSON")
    parser.add_argument("--top-n", type=int, default=10, help="Number of results (default: 10)")
    parser.add_argument("--output-csv", required=True, help="Output CSV")
    args = parser.parse_args()

    with open(args.serp_json) as f:
        data = json.load(f)

    results = data.get("top_results", [])[:args.top_n]

    os.makedirs(os.path.dirname(os.path.abspath(args.output_csv)), exist_ok=True)
    with open(args.output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["position", "title", "url", "snippet"])
        writer.writeheader()
        writer.writerows(results)

    print(f"Extracted {len(results)} results", file=sys.stderr)
    print(f"Output: {args.output_csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
