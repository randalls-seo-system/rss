#!/usr/bin/env python3
"""Spec-driven article validator — single source of truth.

Imports all assertions from lib.spec_assertions. No inline rules.
Replaces v1's validate-structure.py which had bugs (disagreed with prompts,
hardcoded card count, wrong H2 question mix threshold).

Usage:
    python3 validate-article-v2.py \\
        --html-file /path/to/article.html \\
        --intent <cost|decision|definition|process|comparison> \\
        --site <slug> \\
        [--serp-json /path/to/serp.json] \\
        [--atf-faqs-json /path/to/atf-faqs.json] \\
        [--output-format text|json|markdown] \\
        [--strict]

See docs/article-spec.md Section 18 for the assertion list.
See docs/v2-module-architecture.md "tools/validate-article-v2.py" for spec.
"""

import argparse
import json
import sys
import time
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
MODULE_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(MODULE_DIR))

from bs4 import BeautifulSoup

from lib.anchor_pool import AnchorPool
from lib.site_config import load_site_config
from lib.spec_assertions import (
    ALL_HARD_ASSERTIONS,
    ALL_SOFT_ASSERTIONS,
    AssertionResult,
)
from lib.tool_utils import eprint


# ---------------------------------------------------------------------------
# Assertion label extraction
# ---------------------------------------------------------------------------

def _assertion_label(fn) -> str:
    """Extract spec ref + short name from a function's docstring first line."""
    doc = (fn.__doc__ or "").strip()
    if doc:
        return doc.split("\n")[0].rstrip(".")
    return fn.__name__


# ---------------------------------------------------------------------------
# Context builder
# ---------------------------------------------------------------------------

def _build_context(args, soup: BeautifulSoup) -> dict:
    """Build the context dict needed by assertion functions."""
    context: dict = {
        "site_config": {},
        "serp_data": None,
        "anchor_pool": None,
        "intent": args.intent,
        "atf_faqs_text": [],
    }

    # Site config
    try:
        context["site_config"] = load_site_config(args.site)
    except FileNotFoundError:
        eprint(f"Warning: site config not found for '{args.site}', using defaults")

    # SERP data
    if args.serp_json:
        serp_path = Path(args.serp_json)
        if serp_path.exists():
            try:
                from lib.serp_adapter import SerpData
                context["serp_data"] = SerpData(serp_path)
            except Exception as e:
                eprint(f"Warning: failed to load SERP data: {e}")
        else:
            eprint(f"Warning: SERP JSON not found: {serp_path}")

    # Anchor pool
    try:
        context["anchor_pool"] = AnchorPool(args.site)
    except Exception as e:
        eprint(f"Warning: failed to load anchor pool: {e}")

    # ATF FAQ texts for overlap checking
    if args.atf_faqs_json:
        faqs_path = Path(args.atf_faqs_json)
        if faqs_path.exists():
            try:
                context["atf_faqs_text"] = json.loads(faqs_path.read_text())
            except Exception as e:
                eprint(f"Warning: failed to load ATF FAQs JSON: {e}")
    else:
        # Extract from HTML: ATF FAQs are <details> NOT inside .rl-faq
        btf_faq = soup.find(class_="rl-faq")
        all_details = soup.find_all("details")
        if btf_faq:
            btf_set = set(btf_faq.find_all("details"))
            atf_details = [d for d in all_details if d not in btf_set]
        else:
            atf_details = all_details[:3]

        for d in atf_details:
            summary = d.find("summary")
            if summary:
                context["atf_faqs_text"].append(summary.get_text(strip=True))

    return context


# ---------------------------------------------------------------------------
# Assertion runner
# ---------------------------------------------------------------------------

def _run_all(soup: BeautifulSoup, context: dict):
    """Run all hard and soft assertions. Never crashes — wraps exceptions."""
    hard_results = []
    for fn in ALL_HARD_ASSERTIONS:
        label = _assertion_label(fn)
        try:
            result = fn(soup, context)
        except Exception as e:
            result = AssertionResult(
                passed=False, severity="hard",
                detail=f"Assertion crashed: {type(e).__name__}: {e}",
                spec_ref=label.split()[0] if label else "?",
            )
        result._label = label
        hard_results.append(result)

    soft_results = []
    for fn in ALL_SOFT_ASSERTIONS:
        label = _assertion_label(fn)
        try:
            result = fn(soup, context)
        except Exception as e:
            result = AssertionResult(
                passed=False, severity="soft",
                detail=f"Assertion crashed: {type(e).__name__}: {e}",
                spec_ref=label.split()[0] if label else "?",
            )
        result._label = label
        soft_results.append(result)

    return hard_results, soft_results


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def _format_text(html_file, intent, site, serp_avail, hard, soft) -> str:
    hp = sum(1 for r in hard if r.passed)
    hf = sum(1 for r in hard if not r.passed)
    sw = sum(1 for r in soft if not r.passed)

    lines = [
        f"Article validation: {html_file}",
        f"Intent: {intent} | Site: {site} | SERP: {'available' if serp_avail else 'unavailable'}",
        "",
        f"HARD ASSERTIONS (must pass) [{hp}/{len(hard)} passed]",
        "-" * 60,
    ]
    for r in hard:
        label = getattr(r, "_label", r.spec_ref)
        if r.passed:
            lines.append(f"  [PASS] {label}")
        else:
            lines.append(f"  [FAIL] {label}")
            lines.append(f"         spec: docs/article-spec.md#{r.spec_ref}")
            lines.append(f"         detail: {r.detail}")

    lines += [
        "",
        f"SOFT WARNINGS (logged, not blocking) [{sw} warnings]",
        "-" * 60,
    ]
    for r in soft:
        label = getattr(r, "_label", r.spec_ref)
        if r.passed:
            lines.append(f"  [OK]   {label}")
        else:
            lines.append(f"  [WARN] {label}")
            if r.detail:
                lines.append(f"         detail: {r.detail}")

    lines += [
        "",
        f"Summary: {hp}/{len(hard)} hard passed, {hf} hard failed, {sw} soft warnings",
        f"Exit: {1 if hf > 0 else 0}",
    ]
    return "\n".join(lines)


def _format_json(html_file, intent, site, serp_avail, hard, soft) -> str:
    hp = sum(1 for r in hard if r.passed)
    hf = sum(1 for r in hard if not r.passed)
    sw = sum(1 for r in soft if not r.passed)

    def _r(r):
        return {
            "spec_ref": r.spec_ref,
            "label": getattr(r, "_label", ""),
            "passed": r.passed,
            "severity": r.severity,
            "detail": r.detail,
        }

    return json.dumps({
        "html_file": html_file,
        "intent": intent,
        "site": site,
        "serp_available": serp_avail,
        "hard_assertions": [_r(r) for r in hard],
        "soft_assertions": [_r(r) for r in soft],
        "summary": {
            "hard_total": len(hard),
            "hard_passed": hp,
            "hard_failed": hf,
            "soft_total": len(soft),
            "soft_warnings": sw,
            "exit_code": 1 if hf > 0 else 0,
        },
    }, indent=2)


def _format_markdown(html_file, intent, site, serp_avail, hard, soft) -> str:
    hp = sum(1 for r in hard if r.passed)
    hf = sum(1 for r in hard if not r.passed)
    sw = sum(1 for r in soft if not r.passed)

    lines = [
        "# Article Validation Report",
        "",
        f"- **File:** `{html_file}`",
        f"- **Intent:** {intent}",
        f"- **Site:** {site}",
        f"- **SERP:** {'available' if serp_avail else 'unavailable'}",
        "",
        f"## Hard Assertions ({hp}/{len(hard)} passed)",
        "",
    ]
    for r in hard:
        label = getattr(r, "_label", r.spec_ref)
        if r.passed:
            lines.append(f"- [x] {label}")
        else:
            lines.append(f"- [ ] **FAIL** {label}")
            if r.detail:
                lines.append(f"  - {r.detail}")
                lines.append(f"  - Ref: `docs/article-spec.md#{r.spec_ref}`")

    lines += ["", f"## Soft Warnings ({sw} warnings)", ""]
    for r in soft:
        label = getattr(r, "_label", r.spec_ref)
        if r.passed:
            lines.append(f"- [x] {label}")
        else:
            lines.append(f"- [ ] **WARN** {label}")
            if r.detail:
                lines.append(f"  - {r.detail}")

    lines += [
        "", "## Summary", "",
        "| Metric | Count |",
        "|--------|-------|",
        f"| Hard passed | {hp} |",
        f"| Hard failed | {hf} |",
        f"| Soft warnings | {sw} |",
        f"| Exit code | {1 if hf > 0 else 0} |",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validate an assembled article against spec Section 18 assertions"
    )
    parser.add_argument("--html-file", required=True, help="Path to article HTML")
    parser.add_argument(
        "--intent", required=True,
        choices=["cost", "decision", "definition", "process", "comparison"],
        help="Article intent type",
    )
    parser.add_argument("--site", required=True, help="Site slug (e.g., lrg, valn)")
    parser.add_argument("--serp-json", help="Path to SERP JSON (optional)")
    parser.add_argument("--atf-faqs-json", help="Path to ATF FAQ question list JSON")
    parser.add_argument(
        "--output-format", default="text", choices=["text", "json", "markdown"],
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Exit 1 on soft warnings too",
    )
    args = parser.parse_args()

    # Load HTML
    html_path = Path(args.html_file)
    if not html_path.exists():
        eprint(f"Error: HTML file not found: {html_path}")
        sys.exit(1)

    html = html_path.read_text()
    if not html.strip():
        eprint("Error: HTML file is empty")
        sys.exit(1)

    start = time.time()
    soup = BeautifulSoup(html, "html.parser")

    # Build context
    context = _build_context(args, soup)
    serp_avail = context["serp_data"] is not None

    # Run assertions
    hard_results, soft_results = _run_all(soup, context)
    elapsed = time.time() - start

    # Format and print
    fmt = {"text": _format_text, "json": _format_json, "markdown": _format_markdown}
    output = fmt[args.output_format](
        str(html_path), args.intent, args.site, serp_avail,
        hard_results, soft_results,
    )
    print(output)

    # Summary to stderr
    hp = sum(1 for r in hard_results if r.passed)
    hf = sum(1 for r in hard_results if not r.passed)
    sw = sum(1 for r in soft_results if not r.passed)
    eprint(f"\nValidation complete in {elapsed:.2f}s: "
           f"{hp}/{len(hard_results)} hard passed, {hf} failed, {sw} soft warnings")

    # Exit code
    if hf > 0:
        sys.exit(1)
    if args.strict and sw > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
