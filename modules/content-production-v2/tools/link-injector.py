#!/usr/bin/env python3
"""Unified internal-link injector — pool mode and corpus mode.

Pool mode:  match anchor-pool phrases against article text (pipeline use).
Corpus mode: derive candidates from destination title/slug + optional pool
             (legacy-content batch use).

Dry-run is the DEFAULT. --execute required for any writes.
Dry-run executes inject_link_in_paragraph on an in-memory copy; only
injectable rows reach the CSV (parity by construction).

Usage:
    python3 link-injector.py --mode corpus --site-config sites/tln-linker.json \\
        --export posts.jsonl --dry-run-csv out.csv

    python3 link-injector.py --mode corpus --site-config sites/tln-linker.json \\
        --export posts.jsonl --execute --log run.log
"""

import argparse
import copy
import csv
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

TOOLS_DIR = Path(__file__).resolve().parent
MODULE_DIR = TOOLS_DIR.parent
REPO_ROOT = MODULE_DIR.parent.parent
sys.path.insert(0, str(MODULE_DIR))

from bs4 import BeautifulSoup, Tag

from lib.linker_core import (
    STOPWORDS,
    _normalize_for_dedup,
    corpus_candidates,
    deploy_lock,
    inject_link_in_paragraph,
    is_body_section,
    is_dest_capped,
    is_restricted_zone,
    manual_destinations_candidates,
    pool_candidates,
    score_candidate,
)


# ───────────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────────

def _extract_existing_hrefs(content: str, site_domain: str) -> set[str]:
    """Extract normalized internal link destinations already in content."""
    href_re = re.compile(r'<a\b[^>]*\bhref="([^"]*)"', re.IGNORECASE)
    result = set()
    for m in href_re.finditer(content):
        href = m.group(1)
        if not href:
            continue
        is_internal = (
            (href.startswith("/") and not href.startswith("//"))
            or (site_domain and site_domain in href)
        )
        if is_internal:
            result.add(_normalize_for_dedup(href))
    return result


def _compute_inbound_counts(posts: list[dict], site_domain: str) -> dict[str, int]:
    """Count how many posts link to each internal destination."""
    counts: dict[str, int] = {}
    for post in posts:
        content = post.get("content", "")
        if not content:
            continue
        seen_in_post = set()
        href_re = re.compile(r'<a\b[^>]*\bhref="([^"]*)"', re.IGNORECASE)
        for m in href_re.finditer(content):
            href = m.group(1)
            is_internal = (
                (href.startswith("/") and not href.startswith("//"))
                or (site_domain and site_domain in href)
            )
            if is_internal:
                norm = _normalize_for_dedup(href)
                if norm not in seen_in_post:
                    seen_in_post.add(norm)
                    counts[norm] = counts.get(norm, 0) + 1
    return counts


def _build_corpus_index(posts: list[dict], site_domain: str) -> list[dict]:
    """Build corpus index from exported posts (for corpus candidate gen)."""
    index = []
    for p in posts:
        slug = p.get("slug", "")
        title = p.get("title", slug.replace("-", " ").title())
        url = p.get("url", "")
        if not url:
            url = f"/{slug}/"
        index.append({
            "id": p.get("id"),
            "slug": slug,
            "title": title,
            "url": url,
        })
    return index


# ───────────────────────────────────────────────────────────────────────────
# Core injection loop
# ───────────────────────────────────────────────────────────────────────────

def inject_post(
    content: str,
    candidates: list[tuple[str, str, float, str]],
    post_id: int,
    site_domain: str,
    zone_config: dict,
    config: dict,
    inbound_counts: dict[str, int],
    per_run_dest_counts: dict[str, int],
) -> tuple[str, list[dict]]:
    """Inject links into a single post's content.

    Returns (modified_content, list_of_link_details).
    Each detail: {anchor, url, source, section, paragraph_index, injection_verified}
    """
    max_per_post = config.get("max_links_per_post", 10)
    max_per_section = config.get("max_links_per_section", 3)
    max_per_para = config.get("max_links_per_para", 1)
    inbound_min = config.get("inbound_min", 3)
    per_run_cap = config.get("per_run_dest_cap", 10)
    protected = set(config.get("protected_slugs", []))
    excluded_dests = config.get("excluded_destinations", [])

    soup = BeautifulSoup(content, "html.parser")
    soup_str = str(soup)

    # Pre-existing internal links
    used_urls = _extract_existing_hrefs(content, site_domain)
    used_anchors: set[str] = set()
    details: list[dict] = []
    total = 0

    # Find H2/H3 section boundaries
    h_re = re.compile(r'<h[23][^>]*>(.*?)</h[23]>', re.IGNORECASE | re.DOTALL)
    h_matches = list(h_re.finditer(soup_str))
    if not h_matches:
        return content, []

    for h_match in h_matches:
        if total >= max_per_post:
            break
        h_text = re.sub(r'<[^>]+>', '', h_match.group(1)).strip()
        if not is_body_section(h_text):
            continue

        # Section boundaries
        h_end = h_match.end()
        next_h = len(soup_str)
        for other in h_matches:
            if other.start() > h_end:
                next_h = other.start()
                break
        section_html = soup_str[h_end:next_h]

        # Find paragraphs in section via BS4 (for text-node-safe injection)
        section_soup = BeautifulSoup(section_html, "html.parser")
        paras = section_soup.find_all("p")
        section_injected = 0

        for pi, para in enumerate(paras):
            if section_injected >= max_per_section or total >= max_per_post:
                break
            if is_restricted_zone(para, zone_config):
                continue
            text = para.get_text()
            if len(text.split()) < 10:
                continue

            para_injected = 0
            # Score and sort candidates for this paragraph
            scored = []
            for phrase, url, base_score, source in candidates:
                norm_url = _normalize_for_dedup(url)
                if norm_url in used_urls:
                    continue
                if phrase.lower() in used_anchors:
                    continue
                # Hard cap: skip destinations that have reached their per-run limit
                if is_dest_capped(url, per_run_dest_counts, per_run_cap):
                    continue
                # Protected destination check
                if any(p in url for p in protected):
                    continue
                # Excluded destination check (prefix match)
                if any(norm_url.startswith(ex.rstrip("/").lower()) for ex in excluded_dests):
                    continue
                pat = re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
                if not pat.search(text):
                    continue
                s = score_candidate(
                    phrase, base_score, url, inbound_counts, inbound_min,
                )
                scored.append((s, phrase, url, source))

            scored.sort(key=lambda x: (-x[0], -len(x[1])))

            for s, phrase, url, source in scored:
                if para_injected >= max_per_para:
                    break

                # In-memory injection verification (parity by construction)
                para_copy = BeautifulSoup(str(para), "html.parser")
                p_tag = para_copy.find("p") or para_copy
                injected = inject_link_in_paragraph(p_tag, phrase, url)
                if not injected:
                    continue

                norm_url = _normalize_for_dedup(url)
                used_urls.add(norm_url)
                used_anchors.add(phrase.lower())
                para_injected += 1
                section_injected += 1
                total += 1
                per_run_dest_counts[norm_url] = per_run_dest_counts.get(norm_url, 0) + 1

                # Context
                idx = text.lower().find(phrase.lower())
                if idx >= 0:
                    start = max(0, idx - 20)
                    end = min(len(text), idx + len(phrase) + 20)
                    ctx = text[start:end].replace("\n", " ").strip()
                else:
                    ctx = text[:60].replace("\n", " ").strip()

                details.append({
                    "anchor": phrase,
                    "url": url,
                    "candidate_source": source,
                    "section": h_text[:50],
                    "paragraph_index": pi,
                    "surrounding_text_60chars": ctx,
                    "injection_verified": "true",
                })
                break  # one per paragraph

    return content, details  # content unmodified in dry-run; details are the proposals


# ───────────────────────────────────────────────────────────────────────────
# Main
# ───────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Unified internal-link injector")
    parser.add_argument("--mode", choices=["pool", "corpus"], required=True)
    parser.add_argument("--site-config", required=True, help="Path to site linker config JSON")
    parser.add_argument("--export", required=True, help="JSONL export of posts (id, slug, title, type, content)")
    parser.add_argument("--dry-run-csv", help="Output CSV path (dry-run mode, default)")
    parser.add_argument("--execute", action="store_true", help="Write changes (requires lockfile)")
    parser.add_argument("--log", help="Log file path")
    args = parser.parse_args()

    if args.execute:
        print("ERROR: --execute mode not yet implemented. Use dry-run.", file=sys.stderr)
        sys.exit(1)

    # Load config
    with open(args.site_config) as f:
        config = json.load(f)

    site_id = config["site_id"]
    site_domain = config.get("site_domain", "")
    skip_slugs = set(config.get("skip_slugs", []))
    protected_slugs = set(config.get("protected_slugs", []))
    pages_as_sources = config.get("pages_as_sources", False)

    zone_config = {
        "prefixes": config.get("css_prefix", []),
        "suffixes": config.get("zone_suffixes", []),
        "extra_classes": config.get("extra_zone_classes", []),
    }

    # Load posts
    posts = []
    with open(args.export) as f:
        for line in f:
            line = line.strip()
            if line:
                posts.append(json.loads(line))

    # Build candidates
    candidates = []
    if args.mode == "corpus":
        corpus_index = _build_corpus_index(posts, site_domain)
        candidates = corpus_candidates(corpus_index)

    # Add pool candidates if pool_path exists (additive)
    pool_path = config.get("pool_path", "")
    if pool_path:
        full_pool_path = REPO_ROOT / pool_path
        if full_pool_path.exists():
            pool_cands = pool_candidates(full_pool_path)
            # Merge: pool candidates additive, dedup by (phrase_lower, url)
            existing_keys = {(c[0].lower(), c[1]) for c in candidates}
            for c in pool_cands:
                key = (c[0].lower(), c[1])
                if key not in existing_keys:
                    candidates.append(c)
                    existing_keys.add(key)

    # Add manual_destinations if configured (additive, same dedup)
    manual_dests = config.get("manual_destinations", [])
    if manual_dests:
        manual_cands = manual_destinations_candidates(manual_dests)
        existing_keys = {(c[0].lower(), c[1]) for c in candidates}
        for c in manual_cands:
            key = (c[0].lower(), c[1])
            if key not in existing_keys:
                candidates.append(c)
                existing_keys.add(key)

    # Re-sort by phrase length desc
    candidates.sort(key=lambda x: -len(x[0]))

    # Compute inbound counts from the export
    inbound_counts = _compute_inbound_counts(posts, site_domain)

    # Filter posts to scan
    scannable = []
    for p in posts:
        if not pages_as_sources and p.get("type") == "page":
            continue
        if p.get("slug") in skip_slugs:
            continue
        content = p.get("content", "")
        if not content or len(content) < 100:
            continue
        # Protected as source
        slug = p.get("slug", "")
        if any(f"/{slug}/" in ps or slug == ps.strip("/") for ps in protected_slugs):
            continue
        scannable.append(p)

    ts = datetime.now().strftime("%Y%m%d")
    csv_path = Path(args.dry_run_csv) if args.dry_run_csv else Path(f"corpus-dryrun-{ts}.csv")
    log_path = Path(args.log) if args.log else None
    log_lines = []

    def log(msg):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
        print(line)
        log_lines.append(line)

    log(f"=== Link Injector — {datetime.now().isoformat()} ===")
    log(f"Mode: {args.mode}")
    log(f"Site: {site_id}")
    log(f"Export: {len(posts)} posts loaded")
    log(f"Scannable: {len(scannable)} posts (after type/slug/protected filters)")
    log(f"Candidates: {len(candidates)} phrases")
    log(f"Inbound counts: {len(inbound_counts)} destinations tracked")

    # Source breakdown
    source_counts = {}
    for _, _, _, src in candidates:
        source_counts[src] = source_counts.get(src, 0) + 1
    for src, cnt in sorted(source_counts.items()):
        log(f"  {src}: {cnt} candidates")

    csv_rows = []
    per_run_dest_counts: dict[str, int] = {}
    posts_with_links = 0
    total_proposed = 0
    per_post_counts = {}

    for i, post in enumerate(scannable):
        post_id = post["id"]
        slug = post["slug"]
        content = post["content"]

        # Filter candidates: exclude self
        post_candidates = [
            c for c in candidates if _normalize_for_dedup(c[1]) != _normalize_for_dedup(f"/{slug}/")
        ]

        # Language match: prevent cross-language linking
        if config.get("source_dest_language_match"):
            lang_prefixes = config.get("language_prefixes", {})
            spanish_prefix = lang_prefixes.get("spanish", "/spanish-blog/")
            source_url = post.get("url", f"/{slug}/")
            source_is_spanish = spanish_prefix in source_url
            post_candidates = [
                c for c in post_candidates
                if (spanish_prefix in c[1].lower()) == source_is_spanish
            ]

        _, details = inject_post(
            content, post_candidates, post_id, site_domain,
            zone_config, config, inbound_counts, per_run_dest_counts,
        )

        if details:
            posts_with_links += 1
            count = len(details)
            total_proposed += count
            per_post_counts[post_id] = count

            for d in details:
                csv_rows.append({
                    "post_id": post_id,
                    "post_slug": slug,
                    "trigger_matched": d["anchor"],
                    "anchor_text": d["anchor"],
                    "destination_url": d["url"],
                    "paragraph_index": d["paragraph_index"],
                    "surrounding_text_60chars": d["surrounding_text_60chars"],
                    "injection_verified": d["injection_verified"],
                    "candidate_source": d["candidate_source"],
                })

    # Write CSV
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "post_id", "post_slug", "trigger_matched", "anchor_text",
            "destination_url", "paragraph_index", "surrounding_text_60chars",
            "injection_verified", "candidate_source",
        ])
        writer.writeheader()
        writer.writerows(csv_rows)

    # Summary
    log(f"\n{'=' * 60}")
    log(f"DRY-RUN SUMMARY ({args.mode} mode)")
    log(f"{'=' * 60}")
    log(f"Posts scanned:              {len(scannable)}")
    log(f"Posts with proposed links:  {posts_with_links}")
    log(f"Total proposed links:       {total_proposed}")
    if posts_with_links:
        log(f"Average per linked post:    {total_proposed / posts_with_links:.1f}")
    if per_post_counts:
        log(f"Min per post: {min(per_post_counts.values())}, Max per post: {max(per_post_counts.values())}")

    heavy = {pid: c for pid, c in per_post_counts.items() if c > 15}
    if heavy:
        log(f"\nWARNING: {len(heavy)} posts with >15 proposed links:")
        for pid, c in sorted(heavy.items(), key=lambda x: -x[1]):
            log(f"  Post {pid}: {c} links")

    # Candidate source breakdown in results
    src_in_results = {}
    for r in csv_rows:
        s = r["candidate_source"]
        src_in_results[s] = src_in_results.get(s, 0) + 1
    if src_in_results:
        log(f"\nCandidate source breakdown (in proposed links):")
        for s, c in sorted(src_in_results.items()):
            log(f"  {s}: {c}")

    # Inbound projection
    log(f"\nInbound coverage projection:")
    dest_proposed = {}
    for r in csv_rows:
        d = _normalize_for_dedup(r["destination_url"])
        dest_proposed[d] = dest_proposed.get(d, 0) + 1

    before_1 = sum(1 for d in dest_proposed if inbound_counts.get(d, 0) >= 1)
    before_3 = sum(1 for d in dest_proposed if inbound_counts.get(d, 0) >= 3)
    after_1 = sum(1 for d in dest_proposed if inbound_counts.get(d, 0) + dest_proposed[d] >= 1)
    after_3 = sum(1 for d in dest_proposed if inbound_counts.get(d, 0) + dest_proposed[d] >= 3)
    log(f"  Destinations receiving links: {len(dest_proposed)}")
    log(f"  Already had >=1 inbound: {before_1} → after: {after_1}")
    log(f"  Already had >=3 inbound: {before_3} → after: {after_3}")

    # Under-threshold destinations
    under_3 = sum(1 for d in dest_proposed if inbound_counts.get(d, 0) < 3)
    log(f"  Under-3 destinations targeted: {under_3}")

    log(f"\nCSV output: {csv_path}")
    log(f"{'=' * 60}")

    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("\n".join(log_lines) + "\n")
        print(f"Log: {log_path}")


if __name__ == "__main__":
    main()
