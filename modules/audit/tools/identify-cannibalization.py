#!/usr/bin/env python3
"""
Identify near-duplicate pairs that compete for the same keywords.

Uses title similarity to detect potential cannibalization.

Usage:
    python3 identify-cannibalization.py \
        --inventory-csv audits/all-posts.csv \
        --similarity-threshold 0.85 \
        --output-csv audits/cannibalization.csv
"""

import argparse
import csv
import os
import re
import sys
from itertools import combinations


def tokenize(text: str) -> set[str]:
    """Lowercase word tokenization, filtering stopwords."""
    stopwords = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "is", "are", "was", "were", "be", "been", "being",
        "it", "its", "this", "that", "these", "those", "you", "your",
        "how", "what", "when", "where", "why", "here", "there",
        "do", "does", "did", "will", "would", "can", "could", "should",
        "with", "from", "by", "as", "if", "not", "no", "so",
    }
    words = set(re.findall(r"[a-záéíóúñü]+", text.lower()))
    return words - stopwords


def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def main():
    parser = argparse.ArgumentParser(description="Identify near-duplicate content pairs.")
    parser.add_argument("--inventory-csv", required=True, help="WP content inventory CSV")
    parser.add_argument("--gsc-queries-csv", help="GSC queries CSV (for keyword overlap)")
    parser.add_argument("--similarity-threshold", type=float, default=0.85,
                        help="Title similarity threshold (default: 0.85)")
    parser.add_argument("--output-csv", required=True, help="Output CSV")
    parser.add_argument("--review-mode", action="store_true",
                        help="Flag pairs for review, don't auto-decide")
    args = parser.parse_args()

    # Load posts
    posts = []
    with open(args.inventory_csv) as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row.get("post_title", row.get("title", ""))
            slug = row.get("post_name", row.get("slug", ""))
            post_id = row.get("ID", row.get("post_id", ""))
            posts.append({
                "id": post_id,
                "title": title,
                "slug": slug,
                "tokens": tokenize(title),
            })

    # Find similar pairs
    pairs = []
    for a, b in combinations(posts, 2):
        if not a["tokens"] or not b["tokens"]:
            continue
        sim = jaccard_similarity(a["tokens"], b["tokens"])
        if sim >= args.similarity_threshold:
            pairs.append({
                "id_a": a["id"],
                "title_a": a["title"],
                "slug_a": a["slug"],
                "id_b": b["id"],
                "title_b": b["title"],
                "slug_b": b["slug"],
                "similarity": round(sim, 3),
                "action": "review" if args.review_mode else "",
            })

    pairs.sort(key=lambda x: x["similarity"], reverse=True)

    os.makedirs(os.path.dirname(os.path.abspath(args.output_csv)), exist_ok=True)
    with open(args.output_csv, "w", newline="") as f:
        fieldnames = ["id_a", "title_a", "slug_a", "id_b", "title_b", "slug_b",
                       "similarity", "action"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(pairs)

    print(f"=== Cannibalization Candidates ===", file=sys.stderr)
    print(f"Pairs found: {len(pairs)}", file=sys.stderr)
    print(f"Threshold: {args.similarity_threshold}", file=sys.stderr)
    print(f"Output: {args.output_csv}", file=sys.stderr)


if __name__ == "__main__":
    main()
