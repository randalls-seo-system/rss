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
        [--force]                       \\
        [--h2-override <json-file>]     \\
        [--accept-generic]

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

# Load .env from repo root so subprocesses inherit SERP keys
_env_file = REPO_ROOT / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_file)
    except ImportError:
        with open(_env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    os.environ.setdefault(key.strip(), val.strip())

from bs4 import BeautifulSoup

from lib.anchor_pool import AnchorPool
from lib.html_sanitizer import sanitize_assembled_html
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
    load_structural_template,
    render_prompt,
    validate_or_retry,
    write_output,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PYTHON = sys.executable
LLM_CALL_TIMEOUT = 300  # 5 minutes per LLM call

# Mechanical tasks (H2 normalize, polish) use OpenAI to save Opus for content.
MECHANICAL_PROVIDER = "openai"
MECHANICAL_MODEL = "gpt-5.4-mini"

# ---------------------------------------------------------------------------
# Geo-scope filter — prevents multi-locale H2 drift on locale-specific articles
# ---------------------------------------------------------------------------

GEO_ADJACENCY = {
    'austin': ['round rock', 'pflugerville', 'cedar park', 'leander', 'buda', 'kyle',
               'dripping springs', 'lakeway', 'bee cave', 'georgetown', 'hutto',
               'manor', 'travis county', 'williamson county'],
    'san antonio': ['jbsa', 'lackland', 'randolph', 'fort sam houston', 'camp bullis',
                    'alamo heights', 'stone oak', 'helotes', 'leon valley', 'shavano park',
                    'live oak', 'converse', 'schertz', 'universal city', 'selma',
                    'bexar county', 'castle hills', 'olmos park', 'terrell hills',
                    'medical center', 'southtown', 'dominion', 'rogers ranch',
                    'alamo ranch', 'pearl district', 'king william', 'monte vista'],
    'killeen': ['fort cavazos', 'fort hood', 'harker heights', 'copperas cove',
                'temple', 'belton', 'bell county'],
    'new braunfels': ['gruene', 'canyon lake', 'comal county', 'garden ridge'],
    'corpus christi': ['nas corpus christi', 'portland', 'flour bluff', 'calallen',
                       'padre island', 'rockport', 'port aransas', 'nueces county'],
    'boerne': ['fair oaks ranch', 'kendall county', 'comfort'],
    'seguin': ['guadalupe county'],
    'round rock': ['austin', 'pflugerville', 'cedar park', 'hutto', 'williamson county'],
    'georgetown': ['sun city', 'williamson county', 'round rock'],
}

_ALL_GEOS = sorted(set([
    'san antonio', 'austin', 'killeen', 'new braunfels', 'corpus christi',
    'round rock', 'georgetown', 'boerne', 'seguin', 'pflugerville',
    'cedar park', 'dripping springs', 'bastrop', 'marble falls',
    'spring branch', 'bulverde', 'helotes', 'schertz', 'cibolo',
    'converse', 'selma', 'buda', 'kyle', 'leander', 'hutto',
    'temple', 'waco', 'fredericksburg', 'kerrville',
    'fort cavazos', 'fort hood', 'jbsa', 'lackland', 'randolph',
    'fort sam houston', 'camp bullis',
    'abilene', 'dallas', 'houston', 'el paso', 'lubbock',
    'wichita falls', 'del rio', 'laughlin', 'goodfellow',
    'san marcos', 'canyon lake',
    'alamo heights', 'stone oak', 'dominion', 'shavano park',
    'terrell hills', 'olmos park', 'leon valley',
    'portland', 'flour bluff', 'calallen', 'padre island',
    'harker heights', 'copperas cove', 'belton',
    'nas corpus christi',
]), key=len, reverse=True)


def _detect_multi_geo_intent(keyword: str) -> bool:
    """Return True if the keyword indicates a multi-geo or statewide article."""
    kw = keyword.lower()
    if any(w in kw for w in [' vs ', ' versus ', ' compared to ', ' between ']):
        return True
    if any(w in kw for w in ['texas', 'central texas', 'hill country', 'statewide']):
        return True
    if re.search(r'best\s+\w+\s+(?:in|for|near)\b', kw):
        after = re.search(r'best\s+\w+\s+(?:in|for|near)\s+(.+)', kw)
        if after and not any(geo in after.group(1) for geo in _ALL_GEOS):
            return True
    return False


def _filter_subtopics_by_geo(keyword: str, subtopics: list) -> list:
    """Filter subtopics containing off-target geos. Returns filtered list."""
    if _detect_multi_geo_intent(keyword):
        return subtopics

    kw = keyword.lower()
    target_geo = None
    for geo in _ALL_GEOS:
        if geo in kw:
            target_geo = geo
            break
    if not target_geo:
        return subtopics

    allowed = {target_geo}
    if target_geo in GEO_ADJACENCY:
        allowed.update(GEO_ADJACENCY[target_geo])

    kept = []
    for st in subtopics:
        title = st if isinstance(st, str) else st.get('subtopic', st.get('heading', str(st)))
        title_lower = title.lower() if isinstance(title, str) else str(title).lower()

        if target_geo in title_lower:
            kept.append(st)
            continue

        off_geo_found = False
        for geo in _ALL_GEOS:
            if geo in title_lower and geo not in allowed:
                eprint(f"  [geo-filter] Dropped subtopic: '{title}' (contains off-target '{geo}')")
                off_geo_found = True
                break

        if not off_geo_found:
            kept.append(st)

    return kept


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
    hub_box_html: str = ""
    build_hub_box: bool = False

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
                    "--output-json", str(serp_path),
                    "--site", state.site_slug,
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
                gaps_output_path = state.output_dir / f"{state.post_id}-subtopic-gaps.json"
                _run_tool(str(gaps_tool), [
                    "--serp-json", str(state.serp_json_path),
                    "--output", str(gaps_output_path),
                ], "B.8")
                if gaps_output_path.exists():
                    state.subtopic_gaps = json.loads(gaps_output_path.read_text())
                else:
                    state.subtopic_gaps = {}
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

    # If SERP unavailable, write a minimal valid SERP JSON for downstream tools
    if state.serp_json_path is None:
        empty_serp_path = state.output_dir / f"{state.post_id}-empty-serp.json"
        empty_serp_path.write_text(json.dumps({
            "keyword": state.target_keyword,
            "providers_used": [],
            "queried_at": "",
            "intent_signals": {},
            "top_results": [],
            "paa": [],
            "related_searches": [],
            "ai_overview": None,
        }))
        state.serp_json_path = empty_serp_path
        eprint(f"  [B.10] Wrote empty SERP fallback: {empty_serp_path}")

    state.phases_completed.append("B")


# ---------------------------------------------------------------------------
# Phase C: Structure Planning
# ---------------------------------------------------------------------------

def _load_h2_override(state: PipelineState) -> list[dict]:
    """Load manual H2 inventory from --h2-override JSON file."""
    override_path = Path(state.h2_override_path)
    if not override_path.exists():
        raise RuntimeError(f"--h2-override file not found: {override_path}")

    with open(override_path) as f:
        data = json.load(f)

    items = data.get("h2_inventory") or data
    if not isinstance(items, list) or len(items) == 0:
        raise RuntimeError(f"--h2-override JSON must contain a non-empty 'h2_inventory' list")

    h2s = []
    for item in items:
        if isinstance(item, str):
            h2s.append({"title": item, "role": "manual_override", "source": "h2_override"})
        elif isinstance(item, dict):
            title = item.get("title", "")
            if not title:
                raise RuntimeError(f"H2 override item missing 'title': {item}")
            entry = {
                "title": title,
                "role": "manual_override",
                "source": "h2_override",
            }
            if item.get("framing"):
                entry["framing"] = item["framing"]
            h2s.append(entry)

    eprint(f"  [C.10] Loaded {len(h2s)} H2s from --h2-override")
    for h in h2s:
        eprint(f"    - {h['title']}")
    return h2s


def phase_c(state: PipelineState) -> None:
    """Build H2 inventory, header prelude, jump nav."""
    eprint("PHASE C: Structure Planning")

    # Step 10: Build H2 inventory
    eprint("  [C.10] Building H2 inventory")
    if getattr(state, "h2_override_path", None):
        h2s = _load_h2_override(state)
    else:
        h2s = _build_h2_inventory(state)
    state.h2_inventory = h2s
    eprint(f"  [C.10] Raw H2 inventory: {len(h2s)} sections")

    # Step 10b: Natural-language H2 normalization via LLM
    eprint("  [C.10b] Normalizing H2 titles via LLM")
    h2s = _normalize_h2_titles(state, h2s)
    state.h2_inventory = h2s
    eprint(f"  [C.10b] Normalized H2 inventory: {len(h2s)} sections")
    for h in h2s:
        eprint(f"    - {h['title']} [{h['structural_element']}]")

    # Safety check: detect generic-template H2s that signal fallback was used
    _GENERIC_MARKERS = [
        "what to expect", "common mistakes", "how to get started",
        "how should you get started", "how do you get started",
        "costs and timeline", "frequently overlooked", "next steps after",
    ]
    generic_count = sum(
        1 for h in h2s
        if any(m in h["title"].lower() for m in _GENERIC_MARKERS)
    )
    if generic_count >= 4:
        if not getattr(state, "accept_generic", False):
            raise RuntimeError(
                f"SAFETY: {generic_count} of {len(h2s)} H2s match generic-template "
                f"patterns. This usually means SERP scraping failed and the pipeline "
                f"fell back to template H2s. Article quality will be poor.\n"
                f"  Options:\n"
                f"  1. Supply --h2-override <json-file> with topic-specific H2s\n"
                f"  2. Pass --accept-generic to override this check (not recommended)\n"
                f"  H2s: {[h['title'] for h in h2s]}"
            )
        eprint(f"  [C.10] WARNING: {generic_count} generic-template H2s detected, --accept-generic overriding")

    # Step 11: Build header prelude (deterministic)
    eprint("  [C.11] Building header prelude")
    state.header_html = _build_header_prelude(state)

    # Step 12: Build jump nav
    eprint("  [C.12] Building jump nav")
    state.jump_nav_html = _build_jump_nav(state)

    state.phases_completed.append("C")


def _generate_fallback_h2s(state: PipelineState, existing: list[str], needed: int) -> list[str]:
    """Generate natural-language fallback H2 titles via LLM when SERP gaps are insufficient."""
    kw = state.target_keyword
    existing_str = "\n".join(f"- {t}" for t in existing) if existing else "(none yet)"

    prompt = f"""Generate {needed} section headings for an article about "{kw}".
Intent: {state.intent}.

Existing headings already chosen:
{existing_str}

Generate {needed} MORE headings that complement the existing ones. RULES:
- NEVER use "What Is {kw}", "How {kw} Works", "Who Qualifies For {kw}" patterns.
- Each heading should be natural, specific, and 5-12 words.
- Mix questions (ending in ?) and statements.
- Cover different angles: costs, timelines, eligibility, comparisons, practical tips.
- Do NOT repeat topics already covered in the existing headings.

Return a JSON array of {needed} strings. No commentary."""

    client = LLMClient(provider=state.provider, model=state.model)
    import hashlib
    h = hashlib.md5(f"{kw}|{state.intent}|{needed}|{existing_str}".encode()).hexdigest()[:12]
    cache_key = f"{state.site_slug}|{kw}|fallback-h2s|{h}"
    response = client.call(prompt, cache_key=cache_key)
    state.llm_calls += 1
    state.llm_cost += response.cost_estimate

    try:
        titles = json.loads(extract_html(response.text))
        if isinstance(titles, list):
            return [str(t) for t in titles[:needed]]
    except (json.JSONDecodeError, ValueError):
        pass

    # Hard fallback — FATAL: do not silently produce generic-template articles
    raise RuntimeError(
        "FATAL: SERP scraper yielded zero usable subtopics AND LLM fallback H2 "
        "generation failed. Pipeline cannot generate topic-specific H2s. "
        "Supply --h2-override <json-file> with manual H2 inventory, or fix SERP data."
    )


def _build_h2_inventory(state: PipelineState) -> list[dict]:
    """Build H2 section inventory from overlay + SERP gaps."""
    h2s = []
    overlay = state.overlay
    body_default = overlay.body_default

    # Load structural template for this intent (deterministic assignment)
    struct_template = load_structural_template(state.intent)
    template_sections = struct_template.get("sections", []) if struct_template else []
    # Build a lookup from 0-based body index → template section
    # Template uses 1-based index where 1 = BLUF, so body section i maps to index i+2
    template_by_index = {s["index"]: s for s in template_sections}

    # Start from SERP gap analysis: high-coverage subtopics
    high_cov = state.subtopic_gaps.get("high_coverage", [])
    med_cov = state.subtopic_gaps.get("medium_coverage", [])
    low_cov = state.subtopic_gaps.get("low_coverage_gaps", [])

    # Geo-scope filter: drop subtopics containing off-target geo terms
    pre_count = len(high_cov) + len(med_cov) + len(low_cov)
    high_cov = _filter_subtopics_by_geo(state.target_keyword, high_cov)
    med_cov = _filter_subtopics_by_geo(state.target_keyword, med_cov)
    low_cov = _filter_subtopics_by_geo(state.target_keyword, low_cov)
    post_count = len(high_cov) + len(med_cov) + len(low_cov)
    if post_count < pre_count:
        eprint(f"  [C.10] Geo-filter: dropped {pre_count - post_count} off-target subtopic(s)")

    # Build H2 titles from gaps
    def _extract_gap_title(item):
        if isinstance(item, str):
            return item
        # Gap items may use "heading", "subtopic", or "topic" as key
        for key in ("heading", "subtopic", "topic", "title"):
            if key in item and isinstance(item[key], str):
                return item[key]
        return str(item)

    for item in high_cov[:6]:
        h2s.append({"title": _extract_gap_title(item), "role": "high_coverage", "source": "serp"})

    for item in med_cov[:4]:
        h2s.append({"title": _extract_gap_title(item), "role": "medium_coverage", "source": "serp"})

    # Add 1-2 competitive moat subtopics from low-coverage gaps
    for item in low_cov[:2]:
        h2s.append({"title": _extract_gap_title(item), "role": "competitive_moat", "source": "gap"})

    # If SERP gave us fewer than 6, pad from PAA questions
    if len(h2s) < 6 and state.serp:
        for paa in state.serp.paa_questions:
            if len(h2s) >= 10:
                break
            q = paa.question if hasattr(paa, "question") else str(paa)
            if not any(h["title"].lower() == q.lower() for h in h2s):
                h2s.append({"title": q, "role": "paa_derived", "source": "paa"})

    # Fallback: if still too few, generate natural H2s via LLM
    if len(h2s) < 6:
        needed = 6 - len(h2s)
        existing_titles = [h["title"] for h in h2s]
        fallback_h2s = _generate_fallback_h2s(state, existing_titles, needed)
        for fb in fallback_h2s:
            if len(h2s) >= 6:
                break
            h2s.append({"title": fb, "role": "fallback", "source": "llm_fallback"})

    # Trim to max 15
    h2s = h2s[:15]

    # Assign structural elements from template (deterministic)
    callout_prefs = overlay.callout_preferences
    # Map template roles to archetype callout keys/labels
    _CALLOUT_DEFAULTS = {
        "cost_surprise": ("deal_math", "Deal Math"),
        "operator_note": ("file_guidance", "File Guidance"),
        "when_each_wins": ("deal_saver", "Deal Saver"),
        "common_mistake": ("approval_watchpoint", "Approval Watchpoint"),
        "clear_definition": ("file_guidance", "File Guidance"),
        "common_confusion": ("approval_watchpoint", "Approval Watchpoint"),
        "disqualifier": ("approval_watchpoint", "Approval Watchpoint"),
        "key_insight": ("file_guidance", "File Guidance"),
    }

    for i, h2 in enumerate(h2s):
        template_idx = i + 2  # body sections start at template index 2
        tmpl = template_by_index.get(template_idx)

        if tmpl:
            stype = tmpl["type"]
            # Map prose_optional_table to bullets for CLI compatibility
            if stype == "prose_optional_table":
                stype = "bullets"
            h2["structural_element"] = stype
            h2["template_role"] = tmpl.get("role", "")
            h2["template_hint"] = tmpl.get("hint", "")
            h2["h2_format"] = tmpl.get("h2_format", "statement")
        else:
            # Sections beyond template range get prose_optional_table → bullets
            h2["structural_element"] = "bullets"
            h2["template_role"] = "overflow"
            h2["template_hint"] = ""
            h2["h2_format"] = "statement"

        # For h2-override entries, inject framing as template_hint if not already set
        if h2.get("source") == "h2_override" and h2.get("framing") and not h2.get("template_hint"):
            h2["template_hint"] = h2["framing"]

        # Assign callout key/label for callout-type sections
        if h2["structural_element"] == "callout":
            tmpl_role = h2.get("template_role", "")
            default_key, default_label = _CALLOUT_DEFAULTS.get(
                tmpl_role, ("file_guidance", "File Guidance")
            )
            h2["callout_key"] = default_key
            h2["callout_label"] = default_label
        else:
            h2["callout_key"] = ""
            h2["callout_label"] = ""

    return h2s


def _normalize_h2_titles(state: PipelineState, h2s: list[dict]) -> list[dict]:
    """Rewrite raw H2 titles to natural language via a single LLM call."""
    if not h2s:
        return h2s

    raw_list = "\n".join(f"{i+1}. {h['title']}" for i, h in enumerate(h2s))
    import hashlib
    raw_hash = hashlib.md5(raw_list.encode()).hexdigest()[:12]

    kw = state.target_keyword

    # Build format requirements from template
    format_lines = []
    for i, h in enumerate(h2s):
        fmt = h.get("h2_format", "statement")
        format_lines.append(f"  {i+1}. MUST be a {fmt.upper()} — {'ends with ?' if fmt == 'question' else 'no question mark'}")
    format_block = "\n".join(format_lines)

    prompt = f"""You will receive a list of H2 titles and their required formats.

For each H2:
- If REQUIRED_FORMAT is 'statement': output as a statement.
- If REQUIRED_FORMAT is 'question': output as a question ending with '?'.

CRITICAL: Every H2 with REQUIRED_FORMAT='question' MUST end with '?'. If you output a question-format H2 without '?', you have failed the task.

EXAMPLES OF TRANSFORMATION:
- 'Buydown Costs by Type' + format=question → 'How Much Does a Buydown Cost?'
- 'How the 1% Rule Affects a VA Loan' + format=question → 'How Does the 1% Rule Affect a VA Loan?'
- 'What to Expect from a VA Loan Rate Buydown' + format=question → 'What Should You Expect from a VA Loan Rate Buydown?'
- 'Can You Lower Your Rate?' + format=question → 'Can You Lower Your Rate?' (already a question, keep)
- 'How Do Points Work?' + format=statement → 'How Do Points Work?' (keep — questions can stay questions)

FORBIDDEN PATTERNS:
NEVER output a body H2 containing 'FAQ' or 'FAQs'. These belong only in the closing FAQ section. If the input contains these words, rewrite to remove them. Examples:
- 'VA Loan Buydown FAQs' + format=statement → 'Common VA Loan Buydown Questions'
- 'Buydown FAQ Section' + format=question → 'What Are the Most Common Buydown Questions?'
NEVER use these generic patterns:
  "What Is {kw}" → rewrite to a specific question or statement
  "How {kw} Works" → rewrite to describe the mechanism specifically
  "Who Qualifies For {kw}" → rewrite as "Are You Eligible?" or similar
  "Key Benefits of {kw}" → rewrite to name the specific benefit
  "{kw} Requirements" → rewrite to name what's actually required
  "Common Questions About {kw}" → remove entirely, FAQs handle this

ORDER: Return H2s in the SAME order as input. Do not skip, reorder, add, or remove titles. Output length must equal input length.

ADDITIONAL RULES:
- The full target keyword "{kw}" may appear in at most 2 of the H2s. Not all.
- H2s should sound like a knowledgeable human writer, not a keyword tool.
- Keep H2s 5-12 words each.
- Preserve topical coverage of the original. Don't drop subtopics.

---

Article topic: "{kw}"
Intent: {state.intent}

Raw H2 inventory (from SERP gap analysis):
{raw_list}

REQUIRED FORMAT per section (from the article template):
{format_block}

Return a JSON array of strings, one H2 per array element, same order as input. No commentary, no markdown fences, just the JSON."""

    client = LLMClient(provider=MECHANICAL_PROVIDER, model=MECHANICAL_MODEL)
    cache_key = f"{state.site_slug}|{kw}|h2-normalize-v2|{raw_hash}"
    response = client.call(prompt, cache_key=cache_key)
    state.llm_calls += 1
    state.llm_cost += response.cost_estimate

    # Try parsing JSON from response — try raw first, then extract_html
    raw_text = response.text.strip()
    titles = None
    for attempt_text in [raw_text, extract_html(raw_text)]:
        try:
            # Find JSON array in the text (may have preamble)
            start = attempt_text.find("[")
            end = attempt_text.rfind("]")
            if start >= 0 and end > start:
                parsed = json.loads(attempt_text[start:end + 1])
                if isinstance(parsed, list) and len(parsed) == len(h2s):
                    titles = parsed
                    break
        except (json.JSONDecodeError, ValueError):
            continue

    if titles:
        for i, title in enumerate(titles):
            h2s[i]["title"] = str(title)
    else:
        eprint(f"  [C.10b] Warning: Failed to parse H2 normalization JSON. Keeping raw titles.")

    # Post-normalization validation: catch any remaining forbidden patterns
    forbidden_re = re.compile(
        r"^(What Is|How Does|How Is|How .+ Works?|Who Qualifies For|Key Benefits Of|Common Questions About|Why Choose|When To)\s",
        re.IGNORECASE,
    )
    kw_lower = kw.lower()
    kw_count = sum(1 for h in h2s if kw_lower in h["title"].lower())
    has_forbidden = any(forbidden_re.match(h["title"]) for h in h2s)

    if has_forbidden or kw_count > 2:
        eprint(f"  [C.10b] Post-validation: {kw_count} H2s contain full keyword, "
               f"forbidden patterns: {has_forbidden}. Re-normalizing...")
        cache_key2 = f"{state.site_slug}|{kw}|h2-normalize-v2-retry|{raw_hash}"
        retry_list = "\n".join(f"{i+1}. {h['title']}" for i, h in enumerate(h2s))
        retry_prompt = (
            f"These H2 titles still contain SEO-spammy patterns. Fix them.\n\n"
            f"Current titles:\n{retry_list}\n\n"
            f"Target keyword: \"{kw}\"\n\n"
            f"REQUIRED FORMAT per section:\n{format_block}\n\n"
            f"RULES: No title may start with 'What Is', 'How Does', 'Who Qualifies For', "
            f"'Key Benefits Of', or 'Common Questions About'. "
            f"The full keyword '{kw}' may appear in at most 2 titles. "
            f"Every H2 with format=QUESTION must end with '?'. "
            f"No H2 may contain 'FAQ' or 'FAQs'. "
            f"Rewrite every violating title to sound natural and specific.\n\n"
            f"Return a JSON array of strings. No commentary."
        )
        resp2 = client.call(retry_prompt, cache_key=cache_key2)
        state.llm_calls += 1
        state.llm_cost += resp2.cost_estimate
        raw2 = resp2.text.strip()
        parsed2 = None
        for t2 in [raw2, extract_html(raw2)]:
            try:
                s2 = t2.find("[")
                e2 = t2.rfind("]")
                if s2 >= 0 and e2 > s2:
                    p2 = json.loads(t2[s2:e2 + 1])
                    if isinstance(p2, list) and len(p2) == len(h2s):
                        parsed2 = p2
                        break
            except (json.JSONDecodeError, ValueError):
                continue
        if parsed2:
            for i, title in enumerate(parsed2):
                h2s[i]["title"] = str(title)
            eprint("  [C.10b] Re-normalization succeeded.")
        else:
            eprint("  [C.10b] Re-normalization parse failed. Keeping first-pass titles.")

    # Programmatic enforcement: question-format H2s MUST end with '?'
    question_starters = re.compile(
        r"^(who|what|how|when|where|why|is|are|can|do|does|will|should|would|could|which)\s",
        re.IGNORECASE,
    )
    for i, h in enumerate(h2s):
        if h.get("h2_format") == "question" and not h["title"].strip().endswith("?"):
            title = h["title"].strip()
            if question_starters.match(title):
                # Already reads as a question, just missing punctuation
                h2s[i]["title"] = title + "?"
                eprint(f"  [C.10b] Appended '?' to question-format H2 #{i+1}: {h2s[i]['title']}")
            else:
                # Not a natural question — flag but don't break
                eprint(f"  [C.10b] WARNING: H2 #{i+1} is format=question but not a question: {title}")

    # Programmatic enforcement: no FAQ/FAQs in any body H2
    for i, h in enumerate(h2s):
        title_upper = h["title"].upper()
        if "FAQS" in title_upper or "FAQ" in title_upper:
            h2s[i]["title"] = re.sub(r"\bFAQs?\b", "Questions", h["title"], flags=re.IGNORECASE)
            eprint(f"  [C.10b] Stripped FAQ from H2 #{i+1}: {h2s[i]['title']}")

    return h2s


def _build_header_prelude(state: PipelineState) -> str:
    """Build deterministic header HTML (H1 + eyebrow only).

    Byline/Updated date removed — RSS Meta Header plugin renders these
    at WordPress level. Primary sources removed — handled by Resources section.
    """
    config = state.config
    kw = state.target_keyword
    cta_url = config.get("CTA_URL", "/compare-loan-offers/")
    cta_text = config.get("CTA_TEXT", "Get Your Rate")

    # Append ?ref=<post-slug> for lead attribution
    post_slug = re.sub(r"[^a-z0-9]+", "-", kw.lower()).strip("-")
    if "?" not in cta_url:
        cta_url_with_ref = f"{cta_url}?ref={post_slug}"
    else:
        cta_url_with_ref = f"{cta_url}&ref={post_slug}"

    header = (
        f'<header class="rl-hero">\n'
        f'  <div class="rl-eyebrow">{state.intent.title()} &middot; Guide</div>\n'
        f'  <h1>{kw.title()}</h1>\n'
        f'  <a href="{cta_url_with_ref}" class="rl-cta-primary">{cta_text} →</a>\n'
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

    # Step 14: Build 4 ATF cards (sequential, with synthesis diversity)
    eprint("  [D.14] Building 4 ATF cards")
    state.card_htmls = []
    prior_cards_synthesis: list[str] = []
    for i, slot in enumerate(state.overlay.card_slots):
        eprint(f"  [D.14.{i+1}] Card: {slot.role}")
        card_tool = TOOLS_DIR / "build-card.py"
        output_path = state.output_dir / f"{state.post_id}-card-{slot.role}.html"
        card_args = [
            "--site", state.site_slug,
            "--target-keyword", state.target_keyword,
            "--intent", state.intent,
            "--card-slot", slot.role,
            "--serp-json", serp_json,
            "--output", str(output_path),
        ]
        if prior_cards_synthesis:
            card_args += ["--prior-cards-synthesis", json.dumps(prior_cards_synthesis)]
        try:
            _run_tool(str(card_tool), card_args, f"D.14.{i+1}")
            card_html = output_path.read_text()
            state.card_htmls.append(card_html)
            state.llm_calls += 1
            # Extract synthesis bullet (last <li>) for diversity tracking
            card_soup = BeautifulSoup(card_html, "html.parser")
            bullets = card_soup.find_all("li")
            if bullets:
                prior_cards_synthesis.append(bullets[-1].get_text(strip=True))
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
            "--serp-json", serp_json,
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
    prior_sections_summary = ""

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
        if h2.get("template_hint"):
            args_list += ["--template-hint", h2["template_hint"]]
        if h2.get("h2_format"):
            args_list += ["--h2-format", h2["h2_format"]]
        if prior_sections_summary:
            args_list += ["--prior-sections-summary", prior_sections_summary]

        try:
            _run_tool(str(section_tool), args_list, f"F.18.{i+1}")
            section_html = section_path.read_text()
            state.body_section_htmls.append(section_html)
            state.llm_calls += 1

            # Build running summary for cross-section context (Fix 5)
            sec_soup = BeautifulSoup(section_html, "html.parser")
            sec_p = sec_soup.find("p")
            if sec_p:
                sec_summary = f"[{h2['title']}]: {sec_p.get_text(strip=True)[:150]}"
                prior_sections_summary += sec_summary + "\n"
                # Cap at ~500 words to prevent prompt bloat
                words = prior_sections_summary.split()
                if len(words) > 500:
                    prior_sections_summary = " ".join(words[-400:]) + "\n"
        except RuntimeError as e:
            raise RuntimeError(
                f"Phase F step 18 (body H2) failed for section #{i+1}: "
                f'"{h2["title"]}".\nReason: {e}\n'
                f"Debug: Re-run build-h2-section.py with the same args to iterate."
            )

    # Step 19: Mid-article CTA pill after 2nd or 3rd H2
    cta_url = state.config.get("CTA_URL", "/compare-loan-offers/")
    cta_text = state.config.get("CTA_TEXT", "Get Your Rate")
    post_slug = re.sub(r"[^a-z0-9]+", "-", state.target_keyword.lower()).strip("-")
    cta_url_ref = f"{cta_url}?ref={post_slug}" if "?" not in cta_url else f"{cta_url}&ref={post_slug}"
    cta_position = min(2, len(state.body_section_htmls) - 1)
    state.mid_cta_html = (
        f'<div class="rl-cta-mid">'
        f'<a href="{cta_url_ref}" class="rl-cta-pill">{cta_text} →</a>'
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

    # Step 23: Hub box (Explore Resources cluster links, spec §7.5 — opt-in only)
    if state.build_hub_box:
        eprint("  [G.23] Building hub box (--build-hub-box requested)")
        hub_box_tool = TOOLS_DIR / "build-hub-box.py"
        hub_box_path = state.output_dir / f"{state.post_id}-hub-box.html"
        try:
            _run_tool(str(hub_box_tool), [
                "--site", state.site_slug,
                "--target-keyword", state.target_keyword,
                "--post-id", str(state.post_id),
                "--output", str(hub_box_path),
            ], "G.23")
            state.hub_box_html = hub_box_path.read_text().strip()
            if state.hub_box_html:
                eprint(f"  [G.23] Hub box built ({state.hub_box_html.count('<li>')} links)")
            else:
                eprint("  [G.23] Hub box omitted (insufficient cluster pages)")
        except RuntimeError as e:
            eprint(f"  [G.23] Hub box build failed (non-blocking): {e}")
            state.hub_box_html = ""
    else:
        eprint("  [G.23] Skipped (hub box is opt-in, use --build-hub-box for cluster hubs)")

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
    if state.hub_box_html:
        parts.append(state.hub_box_html)
    if state.bluf_html:
        parts.append(state.bluf_html)
    parts.extend(state.body_section_htmls)  # includes mid CTA
    parts.extend([
        state.closing_html,
        state.btf_faqs_html,
        state.resources_html,
    ])

    assembled = "\n\n".join(p for p in parts if p.strip())
    assembled_path = state.output_dir / f"{state.post_id}-assembled-raw.html"
    assembled_path.write_text(assembled)

    # Step 24b: Sanitize assembled HTML (catches upstream defects)
    eprint("  [H.24b] Running post-assembly sanitizer")
    assembled, san_errors = sanitize_assembled_html(assembled)
    if san_errors:
        eprint(f"  [H.24b] SANITIZER HARD STOP — {len(san_errors)} error(s):")
        for err in san_errors:
            eprint(f"    FAIL: {err}")
        sanitized_path = state.output_dir / f"{state.post_id}-assembled-sanitized.html"
        sanitized_path.write_text(assembled)
        raise RuntimeError(
            f"Phase H step 24b (sanitizer) found {len(san_errors)} error(s). "
            f"Fix upstream section builders.\n"
            + "\n".join(f"  - {e}" for e in san_errors)
        )
    eprint("  [H.24b] Sanitizer: PASS")

    # Step 25: Inject internal links
    eprint("  [H.25] Injecting internal links")
    linked_path = state.output_dir / f"{state.post_id}-article.html"
    pending_path = state.output_dir / f"{state.post_id}-pending-links.json"
    inject_tool = TOOLS_DIR / "inject-internal-links.py"

    try:
        _run_tool(str(inject_tool), [
            "--site", state.site_slug,
            "--target-keyword", state.target_keyword,
            "--html-input", str(assembled_path),
            "--html-output", str(linked_path),
            "--pending-links-output", str(pending_path),
            "--exclude-post-id", str(state.post_id),
        ], "H.25")
        state.assembled_html = linked_path.read_text()
        if pending_path.exists():
            state.pending_links = json.loads(pending_path.read_text())
    except RuntimeError as e:
        eprint(f"  [H.25] Link injection failed (non-fatal): {e}")
        state.assembled_html = assembled
        linked_path.write_text(assembled)

    # Step 26: Validate and route output
    eprint("  [H.26] Running validation")
    validator = TOOLS_DIR / "validate-article-v2.py"
    validation_report_path = state.output_dir / f"{state.post_id}-validation-report.md"

    hard_passed = 0
    hard_total = 30
    if validator.exists():
        validator_content = validator.read_text()
        if "NotImplementedError" in validator_content:
            eprint("  [H.26] Validator is still a stub — skipping validation")
        else:
            try:
                # Run validator in JSON mode to parse scores
                json_report = _run_tool(str(validator), [
                    "--html-file", str(linked_path),
                    "--intent", state.intent,
                    "--serp-json", str(state.serp_json_path),
                    "--site", state.site_slug,
                    "--output-format", "json",
                ], "H.26")
                vdata = json.loads(json_report)
                hard_passed = vdata.get("summary", {}).get("hard_passed", 0)
                hard_total = vdata.get("summary", {}).get("hard_total", 30)
                # Write markdown report too
                validation_report_path.write_text(json_report)
                eprint(f"  [H.26] Validator: {hard_passed}/{hard_total} hard passed")
            except RuntimeError as e:
                # Validator exits 1 on hard failures — parse from stderr
                err_str = str(e)
                import re as _re
                score_match = _re.search(r"(\d+)/(\d+) hard passed", err_str)
                if score_match:
                    hard_passed = int(score_match.group(1))
                    hard_total = int(score_match.group(2))
                eprint(f"  [H.26] Validator: {hard_passed}/{hard_total} hard passed")
    else:
        eprint("  [H.26] Validator not found — skipping validation")

    # Route output: 25+ = ready, <25 = needs review
    if hard_passed < 25 and hard_total > 0:
        review_path = state.output_dir / f"{state.post_id}-article.review.html"
        import shutil
        shutil.copy2(str(linked_path), str(review_path))
        eprint(f"  [H.26] Below threshold ({hard_passed}/{hard_total} < 25/30) → saved as .review.html")

    state.phases_completed.append("H")


# ---------------------------------------------------------------------------
# Phase H2: Polish Pass
# ---------------------------------------------------------------------------

def phase_polish(state: PipelineState, skip: bool = False) -> None:
    """Final prose polish via LLM — fixes awkward phrasing, em dashes, filler."""
    if skip:
        eprint("  [Polish] --skip-polish: skipping prose polish")
        return

    eprint("  [Polish] Running final prose polish pass")
    article_path = state.output_dir / f"{state.post_id}-article.html"
    if not article_path.exists():
        eprint("  [Polish] No article file found — skipping")
        return

    html = article_path.read_text()

    # Save pre-polish version
    pre_polish_path = state.output_dir / f"{state.post_id}-article.pre-polish.html"
    pre_polish_path.write_text(html)

    prompt = f"""You are a senior SEO editor reviewing a finished article before publication. Read the article and fix ONLY these issues:

1. Awkward phrasing or sentences that don't flow
2. Repeated phrases within close proximity (within 200 words)
3. Generic transitions ("In conclusion", "It's important to note", "When it comes to") — cut or rewrite
4. Em dashes anywhere — replace with commas, periods, or parentheses
5. Capitalization: Veteran/Veterans/Military must be capitalized, 'va' must be 'VA'
6. Numbers as words where digits are more scannable ("five percent" → "5%", "twenty-six" → "26")
7. Sentences over 35 words — split into two
8. Passive voice where active would be tighter
9. Filler adverbs ("very", "really", "extremely", "quite") — remove

Do NOT change facts, statistics, structure, H2/H3 headings, links, or HTML tags. Do NOT add new content or remove sections. Only fix surface-level prose.

Return the COMPLETE article HTML, ready to publish. No markdown fences.

ARTICLE:
{html}"""

    client = LLMClient(provider=MECHANICAL_PROVIDER, model=MECHANICAL_MODEL)
    cache_key = f"{state.site_slug}|{state.target_keyword}|polish"
    response = client.call(prompt, cache_key=cache_key, max_tokens=8192)
    state.llm_calls += 1
    state.llm_cost += response.cost_estimate

    polished = extract_html(response.text)

    # Basic sanity: polished should be within 20% length of original
    if polished and 0.8 < len(polished) / max(len(html), 1) < 1.2:
        article_path.write_text(polished)
        state.assembled_html = polished
        eprint(f"  [Polish] Polished: {len(html)} → {len(polished)} chars "
               f"({len(polished) - len(html):+d})")
    else:
        eprint(f"  [Polish] Warning: polished output size mismatch "
               f"({len(html)} → {len(polished)}). Keeping original.")


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
        if (not a["href"].startswith(("http://", "https://", "//"))
            or state.config.get("SITE_DOMAIN", "") in a["href"])
        and "rl-cta" not in " ".join(a.get("class", []))
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
        "hub_box_requested": state.build_hub_box,
        "hub_box_present": bool(state.hub_box_html),
        "hub_box_link_count": state.hub_box_html.count("<li>") if state.hub_box_html else 0,
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
    parser.add_argument("--skip-polish", action="store_true", help="Skip final prose polish LLM pass")
    parser.add_argument("--build-hub-box", action="store_true", help="Build Explore Resources hub box (opt-in for cluster hub pages)")
    parser.add_argument("--h2-override", help="JSON file with manual H2 inventory (skips SERP-driven H2 generation)")
    parser.add_argument("--accept-generic", action="store_true", help="Override generic-template H2 safety check (not recommended)")
    args = parser.parse_args()

    # Initialize state
    state = PipelineState()
    state.site_slug = args.site
    state.post_id = args.post_id
    state.target_keyword = args.target_keyword
    state.intent = args.intent or ""
    state.status = args.status
    state.build_hub_box = args.build_hub_box
    state.accept_generic = args.accept_generic
    state.h2_override_path = args.h2_override
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
        phase_polish(state, skip=args.skip_polish)
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
