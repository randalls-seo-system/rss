"""Audit engine — read-only quality assessment of live posts.

Runs the new quality stack (spec assertions, content quality gate,
artifact scan, fact checker) against live post HTML fetched via SSH.
Zero writes to the live site.

Two tiers:
  Tier 1 (deterministic, all posts): spec assertions, quality gate,
      artifact scan, word count vs SERP target.
  Tier 2 (LLM, selective): fact checker + claim extraction. Runs on
      posts that fail Tier 1 OR rank in striking distance (pos 11-30).
      --full forces Tier 2 on everything.
"""

import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

from bs4 import BeautifulSoup

from .spec_assertions import (
    ALL_HARD_ASSERTIONS, ALL_SOFT_ASSERTIONS, AssertionResult,
)
from .content_quality_gate import run_content_quality_gate
from .verification_gates import gate_artifact_scan
from .fact_checker import extract_claims, FactCheckReport
from .tool_utils import eprint

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


@dataclass
class AuditResult:
    post_id: int
    slug: str
    title: str
    top_query: str = ""
    position: float = 0.0
    impressions: int = 0
    word_count: int = 0
    target_word_count: int = 0

    # Tier 1
    hard_failures: list[str] = field(default_factory=list)
    soft_warnings: list[str] = field(default_factory=list)
    quality_gate_failures: list[str] = field(default_factory=list)
    artifact_hits: list[str] = field(default_factory=list)
    hard_pass_count: int = 0
    hard_total_count: int = 0
    soft_pass_count: int = 0
    soft_total_count: int = 0

    # Tier 2
    tier2_ran: bool = False
    claim_count: int = 0
    unsourced_claims: int = 0
    flagged_claims: int = 0
    volatile_claims: int = 0

    # Classification
    page_type: str = ""  # article, service_page, about, other
    frozen: bool = False  # True = ineligible for refresh (pos 1-10 freeze)

    # Verdict
    verdict: str = ""  # PASS, REFRESH, REVIEW
    verdict_reasons: list[str] = field(default_factory=list)


def classify_page_type(slug: str, title: str) -> str:
    """Classify a page as article | service_page | about | other.

    Uses title + slug heuristics. Conservative: only classifies clear
    non-articles; anything ambiguous defaults to 'article'.
    """
    s = slug.lower()
    t = title.lower()

    # Service pages — CTAs, lead gen, applications
    service_signals = [
        "apply-now", "compare-loan-offers", "contact-us",
        "high-quality-mortgage-leads", "mortgage-leads",
        "realtor-referral-program", "referral-program",
        "service-disclaimer", "advertising-disclosures",
        "privacy-policy", "terms-of-use",
    ]
    if any(sig in s for sig in service_signals):
        return "service_page"
    if any(phrase in t for phrase in [
        "join our", "get high-quality", "apply now", "contact us",
        "referral program", "mortgage leads",
    ]):
        return "service_page"

    # About pages
    about_signals = [
        "about-us", "about-the-", "contributor", "editorial-team",
        "our-team", "meet-the-team",
    ]
    if any(sig in s for sig in about_signals):
        return "about"
    if any(phrase in t for phrase in [
        "about us", "become a contributor", "editorial team",
    ]):
        return "about"

    # Hub/index pages
    hub_signals = ["blog", "mortgage-guides", "loan-guides", "resources"]
    if s in hub_signals or (s in ("blog",) and len(t.split()) <= 3):
        return "other"
    if t.lower().strip() in ("blog", "mortgage guides"):
        return "other"

    return "article"


def _word_count(html: str) -> int:
    """Count words in HTML after stripping tags."""
    text = re.sub(r"<[^>]+>", " ", html)
    return len(text.split())


def _build_assertion_context(config: dict, keyword: str = "") -> dict:
    """Build the context dict expected by spec assertions."""
    public_url = config.get("identity", {}).get("public_url", "")
    domain = public_url.replace("https://", "").replace("http://", "").rstrip("/")
    cta_url = config.get("content", {}).get("cta_url", "")
    byline_mode = config.get("authors", {}).get("byline_mode", "single")

    return {
        "site_config": {
            "SITE_DOMAIN": domain,
            "CTA_URL": cta_url,
            "BYLINE_MODE": byline_mode,
        },
        "serp_data": None,
        "anchor_pool": None,
        "intent": "",
        "atf_faqs_text": [],
        "target_keyword": keyword,
    }


def run_tier1(html: str, config: dict, keyword: str = "") -> AuditResult:
    """Run Tier 1 deterministic checks on post HTML.

    Returns a partially filled AuditResult (Tier 2 fields unfilled).
    """
    result = AuditResult(post_id=0, slug="", title="")
    soup = BeautifulSoup(html, "html.parser")
    context = _build_assertion_context(config, keyword)

    # --- Spec assertions ---
    hard_failures = []
    hard_total = 0
    hard_pass = 0
    for fn in ALL_HARD_ASSERTIONS:
        try:
            ar = fn(soup, context)
        except Exception as e:
            hard_failures.append(f"{fn.__name__}: ERROR {e}")
            hard_total += 1
            continue
        hard_total += 1
        if ar.passed:
            hard_pass += 1
        else:
            hard_failures.append(f"{ar.spec_ref}: {ar.detail}")

    soft_warnings = []
    soft_total = 0
    soft_pass = 0
    for fn in ALL_SOFT_ASSERTIONS:
        try:
            ar = fn(soup, context)
        except Exception as e:
            soft_warnings.append(f"{fn.__name__}: ERROR {e}")
            soft_total += 1
            continue
        soft_total += 1
        if ar.passed:
            soft_pass += 1
        else:
            soft_warnings.append(f"{ar.spec_ref}: {ar.detail}")

    result.hard_failures = hard_failures
    result.soft_warnings = soft_warnings
    result.hard_pass_count = hard_pass
    result.hard_total_count = hard_total
    result.soft_pass_count = soft_pass
    result.soft_total_count = soft_total

    # --- Content quality gate ---
    # Use keyword as neighborhood/city for subject-mention checks
    qg_failures = run_content_quality_gate(html, keyword, "")
    result.quality_gate_failures = qg_failures

    # --- Artifact scan (report only, no auto-fix) ---
    gate_result, _ = gate_artifact_scan(html, auto_fix=False)
    if gate_result.fixes_applied:
        result.artifact_hits = gate_result.fixes_applied

    # --- Word count ---
    result.word_count = _word_count(html)

    return result


def run_tier2(html: str, result: AuditResult) -> AuditResult:
    """Run Tier 2 LLM/claims checks. Mutates and returns the result."""
    result.tier2_ran = True

    # Extract claims (deterministic extraction, no LLM needed)
    claims = extract_claims(html, result.top_query, "")
    result.claim_count = len(claims)
    result.unsourced_claims = sum(
        1 for c in claims if c.verified is None and c.consequence == "high"
    )
    result.flagged_claims = sum(
        1 for c in claims if c.consequence == "human-flag"
    )
    result.volatile_claims = sum(
        1 for c in claims if c.category == "volatile"
    )

    return result


def compute_verdict(result: AuditResult) -> AuditResult:
    """Compute PASS / REFRESH / REVIEW verdict from audit data."""
    reasons = []

    # Hard failures → REFRESH
    if result.hard_failures:
        reasons.append(f"{len(result.hard_failures)} hard assertion failure(s)")

    # Quality gate failures → REFRESH
    if result.quality_gate_failures:
        reasons.append(f"{len(result.quality_gate_failures)} quality gate failure(s)")

    # Artifact hits → REFRESH
    if result.artifact_hits:
        reasons.append(f"{len(result.artifact_hits)} leaked artifact(s)")

    # Word count way off → REFRESH
    if result.target_word_count > 0:
        ratio = result.word_count / result.target_word_count
        if ratio < 0.7 or ratio > 1.5:
            reasons.append(
                f"word count {result.word_count} vs target {result.target_word_count} "
                f"({ratio:.0%})"
            )

    # Tier 2: many unsourced high-stakes claims → REVIEW
    tier2_issues = []
    if result.tier2_ran:
        if result.unsourced_claims >= 5:
            tier2_issues.append(f"{result.unsourced_claims} unsourced high-stakes claims")
        if result.volatile_claims >= 3:
            tier2_issues.append(f"{result.volatile_claims} volatile market stats")

    result.verdict_reasons = reasons + tier2_issues

    if reasons:
        result.verdict = "REFRESH"
    elif tier2_issues:
        result.verdict = "REVIEW"
    else:
        result.verdict = "PASS"

    return result


def fetch_post_html(config: dict, post_id: int) -> dict | None:
    """Fetch post data from the live site via SSH. Read-only.

    Returns dict with keys: post_id, slug, title, html, status, post_date.
    Returns None on failure.
    """
    from .orchestrator import ssh_pipe_php

    php = f"""<?php
$p = get_post({post_id});
if (!$p) {{ echo json_encode(['error' => 'not found']); exit; }}
echo json_encode([
    'post_id' => (int)$p->ID,
    'slug' => $p->post_name,
    'title' => $p->post_title,
    'html' => $p->post_content,
    'status' => $p->post_status,
    'post_date' => $p->post_date,
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
"""

    try:
        stdout, rc = ssh_pipe_php(config, php, timeout=30)
        if rc != 0:
            eprint(f"[audit] SSH failed for post {post_id}: rc={rc}")
            return None
        # wp eval-file prepends a "0" — strip it
        stdout = stdout.strip()
        if stdout.startswith("0"):
            stdout = stdout[1:]
        data = json.loads(stdout)
        if "error" in data:
            eprint(f"[audit] Post {post_id}: {data['error']}")
            return None
        return data
    except json.JSONDecodeError as e:
        eprint(f"[audit] JSON parse error for post {post_id}: {e}")
        return None
    except Exception as e:
        eprint(f"[audit] Error fetching post {post_id}: {e}")
        return None


def fetch_gsc_top_pages(config: dict, limit: int = 50) -> list[dict]:
    """Pull top pages by impressions from GSC (last 90 days).

    Returns list of dicts with: page, slug, impressions, clicks, position,
    top_query, top_query_impressions.
    """
    gsc_property = config.get("integrations", {}).get("gsc_property", "")
    if not gsc_property:
        return []

    creds_path = REPO_ROOT / ".gsc-credentials.json"
    if not creds_path.exists():
        return []

    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        from datetime import timedelta

        creds = Credentials.from_service_account_file(
            str(creds_path),
            scopes=["https://www.googleapis.com/auth/webmasters.readonly"],
        )
        service = build("searchconsole", "v1", credentials=creds)

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

        # Get page-level data
        page_response = service.searchanalytics().query(
            siteUrl=gsc_property,
            body={
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": ["page"],
                "rowLimit": limit * 2,  # fetch extra, filter later
            },
        ).execute()

        # Get query+page data for top query per page
        qp_response = service.searchanalytics().query(
            siteUrl=gsc_property,
            body={
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": ["page", "query"],
                "rowLimit": 5000,
            },
        ).execute()

        # Build page -> top query map
        page_top_query = {}
        for row in qp_response.get("rows", []):
            page = row["keys"][0]
            query = row["keys"][1]
            imp = row.get("impressions", 0)
            if page not in page_top_query or imp > page_top_query[page]["impressions"]:
                page_top_query[page] = {
                    "query": query,
                    "impressions": imp,
                    "position": round(row.get("position", 0), 1),
                }

        public_url = config.get("identity", {}).get("public_url", "").rstrip("/")
        results = []
        for row in page_response.get("rows", []):
            page_url = row["keys"][0]
            slug = page_url.replace(public_url + "/", "").strip("/")
            if not slug:
                continue  # skip homepage

            top_q = page_top_query.get(page_url, {})
            results.append({
                "page": page_url,
                "slug": slug,
                "impressions": int(row.get("impressions", 0)),
                "clicks": int(row.get("clicks", 0)),
                "position": round(row.get("position", 0), 1),
                "top_query": top_q.get("query", ""),
                "top_query_impressions": top_q.get("impressions", 0),
                "top_query_position": top_q.get("position", 0),
            })

        results.sort(key=lambda x: x["impressions"], reverse=True)
        return results[:limit]

    except Exception as e:
        eprint(f"[audit] GSC query failed: {e}")
        return []


def fetch_slug_to_id_map(config: dict) -> dict[str, int]:
    """Fetch full slug→post_id map from the live site in one SSH call.

    Returns dict mapping slug to post_id.
    """
    import subprocess
    import os

    ssh_host = config.get("access", {}).get("ssh_host", "")
    ssh_user = config.get("access", {}).get("ssh_user", "")
    ssh_key = config.get("access", {}).get("ssh_key_path", "")
    wp_path = config.get("access", {}).get("wp_path", "")

    if not ssh_host or not ssh_user:
        return {}

    key_path = os.path.expanduser(ssh_key) if ssh_key else None
    ssh_cmd_list = ["ssh", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes",
                    "-o", "StrictHostKeyChecking=accept-new"]
    if key_path:
        ssh_cmd_list += ["-i", key_path, "-o", "IdentitiesOnly=yes"]
    ssh_cmd_list.append(f"{ssh_user}@{ssh_host}")

    try:
        cmd = ssh_cmd_list + [
            f"cd {wp_path} && wp post list --post_type=post,page --post_status=publish --fields=ID,post_name --format=csv 2>/dev/null"
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0:
            return {}

        slug_map = {}
        for line in r.stdout.strip().split("\n")[1:]:  # skip CSV header
            parts = line.strip().split(",", 1)
            if len(parts) == 2 and parts[0].isdigit():
                slug_map[parts[1].strip('"')] = int(parts[0])
        return slug_map
    except Exception as e:
        eprint(f"[audit] Error fetching slug map: {e}")
        return {}


def resolve_post_id_for_slug(config: dict, slug: str) -> int | None:
    """Look up post_id for a slug. Deprecated — use fetch_slug_to_id_map for batches."""
    slug_map = fetch_slug_to_id_map(config)
    return slug_map.get(slug)


def audit_post(
    config: dict,
    post_id: int,
    gsc_data: dict | None = None,
    force_tier2: bool = False,
) -> AuditResult | None:
    """Run full audit on a single post. Read-only.

    Args:
        config: Site config dict.
        post_id: WordPress post ID.
        gsc_data: Optional GSC data dict for this post (position, query, etc.).
        force_tier2: If True, always run Tier 2.

    Returns:
        AuditResult, or None on fetch failure.
    """
    post_data = fetch_post_html(config, post_id)
    if not post_data:
        return None

    if post_data.get("status") != "publish":
        eprint(f"[audit] Post {post_id} is {post_data.get('status')}, skipping")
        return None

    html = post_data["html"]
    keyword = ""
    if gsc_data:
        keyword = gsc_data.get("top_query", "")

    # Run Tier 1
    result = run_tier1(html, config, keyword)
    result.post_id = post_id
    result.slug = post_data["slug"]
    result.title = post_data["title"]

    if gsc_data:
        result.top_query = gsc_data.get("top_query", "")
        result.position = gsc_data.get("top_query_position", gsc_data.get("position", 0))
        result.impressions = gsc_data.get("impressions", 0)

    # Tier 2 trigger logic
    tier1_failed = bool(result.hard_failures or result.quality_gate_failures or result.artifact_hits)
    in_striking_distance = 11 <= result.position <= 30

    if force_tier2 or tier1_failed or in_striking_distance:
        run_tier2(html, result)

    # Compute verdict
    compute_verdict(result)
    return result


def write_audit_report(
    results: list[AuditResult],
    site_slug: str,
    output_dir: Path | None = None,
) -> tuple[Path, Path]:
    """Write audit scorecard as markdown + JSON.

    Returns (md_path, json_path).
    """
    if output_dir is None:
        output_dir = REPO_ROOT / "docs"

    date_str = datetime.now().strftime("%Y%m%d")
    md_path = output_dir / f"{site_slug}-audit-{date_str}.md"
    json_path = output_dir / f"{site_slug}-audit-{date_str}.json"

    # Sort: REFRESH first, then REVIEW, then PASS
    verdict_order = {"REFRESH": 0, "REVIEW": 1, "PASS": 2}
    results.sort(key=lambda r: (verdict_order.get(r.verdict, 3), -r.impressions))

    # Markdown report
    lines = [
        f"# {site_slug.upper()} Audit — {datetime.now().strftime('%Y-%m-%d')}",
        "",
        f"> {len(results)} posts audited. "
        f"REFRESH: {sum(1 for r in results if r.verdict == 'REFRESH')}, "
        f"REVIEW: {sum(1 for r in results if r.verdict == 'REVIEW')}, "
        f"PASS: {sum(1 for r in results if r.verdict == 'PASS')}",
        "",
        "| # | Verdict | Post ID | Slug | Top Query | Pos | Imp | Hard | Soft | QG | Artifacts | Claims | Reasons |",
        "|---|---------|---------|------|-----------|-----|-----|------|------|----|-----------|--------|---------|",
    ]

    for i, r in enumerate(results, 1):
        hard_str = f"{r.hard_pass_count}/{r.hard_total_count}"
        soft_str = f"{r.soft_pass_count}/{r.soft_total_count}"
        qg_str = str(len(r.quality_gate_failures)) if r.quality_gate_failures else "0"
        art_str = str(len(r.artifact_hits)) if r.artifact_hits else "0"
        claims_str = (
            f"{r.unsourced_claims}u/{r.claim_count}"
            if r.tier2_ran else "—"
        )
        reasons_short = "; ".join(r.verdict_reasons[:2]) if r.verdict_reasons else "—"
        if len(reasons_short) > 60:
            reasons_short = reasons_short[:57] + "..."

        lines.append(
            f"| {i} | **{r.verdict}** | {r.post_id} | {r.slug[:35]} | "
            f"{r.top_query[:30]} | {r.position:.0f} | {r.impressions} | "
            f"{hard_str} | {soft_str} | {qg_str} | {art_str} | {claims_str} | {reasons_short} |"
        )

    # Detail section for non-PASS posts
    lines.append("")
    lines.append("## Detail — non-PASS posts")
    lines.append("")

    for r in results:
        if r.verdict == "PASS":
            continue
        lines.append(f"### {r.post_id} — `{r.slug}` [{r.verdict}]")
        lines.append("")
        if r.hard_failures:
            lines.append("**Hard failures:**")
            for f in r.hard_failures:
                lines.append(f"- {f}")
            lines.append("")
        if r.quality_gate_failures:
            lines.append("**Quality gate:**")
            for f in r.quality_gate_failures:
                lines.append(f"- {f[:120]}")
            lines.append("")
        if r.artifact_hits:
            lines.append("**Artifacts:**")
            for f in r.artifact_hits:
                lines.append(f"- {f[:120]}")
            lines.append("")
        if r.tier2_ran and (r.unsourced_claims or r.volatile_claims):
            lines.append(f"**Claims:** {r.claim_count} total, {r.unsourced_claims} unsourced high-stakes, {r.volatile_claims} volatile")
            lines.append("")

    md_path.write_text("\n".join(lines))

    # JSON report
    json_data = {
        "site": site_slug,
        "date": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total": len(results),
            "refresh": sum(1 for r in results if r.verdict == "REFRESH"),
            "review": sum(1 for r in results if r.verdict == "REVIEW"),
            "pass": sum(1 for r in results if r.verdict == "PASS"),
        },
        "results": [asdict(r) for r in results],
    }
    json_path.write_text(json.dumps(json_data, indent=2))

    return md_path, json_path
