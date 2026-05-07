#!/usr/bin/env python3
"""
Extract AI Overview from SERP analysis JSON.

Usage:
    python3 extract-ai-overview.py --serp-json serp/va-loans.json --output-md ai-overview.md
"""

import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(description="Extract AI Overview from SERP JSON.")
    parser.add_argument("--serp-json", required=True, help="analyze-serp.py output JSON")
    parser.add_argument("--output-md", required=True, help="Output markdown path")
    args = parser.parse_args()

    with open(args.serp_json) as f:
        data = json.load(f)

    keyword = data.get("keyword", "unknown")
    ai = data.get("ai_overview")

    os.makedirs(os.path.dirname(os.path.abspath(args.output_md)), exist_ok=True)

    with open(args.output_md, "w") as f:
        f.write(f"# AI Overview: {keyword}\n\n")

        if not ai:
            f.write("No AI Overview present for this query.\n")
            print("No AI Overview present.", file=sys.stderr)
            return

        # Text blocks
        text_blocks = ai.get("text_blocks", [])
        for block in text_blocks:
            if isinstance(block, dict):
                block_type = block.get("type", "paragraph")
                snippet = block.get("snippet", "")
                if block_type == "list":
                    items = block.get("list", [])
                    for item in items:
                        f.write(f"- {item}\n")
                    f.write("\n")
                else:
                    f.write(f"{snippet}\n\n")
            elif isinstance(block, str):
                f.write(f"{block}\n\n")

        # References
        refs = ai.get("references", [])
        if refs:
            f.write("## Sources\n\n")
            for i, ref in enumerate(refs):
                if isinstance(ref, dict):
                    title = ref.get("title", ref.get("source", ""))
                    link = ref.get("link", ref.get("url", ""))
                    f.write(f"{i+1}. [{title}]({link})\n")
                elif isinstance(ref, str):
                    f.write(f"{i+1}. {ref}\n")

        print(f"AI Overview extracted: {len(text_blocks)} blocks, {len(refs)} references", file=sys.stderr)

    print(f"Output: {args.output_md}", file=sys.stderr)


if __name__ == "__main__":
    main()
