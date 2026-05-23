#!/usr/bin/env python3
"""Regenerate anchor pool with distinctive 2-3 word topical phrases.

Reads the existing pool's destination inventory, batches URLs in groups
of 20, calls gpt-5.4-mini to assign primary_anchor + secondary_anchor +
topic_cluster per destination. Enforces primary_anchor uniqueness across
the entire pool.

Usage:
    python3 tools/regenerate-anchor-pool-v2.py --site valn --output sites/valn-anchor-pools-v2.json
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "modules" / "content-production-v2"))

from lib.llm_client import LLMClient
from lib.tool_utils import eprint

BATCH_SIZE = 20

SYSTEM_PROMPT = """You are generating short, distinctive anchor text phrases for an internal-linking system on a VA lending website.

For each destination URL below, produce TWO anchor phrases:
  - primary_anchor: the most distinctive 2-3 word topical phrase that captures what ONLY this destination is about
  - secondary_anchor: a slightly more general 2-3 word alternative

STRICT RULES:
1. EXCLUDE the generic vertical words. Never include in any phrase: "VA Loan", "VA Loans", "VA loan", "VA mortgage", "mortgage", "home loan". The abbreviation "VA" alone is allowed ONLY when paired with a specific program name (e.g., "VA disability", "VA IRRRL", "VA appraisal").
2. Both anchor phrases MUST be 2-3 words. No 1-word phrases. No 4+ word phrases. No filler words like "the", "a", "your".
3. Both anchor phrases MUST be noun phrases that would appear naturally in body prose about the destination's topic.
4. primary_anchor and secondary_anchor MUST be different from each other.
5. NO two destinations in this batch may share the same primary_anchor. If you would assign the same primary to two URLs, regenerate one with a more specific alternative.

Also assign each destination a topic_cluster from this fixed list:
  eligibility, cost, process, refinance, credit, income, property, veteran-specific, comparison, calculation, general

Output STRICTLY as a JSON array. One object per destination, same order as input. No preamble, no commentary, no markdown fences.

Schema per object:
{
  "url": "...",
  "post_id": ...,
  "primary_anchor": "...",
  "secondary_anchor": "...",
  "topic_cluster": "..."
}"""

# Pages to skip (utility, legal, non-content)
SKIP_SLUGS = frozenset({
    "home", "", "privacy-policy", "terms", "legal", "disclaimer",
    "advertising-disclosures", "compare-loan-offers", "contact",
    "va-loan-network-editorial-team", "apply", "confirmation",
    "about-us", "about", "scholarship", "editorial-team",
})


def _slug_from_url(url: str) -> str:
    path = url.rstrip("/").split("/")
    return path[-1] if path else ""


def main():
    parser = argparse.ArgumentParser(description="Regenerate anchor pool with distinctive topical phrases")
    parser.add_argument("--site", required=True, help="Site slug")
    parser.add_argument("--output", required=True, help="Output JSON path")
    parser.add_argument("--limit", type=int, default=0, help="Limit destinations (0=all)")
    args = parser.parse_args()

    # Load existing pool for destination inventory
    pool_path = REPO_ROOT / "sites" / f"{args.site}-anchor-pools.json"
    if not pool_path.exists():
        eprint(f"Pool not found: {pool_path}")
        sys.exit(1)

    with open(pool_path) as f:
        old_pool = json.load(f)

    all_dests = old_pool.get("destinations", [])
    eprint(f"Loaded {len(all_dests)} destinations from existing pool")

    # Filter to content pages
    content_dests = [d for d in all_dests if _slug_from_url(d.get("url", "")) not in SKIP_SLUGS]
    eprint(f"Content destinations (after skip filter): {len(content_dests)}")

    if args.limit > 0:
        content_dests = content_dests[:args.limit]
        eprint(f"Limited to {args.limit} destinations")

    # Initialize LLM client
    client = LLMClient(provider="openai", model="gpt-5.4-mini")

    # Process in batches
    results = []
    total_batches = (len(content_dests) + BATCH_SIZE - 1) // BATCH_SIZE
    total_tokens_in = 0
    total_tokens_out = 0

    for batch_idx in range(total_batches):
        start = batch_idx * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(content_dests))
        batch = content_dests[start:end]

        eprint(f"\n[Batch {batch_idx + 1}/{total_batches}] Processing {len(batch)} destinations...")

        # Build user prompt with destination details
        dest_lines = []
        for d in batch:
            dest_lines.append(
                f"  - URL: {d['url']}\n"
                f"    post_id: {d.get('id', 0)}\n"
                f"    title: {d.get('title', '')}\n"
                f"    primary_keyword (old): {d.get('primary_keyword', '')}"
            )

        user_prompt = (
            f"Generate primary_anchor, secondary_anchor, and topic_cluster for these {len(batch)} destinations:\n\n"
            + "\n\n".join(dest_lines)
        )

        cache_key = f"{args.site}|anchor-pool-v2|batch-{batch_idx}"
        try:
            response = client.call(
                user_prompt,
                system_msg=SYSTEM_PROMPT,
                cache_key=cache_key,
                max_tokens=4096,
            )
            total_tokens_in += response.input_tokens
            total_tokens_out += response.output_tokens

            # Parse JSON response
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            batch_results = json.loads(text)

            if not isinstance(batch_results, list):
                eprint(f"  WARNING: Expected array, got {type(batch_results).__name__}")
                continue

            # Merge with original destination data
            for i, result in enumerate(batch_results):
                if i >= len(batch):
                    break
                orig = batch[i]
                entry = {
                    "id": orig.get("id", 0),
                    "url": orig.get("url", ""),
                    "slug": orig.get("slug", ""),
                    "title": orig.get("title", ""),
                    "primary_keyword": result.get("primary_anchor", ""),
                    "anchors": [
                        result.get("primary_anchor", ""),
                        result.get("secondary_anchor", ""),
                    ],
                    "anchor_count": 2,
                    "topic_cluster": result.get("topic_cluster", "general"),
                    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                }
                # Remove empty anchors
                entry["anchors"] = [a for a in entry["anchors"] if a]
                entry["anchor_count"] = len(entry["anchors"])
                results.append(entry)

            eprint(f"  OK: {len(batch_results)} entries parsed")

        except json.JSONDecodeError as e:
            eprint(f"  ERROR: JSON parse failed: {e}")
            eprint(f"  Raw response: {response.text[:200]}")
            continue
        except Exception as e:
            eprint(f"  ERROR: {e}")
            continue

        # Rate limiting between batches
        if batch_idx < total_batches - 1:
            time.sleep(1)

    eprint(f"\n=== Generation Complete ===")
    eprint(f"Destinations processed: {len(results)}/{len(content_dests)}")
    eprint(f"Tokens: {total_tokens_in} in + {total_tokens_out} out")

    # Dedup audit
    primary_counts: dict[str, list[str]] = {}
    for r in results:
        pk = r["primary_keyword"].lower()
        if pk not in primary_counts:
            primary_counts[pk] = []
        primary_counts[pk].append(r["url"])

    dupes = {k: v for k, v in primary_counts.items() if len(v) > 1}
    if dupes:
        eprint(f"\n=== DEDUP AUDIT: {len(dupes)} primary_anchor collisions ===")
        for pk, urls in sorted(dupes.items()):
            eprint(f"  '{pk}' used by {len(urls)} destinations:")
            for u in urls:
                eprint(f"    - {u}")
    else:
        eprint(f"\nDedup audit: PASS — all primary_anchors are unique")

    # Write output
    output = {
        "site": args.site,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ai_provider": "openai",
        "ai_model": "gpt-5.4-mini",
        "destinations": results,
        "stats": {
            "total_destinations": len(results),
            "prompt_tokens": total_tokens_in,
            "completion_tokens": total_tokens_out,
            "batch_count": total_batches,
        },
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    eprint(f"\nOutput written to: {output_path}")
    eprint(f"Total entries: {len(results)}")


if __name__ == "__main__":
    main()
