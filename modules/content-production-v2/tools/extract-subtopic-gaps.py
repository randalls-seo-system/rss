#!/usr/bin/env python3
"""Extract subtopic frequency map from SERP data.

Takes SERP JSON, returns high/medium/low coverage subtopics.
Low-coverage gaps feed the article's competitive moat.

Usage:
    python3 extract-subtopic-gaps.py --serp-json /path/to/serp.json --output /path/to/gaps.json

See docs/article-spec.md Section 17.1 for subtopic gap analysis logic.
See docs/v2-module-architecture.md "tools/extract-subtopic-gaps.py" for spec.
"""

import argparse
import difflib
import json
import os
import re
import sys
from pathlib import Path

# Add lib/ to path for sibling imports
TOOL_DIR = Path(__file__).resolve().parent
MODULE_DIR = TOOL_DIR.parent
sys.path.insert(0, str(MODULE_DIR))

from lib.page_fetch import fetch_page, strip_boilerplate
from lib.serp_adapter import SerpData

FUZZY_THRESHOLD = 0.75

STRIP_WORDS = {"the", "a", "an", "your", "my", "our", "his", "her", "their", "this", "that", "of", "in", "for", "and", "to", "on", "is", "are", "was"}


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# Heading extraction and normalization
# ---------------------------------------------------------------------------

def extract_headings(html: str) -> list[str]:
    """Extract H2 + H3 heading text from HTML."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "html.parser")

    strip_boilerplate(soup)

    headings = []
    for h in soup.find_all(["h2", "h3"]):
        text = h.get_text(separator=" ", strip=True)
        if text and len(text) > 3:
            headings.append(text)
    return headings


def normalize_heading(text: str) -> str:
    """Normalize heading text for clustering."""
    text = text.lower()
    # Strip punctuation
    text = re.sub(r"[^\w\s]", "", text)
    # Strip year suffixes (2024, 2025, 2026, etc.)
    text = re.sub(r"\b20\d{2}\b", "", text)
    # Strip leading/trailing common words
    words = text.split()
    words = [w for w in words if w not in STRIP_WORDS]
    return " ".join(words).strip()


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

def cluster_headings(all_headings: list[tuple[str, int]]) -> dict[str, list[int]]:
    """Cluster normalized headings using fuzzy matching.

    Args:
        all_headings: list of (normalized_heading, result_index) tuples

    Returns:
        dict mapping cluster representative -> list of result indices
    """
    clusters: list[tuple[str, set[int]]] = []

    for heading, idx in all_headings:
        if not heading or len(heading) < 3:
            continue
        matched = False
        for i, (rep, indices) in enumerate(clusters):
            ratio = difflib.SequenceMatcher(None, heading, rep).ratio()
            if ratio >= FUZZY_THRESHOLD:
                indices.add(idx)
                matched = True
                break
        if not matched:
            clusters.append((heading, {idx}))

    return {rep: sorted(indices) for rep, indices in clusters}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extract subtopic frequency map from SERP data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Output: JSON with high_coverage, medium_coverage, low_coverage_gaps buckets."
    )
    parser.add_argument("--serp-json", required=True, help="analyze-serp.py output JSON path")
    parser.add_argument("--output", required=True, help="Output gaps JSON path")
    args = parser.parse_args()

    log("=== Extract Subtopic Gaps ===")

    serp = SerpData(Path(args.serp_json))
    results = serp.top_results[:5]

    if len(results) < 5:
        log(f"ERROR: SERP JSON has {len(results)} organic results, need at least 5.")
        sys.exit(1)

    log(f"Keyword: {serp.keyword}")
    log(f"Processing top {len(results)} results")

    # Fetch pages and extract headings
    all_headings: list[tuple[str, int]] = []  # (normalized, result_index)
    fetch_failures = 0

    for i, result in enumerate(results):
        log(f"  [{i+1}/5] {result.url[:70]}...")
        html = fetch_page(result.url)
        if html is None:
            fetch_failures += 1
            log(f"  SKIP: could not fetch result {i}")
            continue

        raw_headings = extract_headings(html)
        log(f"    {len(raw_headings)} headings extracted")
        for h in raw_headings:
            norm = normalize_heading(h)
            if norm and len(norm.split()) >= 2:
                all_headings.append((norm, i))

    if fetch_failures >= 3:
        log(f"ERROR: {fetch_failures} of 5 pages failed to parse. Data quality too poor.")
        sys.exit(1)

    log(f"\nTotal headings collected: {len(all_headings)}")

    # Cluster
    clusters = cluster_headings(all_headings)
    log(f"Clusters formed: {len(clusters)}")

    # Bucket
    high = []
    medium = []
    low = []

    for subtopic, indices in sorted(clusters.items(), key=lambda x: -len(x[1])):
        entry = {"subtopic": subtopic, "appears_in": indices}
        n = len(indices)
        if n >= 4:
            high.append(entry)
        elif n == 3:
            medium.append(entry)
        elif n >= 1:
            low.append(entry)

    output = {
        "keyword": serp.keyword,
        "results_analyzed": len(results) - fetch_failures,
        "high_coverage": high,
        "medium_coverage": medium,
        "low_coverage_gaps": low,
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    log(f"\nResults:")
    log(f"  High coverage (4-5/5): {len(high)} subtopics")
    log(f"  Medium coverage (3/5): {len(medium)} subtopics")
    log(f"  Low coverage gaps (1-2/5): {len(low)} subtopics")
    log(f"\nOutput: {args.output}")


if __name__ == "__main__":
    main()
