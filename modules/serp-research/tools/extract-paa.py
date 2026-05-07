#!/usr/bin/env python3
"""
Extract People Also Ask from SERP analysis JSON.

Usage:
    python3 extract-paa.py --serp-json serp/va-loans.json --output-csv paa.csv
"""

import argparse
import csv
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Extract PAA from SERP analysis JSON.")
    parser.add_argument("--serp-json", required=True, help="analyze-serp.py output JSON")
    parser.add_argument("--output-csv", required=True, help="Output CSV")
    parser.add_argument("--include-related-searches", action="store_true",
                        help="Also include related searches")
    args = parser.parse_args()

    with open(args.serp_json) as f:
        data = json.load(f)

    rows = []
    for paa in data.get("paa", []):
        rows.append({
            "question": paa.get("question", ""),
            "answer": paa.get("answer", ""),
            "position": paa.get("position", ""),
            "type": "paa",
        })

    if args.include_related_searches:
        for query in data.get("related_searches", []):
            rows.append({
                "question": query,
                "answer": "",
                "position": "",
                "type": "related",
            })

    os.makedirs(os.path.dirname(os.path.abspath(args.output_csv)), exist_ok=True)
    with open(args.output_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["question", "answer", "position", "type"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Extracted {len(rows)} entries ({sum(1 for r in rows if r['type']=='paa')} PAA, "
          f"{sum(1 for r in rows if r['type']=='related')} related)", file=sys.stderr)
    print(f"Output: {args.output_csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
