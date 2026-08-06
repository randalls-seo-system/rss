"""Topic graph — pending links, spoke queueing, and backfill.

Pending-link schema (source-agnostic):
    {
        "topic": str,           # The topic/question needing a page
        "anchor_phrase": str,   # Exact phrase found in the source article body
        "source_post_id": int,  # Post ID of the article that wants this link
        "source_url": str,      # URL of the source article
        "source_job": str,      # Job ID that produced the source article
        "discovered_from": str, # Open enum: "corpus" | "paa" | "gsc" | "ai_mode" | any future source
        "date": str,            # ISO timestamp of discovery
    }

The discovered_from field is an open enum — any string is valid.
Adding a new discovery source (e.g., ai_mode) requires zero schema
changes; only a new producer that emits entries with that tag.

# TODO: AI Mode integration
# When feat/ai-mode lands, wire the related-questions output from
# AI Mode SERP results into the --topic-candidates JSON as entries
# with discovered_from: "ai_mode". The resolution and queueing paths
# already handle this source tag — see test_ai_mode_candidate_resolves.
# Producer location: assemble-article.py Phase B, after AI Mode SERP fetch.
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def collect_pending_from_corpus(
    body_text: str,
    article_phrases: list[str],
    matched_urls: set[str],
    pool_keywords: set[str],
    source_post_id: int,
    source_url: str,
    source_job: str,
) -> list[dict]:
    """Collect corpus phrases that wanted a link but had no pool destination.

    These are multi-word phrases found in the article body that are
    topically relevant but don't match any anchor pool entry.
    """
    pending = []
    seen = set()
    stopwords = {"the", "a", "an", "in", "of", "to", "and", "is", "for",
                 "on", "at", "by", "with", "from", "or", "that", "this"}

    for phrase in article_phrases:
        p_lower = phrase.lower().strip()
        if p_lower in seen or len(p_lower.split()) < 2:
            continue
        # Skip if it's already matched in the pool
        if p_lower in pool_keywords:
            continue
        # Must actually appear in body text
        if p_lower not in body_text.lower():
            continue
        # Must have at least 2 content words
        content_words = [w for w in p_lower.split() if w not in stopwords]
        if len(content_words) < 2:
            continue

        seen.add(p_lower)
        pending.append({
            "topic": phrase,
            "anchor_phrase": phrase,
            "source_post_id": source_post_id,
            "source_url": source_url,
            "source_job": source_job,
            "discovered_from": "corpus",
            "date": datetime.now(timezone.utc).isoformat(),
        })

    return pending


def collect_pending_from_candidates(
    topic_candidates: list[dict],
    matched_urls: set[str],
    pool_keywords: set[str],
    source_post_id: int,
    source_url: str,
    source_job: str,
) -> list[dict]:
    """Collect topic candidates that aren't covered by existing links.

    topic_candidates: list of {topic, discovered_from, ...} dicts.
    discovered_from is an open enum — any string value is valid.
    """
    pending = []
    seen = set()

    for tc in topic_candidates:
        topic = tc.get("topic", "").strip()
        if not topic:
            continue
        t_lower = topic.lower()
        if t_lower in seen:
            continue
        # Skip if pool already has a keyword matching this topic
        if t_lower in pool_keywords:
            continue
        # Check if any matched URL's slug contains the topic words
        topic_words = set(t_lower.split()) - {"the", "a", "an", "in", "of", "to"}
        already_linked = False
        for url in matched_urls:
            slug = url.strip("/").split("/")[-1] if "/" in url else url
            slug_words = set(slug.replace("-", " ").lower().split())
            if len(topic_words & slug_words) >= 2:
                already_linked = True
                break
        if already_linked:
            continue

        seen.add(t_lower)
        pending.append({
            "topic": topic,
            "anchor_phrase": tc.get("anchor_phrase", topic),
            "source_post_id": source_post_id,
            "source_url": source_url,
            "source_job": source_job,
            "discovered_from": tc.get("discovered_from", "unknown"),
            "date": datetime.now(timezone.utc).isoformat(),
        })

    return pending


def resolve_pending_entries(
    entries: list[dict],
    slug_to_id: dict[str, int],
    gsc_query_pages: dict[str, str],
    site_slug: str,
) -> tuple[list[dict], list[dict]]:
    """Resolve pending entries against existing pages.

    Returns (linked_existing, no_page) where:
    - linked_existing: entries whose topic maps to an existing page
    - no_page: entries with no existing page (spoke candidates)
    """
    linked = []
    no_page = []

    for entry in entries:
        topic = entry["topic"].lower().strip()

        # Check 1: GSC query→page mapping
        matched_slug = gsc_query_pages.get(topic)

        # Check 2: slug/title fuzzy match against post inventory
        if not matched_slug:
            topic_slug = re.sub(r"[^a-z0-9]+", "-", topic).strip("-")
            for slug in slug_to_id:
                if topic_slug in slug or slug in topic_slug:
                    matched_slug = slug
                    break

        # Check 3: word overlap with slugs
        if not matched_slug:
            topic_words = set(topic.split()) - {"the", "a", "an", "in", "of", "to", "and", "for", "how", "what", "is"}
            if len(topic_words) >= 2:
                for slug in slug_to_id:
                    slug_words = set(slug.replace("-", " ").split())
                    overlap = len(topic_words & slug_words)
                    if overlap >= 2 and overlap >= len(topic_words) * 0.5:
                        matched_slug = slug
                        break

        if matched_slug:
            entry_copy = dict(entry)
            entry_copy["resolution"] = "linked_existing"
            entry_copy["destination_slug"] = matched_slug
            entry_copy["destination_url"] = f"/{matched_slug}/"
            entry_copy["destination_post_id"] = slug_to_id.get(matched_slug)
            linked.append(entry_copy)
        else:
            entry_copy = dict(entry)
            entry_copy["resolution"] = "no_page"
            no_page.append(entry_copy)

    return linked, no_page


def dedupe_spoke_candidates(no_page_entries: list[dict]) -> list[dict]:
    """Dedupe spoke candidates: same topic from multiple sources → one item with accumulated notes.

    Returns list of unique topic dicts with backlink_notes arrays.
    """
    topic_map: dict[str, dict] = {}

    for entry in no_page_entries:
        topic_key = entry["topic"].lower().strip()
        if topic_key not in topic_map:
            topic_map[topic_key] = {
                "topic": entry["topic"],
                "target_keyword": entry["topic"],
                "backlink_notes": [],
                "discovered_from_sources": set(),
            }
        item = topic_map[topic_key]
        item["backlink_notes"].append({
            "source_post_id": entry["source_post_id"],
            "source_url": entry["source_url"],
            "anchor_phrase": entry["anchor_phrase"],
        })
        item["discovered_from_sources"].add(entry.get("discovered_from", "unknown"))

    result = []
    for item in topic_map.values():
        item["demand_count"] = len(item["backlink_notes"])
        item["discovered_from_sources"] = sorted(item["discovered_from_sources"])
        result.append(item)

    result.sort(key=lambda x: x["demand_count"], reverse=True)
    return result


def enrich_anchor_pool(
    site_slug: str,
    linked_entries: list[dict],
) -> int:
    """Add keyword variants from resolved entries to the site's anchor pool.

    Returns number of new entries added.
    """
    pool_path = REPO_ROOT / "sites" / f"{site_slug}-anchor-pools.json"
    if not pool_path.exists():
        return 0

    pool_data = json.loads(pool_path.read_text())
    existing_urls = {d.get("url", "").rstrip("/") for d in pool_data}
    added = 0

    for entry in linked_entries:
        dest_url = entry.get("destination_url", "")
        if not dest_url:
            continue

        # Check if URL already in pool
        if dest_url.rstrip("/") in existing_urls:
            # Add anchor phrase as new keyword variant
            for dest in pool_data:
                if dest.get("url", "").rstrip("/") == dest_url.rstrip("/"):
                    anchors = dest.get("anchors", [])
                    phrase = entry.get("anchor_phrase", "")
                    if phrase and phrase.lower() not in {a.lower() for a in anchors}:
                        anchors.append(phrase)
                        dest["anchors"] = anchors
                        added += 1
                    break
        else:
            # Add new destination
            pool_data.append({
                "url": dest_url,
                "slug": entry.get("destination_slug", ""),
                "title": entry.get("topic", ""),
                "primary_keyword": entry.get("topic", ""),
                "anchors": [entry.get("anchor_phrase", entry.get("topic", ""))],
            })
            existing_urls.add(dest_url.rstrip("/"))
            added += 1

    if added > 0:
        pool_path.write_text(json.dumps(pool_data, indent=2, ensure_ascii=False))

    return added


def insert_single_link(html: str, anchor_phrase: str, dest_url: str,
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
        if p.find("a", string=pattern):
            continue
        text = p.get_text()
        m = pattern.search(text)
        if m:
            matched_text = m.group(0)
            # Simple replacement in the paragraph's string content
            for child in list(p.children):
                if isinstance(child, str) and pattern.search(child):
                    before, after = pattern.split(child, maxsplit=1)
                    new_a = soup.new_tag("a", href=dest_url, **{"class": "rss-il"})
                    new_a.string = matched_text
                    child.replace_with(before)
                    p.insert(list(p.children).index(p.find(string=before)) + 1 if p.find(string=before) else 0, new_a)
                    new_a.insert_after(after)
                    return str(soup), True

    return html, False


def build_topic_graph_summary(site_slug: str) -> dict:
    """Build the topic graph summary for a site.

    Returns dict with counts for pending, resolved, queued, backfilled.
    """
    from .queue import load_queue

    # Scan all jobs for pending-links files
    jobs_dir = REPO_ROOT / "jobs"
    pending_total = 0
    pending_by_source: dict[str, int] = {}
    resolved_linked = 0
    resolved_no_page = 0

    if jobs_dir.exists():
        for job_dir in jobs_dir.iterdir():
            if not job_dir.is_dir():
                continue
            # Pending links
            for pl_file in job_dir.glob("*-pending-links.json"):
                try:
                    entries = json.loads(pl_file.read_text())
                    pending_total += len(entries)
                    for e in entries:
                        src = e.get("discovered_from", "unknown")
                        pending_by_source[src] = pending_by_source.get(src, 0) + 1
                except (json.JSONDecodeError, KeyError):
                    pass
            # Resolution reports
            for res_file in job_dir.glob("*-resolution.json"):
                try:
                    res = json.loads(res_file.read_text())
                    resolved_linked += len(res.get("linked_existing", []))
                    resolved_no_page += len(res.get("no_page", []))
                except (json.JSONDecodeError, KeyError):
                    pass

    # Queue stats
    queue = load_queue(site_slug)
    pending_link_items = [i for i in queue if i.get("origin") == "pending_link"]
    backlink_notes_total = sum(
        len(i.get("backlink_notes", [])) for i in pending_link_items
    )

    # Backfill stats
    backfills_completed = 0
    backfills_failed = 0
    for item in queue:
        bf = item.get("backfill_results", {})
        backfills_completed += bf.get("completed", 0)
        backfills_failed += bf.get("failed", 0)

    return {
        "pending_topics": pending_total,
        "pending_by_source": pending_by_source,
        "resolved_linked": resolved_linked,
        "resolved_no_page": resolved_no_page,
        "queued_spokes": len(pending_link_items),
        "queued_backlink_notes": backlink_notes_total,
        "backfills_completed": backfills_completed,
        "backfills_failed": backfills_failed,
    }
