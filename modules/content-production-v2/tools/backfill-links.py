#!/usr/bin/env python3
"""Backfill links into source articles when a spoke page is published.

Usage:
    backfill-links.py --site tln --queue-id <id> [--live]

For each backlink_note on the queue item:
  - Fetch the source article
  - Verify anchor phrase still exists
  - Insert ONE link to the new page at first natural occurrence
  - Run gates on modified HTML before pushing
  - --live required for published posts; drafts/pending can be patched automatically

Safety: never force a link if the phrase is gone; gates must pass on
the modified HTML; backup artifact created before any write.
"""

import argparse
import json
import re
import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MODULE_DIR))

from lib.topic_graph import REPO_ROOT


def _insert_single_link(html: str, anchor_phrase: str, dest_url: str,
                        max_links_per_post: int = 14) -> tuple[str, bool]:
    """Insert ONE link at the first natural occurrence of anchor_phrase.

    Returns (modified_html, was_inserted).
    Respects per-post link cap by counting existing internal links.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # Count existing internal links
    existing_count = 0
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/") and not href.startswith("//"):
            existing_count += 1
    if existing_count >= max_links_per_post:
        return html, False

    # Find first occurrence in a body <p> (not in headings, not already linked)
    pattern = re.compile(r"\b" + re.escape(anchor_phrase) + r"\b", re.IGNORECASE)

    for p in soup.find_all("p"):
        # Skip paragraphs already containing an <a> with this text
        if p.find("a", string=pattern):
            continue
        text = p.get_text()
        m = pattern.search(text)
        if m:
            # Insert the link
            matched_text = m.group(0)
            new_a = soup.new_tag("a", href=dest_url, **{"class": "rss-il"})
            new_a.string = matched_text

            # Replace in the paragraph's contents
            for child in p.children:
                if isinstance(child, str) and pattern.search(child):
                    parts = pattern.split(child, maxsplit=1)
                    if len(parts) == 2:
                        child.replace_with(parts[0])
                        p.insert(list(p.children).index(child) + 1 if child in p.children else len(list(p.children)), new_a)
                        new_a.insert_after(parts[1])
                        return str(soup), True
                    break

    return html, False


def main():
    parser = argparse.ArgumentParser(description="Backfill links into source articles")
    parser.add_argument("--site", required=True)
    parser.add_argument("--queue-id", required=True, help="Queue item ID with backlink_notes")
    parser.add_argument("--live", action="store_true",
                        help="Allow backfill into LIVE published posts (requires explicit flag)")
    args = parser.parse_args()

    from lib.queue import load_queue, save_queue

    items = load_queue(args.site)
    target_item = None
    for it in items:
        if it["id"] == args.queue_id:
            target_item = it
            break

    if not target_item:
        print(f"Queue item {args.queue_id} not found", file=sys.stderr)
        sys.exit(1)

    notes = target_item.get("backlink_notes", [])
    if not notes:
        print(f"Queue item {args.queue_id} has no backlink notes")
        return

    new_url = f"/{target_item.get('target_keyword', '').lower().replace(' ', '-')}/"
    print(f"Backfilling {len(notes)} link(s) to {new_url}")

    results = {"completed": 0, "failed": 0, "skipped_live": 0, "details": []}

    for note in notes:
        source_id = note["source_post_id"]
        anchor = note["anchor_phrase"]
        print(f"  Source post {source_id}: anchor '{anchor}'")

        # In a full implementation, this would:
        # 1. Fetch source post HTML via SSH
        # 2. Verify anchor phrase exists
        # 3. Check if source is draft or published
        # 4. If published and --live not set, skip
        # 5. Insert link, run gates, backup, push

        # For now, record the intent without making live changes
        if not args.live:
            print(f"    SKIPPED: live post, --live flag not set")
            results["skipped_live"] += 1
            results["details"].append({
                "source_post_id": source_id,
                "anchor": anchor,
                "status": "skipped_live",
            })
        else:
            print(f"    Would insert link to {new_url} at '{anchor}'")
            results["details"].append({
                "source_post_id": source_id,
                "anchor": anchor,
                "status": "pending_implementation",
            })

    # Update queue item with backfill results
    for it in items:
        if it["id"] == args.queue_id:
            it["backfill_results"] = results
            break
    save_queue(args.site, items)
    print(f"\nResults: {results['completed']} completed, {results['failed']} failed, "
          f"{results['skipped_live']} skipped (live)")


if __name__ == "__main__":
    main()
