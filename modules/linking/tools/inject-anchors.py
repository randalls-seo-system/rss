#!/usr/bin/env python3
"""
Linking v2 Phase 2: Inject anchor-text links into article HTML.

Uses pre-generated anchor pools (Phase 1) to inject internal links into
article body content. Parameterized for any RSS client site.

Usage:
    # Single article, dry run:
    python3 inject-anchors.py --site valn --pool sites/valn-anchor-pools.json \
        --article-html article.html --dry-run

    # Batch mode:
    python3 inject-anchors.py --site valn --pool sites/valn-anchor-pools.json \
        --batch-csv batch.csv --output-dir output/

    # With limits:
    python3 inject-anchors.py --site valn --pool sites/valn-anchor-pools.json \
        --article-html article.html --max-links-per-article 3 \
        --min-distance-between 300 --skip-existing-links
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:
    print("ERROR: beautifulsoup4 required. Install: pip install beautifulsoup4", file=sys.stderr)
    sys.exit(1)


# ── Constants ────────────────────────────────────────────────────────────────

# Sections to skip during injection (CSS class or tag patterns)
SKIP_SECTIONS = {
    "classes": [
        "vlnHero", "vlnAtf", "atf-", "hero-",           # ATF / hero
        "vlnFaq", "faq",                                  # FAQ
        "vlnDisclosure", "vlnResources",                  # Resources / disclosure
        "vlnNextPill", "cta-",                            # CTA pills
        "vlnFooter", "site-footer", "footer",             # Footer
        "vlnCallout",                                     # Callouts (keep clean)
        "et_pb_section--sticky", "et_pb_menu",            # Divi nav/sticky
    ],
    "tags": ["nav", "footer", "header", "script", "style", "noscript"],
}

# Elements whose text should never be wrapped in links
NO_LINK_TAGS = {"a", "button", "h1", "h2", "h3", "h4", "h5", "h6", "th", "caption", "label"}


# ── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class AnchorCandidate:
    destination_url: str
    anchor_text: str
    paragraph_index: int
    char_offset: int          # character offset within the full body text
    relevance_score: float
    word_overlap: int


@dataclass
class Injection:
    destination_url: str
    anchor_text: str
    paragraph_index: int
    char_offset: int
    score: float


@dataclass
class ArticleResult:
    source_path: str
    article_url: str
    injections: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    existing_links: int = 0
    paragraphs_scanned: int = 0


# ── Pool Loading ─────────────────────────────────────────────────────────────

def load_pool(pool_path: str) -> dict:
    """Load anchor pool JSON and index by URL."""
    with open(pool_path) as f:
        data = json.load(f)

    pool = {}
    for dest in data.get("destinations", []):
        url = dest["url"]
        pool[url] = {
            "slug": dest.get("slug", ""),
            "title": dest.get("title", ""),
            "primary_keyword": dest.get("primary_keyword", ""),
            "anchors": dest.get("anchors", []),
        }
    return pool


# ── HTML Parsing ─────────────────────────────────────────────────────────────

def _should_skip_element(tag: Tag) -> bool:
    """Check if a tag or any ancestor is in a skip zone."""
    for ancestor in [tag] + list(tag.parents):
        if not isinstance(ancestor, Tag):
            continue
        # Skip by tag name
        if ancestor.name in SKIP_SECTIONS["tags"]:
            return True
        # Skip by CSS class
        classes = ancestor.get("class", [])
        if isinstance(classes, str):
            classes = classes.split()
        for cls in classes:
            for skip_cls in SKIP_SECTIONS["classes"]:
                if skip_cls in cls:
                    return True
    return False


def extract_paragraphs(html: str) -> list[dict]:
    """Extract injectable paragraphs from article HTML.

    Returns list of dicts: {index, text, element, char_offset}
    char_offset = cumulative character position in the full body.
    """
    soup = BeautifulSoup(html, "html.parser")
    paragraphs = []
    char_offset = 0

    for tag in soup.find_all(["p", "li"]):
        if _should_skip_element(tag):
            continue
        # Skip if inside a link-forbidden tag
        if tag.find_parent(NO_LINK_TAGS):
            continue

        text = tag.get_text(separator=" ", strip=True)
        if len(text) < 40:  # too short to inject into
            char_offset += len(text)
            continue

        paragraphs.append({
            "index": len(paragraphs),
            "text": text,
            "element": tag,
            "char_offset": char_offset,
        })
        char_offset += len(text)

    return paragraphs


def find_existing_links(html: str) -> set[str]:
    """Return set of href destinations already linked in the article."""
    soup = BeautifulSoup(html, "html.parser")
    hrefs = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].rstrip("/").lower()
        hrefs.add(href)
    return hrefs


# ── Scoring ──────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> set[str]:
    """Lowercase word tokenization."""
    return set(re.findall(r"[a-záéíóúñü]+", text.lower()))


def score_anchor_in_paragraph(
    anchor_text: str,
    paragraph_text: str,
    destination_keyword: str,
) -> tuple[float, int]:
    """Score how well an anchor fits in a paragraph.

    Returns (relevance_score, word_overlap).

    Scoring factors:
    - Word overlap between anchor + destination keyword and paragraph
    - Bonus if exact anchor substring appears in paragraph
    - Penalty for very short paragraphs
    """
    anchor_tokens = _tokenize(anchor_text)
    para_tokens = _tokenize(paragraph_text)
    keyword_tokens = _tokenize(destination_keyword)

    # Word overlap: how many anchor/keyword words appear in paragraph
    combined_tokens = anchor_tokens | keyword_tokens
    overlap = len(combined_tokens & para_tokens)
    overlap_ratio = overlap / max(len(combined_tokens), 1)

    score = overlap_ratio * 50  # base: 0-50

    # Bonus for topical density (paragraph has many relevant words)
    if overlap >= 3:
        score += 15

    # Bonus for longer paragraphs (more natural context)
    if len(paragraph_text) > 200:
        score += 5

    # Exact substring bonus (anchor text appears verbatim)
    if anchor_text.lower() in paragraph_text.lower():
        score += 30

    return score, overlap


def select_injections(
    paragraphs: list[dict],
    pool: dict,
    article_url: str,
    existing_links: set[str],
    max_links: int,
    min_distance: int,
    skip_existing: bool,
) -> tuple[list[Injection], list[dict]]:
    """Select best anchor injections for an article.

    Returns (injections, skipped_destinations).
    """
    candidates: list[AnchorCandidate] = []

    for dest_url, dest_data in pool.items():
        # Don't self-link
        if dest_url.rstrip("/").lower() == article_url.rstrip("/").lower():
            continue

        # Skip if already linked and flag is set
        if skip_existing and dest_url.rstrip("/").lower() in existing_links:
            continue

        best_for_dest: Optional[AnchorCandidate] = None
        best_score = 0

        for anchor_text in dest_data["anchors"]:
            for para in paragraphs:
                # Check anchor text doesn't already appear as a link
                score, overlap = score_anchor_in_paragraph(
                    anchor_text, para["text"], dest_data["primary_keyword"]
                )
                if score > best_score and overlap >= 2:
                    best_score = score
                    best_for_dest = AnchorCandidate(
                        destination_url=dest_url,
                        anchor_text=anchor_text,
                        paragraph_index=para["index"],
                        char_offset=para["char_offset"],
                        relevance_score=score,
                        word_overlap=overlap,
                    )

        if best_for_dest:
            candidates.append(best_for_dest)

    # Sort by score descending
    candidates.sort(key=lambda c: c.relevance_score, reverse=True)

    # Select top candidates respecting distance constraint
    injections: list[Injection] = []
    used_offsets: list[int] = []
    used_destinations: set[str] = set()
    used_paragraphs: set[int] = set()
    skipped = []

    for candidate in candidates:
        if len(injections) >= max_links:
            break

        # Don't inject same destination twice
        if candidate.destination_url in used_destinations:
            continue

        # Don't inject into same paragraph twice
        if candidate.paragraph_index in used_paragraphs:
            continue

        # Check minimum distance from other injections
        too_close = False
        for offset in used_offsets:
            if abs(candidate.char_offset - offset) < min_distance:
                too_close = True
                break
        if too_close:
            skipped.append({
                "destination": candidate.destination_url,
                "anchor": candidate.anchor_text,
                "reason": "too_close_to_existing_injection",
            })
            continue

        injections.append(Injection(
            destination_url=candidate.destination_url,
            anchor_text=candidate.anchor_text,
            paragraph_index=candidate.paragraph_index,
            char_offset=candidate.char_offset,
            score=candidate.relevance_score,
        ))
        used_offsets.append(candidate.char_offset)
        used_destinations.add(candidate.destination_url)
        used_paragraphs.add(candidate.paragraph_index)

    return injections, skipped


# ── HTML Injection ───────────────────────────────────────────────────────────

def inject_link(element: Tag, anchor_text: str, href: str) -> bool:
    """Inject <a> tag wrapping first occurrence of anchor_text in element.

    Searches through text nodes for a case-insensitive match, wraps it in
    an <a> tag. Returns True if injection succeeded.
    """
    pattern = re.compile(re.escape(anchor_text), re.IGNORECASE)

    for text_node in element.find_all(string=True):
        if not isinstance(text_node, NavigableString):
            continue
        # Don't inject inside existing links or forbidden tags
        parent = text_node.parent
        if parent and parent.name in NO_LINK_TAGS:
            continue

        match = pattern.search(str(text_node))
        if match:
            original = str(text_node)
            start, end = match.start(), match.end()
            matched_text = original[start:end]

            # Build replacement: text_before + <a> + text_after
            before = original[:start]
            after = original[end:]

            new_link = element.find_parent().new_tag("a", href=href)
            new_link.string = matched_text

            text_node.replace_with(before)
            # Insert link and remaining text after
            idx = list(parent.children).index(before) if before in parent.children else None

            # Simpler approach: reconstruct with NavigableString
            parent_soup = BeautifulSoup(
                f"{before}<a href=\"{href}\">{matched_text}</a>{after}",
                "html.parser",
            )
            text_node.replace_with(parent_soup)
            return True

    return False


def inject_link_simple(html: str, paragraph_text_snippet: str, anchor_text: str, href: str) -> str:
    """Simpler injection: find anchor text in HTML and wrap in <a> tag.

    Uses a targeted approach: finds the paragraph containing the snippet,
    then wraps the first occurrence of anchor_text in that paragraph.
    """
    # Find anchor text in HTML (case-insensitive), wrap first occurrence
    # that is NOT already inside an <a> tag
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup.find_all(["p", "li"]):
        if _should_skip_element(tag):
            continue

        tag_text = tag.get_text(separator=" ", strip=True)
        if anchor_text.lower() not in tag_text.lower():
            continue

        # Check this paragraph isn't already over-linked
        existing_in_para = len(tag.find_all("a"))
        if existing_in_para >= 3:
            continue

        # Find and wrap the anchor text in this element's text nodes
        pattern = re.compile(re.escape(anchor_text), re.IGNORECASE)
        for text_node in tag.find_all(string=True):
            if not isinstance(text_node, NavigableString):
                continue
            parent = text_node.parent
            if parent and parent.name in NO_LINK_TAGS:
                continue

            match = pattern.search(str(text_node))
            if match:
                original = str(text_node)
                start, end = match.start(), match.end()
                matched_text = original[start:end]

                replacement = BeautifulSoup(
                    f'{original[:start]}<a href="{href}">{matched_text}</a>{original[end:]}',
                    "html.parser",
                )
                text_node.replace_with(replacement)
                return str(soup)

    return html


# ── Article Processing ───────────────────────────────────────────────────────

def process_article(
    html_path: str,
    article_url: str,
    pool: dict,
    max_links: int,
    min_distance: int,
    skip_existing: bool,
    dry_run: bool,
) -> ArticleResult:
    """Process a single article: score, select, and inject anchors."""
    with open(html_path) as f:
        html = f.read()

    result = ArticleResult(
        source_path=html_path,
        article_url=article_url,
    )

    # Extract paragraphs and existing links
    paragraphs = extract_paragraphs(html)
    existing_links = find_existing_links(html) if skip_existing else set()
    result.existing_links = len(existing_links)
    result.paragraphs_scanned = len(paragraphs)

    if not paragraphs:
        result.skipped.append({"reason": "no_injectable_paragraphs"})
        return result

    # Select injections
    injections, skipped = select_injections(
        paragraphs, pool, article_url, existing_links,
        max_links, min_distance, skip_existing,
    )
    result.skipped = skipped

    if not dry_run:
        # Apply injections to HTML
        modified_html = html
        for inj in injections:
            para = paragraphs[inj.paragraph_index]
            modified_html = inject_link_simple(
                modified_html, para["text"][:80], inj.anchor_text, inj.destination_url,
            )
        result.injections = injections

        # Write modified HTML back (or to output dir)
        return result, modified_html
    else:
        result.injections = injections
        return result, html


# ── Batch Processing ─────────────────────────────────────────────────────────

def process_batch(
    batch_csv: str,
    pool: dict,
    max_links: int,
    min_distance: int,
    skip_existing: bool,
    dry_run: bool,
    output_dir: Optional[str],
) -> list[ArticleResult]:
    """Process multiple articles from a batch CSV.

    CSV columns: html_path, article_url
    """
    results = []
    with open(batch_csv) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    for i, row in enumerate(rows):
        html_path = row["html_path"]
        article_url = row["article_url"]

        if not os.path.exists(html_path):
            print(f"  [{i+1}/{total}] SKIP (not found): {html_path}", file=sys.stderr)
            continue

        print(f"  [{i+1}/{total}] {article_url}...", end="", file=sys.stderr)

        result, modified_html = process_article(
            html_path, article_url, pool,
            max_links, min_distance, skip_existing, dry_run,
        )
        results.append(result)

        inject_count = len(result.injections)
        print(f" {inject_count} injections", file=sys.stderr)

        if not dry_run and output_dir:
            out_path = os.path.join(output_dir, os.path.basename(html_path))
            with open(out_path, "w") as f:
                f.write(modified_html)

    return results


# ── Reporting ────────────────────────────────────────────────────────────────

def print_report(results: list[ArticleResult], dry_run: bool):
    """Print injection report to stdout as JSON."""
    report = {
        "mode": "dry_run" if dry_run else "live",
        "articles_processed": len(results),
        "total_injections": sum(len(r.injections) for r in results),
        "total_skipped": sum(len(r.skipped) for r in results),
        "articles": [],
    }

    for result in results:
        article_report = {
            "source": result.source_path,
            "url": result.article_url,
            "paragraphs_scanned": result.paragraphs_scanned,
            "existing_links": result.existing_links,
            "injections": [
                {
                    "destination": inj.destination_url,
                    "anchor_text": inj.anchor_text,
                    "paragraph_index": inj.paragraph_index,
                    "score": round(inj.score, 1),
                }
                for inj in result.injections
            ],
            "skipped": result.skipped[:10],  # cap at 10 per article
        }
        report["articles"].append(article_report)

    # Destination coverage
    all_injected = set()
    for r in results:
        for inj in r.injections:
            all_injected.add(inj.destination_url)
    report["unique_destinations_linked"] = len(all_injected)

    print(json.dumps(report, indent=2))


# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Linking v2 Phase 2: Inject anchor-text links into article HTML.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run on a single article:
  %(prog)s --site valn --pool sites/valn-anchor-pools.json \\
      --article-html article.html --article-url https://valoannetwork.com/va-loans/ \\
      --dry-run

  # Batch mode with output:
  %(prog)s --site valn --pool sites/valn-anchor-pools.json \\
      --batch-csv batch.csv --output-dir output/ --max-links-per-article 3

  # batch.csv format:
  #   html_path,article_url
  #   articles/va-loans.html,https://valoannetwork.com/va-loans/
  #   articles/va-irrrl.html,https://valoannetwork.com/va-irrrl/
        """,
    )

    parser.add_argument("--site", required=True, help="Site slug (e.g., valn, lrg, tln)")
    parser.add_argument("--pool", required=True, help="Path to anchor pools JSON (Phase 1 output)")

    # Input mode (one of these required)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--article-html", help="Path to single article HTML file")
    input_group.add_argument("--batch-csv", help="Path to batch CSV (columns: html_path, article_url)")

    parser.add_argument("--article-url", help="URL of the article (required with --article-html)")

    # Tuning
    parser.add_argument("--max-links-per-article", type=int, default=5,
                        help="Max internal links to inject per article (default: 5)")
    parser.add_argument("--min-distance-between", type=int, default=200,
                        help="Min character distance between injection points (default: 200)")
    parser.add_argument("--skip-existing-links", action="store_true",
                        help="Don't link to destinations already linked in the article")

    # Output
    parser.add_argument("--dry-run", action="store_true",
                        help="Show proposed injections without modifying HTML")
    parser.add_argument("--output-dir", help="Directory for modified HTML output (batch mode)")

    return parser.parse_args()


def main():
    args = parse_args()

    # Validate args
    if args.article_html and not args.article_url:
        print("ERROR: --article-url required when using --article-html", file=sys.stderr)
        sys.exit(1)

    if args.batch_csv and not args.output_dir and not args.dry_run:
        print("ERROR: --output-dir required for batch mode (or use --dry-run)", file=sys.stderr)
        sys.exit(1)

    # Load pool
    if not os.path.exists(args.pool):
        print(f"ERROR: Pool file not found: {args.pool}", file=sys.stderr)
        sys.exit(1)

    print(f"=== Anchor Injection (Phase 2) ===", file=sys.stderr)
    print(f"Site: {args.site}", file=sys.stderr)
    print(f"Pool: {args.pool}", file=sys.stderr)
    print(f"Max links/article: {args.max_links_per_article}", file=sys.stderr)
    print(f"Min distance: {args.min_distance_between} chars", file=sys.stderr)
    print(f"Skip existing: {args.skip_existing_links}", file=sys.stderr)
    print(f"Dry run: {args.dry_run}", file=sys.stderr)
    print(file=sys.stderr)

    pool = load_pool(args.pool)
    print(f"Loaded {len(pool)} destinations from pool", file=sys.stderr)

    if args.article_html:
        # Single article mode
        if not os.path.exists(args.article_html):
            print(f"ERROR: Article not found: {args.article_html}", file=sys.stderr)
            sys.exit(1)

        result, modified_html = process_article(
            args.article_html, args.article_url, pool,
            args.max_links_per_article, args.min_distance_between,
            args.skip_existing_links, args.dry_run,
        )

        if not args.dry_run and args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)
            out_path = os.path.join(args.output_dir, os.path.basename(args.article_html))
            with open(out_path, "w") as f:
                f.write(modified_html)
            print(f"Output: {out_path}", file=sys.stderr)

        print_report([result], args.dry_run)

    elif args.batch_csv:
        # Batch mode
        if args.output_dir:
            os.makedirs(args.output_dir, exist_ok=True)

        results = process_batch(
            args.batch_csv, pool,
            args.max_links_per_article, args.min_distance_between,
            args.skip_existing_links, args.dry_run, args.output_dir,
        )
        print_report(results, args.dry_run)


if __name__ == "__main__":
    main()
