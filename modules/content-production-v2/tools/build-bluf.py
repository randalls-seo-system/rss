#!/usr/bin/env python3
"""Build the BLUF (Bottom Line Up Front) section.

Single-section builder, callable independently for iteration.
Loads topic context from a file, anchor pool for inline links, renders
prompts/bluf.md, calls LLM, validates per spec Section 8.

Usage:
    python3 build-bluf.py \\
        --site lrg \\
        --target-keyword "va funding fee" \\
        --topic-context /path/to/context.json \\
        --friction-point "Fee ranges from 1.25% to 3.3% depending on use count" \\
        --serp-json /path/to/serp.json \\
        [--output /path/to/bluf.html]
"""

import argparse
import json
import re
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
MODULE_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(MODULE_DIR))

from bs4 import BeautifulSoup

from lib.anchor_pool import AnchorPool
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


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def validate_bluf(html: str) -> list[str]:
    """Validate BLUF HTML per spec Section 8."""
    errors = []
    soup = BeautifulSoup(html, "html.parser")

    bluf = soup.find("section", class_="rl-bluf")
    if bluf is None:
        errors.append("Missing <section class='rl-bluf'> wrapper (spec 8.2)")
        return errors

    paragraphs = bluf.find_all("p")
    if len(paragraphs) < 2:
        errors.append(
            f"BLUF has {len(paragraphs)} paragraphs, need at least 2 (lead + body) (spec 8.2)"
        )
        return errors

    # Lead paragraph: 50-70 words, entirely bolded
    lead = paragraphs[0]
    lead_strong = lead.find("strong")
    if lead_strong is None:
        errors.append("BLUF lead paragraph not wrapped in <strong> (spec 8.3.1)")
    lead_text = lead.get_text(strip=True)
    lead_wc = _word_count(lead_text)
    if not (50 <= lead_wc <= 70):
        errors.append(f"BLUF lead is {lead_wc} words, expected 50-70 (spec 8.2)")

    # Body paragraph: 70-100 words, not bolded
    body = paragraphs[1]
    body_text = body.get_text(strip=True)
    body_wc = _word_count(body_text)
    if not (70 <= body_wc <= 100):
        errors.append(f"BLUF body is {body_wc} words, expected 70-100 (spec 8.2)")

    # Exactly 5 capstone bullets
    ul = bluf.find("ul")
    if ul is None:
        errors.append("BLUF missing capstone bullet list (spec 8.3.5)")
    else:
        bullets = ul.find_all("li")
        if len(bullets) != 5:
            errors.append(
                f"BLUF has {len(bullets)} capstone bullets, expected exactly 5 (spec 8.3.5)"
            )

    return errors


def _load_topic_context(ctx_path: Path, serp: SerpData | None, keyword: str) -> str:
    """Load topic context from file, falling back to SERP if file not found."""
    if ctx_path.exists():
        text = ctx_path.read_text()
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return "\n".join(f"- {k}: {v}" for k, v in data.items())
            elif isinstance(data, list):
                return "\n".join(f"- {item}" for item in data)
        except json.JSONDecodeError:
            pass
        return text

    eprint(f"Warning: topic-context file not found: {ctx_path}, using SERP context")
    if serp:
        return build_topic_context(serp, keyword)
    return "(No topic context available)"


def main():
    parser = argparse.ArgumentParser(
        description="Build the BLUF section (spec Section 8)"
    )
    parser.add_argument("--site", required=True, help="Site slug")
    parser.add_argument("--target-keyword", required=True, help="Target keyword")
    parser.add_argument("--topic-context", required=True, help="Path to topic context JSON")
    parser.add_argument("--friction-point", required=True, help="Central friction/watch-out point")
    parser.add_argument("--serp-json", required=True, help="Path to SERP JSON")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    args = parser.parse_args()

    eprint(f"[build-bluf] Building BLUF for: {args.target_keyword}")

    config = load_site_config(args.site)
    archetype = config.get("branding", {}).get("archetype", "")
    provider = config.get("AI_PROVIDER", "claude_cli")
    model = config.get("AI_MODEL") or None

    # Load topic context
    serp = SerpData(Path(args.serp_json))
    topic_context = _load_topic_context(
        Path(args.topic_context), serp, args.target_keyword
    )

    # Load anchor pool
    pool = AnchorPool(args.site)
    candidates = pool.candidates_for_topic(args.target_keyword, max=3)

    if candidates:
        anchor_lines = "\n".join(
            f"{c.anchor_text} -> {c.url}" for c in candidates
        )
    else:
        anchor_lines = "(No anchor pool candidates available)"

    brand_voice = load_brand_voice(archetype) if archetype else ""

    # Render prompt
    template = load_prompt_template("bluf.md")
    prompt = render_prompt(template, {
        "TARGET_KEYWORD": args.target_keyword,
        "TOPIC_CONTEXT": topic_context,
        "FRICTION_POINT": args.friction_point,
        "ANCHOR_POOL_CANDIDATES": anchor_lines,
        "INJECT_BRAND_VOICE": brand_voice,
    })

    # Call LLM
    eprint(f"[build-bluf] Calling LLM ({provider}/{model or 'default'})")
    client = LLMClient(provider=provider, model=model)
    cache_key = f"{args.site}|{args.target_keyword}|build-bluf"
    response = client.call(prompt, cache_key=cache_key)

    eprint(
        f"[build-bluf] LLM: {response.input_tokens}in/{response.output_tokens}out "
        f"(${response.cost_estimate:.4f}, cached={response.cached})"
    )

    html = extract_html(response.text)

    html = validate_or_retry(
        html, validate_bluf, client, prompt, cache_key,
        "build-bluf", args.target_keyword,
    )

    eprint("[build-bluf] BLUF built successfully.")
    write_output(html, args.output)


if __name__ == "__main__":
    main()
