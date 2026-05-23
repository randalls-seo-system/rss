#!/usr/bin/env python3
"""Build ONE ATF quick-card.

Debugging unit: regenerate one card without redoing the whole article.
Loads overlay for card slot definition, SERP for topic context, renders
prompts/atf-card.md, calls LLM, validates per spec Section 6.

Usage:
    python3 build-card.py \\
        --site lrg \\
        --target-keyword "va funding fee" \\
        --intent cost \\
        --card-slot rates_by_category_card \\
        --serp-json /path/to/serp.json \\
        [--output /path/to/card.html]
"""

import argparse
import sys
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
MODULE_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(MODULE_DIR))

from bs4 import BeautifulSoup

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


def validate_card(html: str) -> list[str]:
    """Validate quick-card HTML per spec Section 6."""
    errors = []
    soup = BeautifulSoup(html, "html.parser")

    card = soup.find("article", class_="rl-quick-card")
    if card is None:
        errors.append("Missing <article class='rl-quick-card'> wrapper (spec 6.2)")
        return errors

    h3 = card.find("h3")
    if h3 is None:
        errors.append("Card missing H3 title (spec 6.2)")

    bullets = card.find_all("li")
    if len(bullets) != 4:
        errors.append(f"Card has {len(bullets)} bullets, expected exactly 4 (spec 6.1)")

    for i, li in enumerate(bullets):
        strong = li.find("strong")
        if strong is None:
            errors.append(f"Bullet {i+1} missing <strong> label (spec 6.4.2)")

    links = card.find_all("a")
    if links:
        errors.append(f"Card contains {len(links)} links; zero allowed (spec 6.5.2)")

    return errors


def main():
    parser = argparse.ArgumentParser(
        description="Build ONE ATF quick-card (spec Section 6)"
    )
    parser.add_argument("--site", required=True, help="Site slug (e.g., lrg)")
    parser.add_argument("--target-keyword", required=True, help="Target keyword")
    parser.add_argument(
        "--intent", required=True,
        choices=["definition", "process", "decision", "cost", "comparison"],
        help="Intent type",
    )
    parser.add_argument("--card-slot", required=True, help="Card slot role from overlay")
    parser.add_argument("--serp-json", required=True, help="Path to SERP JSON")
    parser.add_argument("--prior-cards-synthesis", default="", help="JSON array of prior card synthesis bullets")
    parser.add_argument("--output", help="Output file path (default: stdout)")
    args = parser.parse_args()

    eprint(f"[build-card] Building card: {args.card_slot}")

    # Load site config
    config = load_site_config(args.site)
    archetype = config.get("branding", {}).get("archetype", "")
    provider = config.get("AI_PROVIDER", "claude_cli")
    model = config.get("AI_MODEL") or None

    # Load overlay and find card slot
    eprint(f"[build-card] Loading overlay: {args.intent}")
    overlay = load_overlay(args.intent)

    slot = None
    for s in overlay.card_slots:
        if s.role == args.card_slot:
            slot = s
            break
    if slot is None:
        available = [s.role for s in overlay.card_slots]
        eprint(f"Error: card-slot '{args.card_slot}' not found in {args.intent} overlay.")
        eprint(f"Available slots: {available}")
        sys.exit(1)

    # Load SERP data
    eprint("[build-card] Loading SERP data")
    serp = SerpData(Path(args.serp_json))

    # Build topic context from SERP filtered by card's subtopic
    topic_filter = f"{slot.h3_pattern} {slot.role} {args.target_keyword}"
    topic_context = build_topic_context(serp, topic_filter)

    # Load brand voice
    brand_voice = load_brand_voice(archetype) if archetype else ""

    # Parse prior card synthesis bullets for diversity
    prior_synthesis = ""
    if args.prior_cards_synthesis:
        try:
            import json as _json
            bullets = _json.loads(args.prior_cards_synthesis)
            if bullets:
                prior_synthesis = "\n".join(f"- {b}" for b in bullets)
        except Exception:
            pass

    # Load and render prompt
    template = load_prompt_template("atf-card.md")
    prompt = render_prompt(template, {
        "TARGET_KEYWORD": args.target_keyword,
        "CARD_ROLE": slot.role,
        "H3_PATTERN": slot.h3_pattern,
        "BULLET_LABEL_HINTS": ", ".join(slot.bullet_label_hints),
        "TOPIC_CONTEXT": topic_context,
        "PRIOR_CARDS_SYNTHESIS": prior_synthesis or "(none — this is the first card)",
        "INJECT_BRAND_VOICE": brand_voice,
    })

    # Call LLM
    eprint(f"[build-card] Calling LLM ({provider}/{model or 'default'})")
    client = LLMClient(provider=provider, model=model)
    cache_key = f"{args.site}|{args.target_keyword}|build-card|{args.card_slot}"
    response = client.call(prompt, cache_key=cache_key)

    eprint(
        f"[build-card] LLM response: {response.input_tokens}in/{response.output_tokens}out "
        f"(${response.cost_estimate:.4f}, cached={response.cached})"
    )

    html = extract_html(response.text)

    # Validate with retry
    html = validate_or_retry(
        html, validate_card, client, prompt, cache_key,
        "build-card", args.target_keyword,
    )

    eprint("[build-card] Card built successfully.")
    write_output(html, args.output)


if __name__ == "__main__":
    main()
