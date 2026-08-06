#!/usr/bin/env python3
"""Batch neighborhood guide rebuild — generates + verifies all guides sequentially.

Runs assemble-article.py for each neighborhood, then fact-checks + verifies
each output. Produces a consolidated review queue.

Usage:
    python3 batch-neighborhood-rebuild.py \\
        --site lrg \\
        --queue-json queue.json \\
        --output-dir ~/lrg-rewrite/batch-rebuild/ \\
        [--dry-run]              # list what would run, don't generate \\
        [--resume]               # skip already-completed guides \\
        [--pause SECONDS]        # pause between guides (default 3)
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
MODULE_DIR = TOOLS_DIR.parent
REPO_ROOT = MODULE_DIR.parent.parent
sys.path.insert(0, str(MODULE_DIR))

from lib.tool_utils import eprint

# ── PUBLISH GUARD ──
# Protected post IDs: flagship pages that must never be overwritten.
PROTECTED_POST_IDS = {2794, 2790, 2797, 2095}


def _assert_no_publish(queue: list[dict]) -> None:
    """Hard abort if any queue entry would publish or touch protected posts."""
    for entry in queue:
        pid = entry.get("post_id", 0)
        if pid in PROTECTED_POST_IDS:
            eprint(f"HARD ABORT: post_id {pid} is a protected flagship page. "
                   f"Remove it from the queue.")
            sys.exit(1)
        status = entry.get("post_status", "")
        if status == "publish":
            eprint(f"HARD ABORT: queue entry for post {pid} has "
                   f"post_status=publish. This batch produces FILES ONLY.")
            sys.exit(1)
    eprint("  [GUARD] Publish guard: PASS (0 publish entries, 0 protected IDs)")


def _assert_no_wp_writes(cmd_args: list[str]) -> None:
    """Pre-exec check: abort if subprocess args contain wp post create/update."""
    joined = " ".join(str(a) for a in cmd_args)
    if "wp post create" in joined or "wp post update" in joined:
        eprint(f"HARD ABORT: wp post create/update detected in subprocess args.")
        sys.exit(1)


def _filter_serp_for_relevance(entry: dict) -> int:
    """Pre-generation SERP cleanup: reject off-topic results.

    Ported from assemble-article.py:798-843. Rewrites the SERP JSON
    in-place so the generator only sees on-target results.
    Returns the number of rejected results.
    """
    nb = entry.get("neighborhood", "").lower()
    city = entry.get("city", "").lower()
    # Build location tokens (4+ chars, skip stop words)
    raw = re.sub(r'[^a-z0-9\s]', '', f"{nb} {city}").split()
    stop = {'neighborhood', 'neighborhoods', 'best', 'guide', 'texas',
            'live', 'living', 'homebuyers', 'near', 'the'}
    tokens = {t for t in raw if len(t) >= 4 and t not in stop}
    if not tokens:
        return 0

    # Find the SERP file
    nb_slug = re.sub(r'[^a-z0-9]+', '-', nb).strip('-')
    serp_dir = Path.home() / "lrg-rewrite" / "serp"
    candidates = list(serp_dir.glob(f"*{nb_slug}*-neighborhood-serp.json"))
    if not candidates:
        return 0

    serp_path = candidates[0]
    try:
        raw_data = json.loads(serp_path.read_text())
    except (json.JSONDecodeError, OSError):
        return 0

    top = raw_data.get("top_results", [])
    if not top:
        return 0

    filtered, rejected_titles = [], []
    for r in top:
        r_text = (r.get("title", "") + " " + r.get("snippet", "")).lower()
        if any(t in r_text for t in tokens):
            filtered.append(r)
        else:
            rejected_titles.append(r.get("title", "")[:60])

    if rejected_titles:
        raw_data["top_results"] = filtered
        raw_data["_source_filter"] = {
            "original_count": len(top),
            "filtered_count": len(filtered),
            "rejected": rejected_titles,
        }
        serp_path.write_text(json.dumps(raw_data, indent=2))
        eprint(f"  [SERP-FILTER] {len(rejected_titles)} off-topic result(s) rejected:")
        for t in rejected_titles:
            eprint(f"    REJECTED: {t}")
    else:
        eprint(f"  [SERP-FILTER] All {len(top)} results on-target")

    return len(rejected_titles)


def _check_confabulation_risk(html: str, entry: dict) -> list[dict]:
    """Post-gen advisory: flag H2 sections with heritage/history content
    that lack SERP support. Ported from assemble-article.py:1040-1086."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    _CONFAB_MARKERS = [
        "heritage", "history", "historical", "tradition", "founding",
        "settlers", "cultural roots", "origin story", "established in",
    ]

    soup = BeautifulSoup(html, "html.parser")
    h2s = soup.find_all("h2")
    flags = []

    # Load SERP titles for support check
    nb_slug = re.sub(r'[^a-z0-9]+', '-', entry.get("neighborhood", "").lower()).strip('-')
    serp_dir = Path.home() / "lrg-rewrite" / "serp"
    serp_files = list(serp_dir.glob(f"*{nb_slug}*-neighborhood-serp.json"))
    serp_titles = []
    if serp_files:
        try:
            data = json.loads(serp_files[0].read_text())
            serp_titles = [r.get("title", "").lower() for r in data.get("top_results", [])[:10]]
        except Exception:
            pass

    for h2 in h2s:
        h2_text = h2.get_text(strip=True)
        h2_lower = h2_text.lower()
        is_risk = any(m in h2_lower for m in _CONFAB_MARKERS)
        if not is_risk:
            continue
        # Check SERP title support
        title_support = sum(
            1 for t in serp_titles
            if any(m in t for m in _CONFAB_MARKERS) and nb_slug.replace('-', ' ') in t
        )
        if title_support < 1:
            flags.append({
                "type": "confabulation_risk",
                "h2": h2_text,
                "detail": f"Heritage/history H2 '{h2_text}' has 0 SERP title support. "
                          f"Content may be fabricated from thin data.",
                "post_id": entry.get("post_id", 0),
            })

    return flags


# ── FAIR HOUSING SCANNER ──
# Validated against 30 live July 29-31 guides: 35 hits, 23/30 guides.
FH_TIER1_PHRASES = [
    "best for families", "ideal for families", "perfect for families",
    "great for families", "safe for families",
    "family-friendly", "family friendly", "young families",
    "young professionals", "young professional",
    "empty nesters", "empty-nesters", "older-money", "older money",
    "best for young", "best for seniors", "ideal for retirees",
    "best for military families", "ideal for military", "perfect for military",
    "safest neighborhood", "safest area", "safest community",
    "safe neighborhood", "safe community", "safe area",
    "affluent community", "affluent neighborhood",
    "upscale community", "exclusive community", "exclusive neighborhood",
]
FH_FIT_SECTION_PATTERNS = [
    r"families\s+who\s+(?:want|prioritize|prefer|seek|need|require|value)",
    r"families\s+wanting", r"families\s+seeking",
    r"military\s+families",
    r"retirees\s+who", r"retirees$",
    r"seniors\s+who", r"couples\s+who", r"singles\s+who",
    r"\bfamilies$",
]
FH_TIER2_PATTERNS = [
    (r"\bsafest\b", "safest (unsourced superlative)"),
    (r"\bretirees\b", "retirees (demographic)"),
    (r"(?<!young\s)\bprofessionals\b", "professionals (demographic)"),
]


def _scan_fair_housing(html: str, post_id: int) -> list[dict]:
    """Scan for Fair Housing compliance issues. Returns advisory flags."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    hits = []
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    text_lower = text.lower()

    # Tier 1: exact phrase matches
    for phrase in FH_TIER1_PHRASES:
        idx = text_lower.find(phrase.lower())
        if idx >= 0:
            start = max(0, idx - 60)
            end = min(len(text), idx + len(phrase) + 60)
            hits.append({
                "tier": 1, "phrase": phrase,
                "sentence": text[start:end].strip(),
                "post_id": post_id,
            })

    # Tier 1b: fit-section <dt> demographic labels
    for panel in soup.find_all("div", class_=lambda c: c and "nh-panel" in c):
        for dt in panel.find_all("dt"):
            dt_lower = dt.get_text(strip=True).lower()
            for pat in FH_FIT_SECTION_PATTERNS:
                if re.search(pat, dt_lower):
                    hits.append({
                        "tier": 1,
                        "phrase": f"fit-section: '{dt.get_text(strip=True)[:80]}'",
                        "sentence": dt.get_text(strip=True),
                        "post_id": post_id,
                    })
                    break

    # Tier 2: context-dependent
    for pattern, label in FH_TIER2_PATTERNS:
        m = re.search(pattern, text_lower)
        if m and not any(h["sentence"][:30] in text[max(0,m.start()-60):m.end()+60] for h in hits):
            hits.append({
                "tier": 2, "phrase": f"{label}: '{m.group()}'",
                "sentence": text[max(0,m.start()-60):min(len(text),m.end()+60)].strip(),
                "post_id": post_id,
            })

    return hits


def load_queue(queue_path: str) -> list[dict]:
    """Load the rebuild queue JSON.

    Format: [{"post_id": 2736, "neighborhood": "Stone Oak", "city": "San Antonio",
              "keyword": "Stone Oak San Antonio neighborhood", "priority": 1}, ...]
    """
    with open(queue_path) as f:
        return json.load(f)


def run_one_guide(entry: dict, site: str, output_dir: Path, resume: bool = False) -> dict:
    """Generate + verify one neighborhood guide. Returns status dict."""
    post_id = entry["post_id"]
    keyword = entry["keyword"]
    guide_dir = output_dir / str(post_id)
    guide_dir.mkdir(parents=True, exist_ok=True)

    # Neighborhood generator writes {post_id}-nh-guide.html
    article_path = guide_dir / f"{post_id}-nh-guide.html"
    status = {"post_id": post_id, "keyword": keyword, "status": "pending"}

    # Resume check
    if resume and article_path.exists():
        eprint(f"  [SKIP] {keyword} — already generated")
        status["status"] = "skipped_existing"
        return status

    # Step 0: Source-relevance filter — clean SERP before generation
    _filter_serp_for_relevance(entry)

    # Step 1: Generate via generate-neighborhood-guide.py (nh-* format)
    nb = entry.get("neighborhood", keyword)
    city = entry.get("city", "San Antonio")
    metro = entry.get("metro", city)
    eprint(f"  [GEN] {nb} in {city} (post {post_id})")
    gen_start = time.time()

    gen_args = [
        sys.executable, str(TOOLS_DIR / "generate-neighborhood-guide.py"),
        "--site", site,
        "--neighborhood", nb,
        "--city", city,
        "--metro", metro,
        "--post-id", str(post_id),
        "--output-dir", str(guide_dir),
        "--skip-deploy",
    ]
    # Pass verified data JSON if available in the queue entry
    data_json = entry.get("data_json", "")
    if data_json and Path(data_json).exists():
        gen_args += ["--data-json", data_json]
    # Force-new for placeholder IDs (net-new guides)
    if post_id == 0:
        gen_args.append("--force-new")

    _assert_no_wp_writes(gen_args)

    try:
        result = subprocess.run(
            gen_args,
            capture_output=True, text=True, timeout=1800,  # 30 min max
        )
        gen_elapsed = time.time() - gen_start

        if result.returncode != 0:
            eprint(f"  [FAIL] Generation failed ({gen_elapsed:.0f}s)")
            eprint(f"  {result.stderr[-300:]}")
            status["status"] = "gen_failed"
            status["error"] = result.stderr[-200:]
            return status

        eprint(f"  [GEN OK] {gen_elapsed:.0f}s")

    except subprocess.TimeoutExpired:
        eprint(f"  [TIMEOUT] Generation timed out after 1800s")
        status["status"] = "gen_timeout"
        return status

    # Step 2: Run verification
    if article_path.exists():
        eprint(f"  [VERIFY] Running claim verification...")
        try:
            from lib.fact_checker import extract_claims
            from lib.claim_verifier import (
                run_verification, format_verification_report,
                export_verification_json,
            )

            html = article_path.read_text()

            claims = extract_claims(html, nb, city)
            report = run_verification(claims, nb, city, post_id=post_id)

            # Write human-readable report
            report_path = guide_dir / f"{post_id}-verification-report.txt"
            report_path.write_text(format_verification_report(report))

            # Write JSON report
            json_path = guide_dir / f"{post_id}-verification-report.json"
            json_path.write_text(json.dumps(export_verification_json(report), indent=2))

            status["status"] = "complete"
            status["verified"] = report.verified_count
            status["wrong"] = report.wrong_count
            status["couldnt_verify"] = report.couldnt_verify_count
            status["human_flag"] = report.human_flag_count

            # Check SERP sparsity for thin-data flagging
            from lib.content_quality_gate import check_thin_data_risk
            serp_count = 0
            serp_json = guide_dir / f"{post_id}-subtopic-gaps.json"
            # Count from the SERP file if available
            serp_glob = list(Path.home().glob(f"lrg-rewrite/serp/*{entry.get('neighborhood', '').lower().replace(' ', '-')}*-serp.json"))
            if serp_glob:
                try:
                    serp_data = json.loads(serp_glob[0].read_text())
                    serp_count = len(serp_data.get("top_results", []))
                except Exception:
                    pass
            risk = check_thin_data_risk(serp_count, nb)
            status["serp_results"] = serp_count
            status["thin_data_risk"] = risk["risk_level"]
            if risk["risk_level"] in ("HIGH", "MODERATE"):
                status["thin_data_flag"] = risk["flag"]
                eprint(f"  [THIN-DATA] {risk['flag']}")
            status["elapsed"] = gen_elapsed

            # Fair Housing scan (advisory)
            fh_hits = _scan_fair_housing(html, post_id)
            if fh_hits:
                status["fh_flags"] = fh_hits
                eprint(f"  [FH] {len(fh_hits)} compliance flag(s)")
            else:
                eprint(f"  [FH] No automated hits")

            # Confabulation guard (advisory)
            confab_flags = _check_confabulation_risk(html, entry)
            if confab_flags:
                status["confab_flags"] = confab_flags
                eprint(f"  [CONFAB] {len(confab_flags)} heritage/history flag(s)")
                for cf in confab_flags:
                    eprint(f"    {cf['detail'][:80]}")

            eprint(f"  [VERIFY OK] V={report.verified_count} W={report.wrong_count} "
                   f"C={report.couldnt_verify_count} H={report.human_flag_count}")

        except Exception as e:
            eprint(f"  [VERIFY FAIL] {e}")
            status["status"] = "verify_failed"
            status["error"] = str(e)
    else:
        status["status"] = "no_output"

    return status


def build_consolidated_queue(all_statuses: list, output_dir: Path) -> dict:
    """Build the consolidated review queue from all guide statuses."""
    queue = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_guides": len(all_statuses),
        "complete": sum(1 for s in all_statuses if s["status"] == "complete"),
        "failed": sum(1 for s in all_statuses if "fail" in s["status"]),
        "corrections": [],
        "softenings": [],
        "unverified": [],
        "sparse_serp": [],
    }

    for status in all_statuses:
        if status["status"] != "complete":
            continue

        post_id = status["post_id"]
        json_path = output_dir / str(post_id) / f"{post_id}-verification-report.json"
        if not json_path.exists():
            continue

        report = json.loads(json_path.read_text())

        for corr in report.get("corrections", []):
            corr["post_id"] = post_id
            corr["keyword"] = status["keyword"]
            queue["corrections"].append(corr)

        for soft in report.get("softenings", []):
            soft["post_id"] = post_id
            soft["keyword"] = status["keyword"]
            queue["softenings"].append(soft)

        for unv in report.get("unverified", []):
            unv["post_id"] = post_id
            unv["keyword"] = status["keyword"]
            queue["unverified"].append(unv)

        # Track thin-data guides for full-read flagging
        if status.get("thin_data_risk") in ("HIGH", "MODERATE"):
            queue["sparse_serp"].append({
                "post_id": post_id,
                "keyword": status["keyword"],
                "serp_results": status.get("serp_results", 0),
                "risk": status["thin_data_risk"],
                "flag": status.get("thin_data_flag", ""),
            })

    queue["summary"] = {
        "corrections_individual_review": len(queue["corrections"]),
        "softenings_batch_approvable": len(queue["softenings"]),
        "unverified_human_check": len(queue["unverified"]),
        "sparse_serp_read_manually": len(queue["sparse_serp"]),
    }

    return queue


def format_consolidated_summary(queue: dict) -> str:
    """Format the consolidated review queue as human-readable summary."""
    s = queue["summary"]
    lines = [
        f"VERIFICATION BATCH SUMMARY — {queue['total_guides']} neighborhood guides",
        f"{'═' * 70}",
        f"Generated:   {queue['complete']} complete, {queue['failed']} failed",
        f"",
        f"CORRECTIONS — INDIVIDUAL REVIEW REQUIRED: {s['corrections_individual_review']}",
        f"SOFTENINGS — BATCH-APPROVABLE:            {s['softenings_batch_approvable']}",
        f"COULDN'T VERIFY — HUMAN CHECK:            {s['unverified_human_check']}",
        f"SPARSE SERP — READ MANUALLY:              {s['sparse_serp_read_manually']}",
        f"{'═' * 70}",
        f"",
    ]

    if queue["corrections"]:
        lines.append("CORRECTIONS (review each individually):")
        lines.append(f"{'─' * 70}")
        for c in queue["corrections"]:
            stakes = "HIGH" if c.get("requires_individual_review") else "STD"
            lines.append(f"  [{stakes}] Post {c['post_id']} ({c['keyword'][:30]})")
            lines.append(f"         Claim: {c['claim'][:60]}")
            lines.append(f"         Fix:   {c['proposed_patch'][:60]}")
            lines.append(f"         Source: {c['source_url'][:60]}")
            lines.append("")

    if queue["softenings"]:
        lines.append(f"\nSOFTENINGS ({len(queue['softenings'])} — batch-approvable):")
        lines.append(f"{'─' * 70}")
        for s in queue["softenings"][:10]:
            lines.append(f"  [SOFTEN] Post {s['post_id']}: {s['claim'][:50]}")
        if len(queue["softenings"]) > 10:
            lines.append(f"  ... and {len(queue['softenings']) - 10} more")

    if queue["unverified"]:
        lines.append(f"\nCOULDN'T VERIFY ({len(queue['unverified'])} — human check):")
        lines.append(f"{'─' * 70}")
        for u in queue["unverified"][:10]:
            lines.append(f"  [CHECK] Post {u['post_id']}: {u['claim'][:50]}")
        if len(queue["unverified"]) > 10:
            lines.append(f"  ... and {len(queue['unverified']) - 10} more")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Batch neighborhood guide rebuild")
    parser.add_argument("--site", required=True)
    parser.add_argument("--queue-json", required=True, help="JSON file with guide queue")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--pause", type=int, default=3, help="Seconds between guides")
    args = parser.parse_args()

    queue = load_queue(args.queue_json)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # PUBLISH GUARD: hard abort before anything else
    _assert_no_publish(queue)

    eprint(f"{'=' * 70}")
    eprint(f"BATCH NEIGHBORHOOD REBUILD")
    eprint(f"  Site: {args.site}")
    eprint(f"  Guides: {len(queue)}")
    eprint(f"  Output: {output_dir}")
    eprint(f"  Resume: {args.resume}")
    eprint(f"{'=' * 70}\n")

    if args.dry_run:
        eprint("DRY RUN — listing queue:")
        for i, entry in enumerate(queue, 1):
            eprint(f"  {i:>3}. Post {entry['post_id']:>5} | {entry['keyword']}")
        eprint(f"\nTotal: {len(queue)} guides. Run without --dry-run to generate.")
        return

    all_statuses = []
    for i, entry in enumerate(queue, 1):
        eprint(f"\n[{i}/{len(queue)}] {entry['keyword']}")
        status = run_one_guide(entry, args.site, output_dir, resume=args.resume)
        all_statuses.append(status)

        # Save progress after each guide
        progress_path = output_dir / "batch-progress.json"
        progress_path.write_text(json.dumps(all_statuses, indent=2))

        if i < len(queue):
            time.sleep(args.pause)

    # Build consolidated review queue
    consolidated = build_consolidated_queue(all_statuses, output_dir)
    queue_path = output_dir / "consolidated-review-queue.json"
    queue_path.write_text(json.dumps(consolidated, indent=2))

    summary = format_consolidated_summary(consolidated)
    summary_path = output_dir / "review-summary.txt"
    summary_path.write_text(summary)

    eprint(f"\n{'=' * 70}")
    eprint(summary)
    eprint(f"\nFiles:")
    eprint(f"  Review queue: {queue_path}")
    eprint(f"  Summary:      {summary_path}")
    eprint(f"  Progress:     {progress_path}")
    eprint(f"{'=' * 70}")


if __name__ == "__main__":
    main()
