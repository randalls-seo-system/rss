#!/usr/bin/env python3
"""Resolve pending links: match topics to existing pages or queue new spokes.

Usage:
    resolve-pending-links.py --site tln [--job <id> | --all-jobs] [--confirm]

Prerequisites:
    - Post inventory must exist at sites/<slug>/post-inventory.json
      (build via: rss doctor --site <slug>, which caches the inventory)
    - If inventory is missing or empty, this tool ERRORS and resolves nothing.

For each pending entry:
  1. Self-coverage check: is the topic already covered in the source article?
     If yes → covered_in_source (never becomes a spoke)
  2. Page exists → enrich anchor pool + record linked_existing
  3. No page → queue as new-article spoke with backlink notes
  4. Cannibalization guard: topic mapping to existing page = never a new item
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
    """Load slug→ID map from the site's cached post inventory.

    Returns empty dict if not found — caller must check and fail closed.
    """
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


def _load_source_htmls(jobs_dir: Path, pending_entries: list[dict]) -> dict[int, str]:
    """Load source article HTML for self-coverage checks.

    Looks for article HTML in the job dir referenced by each entry's source_job.
    """
    htmls = {}
    for entry in pending_entries:
        source_id = entry.get("source_post_id")
        source_job = entry.get("source_job", "")
        if not source_id or source_id in htmls:
            continue
        if source_job:
            job_dir = jobs_dir / source_job
            # Try *-article.html pattern
            for art_file in job_dir.glob("*-article.html"):
                try:
                    htmls[source_id] = art_file.read_text()
                    break
                except Exception:
                    pass
    return htmls


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

    # FAIL CLOSED: load inventory and check it's non-empty
    slug_map = _load_slug_map(args.site)
    if not slug_map:
        print(
            f"ERROR: Post inventory empty or missing for site '{args.site}'.\n"
            f"  Expected: sites/{args.site}/post-inventory.json\n"
            f"  Build it: rss doctor --site {args.site} (caches inventory)\n"
            f"  Or manually: ssh to site, run wp post list --format=csv, save as JSON.\n"
            f"\n"
            f"Resolving with an empty inventory would misclassify every topic as 'no page'\n"
            f"and queue spoke articles for topics that already have pages. Aborting.",
            file=sys.stderr,
        )
        sys.exit(1)

    gsc_pages = _load_gsc_query_pages(args.site)
    print(f"  Slug map: {len(slug_map)} posts, GSC queries: {len(gsc_pages)} mappings")

    # Load source HTML for self-coverage checks
    source_htmls = _load_source_htmls(jobs_dir, all_pending)
    print(f"  Source articles loaded for coverage check: {len(source_htmls)}")

    # Resolve
    linked, no_page, covered = resolve_pending_entries(
        all_pending, slug_map, gsc_pages, args.site, source_htmls=source_htmls,
    )

    print(f"\nResolution:")
    print(f"  Covered in source article: {len(covered)}")
    print(f"  Linked to existing page:   {len(linked)}")
    print(f"  No page (spoke candidates):{len(no_page)}")

    if covered:
        print(f"\n--- Covered in source ({len(covered)}) ---")
        for e in covered[:20]:
            print(f"  {e['topic'][:50]:50s} (source post {e.get('source_post_id')})")

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
            "covered_in_source": covered,
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
