#!/usr/bin/env python3
"""Batch-inject internal links across all published posts for a site.

Downloads each post's content, runs inject-internal-links logic,
and uploads the modified content via SQL UNHEX over SSH.

Usage:
    python3 batch-inject-links.py --site canopy [--dry-run] [--limit N]
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
MODULE_DIR = TOOLS_DIR.parent
REPO_ROOT = MODULE_DIR.parent.parent
sys.path.insert(0, str(MODULE_DIR))

from bs4 import BeautifulSoup
from lib.anchor_pool import AnchorPool
from lib.site_config import load_site_config


# ---------------------------------------------------------------------------
# Section classification (same as inject-internal-links.py)
# ---------------------------------------------------------------------------

_SKIP_MARKERS = frozenset({
    "bluf", "bottom-line", "bottomline", "resources", "resources-used",
    "faq", "faqs", "in-this-article", "toc", "jump-nav", "closing",
    "rl-quick-card", "rl-atf-faq", "cnprelat",
})

_LINK_TAG_RE = re.compile(r"(<a\b[^>]*>.*?</a>)", flags=re.DOTALL | re.IGNORECASE)


def _is_body_section(tag_text: str) -> bool:
    """Check if text from an H2 section is a body section (not FAQ/BLUF/etc)."""
    lower = tag_text.lower()
    for marker in _SKIP_MARKERS:
        if marker in lower:
            return False
    if "bottom line" in lower:
        return False
    if "frequently asked" in lower:
        return False
    if "related coverage" in lower:
        return False
    return True


def _inject_link_in_html(html_str: str, anchor_text: str, url: str) -> tuple:
    """Replace first occurrence of anchor_text with <a href> outside existing links."""
    segments = _LINK_TAG_RE.split(html_str)
    pattern = re.compile(r"\b" + re.escape(anchor_text) + r"\b", re.IGNORECASE)

    replaced = False
    rebuilt = []
    for seg in segments:
        if replaced or _LINK_TAG_RE.match(seg):
            rebuilt.append(seg)
            continue
        match = pattern.search(seg)
        if match:
            matched_text = seg[match.start():match.end()]
            link = f'<a href="{url}">{matched_text}</a>'
            seg = seg[:match.start()] + link + seg[match.end():]
            replaced = True
        rebuilt.append(seg)

    return "".join(rebuilt), replaced


# ---------------------------------------------------------------------------
# SSH helpers
# ---------------------------------------------------------------------------

def _ssh_cmd(config: dict) -> list:
    key = os.path.expandvars(os.path.expanduser(config.get("SSH_KEY_PATH", "")))
    return ["ssh", "-i", key, "-o", "IdentitiesOnly=yes",
            f"{config['SSH_USER']}@{config['SSH_HOST']}"]


def _fetch_post_content(config: dict, post_id: int) -> str:
    """Fetch post_content from DB via SSH (pipe SQL via stdin)."""
    sql = f"SELECT post_content FROM wp_posts WHERE ID={post_id};"
    cmd = _ssh_cmd(config) + [
        f"wp db query --skip-column-names --path={config['WP_PATH']}"
    ]
    result = subprocess.run(cmd, input=sql, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        return ""
    return result.stdout


def _push_post_content(config: dict, post_id: int, content: str, dry_run: bool) -> bool:
    """Push content via SQL UNHEX (piped via stdin)."""
    hex_content = content.encode("utf-8").hex()
    sql = f"UPDATE wp_posts SET post_content = UNHEX('{hex_content}') WHERE ID={post_id};"

    if dry_run:
        print(f"  [DRY RUN] Would update post {post_id} ({len(content)} bytes)")
        return True

    cmd = _ssh_cmd(config) + [
        f"wp db query --path={config['WP_PATH']}"
    ]
    result = subprocess.run(cmd, input=sql, capture_output=True, text=True, timeout=120)
    return result.returncode == 0


def _flush_cache(config: dict):
    cmd = _ssh_cmd(config) + [f"wp cache flush --path={config['WP_PATH']}"]
    subprocess.run(cmd, capture_output=True, timeout=30)


# ---------------------------------------------------------------------------
# Main injection logic
# ---------------------------------------------------------------------------

_GENERIC_PHRASES = frozenset({
    # Truly generic fragments that are never good anchor text
    "in texas", "for texas", "insurance in", "insurance for",
    "of insurance", "of texas", "and insurance", "insurance and",
    "by trade", "certificate of", "the texas", "your texas",
    "your insurance", "their insurance", "an insurance",
    "this insurance", "that insurance", "the insurance",
    "a insurance", "texas home", "texas auto",
    # Insurance-generic 2-word phrases too ambiguous for specific destinations
    "insurance costs", "insurance rates", "insurance coverage",
    "insurance policy", "insurance claims", "coverage options",
    "policy coverage", "damage coverage", "personal coverage",
    # Geo-generic phrases that appear in every local-business article
    "in san antonio", "san antonio tx", "pizza in san antonio",
    "in san antonio tx", "for san antonio", "near san antonio",
    "of san antonio", "san antonio pizza",
})

# Stopwords — phrases dominated by these are not descriptive enough for anchors
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "it", "to", "in", "on", "at", "of", "for",
    "and", "or", "but", "not", "you", "we", "do", "does", "can", "will",
    "with", "from", "this", "that", "when", "how", "what", "your", "my",
    "are", "was", "were", "be", "been", "has", "have", "had", "if", "by",
    "no", "so", "up", "out", "its", "our", "they", "them", "their",
})

# Maximum links per article — prevents over-linking
MAX_LINKS_PER_POST = 8

# Maximum inbound links per destination across a single batch run.
# Prevents any one page from getting an unnatural spike of new inbound links.
MAX_INBOUND_PER_DEST = 8

# CTA URLs that are PERMITTED to repeat (hero + mid-article CTAs by design).
# The dedup logic only applies to editorial/contextual body links.
CTA_ALLOWLIST = frozenset({
    "/compare-loan-offers",
})


def _normalize_url(url: str, site_domain: str = "") -> str:
    """Normalize a URL for dedup comparison.

    Strips trailing slash, query string, fragment, lowercases host,
    resolves absolute site URLs to relative paths.
    """
    if not url:
        return ""
    # Strip absolute domain variants to relative path
    domains = ["valoannetwork.com", "valoannetwostg.wpenginepowered.com"]
    if site_domain and site_domain not in domains:
        domains.append(site_domain)
    for domain in domains:
        if domain in url:
            idx = url.find(domain)
            slash = url.find("/", idx + len(domain))
            url = url[slash:] if slash >= 0 else "/"
            break
    # Strip query string and fragment
    url = url.split("?")[0].split("#")[0]
    # Strip trailing slash (but keep "/" for root)
    if url != "/" and url.endswith("/"):
        url = url.rstrip("/")
    return url.lower()


def _extract_existing_internal_urls(content: str, site_domain: str = "") -> set:
    """Scan content for all internal <a href> destinations already present.

    Returns a normalized set of destination URLs, EXCLUDING CTA allowlist URLs.
    """
    href_pattern = re.compile(r'<a\b[^>]*\bhref="([^"]*)"', re.IGNORECASE)
    existing = set()
    for match in href_pattern.finditer(content):
        href = match.group(1)
        # Only internal links
        if not href:
            continue
        is_internal = (
            (href.startswith("/") and not href.startswith("//"))
            or "valoannetwork.com" in href
            or "valoannetwostg" in href
            or (site_domain and site_domain in href)
        )
        if not is_internal:
            continue
        normalized = _normalize_url(href, site_domain=site_domain)
        # Skip CTA allowlist — those are permitted to repeat
        if normalized in CTA_ALLOWLIST:
            continue
        if normalized:
            existing.add(normalized)
    return existing


_JUNK_ANCHOR_PATTERNS = [
    # B - Filler phrases
    "what to know about", "what you should know", "what you need to know",
    "things to consider", "things to know", "here's what",
    "everything you need",
    # D - CTA language
    "explore our", "discover the", "see how", "check out",
    "find out", "learn more", "read more", "click here",
    # C - Vague comparatives
    "choosing the right", "picking the right", "finding the best",
    "selecting the best", "how to choose", "how to pick", "how to select",
    # E - Quantity filler
    "top tips", "best practices", "top reasons",
    # G - Vague nouns
    "this guide", "your guide to", "our guide", "the guide to",
    "this article", "this post", "additional information",
    # A - Generic openers
    "before you start", "before you begin", "getting started",
    "where to begin", "where to start",
]

_JUNK_EXACT = frozenset({"what is", "how it works", "when to use"})
_JUNK_QUANTITY_RE = re.compile(r'^\d+\s+(tips|things|ways|reasons)\b', re.IGNORECASE)


def _is_junk_anchor(text: str) -> bool:
    """Reject wrapper-phrase junk anchors (defense in depth)."""
    lower = text.lower().strip()
    if lower in _JUNK_EXACT:
        return True
    if _JUNK_QUANTITY_RE.match(lower):
        return True
    for pattern in _JUNK_ANCHOR_PATTERNS:
        if pattern in lower:
            return True
    return False


def _is_quality_anchor(phrase: str) -> bool:
    """Check if a phrase is descriptive enough to be anchor text.

    Rejects phrases where most words are stopwords, which produce
    garbage anchors like 'to the VA', 'and does not', 'it does not'.
    Also rejects junk wrapper-phrase anchors.
    """
    if _is_junk_anchor(phrase):
        return False
    words = phrase.lower().split()
    if len(words) < 3:
        return len(words) >= 2  # 2-word phrases checked separately
    # For 3+ word phrases, require at least 2 content words (non-stopwords)
    content_words = [w for w in words if w not in _STOPWORDS]
    return len(content_words) >= 2


def _build_phrase_index(
    pool: AnchorPool,
    exclude_post_id: int,
    exclude_dest_ids: set | None = None,
) -> list:
    """Build a phrase index from all destinations for retroactive matching.

    Args:
        exclude_dest_ids: Optional set of destination post IDs to skip
            entirely (e.g. Spanish destinations when processing English posts).

    Returns list of (phrase, url, score_boost) sorted by phrase length desc
    (longer phrases match first = more specific).
    """
    phrases = []
    for dest in pool._destinations:
        if dest.get("id") == exclude_post_id:
            continue
        if exclude_dest_ids and dest.get("id") in exclude_dest_ids:
            continue
        url = dest.get("url", "")
        kw = dest.get("primary_keyword", "")
        anchors = dest.get("anchors", [])

        # Extract 2-4 word phrases from primary keyword
        kw_words = kw.split()
        if 2 <= len(kw_words) <= 4:
            if _is_quality_anchor(kw) and kw.lower() not in _GENERIC_PHRASES:
                phrases.append((kw, url, 1.0))
        # For longer keywords, extract sliding windows of 3-4 words
        if len(kw_words) > 4:
            for size in [4, 3]:
                for i in range(len(kw_words) - size + 1):
                    chunk = " ".join(kw_words[i:i+size])
                    if chunk.lower() in _GENERIC_PHRASES:
                        continue
                    if not _is_quality_anchor(chunk):
                        continue
                    phrases.append((chunk, url, 0.8))

        # Include anchors from the AI-generated pool (2-6 words)
        for anchor in anchors:
            words = anchor.split()
            if len(words) >= 2 and len(words) <= 6:
                if anchor.lower() not in _GENERIC_PHRASES and _is_quality_anchor(anchor):
                    phrases.append((anchor, url, 0.9))

    # Deduplicate by (phrase_lower, url), keep highest score
    seen = {}
    for phrase, url, score in phrases:
        key = (phrase.lower(), url)
        if key not in seen or score > seen[key][2]:
            seen[key] = (phrase, url, score)

    # Sort by phrase length desc (match longest first)
    result = sorted(seen.values(), key=lambda x: -len(x[0]))
    return result


def inject_links_into_content(
    content: str,
    pool: AnchorPool,
    post_id: int,
    internal_keywords: set,
    site_domain: str = "",
    dest_counter: dict | None = None,
    exclude_dest_ids: set | None = None,
) -> tuple:
    """Inject contextual internal links into post content.

    Uses phrase scanning: finds 2-4 word keyword phrases from other posts
    that already appear naturally in paragraph text.

    Args:
        dest_counter: Optional cross-post destination frequency dict.
            Keys are normalized URLs, values are injection counts across
            the batch. When provided, destinations that have already
            reached MAX_INBOUND_PER_DEST are skipped.
        exclude_dest_ids: Optional set of destination post IDs to skip
            (language filter: exclude Spanish dests for English posts, etc).

    Returns (modified_content, links_injected_count, link_details).
    """
    # Build phrase index (all linkable phrases from other posts)
    phrase_index = _build_phrase_index(pool, exclude_post_id=post_id, exclude_dest_ids=exclude_dest_ids)

    # Find all H2s and their positions
    h2_pattern = re.compile(r'<h[23][^>]*>(.*?)</h[23]>', re.IGNORECASE | re.DOTALL)
    h2_matches = list(h2_pattern.finditer(content))

    if not h2_matches:
        return content, 0, []

    # Pre-populate used_urls from links already in the content (dedup gate).
    # This prevents re-processing from creating duplicate destinations.
    # CTA URLs (e.g. /compare-loan-offers/) are excluded — they repeat by design.
    used_urls = _extract_existing_internal_urls(content, site_domain=site_domain)
    used_anchors = set()
    total_injected = 0
    link_details = []
    modified = content

    # Track offset changes from injections
    offset = 0

    for h2_match in h2_matches:
        if total_injected >= MAX_LINKS_PER_POST:
            break
        h2_text = re.sub(r'<[^>]+>', '', h2_match.group(1)).strip()

        if not _is_body_section(h2_text):
            continue

        # Find paragraphs after this H2 (up to next H2 or end)
        h2_end = h2_match.end() + offset
        next_h2_pos = len(modified)
        for other in h2_matches:
            other_start = other.start() + offset
            if other_start > h2_end:
                next_h2_pos = other_start
                break

        section_html = modified[h2_end:next_h2_pos]

        # Find paragraphs and list items in this section
        p_pattern = re.compile(r'<p[^>]*>(.*?)</p>', re.IGNORECASE | re.DOTALL)
        li_pattern = re.compile(r'<li[^>]*>(.*?)</li>', re.IGNORECASE | re.DOTALL)
        p_matches = list(p_pattern.finditer(section_html))
        li_matches = list(li_pattern.finditer(section_html))
        all_matches = p_matches + li_matches

        if not all_matches:
            continue

        # Try to inject 0-2 links in this section
        section_injected = 0
        max_per_section = 3

        for p_match in all_matches[:6]:  # check first 6 elements (p + li)
            if section_injected >= max_per_section:
                break
            if total_injected >= MAX_LINKS_PER_POST:
                break

            p_text = re.sub(r'<[^>]+>', '', p_match.group(1))
            p_html = p_match.group(0)

            # Skip very short paragraphs
            if len(p_text) < 60:
                continue

            # Scan for phrase matches
            for phrase, url, score in phrase_index:
                normalized_url = _normalize_url(url, site_domain=site_domain)
                if normalized_url in used_urls:
                    continue
                if phrase.lower() in used_anchors:
                    continue
                # Cross-post destination frequency cap
                if dest_counter is not None:
                    if dest_counter.get(normalized_url, 0) >= MAX_INBOUND_PER_DEST:
                        continue

                # Check if phrase appears in paragraph text (word boundary)
                pattern = re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
                if not pattern.search(p_text):
                    continue

                # Don't link inside existing <a> tags
                new_p_html, was_injected = _inject_link_in_html(
                    p_html, phrase, url
                )

                if was_injected:
                    abs_start = h2_end + p_match.start()
                    abs_end = h2_end + p_match.end()
                    modified = modified[:abs_start] + new_p_html + modified[abs_end:]

                    len_diff = len(new_p_html) - len(p_html)
                    offset += len_diff

                    used_urls.add(normalized_url)
                    used_anchors.add(phrase.lower())
                    section_injected += 1
                    total_injected += 1

                    # Update cross-post destination counter
                    if dest_counter is not None:
                        dest_counter[normalized_url] = dest_counter.get(normalized_url, 0) + 1

                    link_details.append({
                        "section": h2_text[:50],
                        "anchor": phrase,
                        "url": url,
                        "score": score,
                    })
                    p_html = new_p_html
                    break  # one link per paragraph

    return modified, total_injected, link_details


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Batch-inject internal links across all posts")
    parser.add_argument("--site", required=True, help="Site slug")
    parser.add_argument("--dry-run", action="store_true", help="Don't write changes")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of posts to process")
    parser.add_argument("--start", type=int, default=0, help="Start from this index")
    args = parser.parse_args()

    config = load_site_config(args.site)
    pool = AnchorPool(args.site)
    site_domain = config.get("SITE_DOMAIN", "")

    if not pool._destinations:
        print(f"ERROR: No anchor pool for site '{args.site}'")
        print(f"Expected: sites/{args.site}-anchor-pools.json")
        sys.exit(1)

    internal_keywords = pool.get_internal_keywords_set()
    print(f"Anchor pool: {len(pool._destinations)} destinations, {len(internal_keywords)} keywords")
    print(f"Site domain: {site_domain}")

    # Get list of published posts (pipe SQL via stdin)
    sql = "SELECT ID, post_name FROM wp_posts WHERE post_type='post' AND post_status='publish' ORDER BY ID;"
    cmd = _ssh_cmd(config) + [f"wp db query --path={config['WP_PATH']}"]
    result = subprocess.run(cmd, input=sql, capture_output=True, text=True, timeout=30)

    posts = []
    for line in result.stdout.strip().split("\n")[1:]:  # skip header
        parts = line.split("\t")
        if len(parts) == 2:
            posts.append({"id": int(parts[0]), "slug": parts[1]})

    if args.limit > 0:
        posts = posts[args.start:args.start + args.limit]

    print(f"Processing {len(posts)} posts\n")

    updated = 0
    skipped = 0
    errors = 0
    total_links = 0
    all_details = []

    for i, post in enumerate(posts):
        pid = post["id"]
        slug = post["slug"]
        progress = f"[{i+1}/{len(posts)}]"

        # Fetch content
        content = _fetch_post_content(config, pid)
        if not content or len(content) < 200:
            print(f"{progress} SKIP (no content): {pid} {slug}")
            skipped += 1
            continue

        # Skip if already has injected links (re-run safety)
        existing_internal = len(re.findall(
            r'href="/' + r'[^"]+/"', content
        ))
        # Allow re-processing — some may have had manual links

        # Inject
        modified, link_count, details = inject_links_into_content(
            content, pool, pid, internal_keywords, site_domain=site_domain
        )

        if link_count == 0:
            print(f"{progress} {pid} {slug}: 0 links (no matches)")
            skipped += 1
            continue

        # Push
        success = _push_post_content(config, pid, modified, args.dry_run)
        if success:
            print(f"{progress} {pid} {slug}: {link_count} links injected")
            for d in details:
                print(f"         '{d['anchor']}' → {d['url']} (score={d['score']})")
            updated += 1
            total_links += link_count
            all_details.extend(details)
        else:
            print(f"{progress} ERROR writing {pid} {slug}")
            errors += 1
            if errors >= 3:
                print("HARD STOP: 3 consecutive errors")
                break

        # Pacing
        time.sleep(1.5)

        # Cache flush every 25
        if updated > 0 and updated % 25 == 0:
            _flush_cache(config)
            print(f"--- Cache flushed at {updated} ---")
            time.sleep(2)

    # Final flush
    if not args.dry_run and updated > 0:
        _flush_cache(config)

    print(f"\n=== COMPLETE ===")
    print(f"Updated: {updated}")
    print(f"Skipped: {skipped}")
    print(f"Errors:  {errors}")
    print(f"Total links: {total_links}")
    if updated > 0:
        print(f"Avg links/post: {total_links/updated:.1f}")

    # Distribution
    if all_details:
        link_counts = {}
        for d in all_details:
            url = d["url"]
            link_counts[url] = link_counts.get(url, 0) + 1
        top_targets = sorted(link_counts.items(), key=lambda x: -x[1])[:10]
        print(f"\nTop 10 link targets:")
        for url, cnt in top_targets:
            print(f"  {cnt}x → {url}")

    # Save report
    report_path = REPO_ROOT / "sites" / f"{args.site}-linking-report.json"
    report = {
        "site": args.site,
        "posts_processed": len(posts),
        "posts_updated": updated,
        "posts_skipped": skipped,
        "errors": errors,
        "total_links_injected": total_links,
        "avg_links_per_post": round(total_links / max(updated, 1), 1),
        "details": all_details,
    }
    report_path.write_text(json.dumps(report, indent=2))
    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
