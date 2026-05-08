#!/usr/bin/env python3
"""Orchestrator — replaces v1's produce-article.py + generate-article.py.

Runs the full article pipeline: load config, detect intent, run SERP
research, extract gaps, compute word count target, build all article
sections, assemble HTML, inject links, validate, and optionally deploy.

Usage:
    python3 assemble-article.py \\
        --site <slug> \\
        --post-id <id> \\
        --target-keyword <keyword> \\
        [--intent <intent>]             \\
        [--status <draft|publish>]      \\
        [--output-dir <path>]           \\
        [--skip-deploy]                 \\
        [--allow-no-serp]               \\
        [--force]

See docs/v2-module-architecture.md "tools/assemble-article.py" for pipeline.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
MODULE_DIR = TOOLS_DIR.parent
REPO_ROOT = MODULE_DIR.parent.parent
sys.path.insert(0, str(MODULE_DIR))

from bs4 import BeautifulSoup

from lib.anchor_pool import AnchorPool
from lib.llm_client import LLMClient
from lib.overlay_loader import load_overlay
from lib.serp_adapter import SerpData
from lib.site_config import load_site_config
from lib.tool_utils import (
    build_topic_context,
    eprint,
    extract_html,
    load_brand_voice,
    load_prompt_template,
    render_prompt,
    validate_or_retry,
    write_output,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PYTHON = sys.executable
LLM_CALL_TIMEOUT = 300  # 5 minutes per LLM call

# Intent detection keywords (spec Section 1 table)
_INTENT_TRIGGERS: dict[str, list[str]] = {
    "cost": ["cost", "fee", "fees", "price", "prices", "rate", "rates", "how much"],
    "process": ["how to", "steps to", "guide to", "how do", "process", "step by step"],
    "decision": ["vs", "versus", "or", "compare", "compared", "best", "which"],
    "definition": ["what is", "what are", "defined", "meaning", "definition", "explained"],
    "comparison": ["comparison", "review", "reviews", "top", "ranking"],
}


# ---------------------------------------------------------------------------
# Pipeline state
# ---------------------------------------------------------------------------

@dataclass
class PipelineState:
    """Accumulated state across pipeline phases."""
    # Phase A
    site_slug: str = ""
    post_id: int = 0
    target_keyword: str = ""
    intent: str = ""
    config: dict = field(default_factory=dict)
    archetype: str = ""
    brand_voice: str = ""
    overlay: object = None
    provider: str = "claude_cli"
    model: str | None = None
    output_dir: Path = Path(".")
    status: str = "draft"

    # Phase B
    serp: object = None
    serp_json_path: Path | None = None
    subtopic_gaps: dict = field(default_factory=dict)
    target_wc: dict = field(default_factory=dict)

    # Phase C
    h2_inventory: list[dict] = field(default_factory=list)
    header_html: str = ""
    jump_nav_html: str = ""

    # Phase D
    atf_lede_html: str = ""
    card_htmls: list[str] = field(default_factory=list)
    atf_faqs_html: str = ""

    # Phase E
    bluf_html: str = ""

    # Phase F
    body_section_htmls: list[str] = field(default_factory=list)
    mid_cta_html: str = ""

    # Phase G
    closing_html: str = ""
    btf_faqs_html: str = ""
    resources_html: str = ""
    toc_html: str = ""

    # Phase H
    assembled_html: str = ""
    pending_links: list[dict] = field(default_factory=list)

    # Tracking
    phases_completed: list[str] = field(default_factory=list)
    llm_calls: int = 0
    llm_cost: float = 0.0
    start_time: float = 0.0
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Intent detection
# ---------------------------------------------------------------------------

def detect_intent(keyword: str) -> str:
    """Auto-detect intent from keyword using trigger patterns."""
    kw_lower = keyword.lower()
    scores: dict[str, int] = {}
    for intent, triggers in _INTENT_TRIGGERS.items():
        score = sum(1 for t in triggers if t in kw_lower)
        if score > 0:
            scores[intent] = score

    if not scores:
        return "definition"  # default fallback

    return max(scores, key=scores.get)


# ---------------------------------------------------------------------------
# Subprocess runner
# ---------------------------------------------------------------------------

def _run_tool(tool_path: str, args_list: list[str], step_label: str) -> str:
    """Run a tool as subprocess. Returns stdout. Raises on failure."""
    cmd = [PYTHON, tool_path] + args_list
    eprint(f"  [{step_label}] Running: {Path(tool_path).name} {' '.join(args_list[:6])}...")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=LLM_CALL_TIMEOUT, cwd=str(REPO_ROOT),
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"{step_label} timed out after {LLM_CALL_TIMEOUT}s. "
            f"Tool: {Path(tool_path).name}"
        )

    if result.returncode != 0:
        stderr_tail = (result.stderr or "").strip()[-500:]
        raise RuntimeError(
            f"{step_label} failed (exit {result.returncode}).\n"
            f"Tool: {Path(tool_path).name}\n"
            f"Stderr: {stderr_tail}"
        )

    return result.stdout


# ---------------------------------------------------------------------------
# Phase A: Setup
# ---------------------------------------------------------------------------

def phase_a(state: PipelineState) -> None:
    """Load site config, brand voice, overlay."""
    eprint("PHASE A: Setup")

    # Step 1: Load site config
    eprint("  [A.1] Loading site config")
    state.config = load_site_config(state.site_slug)
    state.archetype = state.config.get("branding", {}).get("archetype", "")
    state.provider = state.config.get("AI_PROVIDER", "claude_cli")
    state.model = state.config.get("AI_MODEL") or None

    # Step 2: Load brand voice
    eprint(f"  [A.2] Loading brand voice: {state.archetype or '(none)'}")
    state.brand_voice = load_brand_voice(state.archetype) if state.archetype else ""

    # Step 3: Detect intent if not provided
    if not state.intent:
        state.intent = detect_intent(state.target_keyword)
        eprint(f"  [A.3] Auto-detected intent: {state.intent}")
    else:
        eprint(f"  [A.3] Intent provided: {state.intent}")

    # Step 4: Load overlay
    eprint(f"  [A.4] Loading overlay: {state.intent}")
    state.overlay = load_overlay(state.intent)

    state.phases_completed.append("A")


# ---------------------------------------------------------------------------
# Phase B: SERP Research
# ---------------------------------------------------------------------------

def phase_b(state: PipelineState, allow_no_serp: bool = False) -> None:
    """Run SERP research, extract gaps, compute target word count."""
    eprint("PHASE B: SERP Research")

    kw_slug = re.sub(r"[^a-z0-9]+", "-", state.target_keyword.lower()).strip("-")
    serp_cache_dir = Path.home() / f"{state.site_slug}-rewrite" / "serp"
    serp_cache_dir.mkdir(parents=True, exist_ok=True)
    serp_path = serp_cache_dir / f"{kw_slug}-serp.json"

    # Step 5: Check cached SERP
    serp_stale = True
    if serp_path.exists():
        age_days = (time.time() - serp_path.stat().st_mtime) / 86400
        if age_days <= 7:
            eprint(f"  [B.5] Using cached SERP ({age_days:.1f} days old): {serp_path}")
            serp_stale = False
        else:
            eprint(f"  [B.5] SERP cache stale ({age_days:.1f} days old)")

    # Step 6: Run SERP analysis if needed
    if serp_stale:
        analyze_serp = REPO_ROOT / "modules" / "serp-research" / "tools" / "analyze-serp.py"
        if analyze_serp.exists() and not allow_no_serp:
            eprint("  [B.6] Running analyze-serp.py")
            try:
                _run_tool(str(analyze_serp), [
                    "--keyword", state.target_keyword,
                    "--output", str(serp_path),
                ], "B.6")
            except RuntimeError as e:
                if allow_no_serp:
                    eprint(f"  [B.6] SERP analysis failed, continuing without: {e}")
                else:
                    raise
        elif allow_no_serp:
            eprint("  [B.6] --allow-no-serp: skipping SERP analysis")
        else:
            raise RuntimeError(
                "SERP analysis tool not found and --allow-no-serp not set. "
                f"Expected: {analyze_serp}"
            )

    # Step 7: Load SERP data
    if serp_path.exists():
        state.serp = SerpData(serp_path)
        state.serp_json_path = serp_path
        eprint(f"  [B.7] SERP loaded: {len(state.serp.top_results)} results, "
               f"{len(state.serp.paa_questions)} PAA questions")
    elif allow_no_serp:
        eprint("  [B.7] No SERP data available (--allow-no-serp)")
        state.serp = None
        state.serp_json_path = None
    else:
        raise RuntimeError("No SERP data available and --allow-no-serp not set")

    # Step 8: Extract subtopic gaps
    if state.serp and state.serp_json_path:
        gaps_tool = TOOLS_DIR / "extract-subtopic-gaps.py"
        if gaps_tool.exists():
            eprint("  [B.8] Extracting subtopic gaps")
            try:
                gaps_json = _run_tool(str(gaps_tool), [
                    "--serp-json", str(state.serp_json_path),
                ], "B.8")
                state.subtopic_gaps = json.loads(gaps_json) if gaps_json.strip() else {}
            except (RuntimeError, json.JSONDecodeError) as e:
                eprint(f"  [B.8] Subtopic gap extraction failed, using defaults: {e}")
    else:
        eprint("  [B.8] Skipping subtopic gaps (no SERP)")

    # Step 9: Compute target word count
    if state.serp and state.serp_json_path:
        wc_tool = TOOLS_DIR / "compute-target-wc.py"
        if wc_tool.exists():
            eprint("  [B.9] Computing target word count")
            try:
                wc_json = _run_tool(str(wc_tool), [
                    "--serp-json", str(state.serp_json_path),
                ], "B.9")
                state.target_wc = json.loads(wc_json) if wc_json.strip() else {}
            except (RuntimeError, json.JSONDecodeError) as e:
                eprint(f"  [B.9] Word count computation failed, using defaults: {e}")

    if not state.target_wc:
        state.target_wc = {"target": 2100, "min": 1800, "max": 2400, "source": "fallback"}
        eprint(f"  [B.9] Using fallback word count: {state.target_wc['target']}")

    state.phases_completed.append("B")


# ---------------------------------------------------------------------------
# Phase C: Structure Planning
# ---------------------------------------------------------------------------

def phase_c(state: PipelineState) -> None:
    """Build H2 inventory, header prelude, jump nav."""
    eprint("PHASE C: Structure Planning")

    # Step 10: Build H2 inventory
    eprint("  [C.10] Building H2 inventory")
    h2s = _build_h2_inventory(state)
    state.h2_inventory = h2s
    eprint(f"  [C.10] H2 inventory: {len(h2s)} sections")
    for h in h2s:
        eprint(f"    - {h['title']} [{h['structural_element']}]")

    # Step 11: Build header prelude (deterministic)
    eprint("  [C.11] Building header prelude")
    state.header_html = _build_header_prelude(state)

    # Step 12: Build jump nav
    eprint("  [C.12] Building jump nav")
    state.jump_nav_html = _build_jump_nav(state)

    state.phases_completed.append("C")


def _build_h2_inventory(state: PipelineState) -> list[dict]:
    """Build H2 section inventory from overlay + SERP gaps."""
    h2s = []
    overlay = state.overlay
    body_default = overlay.body_default

    # Structural element rotation based on body_default
    if body_default == "tables_dominant":
        element_cycle = ["table", "table", "bullets", "table", "bullets", "table"]
    elif body_default == "bullets_dominant":
        element_cycle = ["bullets", "bullets", "table", "bullets", "table", "bullets"]
    else:
        element_cycle = ["bullets", "table", "bullets", "table", "bullets", "table"]

    # Start from SERP gap analysis: high-coverage subtopics
    high_cov = state.subtopic_gaps.get("high_coverage", [])
    med_cov = state.subtopic_gaps.get("medium_coverage", [])
    low_cov = state.subtopic_gaps.get("low_coverage_gaps", [])

    # Build H2 titles from gaps
    for item in high_cov[:6]:
        title = item if isinstance(item, str) else item.get("heading", str(item))
        h2s.append({"title": title, "role": "high_coverage", "source": "serp"})

    for item in med_cov[:4]:
        title = item if isinstance(item, str) else item.get("heading", str(item))
        h2s.append({"title": title, "role": "medium_coverage", "source": "serp"})

    # Add 1-2 competitive moat subtopics from low-coverage gaps
    for item in low_cov[:2]:
        title = item if isinstance(item, str) else item.get("heading", str(item))
        h2s.append({"title": title, "role": "competitive_moat", "source": "gap"})

    # If SERP gave us fewer than 6, pad from PAA questions
    if len(h2s) < 6 and state.serp:
        for paa in state.serp.paa_questions:
            if len(h2s) >= 10:
                break
            q = paa.question if hasattr(paa, "question") else str(paa)
            if not any(h["title"].lower() == q.lower() for h in h2s):
                h2s.append({"title": q, "role": "paa_derived", "source": "paa"})

    # Fallback: if still too few, generate from keyword
    if len(h2s) < 6:
        kw = state.target_keyword
        fallbacks = [
            f"What Is {kw.title()}",
            f"How {kw.title()} Works",
            f"Who Qualifies for {kw.title()}",
            f"Key Benefits of {kw.title()}",
            f"{kw.title()} Requirements",
            f"Common Questions About {kw.title()}",
        ]
        for fb in fallbacks:
            if len(h2s) >= 6:
                break
            if not any(h["title"].lower() == fb.lower() for h in h2s):
                h2s.append({"title": fb, "role": "fallback", "source": "generated"})

    # Trim to max 15
    h2s = h2s[:15]

    # Assign structural elements and callout preferences
    callout_prefs = overlay.callout_preferences
    for i, h2 in enumerate(h2s):
        h2["structural_element"] = element_cycle[i % len(element_cycle)]
        # Assign callout if available for this role
        role = h2.get("role", "")
        if role in callout_prefs and callout_prefs[role]:
            h2["callout_key"] = callout_prefs[role][0]
            h2["callout_label"] = callout_prefs[role][0].replace("_", " ").title()
        else:
            h2["callout_key"] = ""
            h2["callout_label"] = ""

    return h2s


def _build_header_prelude(state: PipelineState) -> str:
    """Build deterministic header HTML (H1, eyebrow, byline, primary sources)."""
    config = state.config
    kw = state.target_keyword
    site_domain = config.get("SITE_DOMAIN", "")
    byline = config.get("BYLINE", "")
    cta_url = config.get("CTA_URL", "/compare-loan-offers/")
    year = datetime.now().year

    # Primary sources from SERP
    primary_sources = ""
    if state.serp:
        refs = state.serp.ai_overview_references[:3]
        if refs:
            sources = []
            for ref in refs:
                title = ref.title if hasattr(ref, "title") else str(ref)
                link = ref.link if hasattr(ref, "link") else ""
                source = ref.source if hasattr(ref, "source") else ""
                if link:
                    sources.append(f'<a href="{link}">{source or title}</a>')
            if sources:
                primary_sources = (
                    '<div class="rl-primary-sources">Primary Sources: '
                    + ", ".join(sources)
                    + "</div>"
                )

    header = (
        f'<header class="rl-hero">\n'
        f'  <div class="rl-eyebrow">{state.intent.title()} Guide</div>\n'
        f'  <h1>{kw.title()}</h1>\n'
        f'  <div class="rl-byline">{byline} | Updated {year}</div>\n'
        f'  {primary_sources}\n'
        f'  <a href="{cta_url}" class="rl-cta-primary">Get Your Rate →</a>\n'
        f'</header>\n'
    )
    return header


def _build_jump_nav(state: PipelineState) -> str:
    """Build jump nav with first 4 H2 titles + FAQs (spec Section 4)."""
    links = []
    for h2 in state.h2_inventory[:4]:
        slug = re.sub(r"[^a-z0-9]+", "-", h2["title"].lower()).strip("-")
        links.append(f'<a href="#{slug}">{h2["title"]}</a>')
    links.append('<a href="#faqs">FAQs</a>')

    nav = (
        '<nav class="rl-jump-nav" aria-label="Jump to section">\n'
        "  " + "\n  ".join(links) + "\n"
        "</nav>\n"
    )
    return nav


# ---------------------------------------------------------------------------
# Phase D: ATF Generation
# ---------------------------------------------------------------------------

def phase_d(state: PipelineState) -> None:
    """Build ATF lede, 4 cards, 3 ATF FAQs."""
    eprint("PHASE D: ATF Generation")

    client = LLMClient(provider=state.provider, model=state.model)
    serp_json = str(state.serp_json_path) if state.serp_json_path else ""

    # Step 13: ATF lede
    eprint("  [D.13] Building ATF lede")
    state.atf_lede_html = _build_atf_lede(state, client)

    # Step 14: Build 4 ATF cards (sequential)
    eprint("  [D.14] Building 4 ATF cards")
    state.card_htmls = []
    for i, slot in enumerate(state.overlay.card_slots):
        eprint(f"  [D.14.{i+1}] Card: {slot.role}")
        card_tool = TOOLS_DIR / "build-card.py"
        output_path = state.output_dir / f"{state.post_id}-card-{slot.role}.html"
        try:
            _run_tool(str(card_tool), [
                "--site", state.site_slug,
                "--target-keyword", state.target_keyword,
                "--intent", state.intent,
                "--card-slot", slot.role,
                "--serp-json", serp_json or "/dev/null",
                "--output", str(output_path),
            ], f"D.14.{i+1}")
            state.card_htmls.append(output_path.read_text())
            state.llm_calls += 1
        except RuntimeError as e:
            raise RuntimeError(
                f"Phase D step 14 (ATF cards) failed for card_slot={slot.role}.\n"
                f"Reason: {e}\n"
                f"Debug: Re-run with --debug-section card:{slot.role} to iterate."
            )

    # Step 15: Build 3 ATF FAQs
    eprint("  [D.15] Building ATF FAQs")
    faqs_tool = TOOLS_DIR / "build-faqs.py"
    atf_faq_path = state.output_dir / f"{state.post_id}-atf-faqs.html"
    try:
        _run_tool(str(faqs_tool), [
            "--site", state.site_slug,
            "--target-keyword", state.target_keyword,
            "--mode", "atf",
            "--serp-json", serp_json or "/dev/null",
            "--output", str(atf_faq_path),
        ], "D.15")
        state.atf_faqs_html = atf_faq_path.read_text()
        state.llm_calls += 3  # 3 individual FAQ calls
    except RuntimeError as e:
        raise RuntimeError(f"Phase D step 15 (ATF FAQs) failed.\nReason: {e}")

    state.phases_completed.append("D")


def _build_atf_lede(state: PipelineState, client: LLMClient) -> str:
    """Build ATF lede via direct LLM call."""
    template = load_prompt_template("atf-lede.md")

    serp_ledes = ""
    ai_overview = ""
    if state.serp:
        top = state.serp.top_results[:3]
        serp_ledes = "\n".join(f"- {r.title}: {r.snippet}" for r in top)
        ai_overview = state.serp.ai_overview_text or ""

    prompt = render_prompt(template, {
        "TARGET_KEYWORD": state.target_keyword,
        "TOPIC_NOUN": state.target_keyword,
        "SERP_TOP_RESULT_LEDES": serp_ledes or "(unavailable)",
        "AI_OVERVIEW_TEXT": ai_overview or "(unavailable)",
        "INJECT_BRAND_VOICE": state.brand_voice,
    })

    cache_key = f"{state.site_slug}|{state.target_keyword}|atf-lede"
    response = client.call(prompt, cache_key=cache_key)
    state.llm_calls += 1
    state.llm_cost += response.cost_estimate

    html = extract_html(response.text)
    eprint(f"  [D.13] Lede: {len(html.split())} words, ${response.cost_estimate:.4f}")
    return html


# ---------------------------------------------------------------------------
# Phase E: BLUF (conditional)
# ---------------------------------------------------------------------------

def phase_e(state: PipelineState) -> None:
    """Build BLUF if overlay says to include it."""
    eprint("PHASE E: BLUF")

    bluf_setting = state.overlay.bluf_default
    if bluf_setting == "omit":
        eprint("  [E.16] BLUF omitted per overlay")
        state.phases_completed.append("E")
        return

    if bluf_setting == "conditional":
        eprint("  [E.16] BLUF conditional — including for safety")

    eprint("  [E.17] Building BLUF")
    bluf_tool = TOOLS_DIR / "build-bluf.py"
    bluf_path = state.output_dir / f"{state.post_id}-bluf.html"

    # Write topic context to temp file for build-bluf
    context_path = state.output_dir / f"{state.post_id}-topic-context.json"
    topic_ctx = build_topic_context(state.serp, state.target_keyword) if state.serp else ""
    context_path.write_text(json.dumps({"context": topic_ctx}))

    serp_json = str(state.serp_json_path) if state.serp_json_path else "/dev/null"
    try:
        _run_tool(str(bluf_tool), [
            "--site", state.site_slug,
            "--target-keyword", state.target_keyword,
            "--topic-context", str(context_path),
            "--friction-point", f"Key considerations for {state.target_keyword}",
            "--serp-json", serp_json,
            "--output", str(bluf_path),
        ], "E.17")
        state.bluf_html = bluf_path.read_text()
        state.llm_calls += 1
    except RuntimeError as e:
        eprint(f"  [E.17] BLUF build failed (non-fatal if conditional): {e}")
        if bluf_setting == "include":
            raise RuntimeError(f"Phase E step 17 (BLUF) failed.\nReason: {e}")

    state.phases_completed.append("E")


# ---------------------------------------------------------------------------
# Phase F: Body Sections
# ---------------------------------------------------------------------------

def phase_f(state: PipelineState) -> None:
    """Build body H2 sections + mid-article CTA."""
    eprint("PHASE F: Body Sections")

    body_target = state.target_wc.get("target", 2100)
    h2_count = len(state.h2_inventory)
    per_section_wc = max(200, body_target // max(h2_count, 1))

    section_tool = TOOLS_DIR / "build-h2-section.py"
    serp_json = str(state.serp_json_path) if state.serp_json_path else "/dev/null"
    state.body_section_htmls = []

    for i, h2 in enumerate(state.h2_inventory):
        eprint(f"  [F.18.{i+1}] Building H2: {h2['title'][:50]}")
        section_path = state.output_dir / f"{state.post_id}-h2-{i:02d}.html"

        args_list = [
            "--site", state.site_slug,
            "--target-keyword", state.target_keyword,
            "--h2-title", h2["title"],
            "--section-role", h2.get("role", "body"),
            "--structural-element", h2["structural_element"],
            "--target-word-count", str(per_section_wc),
            "--serp-json", serp_json,
            "--output", str(section_path),
        ]
        if h2.get("callout_key"):
            args_list += ["--callout-key", h2["callout_key"]]
        if h2.get("callout_label"):
            args_list += ["--callout-label", h2["callout_label"]]

        try:
            _run_tool(str(section_tool), args_list, f"F.18.{i+1}")
            state.body_section_htmls.append(section_path.read_text())
            state.llm_calls += 1
        except RuntimeError as e:
            raise RuntimeError(
                f"Phase F step 18 (body H2) failed for section #{i+1}: "
                f'"{h2["title"]}".\nReason: {e}\n'
                f"Debug: Re-run build-h2-section.py with the same args to iterate."
            )

    # Step 19: Mid-article CTA pill after 2nd or 3rd H2
    cta_url = state.config.get("CTA_URL", "/compare-loan-offers/")
    cta_position = min(2, len(state.body_section_htmls) - 1)
    state.mid_cta_html = (
        f'<div class="rl-cta-mid">'
        f'<a href="{cta_url}" class="rl-cta-pill">Get Your Rate →</a>'
        f'</div>\n'
    )

    # Insert CTA after the designated position
    if state.body_section_htmls and cta_position >= 0:
        state.body_section_htmls.insert(
            cta_position + 1, state.mid_cta_html
        )

    state.phases_completed.append("F")


# ---------------------------------------------------------------------------
# Phase G: Closing
# ---------------------------------------------------------------------------

def phase_g(state: PipelineState) -> None:
    """Build closing Bottom Line, BTF FAQs, Resources, TOC."""
    eprint("PHASE G: Closing")

    client = LLMClient(provider=state.provider, model=state.model)
    serp_json = str(state.serp_json_path) if state.serp_json_path else "/dev/null"

    # Step 20: Closing "The Bottom Line"
    eprint("  [G.20] Building closing Bottom Line")
    state.closing_html = _build_closing(state, client)

    # Step 21: BTF FAQs
    eprint("  [G.21] Building BTF FAQs")
    faqs_tool = TOOLS_DIR / "build-faqs.py"
    btf_path = state.output_dir / f"{state.post_id}-btf-faqs.html"

    # Write ATF FAQ questions as exclusion list
    exclude_path = state.output_dir / f"{state.post_id}-atf-faq-exclude.json"
    atf_soup = BeautifulSoup(state.atf_faqs_html, "html.parser")
    atf_questions = [
        s.get_text(strip=True)
        for s in atf_soup.find_all("summary")
    ]
    exclude_path.write_text(json.dumps(atf_questions))

    try:
        _run_tool(str(faqs_tool), [
            "--site", state.site_slug,
            "--target-keyword", state.target_keyword,
            "--mode", "btf",
            "--serp-json", serp_json,
            "--exclude-questions", str(exclude_path),
            "--output", str(btf_path),
        ], "G.21")
        state.btf_faqs_html = btf_path.read_text()
        state.llm_calls += 1
    except RuntimeError as e:
        raise RuntimeError(f"Phase G step 21 (BTF FAQs) failed.\nReason: {e}")

    # Step 22: Resources Used
    eprint("  [G.22] Building Resources")
    resources_tool = TOOLS_DIR / "build-resources.py"
    resources_path = state.output_dir / f"{state.post_id}-resources.html"
    try:
        _run_tool(str(resources_tool), [
            "--site", state.site_slug,
            "--target-keyword", state.target_keyword,
            "--serp-json", serp_json,
            "--output", str(resources_path),
        ], "G.22")
        state.resources_html = resources_path.read_text()
    except RuntimeError as e:
        raise RuntimeError(f"Phase G step 22 (Resources) failed.\nReason: {e}")

    # Step 23: TOC
    eprint("  [G.23] Generating TOC")
    state.toc_html = _build_toc(state)

    state.phases_completed.append("G")


def _build_closing(state: PipelineState, client: LLMClient) -> str:
    """Build closing Bottom Line via direct LLM call."""
    template = load_prompt_template("closing-bottom-line.md")

    # Build article summary from H2 titles + first sentences
    summary_lines = []
    for i, h2 in enumerate(state.h2_inventory):
        section_html = state.body_section_htmls[i] if i < len(state.body_section_htmls) else ""
        soup = BeautifulSoup(section_html, "html.parser")
        intro_p = soup.find("p")
        intro = intro_p.get_text(strip=True)[:200] if intro_p else ""
        summary_lines.append(f"- **{h2['title']}**: {intro}")

    prompt = render_prompt(template, {
        "TARGET_KEYWORD": state.target_keyword,
        "ARTICLE_SUMMARY": "\n".join(summary_lines),
        "INJECT_BRAND_VOICE": state.brand_voice,
    })

    cache_key = f"{state.site_slug}|{state.target_keyword}|closing"
    response = client.call(prompt, cache_key=cache_key)
    state.llm_calls += 1
    state.llm_cost += response.cost_estimate

    return extract_html(response.text)


def _build_toc(state: PipelineState) -> str:
    """Auto-generate In This Article TOC from H2 inventory."""
    items = []
    for h2 in state.h2_inventory:
        slug = re.sub(r"[^a-z0-9]+", "-", h2["title"].lower()).strip("-")
        items.append(f'  <li><a href="#{slug}">{h2["title"]}</a></li>')

    return (
        '<nav class="rl-toc" aria-label="In this article">\n'
        "  <h2>In This Article</h2>\n"
        "  <ol>\n" + "\n".join(items) + "\n  </ol>\n"
        "</nav>\n"
    )


# ---------------------------------------------------------------------------
# Phase H: Assembly
# ---------------------------------------------------------------------------

def phase_h(state: PipelineState) -> None:
    """Assemble all sections, inject links, validate."""
    eprint("PHASE H: Assembly")

    # Step 24: Concatenate in canonical order (spec Section 2)
    eprint("  [H.24] Assembling article")
    parts = [
        state.header_html,
        state.jump_nav_html,
        state.atf_lede_html,
        "\n".join(state.card_htmls),
        state.atf_faqs_html,
    ]
    if state.bluf_html:
        parts.append(state.bluf_html)
    parts.extend(state.body_section_htmls)  # includes mid CTA
    parts.extend([
        state.closing_html,
        state.btf_faqs_html,
        state.resources_html,
        state.toc_html,
    ])

    assembled = "\n\n".join(p for p in parts if p.strip())
    assembled_path = state.output_dir / f"{state.post_id}-assembled-raw.html"
    assembled_path.write_text(assembled)

    # Step 25: Inject internal links
    eprint("  [H.25] Injecting internal links")
    linked_path = state.output_dir / f"{state.post_id}-article.html"
    pending_path = state.output_dir / f"{state.post_id}-pending-links.json"
    inject_tool = TOOLS_DIR / "inject-internal-links.py"

    try:
        _run_tool(str(inject_tool), [
            "--site", state.site_slug,
            "--html-input", str(assembled_path),
            "--html-output", str(linked_path),
            "--pending-links-output", str(pending_path),
        ], "H.25")
        state.assembled_html = linked_path.read_text()
        if pending_path.exists():
            state.pending_links = json.loads(pending_path.read_text())
    except RuntimeError as e:
        eprint(f"  [H.25] Link injection failed (non-fatal): {e}")
        state.assembled_html = assembled
        linked_path.write_text(assembled)

    # Step 26: Validate
    eprint("  [H.26] Running validation")
    validator = TOOLS_DIR / "validate-article-v2.py"
    validation_report_path = state.output_dir / f"{state.post_id}-validation-report.md"

    if validator.exists():
        # Check if validator is still a stub
        validator_content = validator.read_text()
        if "NotImplementedError" in validator_content:
            eprint("  [H.26] Validator is still a stub — skipping validation")
        else:
            try:
                report = _run_tool(str(validator), [
                    "--html-file", str(linked_path),
                    "--intent", state.intent,
                    "--serp-json", str(state.serp_json_path or "/dev/null"),
                    "--site", state.site_slug,
                    "--output-format", "markdown",
                ], "H.26")
                validation_report_path.write_text(report)
                eprint(f"  [H.26] Validation report written: {validation_report_path}")
            except RuntimeError as e:
                eprint(f"  [H.26] Validation failed (non-fatal): {e}")
    else:
        eprint("  [H.26] Validator not found — skipping validation")

    state.phases_completed.append("H")


# ---------------------------------------------------------------------------
# Phase I: Deploy
# ---------------------------------------------------------------------------

def phase_i(state: PipelineState, skip_deploy: bool) -> None:
    """Optionally push to WordPress."""
    eprint("PHASE I: Deploy")

    if skip_deploy:
        eprint("  [I.28] --skip-deploy: skipping WordPress deploy")
        state.phases_completed.append("I")
        return

    push_tool = REPO_ROOT / "modules" / "wp-deploy" / "tools" / "push-post-content.py"
    if not push_tool.exists():
        eprint(f"  [I.29] Deploy tool not found: {push_tool}")
        eprint("  [I.29] Skipping deploy — push manually when ready")
        state.phases_completed.append("I")
        return

    article_path = state.output_dir / f"{state.post_id}-article.html"
    eprint(f"  [I.29] Deploying to WordPress (status={state.status})")

    try:
        _run_tool(str(push_tool), [
            "--site", state.site_slug,
            "--post-id", str(state.post_id),
            "--html-file", str(article_path),
            "--status", state.status,
        ], "I.29")
        eprint(f"  [I.29] Deployed post {state.post_id} as {state.status}")
    except RuntimeError as e:
        raise RuntimeError(f"Phase I step 29 (deploy) failed.\nReason: {e}")

    state.phases_completed.append("I")


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def _write_manifest(state: PipelineState) -> dict:
    """Write pipeline manifest JSON."""
    elapsed = time.time() - state.start_time

    # Count elements from assembled HTML
    soup = BeautifulSoup(state.assembled_html, "html.parser")
    internal_links = len([
        a for a in soup.find_all("a", href=True)
        if not a["href"].startswith(("http://", "https://", "//"))
        or state.config.get("SITE_DOMAIN", "") in a["href"]
    ])
    external_links = len([
        a for a in soup.find_all("a", href=True)
        if a["href"].startswith(("http://", "https://"))
        and state.config.get("SITE_DOMAIN", "") not in a["href"]
    ])
    callout_count = len(soup.find_all(class_=re.compile(r"rl-callout")))
    btf_faq_soup = BeautifulSoup(state.btf_faqs_html, "html.parser")
    btf_faq_count = len(btf_faq_soup.find_all("details"))
    total_words = len(soup.get_text().split())
    body_words = sum(
        len(BeautifulSoup(s, "html.parser").get_text().split())
        for s in state.body_section_htmls
    )

    manifest = {
        "post_id": state.post_id,
        "target_keyword": state.target_keyword,
        "intent": state.intent,
        "site": state.site_slug,
        "word_count_total": total_words,
        "word_count_body": body_words,
        "h2_count": len(state.h2_inventory),
        "card_count": len(state.card_htmls),
        "atf_faq_count": 3,
        "btf_faq_count": btf_faq_count,
        "callout_count": callout_count,
        "internal_links_injected": internal_links,
        "external_links_count": external_links,
        "pending_links_count": len(state.pending_links),
        "validation": {
            "ran": (state.output_dir / f"{state.post_id}-validation-report.md").exists(),
            "hard_passed": None,
            "soft_warnings": None,
        },
        "llm_calls_total": state.llm_calls,
        "llm_cost_estimate_usd": round(state.llm_cost, 4),
        "elapsed_seconds": round(elapsed, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phases_completed": state.phases_completed,
    }

    manifest_path = state.output_dir / f"{state.post_id}-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    eprint(f"\nManifest written: {manifest_path}")
    return manifest


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Assemble a full article via the v2 pipeline (22-step orchestrator)"
    )
    parser.add_argument("--site", required=True, help="Site slug (e.g., lrg, valn)")
    parser.add_argument("--post-id", required=True, type=int, help="WordPress post ID")
    parser.add_argument("--target-keyword", required=True, help="Target keyword")
    parser.add_argument(
        "--intent",
        choices=["definition", "process", "decision", "cost", "comparison"],
        help="Intent type (auto-detected if omitted)",
    )
    parser.add_argument(
        "--status", default="draft", choices=["draft", "publish"],
        help="WordPress post status (default: draft)",
    )
    parser.add_argument(
        "--output-dir",
        help="Output directory (default: ~/<site>-rewrite/articles-v2/)",
    )
    parser.add_argument("--skip-deploy", action="store_true", help="Don't push to WordPress")
    parser.add_argument("--allow-no-serp", action="store_true", help="Skip SERP research")
    parser.add_argument("--force", action="store_true", help="Overwrite existing outputs")
    args = parser.parse_args()

    # Initialize state
    state = PipelineState()
    state.site_slug = args.site
    state.post_id = args.post_id
    state.target_keyword = args.target_keyword
    state.intent = args.intent or ""
    state.status = args.status
    state.start_time = time.time()

    # Output directory
    if args.output_dir:
        state.output_dir = Path(args.output_dir)
    else:
        state.output_dir = Path.home() / f"{args.site}-rewrite" / "articles-v2"
    state.output_dir.mkdir(parents=True, exist_ok=True)

    # Idempotency check
    article_path = state.output_dir / f"{state.post_id}-article.html"
    if article_path.exists() and not args.force:
        eprint(f"Outputs exist for post {state.post_id} at {article_path}.")
        eprint("Use --force to overwrite.")
        sys.exit(1)

    eprint(f"{'=' * 60}")
    eprint(f"ASSEMBLE-ARTICLE v2 Pipeline")
    eprint(f"  Site: {state.site_slug}")
    eprint(f"  Post ID: {state.post_id}")
    eprint(f"  Keyword: {state.target_keyword}")
    eprint(f"  Output: {state.output_dir}")
    eprint(f"{'=' * 60}\n")

    # Run pipeline
    try:
        phase_a(state)
        phase_b(state, allow_no_serp=args.allow_no_serp)
        phase_c(state)
        phase_d(state)
        phase_e(state)
        phase_f(state)
        phase_g(state)
        phase_h(state)
        phase_i(state, skip_deploy=args.skip_deploy)
    except RuntimeError as e:
        eprint(f"\nPIPELINE FAILED")
        eprint(f"Phases completed: {state.phases_completed}")
        eprint(f"Error: {e}")
        eprint(f"\nPartial outputs in: {state.output_dir}")
        _write_manifest(state)
        sys.exit(1)
    except KeyboardInterrupt:
        eprint("\nPipeline interrupted by user.")
        _write_manifest(state)
        sys.exit(130)

    # Write manifest
    manifest = _write_manifest(state)

    # Summary
    elapsed = time.time() - state.start_time
    eprint(f"\n{'=' * 60}")
    eprint(f"PIPELINE COMPLETE")
    eprint(f"  Phases: {' → '.join(state.phases_completed)}")
    eprint(f"  H2 sections: {len(state.h2_inventory)}")
    eprint(f"  LLM calls: {state.llm_calls}")
    eprint(f"  Cost estimate: ${state.llm_cost:.4f}")
    eprint(f"  Elapsed: {elapsed:.0f}s")
    eprint(f"  Output: {state.output_dir / f'{state.post_id}-article.html'}")
    eprint(f"{'=' * 60}")


if __name__ == "__main__":
    main()
