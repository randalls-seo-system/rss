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
import atexit
import json
import os
import re
import signal
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
from lib.brand_rules import load_brand_rules_block as _load_brand_rules_from_config
from lib.brand_rules import validate_brand_rules
from lib.tool_utils import (
    build_topic_context,
    eprint,
    extract_html,
    load_brand_voice,
    load_business_facts,
    load_prompt_template,
    load_structural_template,
    render_prompt,
    validate_or_retry,
    write_output,
)

# Repo-root lib/ imports via importlib (avoids namespace collision with module lib/)
import importlib.util as _ilu
_gl_spec = _ilu.spec_from_file_location("gate_library", REPO_ROOT / "lib" / "gate_library.py")
_gl_mod = _ilu.module_from_spec(_gl_spec)
_gl_spec.loader.exec_module(_gl_mod)
_run_universal_gates = _gl_mod.run_universal_gates
_GateReport = _gl_mod.GateReport

_const_spec = _ilu.spec_from_file_location("constants", REPO_ROOT / "lib" / "constants.py")
_const_mod = _ilu.module_from_spec(_const_spec)
_const_spec.loader.exec_module(_const_mod)
GENERATION_CSS_PREFIX = _const_mod.GENERATION_CSS_PREFIX

# Gate config for generation-time CSS prefix check.
# Deploy-time gates check the site's config.json prefix (post-conversion).
# Generation-time gates check the pipeline's emission prefix (pre-conversion).
_GENERATION_GATE_CONFIG = {
    "content": {
        "css_prefix": [GENERATION_CSS_PREFIX],
    }
}

# Intent → gate content_type mapping. Explicit "article" default.
_INTENT_TO_CONTENT_TYPE = {
    "community-guide": "guide",
}


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PYTHON = sys.executable
LLM_CALL_TIMEOUT = 480  # 8 minutes per LLM call (raised from 300 for enriched community-guide hints)


def load_site_structure(site_slug: str) -> dict:
    """Load per-site structural overlay from sites/<slug>-structure.yaml.

    Returns dict of flags controlling which pipeline components to emit.
    If no overlay file exists, returns empty dict (all defaults = emit everything).
    """
    overlay_path = REPO_ROOT / "sites" / f"{site_slug}-structure.yaml"
    if not overlay_path.exists():
        return {}
    import yaml as _yaml
    return _yaml.safe_load(overlay_path.read_text()) or {}

# Mechanical tasks (H2 normalize, polish) use OpenAI to save Opus for content.
MECHANICAL_PROVIDER = "openai"
MECHANICAL_MODEL = "gpt-5.4-mini"


def _build_research_context_summary(rc: dict) -> str:
    """Build a text summary from research-context.json for universal LLM injection.

    Accepts any JSON structure. Looks for common fields: summary, context,
    sources, quotes, case_frame, key_facts. Falls back to serializing
    the entire dict if no recognized fields found.
    """
    parts = []
    if rc.get("summary"):
        parts.append(rc["summary"])
    if rc.get("context"):
        parts.append(rc["context"])
    if rc.get("case_frame"):
        parts.append(rc["case_frame"])
    if rc.get("key_facts"):
        if isinstance(rc["key_facts"], list):
            parts.append("\n".join(f"- {f}" for f in rc["key_facts"]))
        else:
            parts.append(str(rc["key_facts"]))
    if rc.get("quotes"):
        if isinstance(rc["quotes"], list):
            for q in rc["quotes"]:
                if isinstance(q, dict):
                    parts.append(f'Quote: "{q.get("text", "")}" — {q.get("source", "")}')
                else:
                    parts.append(f'Quote: "{q}"')
    if rc.get("sources"):
        if isinstance(rc["sources"], list):
            src_lines = ["Sources:"]
            for s in rc["sources"]:
                if isinstance(s, dict):
                    src_lines.append(f"  - {s.get('outlet', '')} ({s.get('date', '')}): {s.get('url', '')}")
                else:
                    src_lines.append(f"  - {s}")
            parts.append("\n".join(src_lines))
    # Fallback: if no recognized fields, dump the whole dict
    if not parts:
        import json as _json_fb
        parts.append(_json_fb.dumps(rc, indent=2, default=str))
    return "\n\n".join(parts)


def _build_community_atf_data(cd: dict, ratings: dict) -> tuple[str, str]:
    """Build community-guide qstats strip + rating bars from JSON data only (no LLM).

    Returns (qstats_html, rating_bars_html). Both are empty string if
    ratings block is missing or incomplete.
    """
    from html import escape as _esc

    # ── qstats strip: 4 stats from community data ──
    builders = cd.get("builders", [])
    all_prices = []
    for b in builders:
        all_prices.extend([b.get("price_low", 0), b.get("price_high", 0)])
    price_lo = min(p for p in all_prices if p > 0) if all_prices else 0
    price_hi = max(all_prices) if all_prices else 0
    price_range = f"${price_lo // 1000:,}K–${price_hi // 1000:,}K" if price_lo else "—"

    tax_rate = cd.get("tax", {}).get("base_rate", "—")
    school_district = cd.get("schools", {}).get("district", "—")

    commute_r = ratings.get("commute", {})
    drive_min = commute_r.get("drive_minutes")
    drive_dest = commute_r.get("destination", "")
    commute_val = f"{int(drive_min)} min" if drive_min else "—"
    commute_label = f"Drive to {drive_dest}" if drive_dest else "Commute"

    # Source URLs for qstats
    tax_src = cd.get("tax", {}).get("source_url", "")
    school_src = cd.get("schools", {}).get("source_url", "")
    builder_src = builders[0].get("source_url", "") if builders else ""
    commute_src = commute_r.get("source_url", "")

    stats = [
        {"value": price_range, "label": "Price Range", "source_url": builder_src},
        {"value": tax_rate, "label": "Property Tax Rate", "source_url": tax_src},
        {"value": commute_val, "label": commute_label, "source_url": commute_src},
        {"value": school_district, "label": "School District", "source_url": school_src},
    ]

    boxes = []
    for s in stats:
        boxes.append(
            f'<div class="rl-qs">'
            f'<div class="v">{_esc(s["value"])}</div>'
            f'<div class="l">{_esc(s["label"])}</div>'
            f'</div>'
        )
    qstats_html = '<div class="rl-qstats">\n' + "\n".join(boxes) + "\n</div>"

    # ── rating bars: 4 scored bars from JSON (all labeled est.) ──
    _RATING_LABELS = {
        "walkability": "Walkability",
        "dining_retail": "Dining & Retail",
        "value": "Value",
        "commute": "Commute",
    }
    _RATING_ORDER = ("walkability", "dining_retail", "value", "commute")

    bars = []
    for rkey in _RATING_ORDER:
        r = ratings.get(rkey, {})
        score = r.get("score")
        if score is None:
            continue  # assertion: no bar without JSON-sourced score
        score = float(score)
        pct = int(min(score / 10.0, 1.0) * 100)
        label = _RATING_LABELS.get(rkey, rkey.replace("_", " ").title())
        bars.append(
            f'<div class="rl-rating-bar">'
            f'<span class="rb-label">{_esc(label)}</span>'
            f'<div class="rb-track"><div class="rb-fill" style="width:{pct}%"></div></div>'
            f'<span class="rb-val">{score:.1f} <small>est.</small></span>'
            f'</div>'
        )

    if not bars:
        return qstats_html, ""

    rating_bars_html = '<div class="rl-rating-bars">\n' + "\n".join(bars) + "\n</div>"
    return qstats_html, rating_bars_html


def _build_entity_disambiguation(cd: dict) -> str:
    """Build adversarial entity disambiguation block for community-guide LLM calls."""
    builders = cd.get("builders", [])
    b_names = ", ".join(b["name"] for b in builders)
    return (
        f"SUBJECT: {cd.get('community_name', '')}, a master-planned residential community "
        f"in {cd.get('city', '')} ({cd.get('zip', '')}), {cd.get('county', '')} County, "
        f"built by {b_names}. "
        f"Located {cd.get('geo_anchor', cd.get('city', ''))}. "
        f"This is NOT a restaurant, bar, venue, or business of the same name. "
        f"Do not reference any establishment, neighborhood, or geography other than "
        f"the one described."
    )


def _validate_community_data(data: dict) -> None:
    """Validate community-data.json schema. Fail loud on missing required fields."""
    errors = []
    if not isinstance(data, dict):
        raise RuntimeError("community-data.json root must be a JSON object")

    if not data.get("community_name"):
        errors.append("Missing required field: community_name")

    builders = data.get("builders", [])
    if not isinstance(builders, list) or len(builders) == 0:
        errors.append("Missing or empty required field: builders (need >=1 builder)")
    else:
        for i, b in enumerate(builders):
            for field in ("name", "price_low", "price_high", "plan_count", "sqft_low", "sqft_high",
                          "source_url", "captured_date"):
                if field not in b or b[field] is None:
                    errors.append(f"builders[{i}] missing required field: {field}")

    tax = data.get("tax", {})
    if not isinstance(tax, dict) or not tax:
        errors.append("Missing required field: tax")
    else:
        for field in ("base_rate", "county", "source_url", "captured_date"):
            if field not in tax or not tax[field]:
                errors.append(f"tax missing required field: {field}")
        # MUD/PID: mud_name and mud_rate may be null (no district), but keys must exist
        if "mud_name" not in tax:
            errors.append("tax missing required field: mud_name (set to null if no MUD/PID)")
        if "mud_rate" not in tax:
            errors.append("tax missing required field: mud_rate (set to null if no MUD/PID)")

    schools = data.get("schools", {})
    if not isinstance(schools, dict) or not schools:
        errors.append("Missing required field: schools")
    else:
        for field in ("district", "source_url", "captured_date"):
            if field not in schools or not schools[field]:
                errors.append(f"schools missing required field: {field}")

    # worked_examples: optional, but if present all fields required
    worked = data.get("worked_examples", [])
    if worked:
        if not isinstance(worked, list):
            errors.append("worked_examples must be a list")
        else:
            for i, ex in enumerate(worked):
                if not isinstance(ex, dict):
                    errors.append(f"worked_examples[{i}] must be a dict")
                    continue
                if "example_price" not in ex or ex["example_price"] is None:
                    errors.append(f"worked_examples[{i}] missing required field: example_price")
                derived = ex.get("derived", [])
                if not isinstance(derived, list) or len(derived) == 0:
                    errors.append(f"worked_examples[{i}] missing or empty required field: derived")
                else:
                    for j, d in enumerate(derived):
                        for field in ("label", "value"):
                            if field not in d or d[field] is None:
                                errors.append(f"worked_examples[{i}].derived[{j}] missing: {field}")
                if "captured_date" not in ex or not ex["captured_date"]:
                    errors.append(f"worked_examples[{i}] missing required field: captured_date")

    # ratings: optional, but if present all 4 scores + methodology required
    ratings = data.get("ratings", {})
    if ratings:
        _REQUIRED_RATINGS = ("walkability", "dining_retail", "value", "commute")
        for rkey in _REQUIRED_RATINGS:
            r = ratings.get(rkey)
            if not isinstance(r, dict):
                errors.append(f"ratings.{rkey} must be a dict (got {type(r).__name__})")
                continue
            if "score" not in r or not isinstance(r["score"], (int, float)):
                errors.append(f"ratings.{rkey} missing or non-numeric 'score'")
            if not r.get("methodology"):
                errors.append(f"ratings.{rkey} missing required field: methodology")
            if not r.get("captured_date"):
                errors.append(f"ratings.{rkey} missing required field: captured_date")
            # commute requires destination + drive_minutes
            if rkey == "commute":
                if not r.get("destination"):
                    errors.append(f"ratings.commute missing required field: destination")
                if "drive_minutes" not in r or not isinstance(r.get("drive_minutes"), (int, float)):
                    errors.append(f"ratings.commute missing or non-numeric 'drive_minutes'")

    if errors:
        raise RuntimeError(
            f"community-data.json schema validation failed ({len(errors)} errors):\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

# ---------------------------------------------------------------------------
# FAQ topic-drift filter stopwords (shared between ATF D.15b and BTF G.21b)
# ---------------------------------------------------------------------------

_FAQ_DRIFT_STOPWORDS = {
    'neighborhood', 'neighborhoods', 'tx', 'texas', 'best', 'guide',
    'in', 'the', 'vs', 'versus',
}


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


# ---------------------------------------------------------------------------
# Slug generation
# ---------------------------------------------------------------------------

_SLUG_STOP_WORDS = frozenset({
    "in", "the", "of", "for", "an", "a", "on", "at", "with",
    "to", "and", "by", "best", "top", "your", "our", "my",
})


def generate_slug(target_keyword: str, site_structure: dict, config: dict = None) -> str:
    """Generate a short slug from target keyword using site overlay rules.

    Strategy 'keyword_first': strip market geo + stop words, truncate, hyphenate.
    If no slug config in overlay, returns empty string (caller should skip).
    """
    max_words = site_structure.get("slug_max_words", 10)
    max_chars = site_structure.get("slug_max_chars", 60)

    kw = target_keyword.lower()

    # Strip market geo (e.g., "san antonio" for GFP).
    # GEO_FOCUS may include state ("San Antonio, TX") — try both full and city-only.
    if config:
        geo_raw = config.get("GEO_FOCUS", "").lower().strip()
        if geo_raw:
            kw = kw.replace(geo_raw, "").strip()
            geo_city = geo_raw.split(",")[0].strip()
            if geo_city and geo_city != geo_raw:
                kw = kw.replace(geo_city, "").strip()

    words = kw.split()
    words = [w for w in words if w not in _SLUG_STOP_WORDS]
    words = words[:max_words]

    slug = "-".join(words)

    # Clean: remove apostrophes, special chars
    slug = re.sub(r"[']", "", slug)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")

    # Truncate to max chars at word boundary
    if len(slug) > max_chars:
        slug = slug[:max_chars].rsplit("-", 1)[0]

    return slug


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
    vertical_rules: str = ""
    overlay: object = None
    site_structure: dict = field(default_factory=dict)
    provider: str = "claude_cli"
    model: str | None = None
    output_dir: Path = Path(".")
    status: str = "draft"

    # Community data (community-guide intent)
    community_data: dict = field(default_factory=dict)
    research_context: dict = field(default_factory=dict)
    research_context_path: str | None = None

    # Phase B
    serp: object = None
    serp_json_path: Path | None = None
    subtopic_gaps: dict = field(default_factory=dict)
    target_wc: dict = field(default_factory=dict)
    evidence_path: Path | None = None
    evidence_status: str = ""
    exclude_url: str = ""
    evidence_exclusion: dict = field(default_factory=dict)

    # Phase C
    h2_inventory: list[dict] = field(default_factory=list)
    header_html: str = ""
    jump_nav_html: str = ""

    # Phase D
    atf_lede_html: str = ""
    qstats_html: str = ""
    rating_bars_html: str = ""
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

    # Step 2b: Load business facts (closed standard — appended to brand voice)
    facts = load_business_facts(state.site_slug)
    if facts:
        state.brand_voice += facts
        eprint(f"  [A.2b] Business facts loaded ({len(facts)} chars)")
    else:
        eprint(f"  [A.2b] WARNING: No business-facts file for '{state.site_slug}'. "
               f"Content may invent operational details (prices, hours, zones). "
               f"Create sites/{state.site_slug}-business-facts.md to prevent this.")

    # Step 2c: Load brand rules (competitor policy, price policy, forbidden terms)
    brand_rules = _load_brand_rules_from_config(state.config)
    if brand_rules:
        state.brand_voice += f"\n\n{brand_rules}"
        eprint(f"  [A.2c] Brand rules loaded ({len(brand_rules)} chars)")
    else:
        eprint(f"  [A.2c] No brand rules configured for '{state.site_slug}'")

    # Step 2d: Load vertical rules (real_estate, mortgage, etc.)
    from lib.brand_rules import load_vertical_rules_block
    state.vertical_rules = load_vertical_rules_block(state.site_slug)
    if state.vertical_rules:
        eprint(f"  [A.2d] Vertical rules loaded ({len(state.vertical_rules)} chars)")
    else:
        eprint(f"  [A.2d] No vertical declared for '{state.site_slug}'")

    # Step 3: Detect intent if not provided
    if not state.intent:
        state.intent = detect_intent(state.target_keyword)
        eprint(f"  [A.3] Auto-detected intent: {state.intent}")
    else:
        eprint(f"  [A.3] Intent provided: {state.intent}")

    # Step 4: Load overlay
    eprint(f"  [A.4] Loading overlay: {state.intent}")
    state.overlay = load_overlay(state.intent)

    # Step 5: Load site structural overlay
    state.site_structure = load_site_structure(state.site_slug)
    if state.site_structure:
        eprint(f"  [A.5] Site structure overlay loaded ({len(state.site_structure)} flags)")
    else:
        eprint(f"  [A.5] No site structure overlay — using defaults")

    # Step 6: Community data validation (community-guide only)
    if state.intent == "community-guide":
        cd_path = getattr(state, "community_data_path", None)
        if not cd_path:
            raise RuntimeError(
                "FATAL: --community-data is required for community-guide intent. "
                "Provide a community-data.json file with builders, tax, and schools blocks."
            )
        cd_file = Path(cd_path)
        if not cd_file.exists():
            raise RuntimeError(f"FATAL: community-data.json not found: {cd_file}")
        try:
            state.community_data = json.loads(cd_file.read_text())
        except json.JSONDecodeError as e:
            raise RuntimeError(f"FATAL: community-data.json is invalid JSON: {e}")
        # Schema validation
        _validate_community_data(state.community_data)
        eprint(f"  [A.6] Community data loaded and validated: {cd_file}")

        # Step 7: Research context validation (community-guide — strict schema)
        rc_path = state.research_context_path
        if not rc_path:
            raise RuntimeError(
                "FATAL: --research-context is required for community-guide intent. "
                "Provide a research-context.json file with location, amenities, and named entities."
            )
        rc_file = Path(rc_path)
        if not rc_file.exists():
            raise RuntimeError(f"FATAL: research-context.json not found: {rc_file}")
        try:
            state.research_context = json.loads(rc_file.read_text())
        except json.JSONDecodeError as e:
            raise RuntimeError(f"FATAL: research-context.json is invalid JSON: {e}")
        # Minimal validation: location, amenities_status, and >=3 named entities
        rc = state.research_context
        rc_errors = []
        if not rc.get("location"):
            rc_errors.append("'location' block is missing or empty")
        if not rc.get("amenities_status"):
            rc_errors.append("'amenities_status' block is missing or empty")
        entities = rc.get("named_entities", [])
        if len(entities) < 3:
            rc_errors.append(f"'named_entities' has {len(entities)} entries (minimum 3)")
        if rc_errors:
            raise RuntimeError(
                f"FATAL: research-context.json validation failed ({len(rc_errors)} errors):\n"
                + "\n".join(f"  - {e}" for e in rc_errors)
            )
        eprint(f"  [A.7] Research context loaded and validated: {rc_file} ({len(entities)} named entities)")

    # Step 7b: Research context for non-community-guide intents (universal injection)
    # When --research-context is provided for any intent, load it without
    # community-guide-specific schema validation. Content reaches every builder.
    if state.intent != "community-guide" and state.research_context_path:
        rc_file = Path(state.research_context_path)
        if not rc_file.exists():
            raise RuntimeError(f"FATAL: --research-context file not found: {rc_file}")
        try:
            state.research_context = json.loads(rc_file.read_text())
        except json.JSONDecodeError as e:
            raise RuntimeError(f"FATAL: research-context.json is invalid JSON: {e}")
        eprint(f"  [A.7b] Research context loaded (universal): {rc_file}")

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

    # Step 7b: Source-relevance filter — reject SERP results not about the target
    if state.serp and state.serp.top_results:
        kw_lower = state.target_keyword.lower()
        # Extract location tokens from the keyword (neighborhood + city names)
        location_tokens = set(re.sub(r'[^a-z0-9\s]', '', kw_lower).split()) - {
            'neighborhood', 'neighborhoods', 'best', 'guide', 'tx', 'in', 'the',
            'to', 'live', 'living', 'for', 'homebuyers', 'near',
        }
        # Keep tokens with 4+ chars for matching (avoids false matches on short words)
        location_tokens = {t for t in location_tokens if len(t) >= 4}

        if location_tokens:
            original_count = len(state.serp.top_results)
            filtered = []
            rejected = []
            for r in state.serp.top_results:
                r_text = (getattr(r, "title", "") + " " + getattr(r, "snippet", "")).lower()
                # Result must mention at least ONE location token
                has_location = any(t in r_text for t in location_tokens)
                if has_location:
                    filtered.append(r)
                else:
                    rejected.append(getattr(r, "title", "")[:60])

            if rejected:
                eprint(f"  [B.7b] Source-relevance filter: {len(rejected)} off-topic result(s) rejected:")
                for title in rejected:
                    eprint(f"    REJECTED: {title}")
                state.serp._top_results = filtered
                # Also rewrite the SERP JSON so downstream tools see filtered data
                raw = json.loads(state.serp_json_path.read_text())
                raw_filtered = [
                    r for r in raw.get("top_results", [])
                    if any(t in (r.get("title", "") + " " + r.get("snippet", "")).lower()
                           for t in location_tokens)
                ]
                raw["top_results"] = raw_filtered
                raw["_source_filter"] = {
                    "original_count": original_count,
                    "filtered_count": len(raw_filtered),
                    "rejected": rejected,
                }
                state.serp_json_path.write_text(json.dumps(raw, indent=2))
                eprint(f"  [B.7b] SERP filtered: {original_count} → {len(filtered)} results")
            else:
                eprint(f"  [B.7b] Source-relevance: all {original_count} results on-target")

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

    # Step 8b: Build evidence store
    if state.serp:
        eprint("  [B.8b] Building evidence store")
        try:
            from lib.evidence import build_evidence_store
            exclude_url = getattr(state, "exclude_url", "")
            ev_path, exclusion_info = build_evidence_store(
                state.serp, state.site_slug, state.output_dir, state.post_id,
                exclude_url=exclude_url,
            )
            state.evidence_path = ev_path
            state.evidence_exclusion = exclusion_info
            # Count items for status
            ev_data = json.loads(ev_path.read_text())
            state.evidence_status = f"ok ({len(ev_data)} items)"
            eprint(f"  [B.8b] Evidence store: {len(ev_data)} items")
        except Exception as e:
            eprint(f"  [B.8b] Evidence store build FAILED (non-fatal): {e}")
            state.evidence_path = None
            state.evidence_status = f"failed: {e}"
    else:
        eprint("  [B.8b] Skipping evidence store (no SERP)")
        state.evidence_status = "skipped: no SERP data"

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
        # Community-guide: inject community data summary as AI overview
        # so downstream tools (build-faqs, build-bluf) have context
        ai_overview = None
        if state.intent == "community-guide" and state.community_data:
            cd = state.community_data
            builders = cd.get("builders", [])
            b_names = [b["name"] for b in builders]
            prices = [b["price_low"] for b in builders] + [b["price_high"] for b in builders]
            disambig = _build_entity_disambiguation(cd)
            summary_text = (
                f"{disambig} "
                f"Price range: ${min(prices):,} to ${max(prices):,}. "
                f"School district: {cd.get('schools', {}).get('district', 'N/A')}. "
                f"Tax rate: {cd.get('tax', {}).get('base_rate', 'N/A')}. "
                f"{'No MUD or PID applies. ' if cd.get('tax', {}).get('mud_name') is None else ''}"
                f"This article is a community guide covering builder comparisons, "
                f"costs, schools, and buyer fit."
            )
            ai_overview = {
                "text_blocks": [{"type": "paragraph", "snippet": summary_text}],
                "references": [],
            }
        empty_serp_path.write_text(json.dumps({
            "keyword": state.target_keyword,
            "providers_used": [],
            "queried_at": "",
            "intent_signals": {},
            "top_results": [],
            "paa": [],
            "related_searches": [],
            "ai_overview": ai_overview,
        }))
        state.serp_json_path = empty_serp_path
        eprint(f"  [B.10] Wrote {'enriched' if ai_overview else 'empty'} SERP fallback: {empty_serp_path}")

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

    items = data.get("h2_inventory") if isinstance(data, dict) else data
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
            # Pass through all override fields so structural_element,
            # template_hint, callout_key, callout_label, and h2_format
            # survive into phase_c/phase_f instead of being dropped.
            for key in ("framing", "structural_element", "template_hint",
                        "h2_format", "callout_key", "callout_label"):
                if item.get(key):
                    entry[key] = item[key]
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
    # Ensure all H2s have structural_element (overrides may lack it)
    for h in h2s:
        if "structural_element" not in h:
            h["structural_element"] = "prose"
            h["template_role"] = h.get("template_role", "manual_override")
            h["template_hint"] = h.get("template_hint", h.get("framing", ""))
            h["h2_format"] = h.get("h2_format", "statement")
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

    # Confabulation guard: filter out heritage/history/culture H2s when
    # these topics have thin SERP support (< 2 results mentioning the topic).
    # The LLM amplifies thin SERP mentions into fabricated narrative sections.
    _CONFAB_RISK_MARKERS = [
        "heritage", "history", "historical", "tradition", "founding",
        "settlers", "cultural roots", "origin story", "established in",
    ]
    if state.serp and hasattr(state.serp, 'top_results'):
        serp_text = " ".join(
            (getattr(r, "title", "") + " " + getattr(r, "snippet", "")).lower()
            for r in state.serp.top_results[:10]
        )
    else:
        serp_text = ""

    filtered_h2s = []
    for h in h2s:
        h_lower = h["title"].lower()
        is_confab_risk = any(m in h_lower for m in _CONFAB_RISK_MARKERS)
        if is_confab_risk:
            # Strict check: a heritage/history H2 is only justified if a SERP
            # result's TITLE (not just snippet) specifically addresses this topic
            # for THIS place. A passing mention in a snippet is thin support that
            # the LLM will amplify into fabricated narrative.
            title_support = 0
            if state.serp and hasattr(state.serp, 'top_results'):
                kw_core = re.sub(r'\b(?:neighborhood|tx|texas|best|neighborhoods|guide)\b', '',
                                 state.target_keyword.lower()).strip()
                for r in state.serp.top_results[:10]:
                    r_title = getattr(r, "title", "").lower()
                    if (any(m in r_title for m in _CONFAB_RISK_MARKERS) and
                        any(t in r_title for t in kw_core.split() if len(t) > 3)):
                        title_support += 1

            if title_support < 1:
                eprint(f"  [C.10c] DROPPED confab-risk H2: '{h['title']}' "
                       f"(0 SERP titles specifically about this heritage topic)")
                continue
            else:
                eprint(f"  [C.10c] KEPT heritage H2: '{h['title']}' "
                       f"({title_support} SERP title(s) specifically address it)")
        filtered_h2s.append(h)

    if len(filtered_h2s) < len(h2s):
        eprint(f"  [C.10c] Confabulation guard dropped {len(h2s) - len(filtered_h2s)} H2(s)")
        state.h2_inventory = filtered_h2s
        h2s = filtered_h2s

    # Step 11: Build header prelude (deterministic)
    ss = state.site_structure
    if ss.get("emit_hero_block", True):
        eprint("  [C.11] Building header prelude")
        state.header_html = _build_header_prelude(state)
    else:
        # Emit standalone H1 only (no hero wrapper, no eyebrow, no CTA)
        kw = state.target_keyword
        state.header_html = f'<h1>{kw.title()}</h1>'
        eprint("  [C.11] Standalone H1 (hero block disabled by site overlay)")

    # Step 12: Jump nav retired — sidebar TOC (rss-toc-manager) handles navigation.
    # In-body jump nav is prohibited by spec assertion 18.1.5.
    state.jump_nav_html = ""
    eprint("  [C.12] Jump nav skipped (sidebar TOC handles navigation)")

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

    # Community-guide: seed H2s from template roles, not SERP gaps.
    # The template sections define the article structure; SERP gaps merge
    # in as title refinements where present, but the section list is fixed.
    if state.intent == "community-guide" and template_sections:
        # Build data blocks to inject into hints so the LLM sees actual values
        cd = state.community_data
        builder_data_block = ""
        if cd.get("builders"):
            lines = []
            for b in cd["builders"]:
                lines.append(f"  {b['name']}: ${b['price_low']:,}-${b['price_high']:,}, "
                             f"{b['plan_count']} plans, {b['sqft_low']:,}-{b['sqft_high']:,} sqft")
            builder_data_block = "VERIFIED BUILDER DATA (use verbatim):\n" + "\n".join(lines)

        tax_data_block = ""
        tax = cd.get("tax", {})
        if tax:
            parts = [f"Base rate: {tax.get('base_rate', 'N/A')} ({tax.get('county', '')} County)"]
            if tax.get("rate_detail"):
                parts.append(f"Breakdown: {tax['rate_detail']}")
            if tax.get("mud_name"):
                parts.append(f"MUD/PID: {tax['mud_name']} at {tax.get('mud_rate', 'N/A')}")
            else:
                parts.append("No MUD or PID applies to this community.")
            if tax.get("hoa_annual"):
                parts.append(f"HOA: {tax['hoa_annual']}/year ({tax.get('hoa_monthly', 'N/A')}/month)")
            tax_data_block = "VERIFIED TAX/COST DATA (use verbatim):\n  " + "\n  ".join(parts)

        # Worked examples: pre-computed derived amounts for the cost section
        worked_examples = cd.get("worked_examples", [])
        if worked_examples:
            we_lines = []
            for ex in worked_examples:
                we_lines.append(f"WORKED EXAMPLE (use these figures verbatim, do not recompute):")
                we_lines.append(f"  Example home price: ${ex['example_price']:,}")
                for d in ex.get("derived", []):
                    val = d["value"]
                    formatted = f"${val:,.2f}" if isinstance(val, (int, float)) else str(val)
                    we_lines.append(f"  {d['label']}: {formatted}")
            tax_data_block += "\n" + "\n".join(we_lines)

        school_data_block = ""
        schools = cd.get("schools", {})
        if schools:
            school_data_block = (
                f"VERIFIED SCHOOL DATA (use verbatim):\n"
                f"  District: {schools.get('district', 'N/A')}\n"
                f"  Elementary: {schools.get('elementary', 'N/A')}\n"
                f"  Middle: {schools.get('middle', 'N/A')}\n"
                f"  High: {schools.get('high', 'N/A')}"
            )

        mil_block = ""
        mil = cd.get("military_proximity", {})
        if mil:
            parts = []
            if mil.get("lackland_afb_miles"):
                parts.append(f"Lackland AFB: ~{mil['lackland_afb_miles']} miles")
            if mil.get("fort_sam_houston_miles"):
                parts.append(f"Fort Sam Houston: ~{mil['fort_sam_houston_miles']} miles")
            if mil.get("jbsa_note"):
                parts.append(mil["jbsa_note"])
            if parts:
                mil_block = "MILITARY PROXIMITY DATA:\n  " + "\n  ".join(parts)

        # Market data block
        market_block = ""
        market = cd.get("market", {})
        if market:
            market_block = (
                f"VERIFIED MARKET DATA (use verbatim, do not invent market figures):\n"
                f"  MSA: {market.get('msa', 'N/A')}\n"
                f"  Period: {market.get('period', 'N/A')}\n"
                f"  Median sale price: ${market.get('median_price', 0):,}\n"
                f"  Closed sales: {market.get('closed_sales', 'N/A'):,}\n"
                f"  Months of inventory: {market.get('months_inventory', 'N/A')}\n"
            )
            if market.get("active_listings"):
                market_block += f"  Active listings: {market['active_listings']:,}\n"
            market_block += f"  Source: {market.get('source_name', '')}"

        # BAH data block
        bah_block = ""
        bah = cd.get("bah", {})
        if bah and bah.get("with_dependents"):
            wd = bah["with_dependents"]
            bah_block = (
                f"VERIFIED BAH DATA (use verbatim, do not invent BAH figures):\n"
                f"  Installation: {bah.get('installation', 'N/A')}, {bah.get('year', 'N/A')}\n"
                f"  E-5 with dependents: ${wd.get('E-5', 0):,}/month\n"
                f"  E-6 with dependents: ${wd.get('E-6', 0):,}/month\n"
                f"  E-7 with dependents: ${wd.get('E-7', 0):,}/month"
            )

        # Plans block (single-builder per-plan data)
        plans_block = ""
        plans = cd.get("plans", [])
        if plans:
            lines = ["VERIFIED PLAN DATA (use verbatim for the plan-level comparison table):"]
            for p in plans:
                lines.append(f"  {p['name']}: ${p['price']:,}, {p['sqft']:,} sqft, {p['beds']} bed/{p['baths']} bath")
            plans_block = "\n".join(lines)

        # Research context block (injected into all section hints)
        research_block = ""
        rc = state.research_context or {}
        if rc:
            rc_lines = ["RESEARCH CONTEXT (verified facts from live sources):"]
            loc = rc.get("location", {})
            if loc:
                rc_lines.append(f"  Location: {loc.get('description', '')}")
            amenities = rc.get("amenities_status", {})
            if amenities:
                rc_lines.append(f"  Amenities: {amenities.get('summary', '')}")
            for ent in rc.get("named_entities", []):
                if isinstance(ent, dict):
                    rc_lines.append(f"  Entity: {ent.get('name', '')} — {ent.get('context', '')}")
            research_block = "\n".join(rc_lines)

        # Map roles to their data enrichment
        _role_data = {
            "builder_comparison": (plans_block if plans_block else builder_data_block),
            "cost_reality": tax_data_block,
            "data_strip": market_block,
            "schools_commute": school_data_block + ("\n" + mil_block if mil_block else ""),
            "military_buyer_fit": (bah_block + "\n" if bah_block else "") + mil_block + ("\n" + builder_data_block if builder_data_block else ""),
            "community_overview": f"Community: {cd.get('community_name', '')}, {cd.get('address', '')}\n"
                                  f"Amenities: {', '.join(cd.get('amenities', []))}",
            "verify_checklist": tax_data_block,
            "community_verdict": builder_data_block + "\n" + tax_data_block,
        }

        # Reader-facing H2 title patterns per role
        _cn = cd.get("community_name", "")
        _city = cd.get("city", "San Antonio")
        _role_titles = {
            "community_overview": f"Living in {_cn}",
            "cost_reality": f"What It Really Costs to Own in {_cn}",
            "data_strip": f"{_city} Market Snapshot",
            "schools_commute": f"Schools and Commute from {_cn}",
            "military_buyer_fit": f"Is {_cn} a Good Fit for Military Buyers?",
            "verify_checklist": f"What to Verify Before You Sign at {_cn}",
            "community_verdict": f"The Verdict on {_cn}",
        }

        for tmpl in template_sections:
            role = tmpl.get("role", "body")
            hint = tmpl.get("hint", "")
            # Enrich hint with actual data for this role
            data_enrichment = _role_data.get(role, "")
            if data_enrichment:
                hint = hint + "\n\n" + data_enrichment
            # Inject research context into all sections
            if research_block:
                hint = hint + "\n\n" + research_block
            # Reader-facing H2 title (never a role name)
            seed_title = _role_titles.get(role, role.replace("_", " ").title())
            # Builder comparison H2: include builder names for SERP relevance
            if role == "builder_comparison" and cd.get("builders"):
                b_names_short = [b["name"] for b in cd["builders"]]
                if len(b_names_short) == 1:
                    seed_title = f"What {b_names_short[0]} Builds at {_cn}"
                elif len(b_names_short) == 2:
                    seed_title = f"What {b_names_short[0]} and {b_names_short[1]} Build at {_cn}"
                else:
                    seed_title = f"What {b_names_short[0]}, {b_names_short[1]}, and Others Build at {_cn}"
            h2s.append({
                "title": seed_title,
                "role": role,
                "source": "template_seed",
                "structural_element": tmpl["type"] if tmpl["type"] != "prose_optional_table" else "prose_optional_table",
                "template_role": role,
                "template_hint": hint,
                "h2_format": tmpl.get("h2_format", "statement"),
                "callout_key": "",
                "callout_label": "",
            })
        # Assign callout key/label for callout-type sections
        for h2 in h2s:
            if h2["structural_element"] == "callout":
                callout_prefs = overlay.callout_preferences
                role = h2.get("template_role", "")
                if role in callout_prefs:
                    keys = callout_prefs[role]
                    h2["callout_key"] = keys[0] if keys else "reality_check"
                    h2["callout_label"] = keys[0].replace("_", " ").title() if keys else "Reality Check"
                else:
                    h2["callout_key"] = "reality_check"
                    h2["callout_label"] = "Reality Check"
        eprint(f"  [C.10] Community-guide: seeded {len(h2s)} H2s from structural template (data-enriched)")

        # H2 role-name leak assertion: no H2 title may match a structural template role name
        _all_roles = {s.get("role", "") for s in template_sections}
        _role_name_variants = set()
        for r in _all_roles:
            _role_name_variants.add(r.replace("_", " ").lower())
            _role_name_variants.add(r.replace("_", " ").title().lower())
        leaked = []
        for h2 in h2s:
            title_lower = h2["title"].strip().lower()
            if title_lower in _role_name_variants:
                leaked.append(f"H2 '{h2['title']}' matches role name '{h2.get('template_role', '')}'")
        if leaked:
            raise RuntimeError(
                f"H2 ROLE-NAME LEAK: {len(leaked)} H2 title(s) are internal role names, not reader-facing:\n"
                + "\n".join(f"  - {l}" for l in leaked)
                + "\nFix _role_titles map in Phase C community-guide H2 seeding."
            )

        return h2s

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

    # Fill from GSC-derived subtopic queries (required H2 slots from gsc-section-inputs.json)
    gsc_section_path = state.output_dir / "gsc-section-inputs.json"
    if gsc_section_path.exists():
        gsc_sections = json.loads(gsc_section_path.read_text())
        existing_titles_lower = {h["title"].lower() for h in h2s}
        for gsc_q in gsc_sections:
            if len(h2s) >= 15:
                break
            if gsc_q.lower() not in existing_titles_lower:
                h2s.append({"title": gsc_q, "role": "gsc_required", "source": "gsc_subtopic"})
                eprint(f"  [C.10] Added GSC-derived H2: {gsc_q}")

    # Pad from PAA questions if below minimum 8
    MIN_H2_COUNT = 8
    if len(h2s) < MIN_H2_COUNT and state.serp:
        for paa in state.serp.paa_questions:
            if len(h2s) >= 12:
                break
            q = paa.question if hasattr(paa, "question") else str(paa)
            if not any(h["title"].lower() == q.lower() for h in h2s):
                h2s.append({"title": q, "role": "paa_derived", "source": "paa"})

    # Fallback: if still below minimum, generate natural H2s via LLM
    if len(h2s) < MIN_H2_COUNT:
        needed = MIN_H2_COUNT - len(h2s)
        existing_titles = [h["title"] for h in h2s]
        fallback_h2s = _generate_fallback_h2s(state, existing_titles, needed)
        for fb in fallback_h2s:
            if len(h2s) >= MIN_H2_COUNT:
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
            # Map prose_optional_table to bullets
            if stype == "prose_optional_table":
                stype = "bullets"
            h2["structural_element"] = stype
            h2["template_role"] = tmpl.get("role", "")
            h2["template_hint"] = tmpl.get("hint", "")
            h2["h2_format"] = tmpl.get("h2_format", "statement")
        else:
            # Sections beyond template range
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

        # Apply site-specific callout label mapping from structure overlay.
        # If callout_label_map exists: mapped string = relabel, null/unmapped = remove callout.
        # If callout_label_map absent: keep defaults (backward compatible).
        callout_label_map = state.site_structure.get("callout_label_map")
        if callout_label_map is not None and h2.get("callout_key"):
            mapped_label = callout_label_map.get(h2["callout_key"])
            if mapped_label:
                h2["callout_label"] = mapped_label
                eprint(f"    [callout-map] Relabeled '{h2['callout_key']}' → '{mapped_label}'")
            else:
                eprint(f"    [callout-map] Removed callout '{h2['callout_key']}' (null/unmapped)")
                h2["structural_element"] = "bullets"
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

    # Inject brand rules into the normalize prompt
    brand_rules_for_h2 = _load_brand_rules_from_config(state.config)

    prompt = f"""{brand_rules_for_h2}

You will receive a list of H2 titles and their required formats.

For each H2:
- If REQUIRED_FORMAT is 'statement': output as a statement.
- If REQUIRED_FORMAT is 'question': output as a question ending with '?'.
- If an H2 title names a competitor or forbidden term, REWRITE it to remove that name entirely. Replace with a generic category (e.g. "Pizza Hut" → "national chains", "Big Lou's" → "other local shops").

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

    # Brand rules: drop H2s containing forbidden terms
    from lib.brand_rules import get_forbidden_terms
    forbidden = get_forbidden_terms(state.config)
    if forbidden:
        clean_h2s = []
        dropped = []
        for h in h2s:
            title_lower = h["title"].lower()
            hit = next((t for t in forbidden if t.lower() in title_lower), None)
            if hit:
                dropped.append(f"'{h['title']}' (matched '{hit}')")
            else:
                clean_h2s.append(h)
        if dropped:
            eprint(f"  [C.10b] Brand filter: dropped {len(dropped)} H2(s) with forbidden terms:")
            for d in dropped:
                eprint(f"           - {d}")
            h2s = clean_h2s

            # If we dropped below minimum (4), generate replacements
            if len(h2s) < 4:
                needed = 6 - len(h2s)
                existing_titles = [h["title"] for h in h2s]
                eprint(f"  [C.10b] Only {len(h2s)} H2s remain after brand filter — generating {needed} replacements")
                replacement_h2s = _generate_fallback_h2s(state, existing_titles, needed)
                for fb in replacement_h2s:
                    h2s.append({"title": fb, "role": "brand_replacement", "source": "llm_fallback",
                                "h2_format": "question", "structural_element": "prose_optional_table"})

    return h2s


def _build_header_prelude(state: PipelineState) -> str:
    """Build deterministic header HTML (H1 + eyebrow only).

    Byline/Updated date removed — RSS Meta Header plugin renders these
    at WordPress level. Primary sources removed — handled by Resources section.
    """
    config = state.config
    kw = state.target_keyword
    form_slug = config.get("FORM_PAGE_SLUG", "")
    cta_url = config.get("CTA_URL", f"/{form_slug}/" if form_slug else "/compare-loan-offers/")
    cta_text = config.get("CTA_TEXT", "Get Your Free Quote" if form_slug else "Get Your Rate")

    # Append ?ref=<post-slug> for lead attribution
    post_slug = re.sub(r"[^a-z0-9]+", "-", kw.lower()).strip("-")
    if "?" not in cta_url:
        cta_url_with_ref = f"{cta_url}?ref={post_slug}"
    else:
        cta_url_with_ref = f"{cta_url}&ref={post_slug}"

    header = (
        f'<header class="rl-hero">\n'
        f'  <div class="rl-eyebrow">{state.intent.replace("-", " ").title()} &middot; Guide</div>\n'
        f'  <h1>{kw.title()}</h1>\n'
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
    ss = state.site_structure

    client = LLMClient(provider=state.provider, model=state.model)
    serp_json = str(state.serp_json_path) if state.serp_json_path else ""

    # Pre-write topic-context file for card/FAQ builders when research_context
    # is present (file is rewritten in Phase E with full SERP enrichment, but
    # cards/FAQs need it NOW in Phase D).
    context_path = state.output_dir / f"{state.post_id}-topic-context.json"
    if state.research_context and not context_path.exists():
        rc_summary = _build_research_context_summary(state.research_context)
        context_path.write_text(json.dumps({"context": rc_summary}))
        eprint(f"  [D.12b] Pre-wrote topic-context for card/FAQ builders ({len(rc_summary)} chars)")

    # Step 13: ATF lede
    eprint("  [D.13] Building ATF lede")
    state.atf_lede_html = _build_atf_lede(state, client)

    # Step 13b: Community-guide qstats strip + rating bars (no LLM — pure data)
    if state.intent == "community-guide" and state.community_data:
        cd = state.community_data
        ratings = cd.get("ratings", {})
        if ratings:
            state.qstats_html, state.rating_bars_html = _build_community_atf_data(cd, ratings)
            eprint(f"  [D.13b] Community qstats + rating bars built from JSON")
        else:
            eprint("  [D.13b] No ratings in community-data — qstats/bars skipped")

    # Step 14: Build 4 ATF cards (sequential, with synthesis diversity)
    if not ss.get("emit_atf_cards", True):
        eprint("  [D.14] ATF cards disabled by site overlay")
        state.card_htmls = []
    else:
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
            if context_path.exists():
                card_args += ["--topic-context", str(context_path)]
            if prior_cards_synthesis:
                card_args += ["--prior-cards-synthesis", json.dumps(prior_cards_synthesis)]
            try:
                _run_tool(str(card_tool), card_args, f"D.14.{i+1}")
                card_html = output_path.read_text()
                state.card_htmls.append(card_html)
                state.llm_calls += 1
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

    # Step 15: Build ATF FAQs
    if not ss.get("emit_inline_faqs", True):
        eprint("  [D.15] ATF FAQs disabled by site overlay")
        state.atf_faqs_html = ""
    else:
        eprint("  [D.15] Building ATF FAQs")
        faqs_tool = TOOLS_DIR / "build-faqs.py"
        atf_faq_path = state.output_dir / f"{state.post_id}-atf-faqs.html"
        faq_args = [
                "--site", state.site_slug,
                "--target-keyword", state.target_keyword,
                "--mode", "atf",
                "--serp-json", serp_json,
                "--output", str(atf_faq_path),
            ]
        if context_path.exists():
            faq_args += ["--topic-context", str(context_path)]
        if state.evidence_path and state.evidence_path.exists():
            faq_args += ["--evidence-json", str(state.evidence_path)]
        try:
            _run_tool(str(faqs_tool), faq_args, "D.15")
            state.atf_faqs_html = atf_faq_path.read_text()
            state.llm_calls += 3

            # ATF FAQ topic-drift filter — same logic as BTF filter
            kw_lower = state.target_keyword.lower()
            kw_tokens = set(re.sub(r'[^a-z0-9\s]', '', kw_lower).split()) - _FAQ_DRIFT_STOPWORDS
            if kw_tokens:
                atf_faq_soup = BeautifulSoup(state.atf_faqs_html, "html.parser")
                atf_details = atf_faq_soup.find_all("details")
                kept_atf = []
                for d in atf_details:
                    summary = d.find("summary")
                    if summary:
                        q_text = summary.get_text(strip=True).lower()
                        has_topic = any(t in q_text for t in kw_tokens)
                        if has_topic:
                            kept_atf.append(d)
                        else:
                            eprint(f"  [D.15b] DROPPED generic ATF FAQ: {summary.get_text(strip=True)[:60]}")
                    else:
                        kept_atf.append(d)
                if len(kept_atf) < len(atf_details):
                    state.atf_faqs_html = "\n".join(str(d) for d in kept_atf)
                    atf_faq_path.write_text(state.atf_faqs_html)

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

    # Community-guide: inject entity disambiguation directly into the prompt
    entity_preamble = ""
    if state.intent == "community-guide" and state.community_data:
        entity_preamble = _build_entity_disambiguation(state.community_data) + "\n\n"

    # Universal research context injection into lede prompt
    if state.research_context:
        rc_summary = _build_research_context_summary(state.research_context)
        if rc_summary:
            entity_preamble = rc_summary + "\n\n" + entity_preamble

    prompt = render_prompt(template, {
        "TARGET_KEYWORD": state.target_keyword,
        "TOPIC_NOUN": state.target_keyword,
        "SERP_TOP_RESULT_LEDES": serp_ledes or "(unavailable)",
        "AI_OVERVIEW_TEXT": ai_overview or "(unavailable)",
        "VERTICAL_RULES": state.vertical_rules,
        "INJECT_BRAND_VOICE": entity_preamble + state.brand_voice,
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

    # Site structure override
    if not state.site_structure.get("emit_bluf", True):
        eprint("  [E.16] BLUF disabled by site overlay")
        state.phases_completed.append("E")
        return

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

    # Write topic context to temp file for build-bluf (and reused by cards/FAQs)
    context_path = state.output_dir / f"{state.post_id}-topic-context.json"
    topic_ctx = build_topic_context(state.serp, state.target_keyword) if state.serp else ""
    # Community-guide: inject entity disambiguation into topic context
    # so ALL downstream builders (BLUF, FAQs, lede) know the subject.
    if state.intent == "community-guide" and state.community_data:
        cd = state.community_data
        cd_summary = _build_entity_disambiguation(cd)
        builders = cd.get("builders", [])
        if builders:
            prices = [b["price_low"] for b in builders] + [b["price_high"] for b in builders]
            cd_summary += f" Price range: ${min(prices):,}-${max(prices):,}."
        schools = cd.get("schools", {})
        if schools.get("district"):
            cd_summary += f" School district: {schools['district']}."
        tax = cd.get("tax", {})
        if tax.get("base_rate"):
            cd_summary += f" Property tax rate: {tax['base_rate']}."
            if tax.get("mud_name") is None:
                cd_summary += " No MUD or PID applies."
        topic_ctx = cd_summary + (topic_ctx or "")
    # Universal research-context injection: prepend research summary
    # to topic context so BLUF, cards, FAQs, and lede all receive it.
    if state.research_context:
        rc_summary = _build_research_context_summary(state.research_context)
        if rc_summary:
            topic_ctx = rc_summary + "\n\n" + (topic_ctx or "")
    context_path.write_text(json.dumps({"context": topic_ctx}))

    serp_json = str(state.serp_json_path) if state.serp_json_path else "/dev/null"
    bluf_args = [
        "--site", state.site_slug,
        "--target-keyword", state.target_keyword,
        "--topic-context", str(context_path),
        "--friction-point", f"Key considerations for {state.target_keyword}",
        "--serp-json", serp_json,
        "--output", str(bluf_path),
    ]
    if state.evidence_path and state.evidence_path.exists():
        bluf_args += ["--evidence-json", str(state.evidence_path)]
    try:
        _run_tool(str(bluf_tool), bluf_args, "E.17")
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
    # Enforce 1800 body-word floor
    BODY_WC_FLOOR = 1800
    if body_target < BODY_WC_FLOOR:
        eprint(f"  [F.18] SERP target {body_target}w below floor {BODY_WC_FLOOR}w — scaling up")
        body_target = BODY_WC_FLOOR
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
        # Inject research context into template_hint for body sections
        section_hint = h2.get("template_hint", "")
        if state.research_context and state.intent != "community-guide":
            rc_block = _build_research_context_summary(state.research_context)
            if rc_block:
                section_hint = (section_hint + "\n\n" + rc_block) if section_hint else rc_block
        if section_hint:
            args_list += ["--template-hint", section_hint]
        if h2.get("h2_format"):
            args_list += ["--h2-format", h2["h2_format"]]
        if prior_sections_summary:
            args_list += ["--prior-sections-summary", prior_sections_summary]
        if state.evidence_path and state.evidence_path.exists():
            args_list += ["--evidence-json", str(state.evidence_path)]

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
    _form_slug = state.config.get("FORM_PAGE_SLUG", "")
    cta_url = state.config.get("CTA_URL", f"/{_form_slug}/" if _form_slug else "/compare-loan-offers/")
    cta_text = state.config.get("CTA_TEXT", "Get Your Free Quote" if _form_slug else "Get Your Rate")
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

    ss = state.site_structure

    # Step 20: Closing "The Bottom Line"
    if not ss.get("emit_closing_bottom_line", True):
        eprint("  [G.20] Closing Bottom Line disabled by site overlay")
        state.closing_html = ""
    else:
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

    btf_faq_args = [
            "--site", state.site_slug,
            "--target-keyword", state.target_keyword,
            "--mode", "btf",
            "--serp-json", serp_json,
            "--exclude-questions", str(exclude_path),
            "--output", str(btf_path),
        ]
    context_path = state.output_dir / f"{state.post_id}-topic-context.json"
    if context_path.exists():
        btf_faq_args += ["--topic-context", str(context_path)]
    if state.evidence_path and state.evidence_path.exists():
        btf_faq_args += ["--evidence-json", str(state.evidence_path)]
    try:
        _run_tool(str(faqs_tool), btf_faq_args, "G.21")
        state.btf_faqs_html = btf_path.read_text()
        state.llm_calls += 1

        # FAQ topic-drift filter: strip generic questions not about this specific topic
        kw_lower = state.target_keyword.lower()
        kw_tokens = set(re.sub(r'[^a-z0-9\s]', '', kw_lower).split()) - _FAQ_DRIFT_STOPWORDS
        if kw_tokens:
            faq_soup = BeautifulSoup(state.btf_faqs_html, "html.parser")
            details = faq_soup.find_all("details")
            kept = []
            dropped = []
            for d in details:
                summary = d.find("summary")
                if summary:
                    q_text = summary.get_text(strip=True).lower()
                    has_topic = any(t in q_text for t in kw_tokens)
                    if has_topic:
                        kept.append(d)
                    else:
                        dropped.append(summary.get_text(strip=True))
                else:
                    kept.append(d)
            if dropped:
                eprint(f"  [G.21b] FAQ topic-drift filter dropped {len(dropped)} generic Q(s):")
                for dq in dropped:
                    eprint(f"    DROPPED: {dq[:70]}")
                # Rebuild FAQ HTML with only kept questions
                new_faq = "\n".join(str(d) for d in kept)
                state.btf_faqs_html = new_faq
                btf_path.write_text(new_faq)
    except RuntimeError as e:
        raise RuntimeError(f"Phase G step 21 (BTF FAQs) failed.\nReason: {e}")

    # Enforce FAQ count cap from site structure overlay
    faq_max = ss.get("faq_count", ss.get("faq_count_max", 12))
    faq_min = ss.get("faq_count_min", 4)
    btf_faq_soup = BeautifulSoup(state.btf_faqs_html, "html.parser")
    btf_details = btf_faq_soup.find_all("details")
    if len(btf_details) > faq_max:
        eprint(f"  [G.21b] Trimming BTF FAQs from {len(btf_details)} to {faq_max} (site overlay cap)")
        for d in btf_details[faq_max:]:
            d.decompose()
        state.btf_faqs_html = str(btf_faq_soup)
    elif len(btf_details) < faq_min:
        eprint(f"  [G.21b] WARNING: BTF FAQs has {len(btf_details)} items, minimum is {faq_min}")

    # Step 22: Resources Used
    resources_policy = ss.get("emit_resources_box", True)
    if resources_policy == "conditional_on_citation" or resources_policy is False:
        eprint("  [G.22] Resources box omitted (site overlay: conditional/disabled)")
        state.resources_html = ""
    else:
        eprint("  [G.22] Building Resources")
        resources_tool = TOOLS_DIR / "build-resources.py"
        resources_path = state.output_dir / f"{state.post_id}-resources.html"

        resources_args = [
            "--site", state.site_slug,
            "--target-keyword", state.target_keyword,
            "--serp-json", serp_json,
            "--output", str(resources_path),
        ]

        # Community-guide: build resources list from community-data.json sources
        if state.intent == "community-guide" and state.community_data:
            res_items = state.community_data.get("resources", [])
            # Auto-generate from builder/tax/school source URLs if no explicit resources
            if not res_items:
                seen_urls = set()
                for b in state.community_data.get("builders", []):
                    url = b.get("source_url", "")
                    if url and url not in seen_urls:
                        res_items.append({"title": f"{b['name']} — {state.community_data.get('community_name', '')} Community Page", "url": url})
                        seen_urls.add(url)
                tax_url = state.community_data.get("tax", {}).get("source_url", "")
                if tax_url and tax_url not in seen_urls:
                    county = state.community_data.get("tax", {}).get("county", "")
                    res_items.append({"title": f"{county} County — Official Tax Rates", "url": tax_url})
                    seen_urls.add(tax_url)
                schools_url = state.community_data.get("schools", {}).get("source_url", "")
                if schools_url and schools_url not in seen_urls:
                    district = state.community_data.get("schools", {}).get("district", "")
                    res_items.append({"title": f"{district} — District Information", "url": schools_url})
                    seen_urls.add(schools_url)
            if res_items:
                res_list_path = state.output_dir / f"{state.post_id}-resources-list.json"
                res_list_path.write_text(json.dumps(res_items, indent=2))
                resources_args += ["--resources-list", str(res_list_path)]
                eprint(f"  [G.22] Community-guide: {len(res_items)} resources from community-data.json")

        try:
            _run_tool(str(resources_tool), resources_args, "G.22")
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
        "VERTICAL_RULES": state.vertical_rules,
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

def _run_validator(validator: Path, html_path: Path, state: "PipelineState",
                   report_path: Path) -> tuple[int, int, list[str]]:
    """Run the validator subprocess and parse its JSON result.

    Returns (hard_passed, hard_total, failure_names).

    The validator's exit code is NOT consulted. The parsed JSON stdout is the
    sole source of truth. A valid result requires ALL of:
      - stdout parses as JSON
      - summary.hard_passed is present and an int
      - summary.hard_total is present, an int, and > 0
    Anything short of that is a crash → fail closed at (0, 30, []).
    """
    cmd = [PYTHON, str(validator),
           "--html-file", str(html_path),
           "--intent", state.intent,
           "--serp-json", str(state.serp_json_path),
           "--site", state.site_slug,
           "--output-format", "json"]
    eprint(f"  [H.26] Running: {validator.name}")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True,
            timeout=LLM_CALL_TIMEOUT, cwd=str(REPO_ROOT),
        )
    except subprocess.TimeoutExpired:
        eprint(f"  [H.26] Validator timed out after {LLM_CALL_TIMEOUT}s")
        return 0, 30, []

    # Parse JSON from stdout — exit code is irrelevant
    stdout = (result.stdout or "").strip()
    if not stdout:
        eprint(f"  [H.26] Validator produced no stdout (crash). "
               f"Stderr: {(result.stderr or '')[-300:]}")
        return 0, 30, []

    try:
        vdata = json.loads(stdout)
    except (json.JSONDecodeError, ValueError) as e:
        eprint(f"  [H.26] Validator stdout is not valid JSON (crash): {e}")
        eprint(f"  [H.26] Stderr: {(result.stderr or '')[-300:]}")
        return 0, 30, []

    # Strict shape validation — partial/corrupt output is a crash
    summary = vdata.get("summary")
    if not isinstance(summary, dict):
        eprint(f"  [H.26] Validator JSON has no 'summary' dict (crash)")
        return 0, 30, []

    hp = summary.get("hard_passed")
    ht = summary.get("hard_total")
    if not isinstance(hp, int) or not isinstance(ht, int) or ht <= 0:
        eprint(f"  [H.26] Validator summary malformed: hard_passed={hp!r}, "
               f"hard_total={ht!r} (crash)")
        return 0, 30, []

    # Valid result — write report and extract failure names
    report_path.write_text(stdout)
    eprint(f"  [H.26] Validator: {hp}/{ht} hard passed")

    failures = []
    for a in vdata.get("hard_assertions", []):
        if isinstance(a, dict) and not a.get("passed"):
            ref = a.get("spec_ref", "?")
            detail = a.get("detail", "")
            failures.append(f"{ref}: {detail}" if detail else ref)
            eprint(f"  [H.26] FAILED: {ref} — {detail}")

    return hp, ht, failures


def phase_h(state: PipelineState) -> None:
    """Assemble all sections, inject links, validate."""
    eprint("PHASE H: Assembly")

    # Step 24: Concatenate in canonical order (spec Section 2)
    eprint("  [H.24] Assembling article")
    parts = [
        state.header_html,
        state.jump_nav_html,
        state.atf_lede_html,
        state.qstats_html,
        state.rating_bars_html,
        "\n".join(state.card_htmls),
        state.atf_faqs_html,
    ]
    if state.hub_box_html:
        parts.append(state.hub_box_html)
    if state.bluf_html:
        parts.append(state.bluf_html)
    parts.extend(state.body_section_htmls)  # includes mid CTA
    # Wrap BTF FAQs in .rl-faq div if not already wrapped
    btf_faq_block = state.btf_faqs_html.strip()
    if btf_faq_block and '<div class="rl-faq">' not in btf_faq_block:
        btf_faq_block = (
            '<div class="rl-faq">\n'
            '<h2>Frequently Asked Questions</h2>\n'
            f'{btf_faq_block}\n'
            '</div>'
        )
    parts.extend([
        state.closing_html,
        state.mid_cta_html,  # second CTA before FAQ section
        btf_faq_block,
        state.resources_html,
    ])

    inner = "\n\n".join(p for p in parts if p.strip())
    assembled = f'<div class="rl-page">\n{inner}\n</div>'
    assembled_path = state.output_dir / f"{state.post_id}-assembled-raw.html"
    assembled_path.write_text(assembled)

    # Step 24b: Sanitize assembled HTML (catches upstream defects)
    eprint("  [H.24b] Running post-assembly sanitizer")
    assembled, san_errors = sanitize_assembled_html(assembled, site=state.site_slug)
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
    assembled_path.write_text(assembled)
    eprint("  [H.24b] Sanitizer: PASS, wrote sanitized HTML back to " + str(assembled_path))

    # Post-sanitize assertion: fail loud if grid wrapper is missing
    _check = assembled_path.read_text()
    if 'rl-quick-card' in _check and 'rl-quick-grid' not in _check:
        raise SystemExit(
            "[H.24b] FATAL: rl-quick-card present but rl-quick-grid missing after sanitize "
            "— refusing to deploy stacked cards. Post: " + str(state.post_id)
        )

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
    #
    # NOTE ON EXIT CODE: The validator's exit code is NOT consulted for the
    # pass/fail decision. The parsed JSON is the sole source of truth.
    # Exit 0 with unparseable stdout is still a crash (fail closed at 0/30).
    # Exit 1 with valid JSON and summary.hard_passed is a real result.
    # This is intentional — validate-article-v2.py uses exit 1 for both
    # "file not found" and "ran, found failures" (L23 backlog). The JSON
    # output distinguishes them; the exit code does not.
    eprint("  [H.26] Running validation")
    validator = TOOLS_DIR / "validate-article-v2.py"
    validation_report_path = state.output_dir / f"{state.post_id}-validation-report.md"

    hard_passed = 0
    hard_total = 30
    hard_failure_names = []
    if validator.exists():
        validator_content = validator.read_text()
        if "NotImplementedError" in validator_content:
            eprint("  [H.26] Validator is still a stub — skipping validation")
        else:
            hard_passed, hard_total, hard_failure_names = _run_validator(
                validator, linked_path, state, validation_report_path
            )
    else:
        eprint("  [H.26] Validator not found — skipping validation")

    # Store scores on state for manifest
    state.validation_hard_passed = hard_passed
    state.validation_hard_total = hard_total
    state.validation_report_path = str(validation_report_path) if validation_report_path.exists() else ""
    state.validation_failures = hard_failure_names

    # Route output: 25+ = ready, <25 = needs review
    if hard_passed < 25 and hard_total > 0:
        if getattr(state, "soft_validate", False):
            review_path = state.output_dir / f"{state.post_id}-article.review.html"
            import shutil
            shutil.copy2(str(linked_path), str(review_path))
            eprint(f"  [H.26] Below threshold ({hard_passed}/{hard_total} < 25/30) → saved as .review.html (--soft-validate)")
        else:
            raise RuntimeError(
                f"Validation FAILED: {hard_passed}/{hard_total} hard passed (threshold 25). "
                f"Report: {validation_report_path}"
            )

    # Step 27: Business-facts claims check (D2-style)
    # Scan assembled HTML for operational claims (prices, hours, zones)
    # that may have been invented if the facts file was missing or incomplete.
    facts_file = REPO_ROOT / "sites" / f"{state.site_slug}-business-facts.md"
    has_facts_file = facts_file.exists()
    text = BeautifulSoup(state.assembled_html, "html.parser").get_text()

    import re as _re
    claim_flags = []
    # Specific dollar amounts
    prices = _re.findall(r'\$\d+\.?\d{0,2}', text)
    if len(prices) >= 3:
        claim_flags.append(f"PRICES: {len(prices)} dollar amounts found")
    # Specific hours
    if _re.search(r'(?:sunday|monday|tuesday|wednesday|thursday|friday|saturday).{0,20}\d{1,2}\s*(?:am|pm)', text, _re.I):
        claim_flags.append("HOURS: specific day+time schedule asserted")
    # Delivery zone claims
    if _re.search(r'we deliver to|our delivery (?:area|zone|radius)', text, _re.I):
        claim_flags.append("DELIVERY: specific zone/area claimed")

    if claim_flags:
        claims_path = state.output_dir / f"{state.post_id}-claims-review.txt"
        lines = [
            f"CLAIMS CHECK — {state.site_slug} post {state.post_id}",
            f"Business facts file: {'PRESENT' if has_facts_file else 'MISSING'}",
            f"Flags ({len(claim_flags)}):",
        ]
        for f in claim_flags:
            lines.append(f"  - {f}")
        if not has_facts_file:
            lines.append("")
            lines.append("WARNING: No business-facts file. These claims are likely invented.")
            lines.append("Create sites/{}-business-facts.md and re-run.".format(state.site_slug))
        claims_path.write_text("\n".join(lines))
        eprint(f"  [H.27] Claims check: {len(claim_flags)} flag(s) → {claims_path.name}")
    else:
        eprint("  [H.27] Claims check: clean (no operational claims detected)")

    # Step 27b: Fact-checker — extract and categorize checkable claims
    try:
        from lib.fact_checker import run_fact_check, format_fact_check_report
        fc_report = run_fact_check(
            state.assembled_html, state.target_keyword, state.site_slug
        )
        fc_path = state.output_dir / f"{state.post_id}-fact-check.txt"
        fc_path.write_text(format_fact_check_report(fc_report))
        if fc_report.flagged_for_human > 0:
            eprint(f"  [H.27b] Fact-check: {fc_report.flagged_for_human} claims to verify → {fc_path.name}")
        else:
            eprint(f"  [H.27b] Fact-check: no high-stakes claims found")
    except Exception as e:
        eprint(f"  [H.27b] *** FACT-CHECK FAILED (non-fatal but visible) ***")
        eprint(f"  [H.27b] Error: {e}")
        eprint(f"  [H.27b] The fact-check report was NOT generated for this article.")
        eprint(f"  [H.27b] Claims will NOT be flagged for human review. Investigate.")

    # Step 28: Brand rules validation (forbidden terms + price policy)
    eprint("  [H.28] Brand rules validation")
    brand_violations = validate_brand_rules(state.assembled_html, state.config)
    if brand_violations:
        fail_path = state.output_dir / f"{state.post_id}-brand-violations.log"
        lines = [
            f"BRAND RULES VALIDATION FAILED — {state.site_slug} post {state.post_id}",
            f"Target keyword: {state.target_keyword}",
            f"Violations ({len(brand_violations)}):",
            "",
        ]
        for v in brand_violations:
            lines.append(f"  - {v}")
        fail_path.write_text("\n".join(lines))
        eprint(f"  [H.28] FAILED: {len(brand_violations)} violation(s) → {fail_path.name}")
        for v in brand_violations:
            eprint(f"         {v}")
        raise RuntimeError(
            f"Brand rules validation failed with {len(brand_violations)} violation(s). "
            f"Article contains forbidden terms or specific prices. "
            f"See {fail_path} for details. Pipeline will NOT deploy."
        )
    eprint("  [H.28] Brand rules: PASS (0 violations)")

    # Step 28b: wrong_geo output assertion (community-guide only, hard fail)
    if state.intent == "community-guide" and state.community_data:
        wrong_geo = state.community_data.get("wrong_geo", [])
        if wrong_geo:
            eprint("  [H.28b] wrong_geo output check")
            from bs4 import BeautifulSoup as _BS
            text = _BS(state.assembled_html, "html.parser").get_text(" ", strip=True).lower()
            violations = []
            for term in wrong_geo:
                if term.lower() in text:
                    violations.append(term)
            if violations:
                fail_path = state.output_dir / f"{state.post_id}-wrong-geo-violations.log"
                lines = [
                    f"WRONG_GEO ASSERTION FAILED — {state.site_slug} post {state.post_id}",
                    f"Target: {state.target_keyword}",
                    f"Violations ({len(violations)}):",
                ]
                for v in violations:
                    lines.append(f"  - '{v}' found in output (listed in wrong_geo)")
                fail_path.write_text("\n".join(lines))
                eprint(f"  [H.28b] FAILED: {len(violations)} wrong_geo term(s) in output → {fail_path.name}")
                for v in violations:
                    eprint(f"         '{v}'")
                raise RuntimeError(
                    f"wrong_geo assertion failed: {len(violations)} prohibited geographic term(s) "
                    f"found in output. See {fail_path}."
                )
            eprint(f"  [H.28b] wrong_geo: PASS (checked {len(wrong_geo)} terms, 0 in output)")
        else:
            eprint("  [H.28b] wrong_geo: SKIP (no wrong_geo list in community data)")

    # Step 28c: Named-entity flag pass (soft, community-guide only)
    if state.intent == "community-guide" and state.community_data:
        eprint("  [H.28c] Named-entity flag pass")
        import re as _ner
        # Collect known entities from community-data + research-context
        known_entities = set()
        cd = state.community_data
        for b in cd.get("builders", []):
            known_entities.add(b["name"].lower())
        for field in ["community_name", "city", "county", "zip", "address"]:
            v = cd.get(field, "")
            if v:
                known_entities.add(str(v).lower())
        schools = cd.get("schools", {})
        for field in ["district", "elementary", "middle", "high"]:
            v = schools.get(field, "")
            if v:
                known_entities.add(v.lower())
        rc = state.research_context or {}
        for ent in rc.get("named_entities", []):
            if isinstance(ent, dict):
                known_entities.add(ent.get("name", "").lower())
            elif isinstance(ent, str):
                known_entities.add(ent.lower())
        for src in rc.get("sources", []):
            if isinstance(src, dict) and src.get("title"):
                known_entities.add(src["title"].lower())
        # Extract proper nouns from prose (title-cased multi-word sequences)
        text = _BS(state.assembled_html, "html.parser").get_text(" ", strip=True)
        # Match sequences of 2+ title-cased words (proper nouns)
        proper_nouns = set()
        for m in _ner.finditer(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', text):
            pn = m.group(1)
            # Skip common patterns
            if pn.lower() in {"the bottom", "bottom line", "resources used", "frequently asked"}:
                continue
            proper_nouns.add(pn)
        # Flag proper nouns not in known entities
        unknown_pn = []
        for pn in sorted(proper_nouns):
            if not any(pn.lower() in ke or ke in pn.lower() for ke in known_entities):
                unknown_pn.append(pn)
        if unknown_pn:
            flag_path = state.output_dir / f"{state.post_id}-entity-flags.txt"
            lines = [
                f"NAMED-ENTITY FLAGS (soft) — {state.site_slug} post {state.post_id}",
                f"Target: {state.target_keyword}",
                f"Known entities: {len(known_entities)}",
                f"Unknown proper nouns ({len(unknown_pn)}):",
            ]
            for pn in unknown_pn:
                lines.append(f"  - {pn}")
            flag_path.write_text("\n".join(lines))
            eprint(f"  [H.28c] Named-entity flags: {len(unknown_pn)} unknown proper noun(s) → {flag_path.name}")
        else:
            eprint(f"  [H.28c] Named-entity flags: clean ({len(proper_nouns)} proper nouns, all known)")

    state.phases_completed.append("H")

    # Write manifest now — Phase I (deploy) needs it to exist.
    # Phase I and J will re-write with updated phases_completed.
    _write_manifest(state)
    eprint(f"  [H.29] Pre-deploy manifest written")


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

    # Build brand rules reminder for the polish pass
    brand_rules_block = _load_brand_rules_from_config(state.config)
    brand_rules_reminder = ""
    if brand_rules_block:
        brand_rules_reminder = f"\n\n{brand_rules_block}\n\nIMPORTANT: While polishing, if you find any content that violates the BRAND RULES above (competitor names, specific prices, forbidden terms), REMOVE or rewrite those violations. This is your last chance to catch them.\n"

    prompt = f"""You are a senior SEO editor reviewing a finished article before publication.{brand_rules_reminder}

Read the article and fix ONLY these issues:

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

    # Post-polish brand rules re-check (polish LLM can introduce violations)
    post_polish_violations = validate_brand_rules(state.assembled_html, state.config)
    if post_polish_violations:
        fail_path = state.output_dir / f"{state.post_id}-brand-violations.log"
        lines = [
            f"BRAND RULES FAILED (POST-POLISH) — {state.site_slug} post {state.post_id}",
            f"Violations ({len(post_polish_violations)}):",
        ]
        for v in post_polish_violations:
            lines.append(f"  - {v}")
        fail_path.write_text("\n".join(lines))
        eprint(f"  [Polish] BRAND CHECK FAILED: {len(post_polish_violations)} violation(s)")
        raise RuntimeError(
            f"Post-polish brand validation failed with {len(post_polish_violations)} "
            f"violation(s). See {fail_path}."
        )
    eprint("  [Polish] Post-polish brand check: PASS")


## _generate_schema removed — FAQPage now rendered by lrg-faq-schema.php
## mu-plugin at page-serve time; Article/Breadcrumb handled by Yoast.
## Inline <script> in post_content was stripped by wp_kses_post on deploy.


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
    _write_manifest(state)  # update manifest with deploy phase


# ---------------------------------------------------------------------------
# Phase J: Featured Image
# ---------------------------------------------------------------------------

def _set_thumbnail_via_ssh(state: PipelineState, thumbnail_id: int) -> bool:
    """Set _thumbnail_id on a WP post via SSH wp eval."""
    ssh_host = state.config.get("SSH_HOST", "")
    ssh_user = state.config.get("SSH_USER", "")
    ssh_key = state.config.get("SSH_KEY_PATH", "").replace("~", str(Path.home()))
    if not ssh_host or not ssh_user:
        eprint("  [J.30] WARNING: SSH config incomplete, cannot set thumbnail")
        return False

    ssh_base = ["ssh"]
    if ssh_key:
        ssh_base += ["-i", ssh_key, "-o", "IdentitiesOnly=yes"]
    ssh_base.append(f"{ssh_user}@{ssh_host}")

    php = f"set_post_thumbnail({state.post_id}, {thumbnail_id}); echo 'OK thumb={thumbnail_id}';"
    # Shell-quote the PHP so parentheses aren't interpreted by bash
    cmd_str = " ".join(ssh_base) + f" 'wp eval \"{php}\"'"

    r = subprocess.run(cmd_str, shell=True, capture_output=True, text=True, timeout=30)
    if r.returncode != 0 or "OK" not in r.stdout:
        eprint(f"  [J.30] WARNING: set_post_thumbnail failed: {r.stdout} {r.stderr[:200]}")
        return False
    eprint(f"  [J.30] {r.stdout.strip()}")
    return True


def phase_j(state: PipelineState, skip: bool = False) -> None:
    """Generate and upload a branded GPT featured image."""
    eprint("PHASE J: Featured Image")

    if skip:
        eprint("  [J.30] --skip-featured-image: skipping")
        state.phases_completed.append("J")
        return

    # --- Pool rotation strategy (e.g. GFP branded photo pool) ---
    fi_config = state.site_structure.get("featured_image", {})
    if fi_config.get("strategy") == "rotate_from_pool":
        _repo_lib = str(REPO_ROOT / "lib")
        if _repo_lib not in sys.path:
            sys.path.append(_repo_lib)
        from featured_image import select_featured_image

        try:
            thumbnail_id = select_featured_image(state.target_keyword, state.site_structure)
        except ValueError as e:
            eprint(f"  [J.30] WARNING: Pool rotation failed: {e}")
            state.phases_completed.append("J")
            return

        eprint(f"  [J.30] Pool rotation selected image {thumbnail_id}"
               f" for keyword '{state.target_keyword}'")

        if state.post_id == 0:
            eprint(f"  [J.30] post_id=0: thumbnail {thumbnail_id} logged"
                   f" — set manually after deploy")
        else:
            _set_thumbnail_via_ssh(state, thumbnail_id)

        state.phases_completed.append("J")
        return

    # --- Default: GPT-generated featured image (Phase J original) ---
    feat_tool = TOOLS_DIR / "generate-featured-image.py"
    if not feat_tool.exists():
        eprint(f"  [J.30] Tool not found: {feat_tool}, skipping")
        state.phases_completed.append("J")
        return

    title = state.target_keyword.replace("-", " ").title()
    # Use the actual WP post title if available
    if hasattr(state, "post_title") and state.post_title:
        title = state.post_title

    # If post_id is 0 (--skip-deploy), generate locally but skip upload.
    # The image file will be at featured-images/{site}/post-0-final.jpg
    # and must be uploaded + set_post_thumbnail after manual deploy.
    skip_upload = (state.post_id == 0)
    if skip_upload:
        eprint(f"  [J.30] post_id=0: generating image locally (upload after manual deploy)")

    feat_args = [
        "--site", state.site_slug,
        "--post-id", str(state.post_id),
        "--title", title,
    ]
    if skip_upload:
        feat_args.append("--skip-upload")

    eprint(f"  [J.30] Generating featured image for post {state.post_id}")
    try:
        _run_tool(str(feat_tool), feat_args, "J.30")
        if skip_upload:
            eprint(f"  [J.30] Image generated locally. Run generate-featured-image.py"
                   f" with real post_id after deploy to upload and set _thumbnail_id.")
        else:
            eprint(f"  [J.30] Featured image set for post {state.post_id}")
    except RuntimeError as e:
        # Featured image failure is non-fatal — log and continue
        eprint(f"  [J.30] WARNING: Featured image failed: {e}")
        eprint(f"  [J.30] Article deployed successfully, image can be set manually")

    state.phases_completed.append("J")
    _write_manifest(state)  # update manifest with featured image phase


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
            "hard_passed": getattr(state, "validation_hard_passed", None),
            "hard_total": getattr(state, "validation_hard_total", None),
            "report_path": getattr(state, "validation_report_path", ""),
            "failures": getattr(state, "validation_failures", []),
        },
        "llm_calls_total": state.llm_calls,
        "llm_cost_estimate_usd": round(state.llm_cost, 4),
        "elapsed_seconds": round(elapsed, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phases_completed": state.phases_completed,
        "evidence_status": state.evidence_status or "not run",
        "evidence_self_exclusion": state.evidence_exclusion if state.evidence_exclusion else None,
    }

    # Community-guide: include research_context metadata in manifest
    if state.intent == "community-guide" and state.research_context:
        rc = state.research_context
        manifest["research_context"] = {
            "file_path": state.research_context_path or "",
            "captured_sources_count": len(rc.get("sources", [])),
            "named_entities_count": len(rc.get("named_entities", [])),
            "generated_date": rc.get("generated_date", ""),
        }

    # Community-guide: include volatile_data from community-data.json
    if state.intent == "community-guide" and state.community_data:
        volatile = []
        for b in state.community_data.get("builders", []):
            bname = b.get("name", "unknown")
            for fld in ("price_low", "price_high", "plan_count", "sqft_low", "sqft_high"):
                if b.get(fld) is not None:
                    volatile.append({
                        "field": f"{bname}.{fld}",
                        "value": b[fld],
                        "source_url": b.get("source_url", ""),
                        "captured_date": b.get("captured_date", ""),
                    })
        tax = state.community_data.get("tax", {})
        for fld in ("base_rate", "mud_rate", "hoa_monthly"):
            if tax.get(fld) is not None:
                volatile.append({
                    "field": f"tax.{fld}",
                    "value": tax[fld],
                    "source_url": tax.get("source_url", ""),
                    "captured_date": tax.get("captured_date", ""),
                })
        # Worked examples: pre-computed derived amounts
        for ex in state.community_data.get("worked_examples", []):
            ex_price = ex.get("example_price")
            src = ex.get("source_url", tax.get("source_url", ""))
            cap = ex.get("captured_date", tax.get("captured_date", ""))
            if ex_price is not None:
                volatile.append({
                    "field": "worked_example.example_price",
                    "value": ex_price,
                    "source_url": src,
                    "captured_date": cap,
                })
            for d in ex.get("derived", []):
                volatile.append({
                    "field": f"worked_example.{d['label']}",
                    "value": d["value"],
                    "source_url": src,
                    "captured_date": cap,
                })
        # Market data
        market = state.community_data.get("market", {})
        if market:
            msrc = market.get("source_url", "")
            mcap = market.get("captured_date", "")
            for fld in ("median_price", "closed_sales", "months_inventory", "active_listings"):
                if market.get(fld) is not None:
                    volatile.append({"field": f"market.{fld}", "value": market[fld],
                                     "source_url": msrc, "captured_date": mcap})
        # BAH data
        bah = state.community_data.get("bah", {})
        if bah and bah.get("with_dependents"):
            bsrc = bah.get("source_url", "")
            bcap = bah.get("captured_date", "")
            for grade, val in bah["with_dependents"].items():
                volatile.append({"field": f"bah.{grade}", "value": val,
                                 "source_url": bsrc, "captured_date": bcap})
        # Per-plan data
        for plan in state.community_data.get("plans", []):
            volatile.append({"field": f"plan.{plan['name']}.price", "value": plan["price"],
                             "source_url": state.community_data["builders"][0].get("source_url", ""),
                             "captured_date": state.community_data["builders"][0].get("captured_date", "")})
        manifest["volatile_data"] = volatile

    manifest_path = state.output_dir / f"{state.post_id}-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    eprint(f"\nManifest written: {manifest_path}")
    return manifest


# ---------------------------------------------------------------------------
# P1/P7: Deploy lock (centralized in lib/deploy_lock.py)
# ---------------------------------------------------------------------------

sys.path.insert(0, str(REPO_ROOT / 'modules' / '_shared'))
from lib.deploy_lock import acquire_deploy_lock as _acquire_lock_impl


def _acquire_lock(site_slug: str) -> None:
    """Acquire the centralized deploy lock for assemble-article."""
    _acquire_lock_impl(site_slug, tool_name='assemble-article')


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
        choices=["definition", "process", "decision", "cost", "comparison", "employer-relocation", "community-guide"],
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
    parser.add_argument("--skip-featured-image", action="store_true", help="Skip GPT-generated branded featured image (Phase J)")
    parser.add_argument("--community-data", help="Path to community-data.json (required for community-guide intent)")
    parser.add_argument("--research-context", help="Path to research-context.json (required for community-guide intent)")
    parser.add_argument("--soft-validate", action="store_true", help="Advisory validation only — do not block on low scores (debugging)")
    parser.add_argument("--exclude-url", default="", help="URL to exclude from evidence (self-exclusion on refresh)")
    args = parser.parse_args()

    # P1: Single-agent lockfile — abort if another instance is running
    _acquire_lock(args.site)

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
    state.community_data_path = getattr(args, "community_data", None)
    state.research_context_path = getattr(args, "research_context", None)
    state.soft_validate = getattr(args, "soft_validate", False)
    state.exclude_url = getattr(args, "exclude_url", "")
    state.start_time = time.time()

    # Output directory
    if args.output_dir:
        state.output_dir = Path(args.output_dir)
    else:
        state.output_dir = Path.home() / f"{args.site}-rewrite" / "articles-v2"
    state.output_dir.mkdir(parents=True, exist_ok=True)

    # ── DUPE GUARD (slug collision + keyword similarity check) ──
    from lib.dupe_guard import run_dupe_guard_article
    run_dupe_guard_article(
        site_slug=state.site_slug,
        target_keyword=state.target_keyword,
        post_id=state.post_id,
        force=args.force,
    )

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

        # Universal generation gate — no article produced without passing.
        eprint("  [GATE] Running universal generation gates")
        _content_type = _INTENT_TO_CONTENT_TYPE.get(state.intent, "article")
        _gate_report = _run_universal_gates(
            state.assembled_html,
            site_slug=state.site_slug,
            title="",  # extract from H1 in the assembled HTML
            content_type=_content_type,
            config=_GENERATION_GATE_CONFIG,
        )
        if not _gate_report.passed:
            eprint(f"  [GATE] GENERATION GATE FAILED — refusing to produce article:")
            for _gf in _gate_report.failures:
                eprint(f"    [{_gf.name}] {_gf.detail}")
            raise RuntimeError(
                f"Generation gate failed ({len(_gate_report.failures)} "
                f"failure(s)): {_gate_report.summary()}"
            )
        eprint(f"  [GATE] {_gate_report.summary()}")

        # Schema removed: FAQPage now handled by lrg-faq-schema.php mu-plugin
        # at render time; Article/Breadcrumb handled by Yoast in <head>.
        phase_i(state, skip_deploy=args.skip_deploy)
        # Phase J: featured image. Runs after deploy (needs post_id).
        # When --skip-deploy is used, Phase J still generates the image
        # locally but skips upload (post_id=0 → no WP target).
        # The deploy script or manual publish MUST run generate-featured-image.py
        # separately to upload and set _thumbnail_id.
        # CRITICAL: The lrg-blog feed query INNER JOINs on _thumbnail_id.
        # Posts without a real meta row are invisible in the feed.
        phase_j(state, skip=args.skip_featured_image)
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
