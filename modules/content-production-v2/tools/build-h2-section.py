#!/usr/bin/env python3
"""Build ONE body H2 section.

Debugging unit: regenerate one H2 section independently.
Loads SERP for topic context, anchor pool for inline links, renders
prompts/h2-section.md, calls LLM, validates per spec Section 9.

Usage:
    python3 build-h2-section.py \\
        --site lrg \\
        --target-keyword "va funding fee" \\
        --h2-title "Who Is Exempt From The VA Funding Fee" \\
        --section-role exemptions_section \\
        --structural-element bullets \\
        --target-word-count 280 \\
        --serp-json /path/to/serp.json \\
        [--callout-key numerical_proof] \\
        [--callout-label "Deal Math"] \\
        [--output /path/to/section.html]
"""

import argparse
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
MODULE_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(MODULE_DIR))

from bs4 import BeautifulSoup, Tag

from lib.llm_client import LLMClient
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


def _is_external(href: str, site_domain: str = "") -> bool:
    """Check if a URL is external. Same-domain absolute URLs are internal."""
    if not (href.startswith("http://") or href.startswith("https://")):
        return False
    if site_domain:
        from urllib.parse import urlparse
        host = urlparse(href).netloc.lower().lstrip("www.")
        if host == site_domain.lower().lstrip("www."):
            return False
    return True


def make_validator(structural_pref: str, site_domain: str = ""):
    """Return a validation function for the given structural element preference."""

    def validate_h2_section(html: str) -> list[str]:
        errors = []
        soup = BeautifulSoup(html, "html.parser")

        h2 = soup.find("h2")
        if h2 is None:
            errors.append("Missing H2 heading (spec 9.3)")

        paragraphs = soup.find_all("p")
        if not paragraphs:
            errors.append("Missing intro paragraph (spec 9.3)")

        tables = soup.find_all("table")
        lists = soup.find_all("ul")
        callouts = soup.find_all(
            "div", class_=lambda c: c and "rl-callout" in c
        )

        struct_count = len(tables) + len(lists) + len(callouts)
        if structural_pref == "prose_optional_table":
            # prose_optional_table: structural element is optional
            pass
        elif struct_count == 0:
            errors.append(
                f"No structural element found; expected '{structural_pref}' (spec 9.3)"
            )
        elif struct_count > 1:
            errors.append(
                f"Found {struct_count} structural elements; expected exactly 1 (spec 9.3)"
            )

        if structural_pref == "table" and not tables and struct_count > 0:
            errors.append("Expected table structural element, got other type")
        elif structural_pref == "bullets" and not lists and struct_count > 0:
            errors.append("Expected bullets (ul) structural element, got other type")
        elif structural_pref == "callout" and not callouts and struct_count > 0:
            errors.append("Expected callout structural element, got other type")

        for a in soup.find_all("a", href=True):
            if _is_external(a["href"], site_domain):
                errors.append(
                    f"External link found: {a['href'][:60]} (spec 9.6.4)"
                )
                break

        return errors

    return validate_h2_section


def main():
    parser = argparse.ArgumentParser(
        description="Build ONE body H2 section (spec Section 9)"
    )
    parser.add_argument("--site", required=True, help="Site slug")
    parser.add_argument("--target-keyword", required=True, help="Target keyword")
    parser.add_argument("--h2-title", required=True, help="H2 section title")
    parser.add_argument("--section-role", required=True, help="Section role")
    parser.add_argument(
        "--structural-element", required=True,
        choices=["table", "bullets", "callout", "prose_optional_table"],
        help="Locked structural element from template",
    )
    parser.add_argument("--callout-key", help="Callout CSS key (required if structural-element=callout)")
    parser.add_argument("--callout-label", help="Callout visible label (required if structural-element=callout)")
    parser.add_argument(
        "--target-word-count", required=True, type=int,
        help="Target word count for this section",
    )
    parser.add_argument("--serp-json", required=True, help="Path to SERP JSON")
    parser.add_argument("--template-hint", default="", help="Role hint from structural template (e.g., 'Headline fee schedule or rate breakdown')")
    parser.add_argument("--prior-sections-summary", default="", help="Summary of prior sections for context continuity")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    args = parser.parse_args()

    if args.structural_element == "callout":
        if not args.callout_key or not args.callout_label:
            parser.error(
                "--callout-key and --callout-label required when --structural-element=callout"
            )

    eprint(f"[build-h2-section] Building: {args.h2_title}")

    config = load_site_config(args.site)
    archetype = config.get("branding", {}).get("archetype", "")
    provider = config.get("AI_PROVIDER", "claude_cli")
    model = config.get("AI_MODEL") or None

    # Load SERP and build context
    serp = SerpData(Path(args.serp_json))
    topic_context = build_topic_context(serp, f"{args.h2_title} {args.target_keyword}")

    brand_voice = load_brand_voice(archetype) if archetype else ""

    # Prior sections summary (for cross-section context)
    prior_summary = args.prior_sections_summary if hasattr(args, 'prior_sections_summary') and args.prior_sections_summary else ""

    # Render prompt (no anchor pool — linking is single-pass via inject-internal-links.py)
    template = load_prompt_template("h2-section.md")
    prompt = render_prompt(template, {
        "TARGET_KEYWORD": args.target_keyword,
        "H2_TITLE": args.h2_title,
        "SECTION_ROLE": args.section_role,
        "STRUCTURAL_ELEMENT_PREFERENCE": args.structural_element,
        "TEMPLATE_HINT": args.template_hint or "",
        "CALLOUT_KEY": args.callout_key or "",
        "CALLOUT_LABEL": args.callout_label or "",
        "TARGET_WORD_COUNT": str(args.target_word_count),
        "TOPIC_CONTEXT": topic_context,
        "PRIOR_SECTIONS_SUMMARY": prior_summary,
        "INJECT_BRAND_VOICE": brand_voice,
    })

    # Call LLM
    eprint(f"[build-h2-section] Calling LLM ({provider}/{model or 'default'})")
    client = LLMClient(provider=provider, model=model)
    cache_key = f"{args.site}|{args.target_keyword}|build-h2-section|{args.h2_title}"
    response = client.call(prompt, cache_key=cache_key)

    eprint(
        f"[build-h2-section] LLM: {response.input_tokens}in/{response.output_tokens}out "
        f"(${response.cost_estimate:.4f}, cached={response.cached})"
    )

    html = extract_html(response.text)

    site_domain = config.get("SITE_DOMAIN", "")
    validator = make_validator(args.structural_element, site_domain)
    html = validate_or_retry(
        html, validator, client, prompt, cache_key,
        "build-h2-section", args.target_keyword,
    )

    eprint("[build-h2-section] Section built successfully.")
    write_output(html, args.output)


if __name__ == "__main__":
    main()
