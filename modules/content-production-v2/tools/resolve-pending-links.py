#!/usr/bin/env python3
"""Resolve pending links: match topics to existing pages or queue new spokes.

Usage:
    resolve-pending-links.py --site tln [--job <id> | --all-jobs] [--confirm]

For each pending entry:
  - Page exists → enrich anchor pool + record linked_existing
  - No page → queue as new-article spoke with backlink notes
  - Cannibalization guard: topic mapping to existing page = never a new item
"""

import argparse
import json
import sys
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(MODULE_DIR))

from lib.topic_graph import (
    resolve_pending_entries, dedupe_spoke_candidates, enrich_anchor_pool,
    REPO_ROOT,
)
from lib.queue import load_queue, add_item


def _load_slug_map(site_slug: str) -> dict[str, int]:
    """Load slug→ID map from the site's queue or cached inventory."""
    # Try to load from a cached inventory file
    inv_path = REPO_ROOT / "sites" / site_slug / "post-inventory.json"
    if inv_path.exists():
        try:
            return json.loads(inv_path.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def _load_gsc_query_pages(site_slug: str) -> dict[str, str]:
    """Load query→slug mapping from the latest audit or seed data."""
    docs_dir = REPO_ROOT / "docs"
    audit_files = sorted(docs_dir.glob(f"{site_slug}-audit-*.json"), reverse=True)
    if not audit_files:
        return {}
    try:
        audit = json.loads(audit_files[0].read_text())
        mapping = {}
        for r in audit.get("results", []):
            if r.get("top_query") and r.get("slug"):
                mapping[r["top_query"].lower()] = r["slug"]
        return mapping
    except (json.JSONDecodeError, KeyError):
        return {}


def main():
    parser = argparse.ArgumentParser(description="Resolve pending links into pool entries or queue spokes")
    parser.add_argument("--site", required=True)
    parser.add_argument("--job", default="", help="Resolve pending links from a specific job")
    parser.add_argument("--all-jobs", action="store_true", help="Resolve across all jobs")
    parser.add_argument("--confirm", action="store_true", help="Actually write to pool/queue")
    args = parser.parse_args()

    jobs_dir = REPO_ROOT / "jobs"

    # Collect all pending entries
    all_pending = []
    if args.job:
        job_dir = jobs_dir / args.job
        for pl_file in job_dir.glob("*-pending-links.json"):
            entries = json.loads(pl_file.read_text())
            all_pending.extend(entries)
    elif args.all_jobs:
        if jobs_dir.exists():
            for job_dir in sorted(jobs_dir.iterdir()):
                if not job_dir.is_dir():
                    continue
                for pl_file in job_dir.glob("*-pending-links.json"):
                    try:
                        entries = json.loads(pl_file.read_text())
                        all_pending.extend(entries)
                    except json.JSONDecodeError:
                        pass
    else:
        print("Specify --job <id> or --all-jobs", file=sys.stderr)
        sys.exit(1)

    if not all_pending:
        print("No pending links found.")
        return

    print(f"Found {len(all_pending)} pending entries")

    # Load resolution data
    slug_map = _load_slug_map(args.site)
    gsc_pages = _load_gsc_query_pages(args.site)
    print(f"  Slug map: {len(slug_map)} posts, GSC queries: {len(gsc_pages)} mappings")

    # Resolve
    linked, no_page = resolve_pending_entries(all_pending, slug_map, gsc_pages, args.site)

    print(f"\nResolution:")
    print(f"  Linked to existing page: {len(linked)}")
    print(f"  No page (spoke candidates): {len(no_page)}")

    if linked:
        print(f"\n--- Linked existing ({len(linked)}) ---")
        for e in linked[:20]:
            print(f"  {e['topic'][:40]:40s} → {e.get('destination_slug', '?')}")

    # Dedupe spokes
    spokes = dedupe_spoke_candidates(no_page)

    if spokes:
        print(f"\n--- Spoke candidates ({len(spokes)}) ---")
        for s in spokes[:20]:
            sources = ", ".join(s["discovered_from_sources"])
            print(f"  [{s['demand_count']}x] {s['topic'][:50]:50s} ({sources})")

    # Check cannibalization: any spoke topic that maps to an existing page
    # should NOT become a new item (already caught by resolve, but double-check)
    existing_queue = load_queue(args.site)
    existing_topics = {i["target_keyword"].lower() for i in existing_queue}

    if args.confirm:
        # Enrich pool
        pool_added = enrich_anchor_pool(args.site, linked)
        print(f"\nPool enrichment: {pool_added} new entries added")

        # Queue spokes
        queued = 0
        for spoke in spokes:
            t_lower = spoke["target_keyword"].lower()
            if t_lower in existing_topics:
                print(f"  SKIP (already queued): {spoke['topic'][:50]}")
                continue
            item = add_item(
                args.site, spoke["topic"],
                keyword=spoke["target_keyword"],
            )
            # Patch the item with backlink notes and origin
            items = load_queue(args.site)
            for it in items:
                if it["id"] == item["id"]:
                    it["origin"] = "pending_link"
                    it["backlink_notes"] = spoke["backlink_notes"]
                    break
            from lib.queue import save_queue
            save_queue(args.site, items)
            existing_topics.add(t_lower)
            queued += 1
        print(f"Queued {queued} new spoke articles")

        # Save resolution report
        if args.job:
            res_path = jobs_dir / args.job / f"{args.job}-resolution.json"
        else:
            res_path = REPO_ROOT / "docs" / f"{args.site}-resolution-latest.json"
        res_path.parent.mkdir(parents=True, exist_ok=True)
        res_path.write_text(json.dumps({
            "linked_existing": linked,
            "no_page": no_page,
            "spokes_queued": queued,
            "pool_enriched": pool_added,
        }, indent=2))
        print(f"Resolution report: {res_path}")
    else:
        print(f"\nDry run — re-run with --confirm to write to pool/queue")


if __name__ == "__main__":
    main()
