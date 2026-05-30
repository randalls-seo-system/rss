#!/usr/bin/env python3
"""Build ATF FAQs (3 items) or BTF FAQs (5-12 items).

ATF mode: calls LLM 3 times (once per FAQ), validates each answer 35-60 words.
BTF mode: single LLM call for all FAQs, validates 5-12 items with no ATF overlap.

Usage (ATF):
    python3 build-faqs.py \\
        --site lrg \\
        --target-keyword "va funding fee" \\
        --mode atf \\
        --serp-json /path/to/serp.json \\
        [--output /path/to/faqs.html]

Usage (BTF):
    python3 build-faqs.py \\
        --site lrg \\
        --target-keyword "va funding fee" \\
        --mode btf \\
        --serp-json /path/to/serp.json \\
        [--exclude-questions /path/to/exclude.json] \\
        [--output /path/to/faqs.html]
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


# ---------------------------------------------------------------------------
# ATF FAQ validation + question sourcing
# ---------------------------------------------------------------------------

def validate_atf_faq(html: str) -> list[str]:
    """Validate a single ATF FAQ <details> element.

    Also rejects responses containing content outside <details> — catches
    LLM reasoning leakage like "Wait, I used an en dash. Let me fix that."
    """
    errors = []
    soup = BeautifulSoup(html, "html.parser")

    # Check for exactly one <details> element
    all_details = soup.find_all("details")
    if len(all_details) == 0:
        errors.append("Missing <details> element")
        return errors
    if len(all_details) > 1:
        errors.append(
            f"Expected 1 <details> element, found {len(all_details)} "
            f"(possible LLM self-correction with duplicate)"
        )

    details = all_details[0]

    summary = details.find("summary")
    if summary is None:
        errors.append("Missing <summary> in <details>")
        return errors

    answer_text = details.get_text(strip=True).replace(
        summary.get_text(strip=True), ""
    ).strip()
    wc = _word_count(answer_text)
    if not (35 <= wc <= 60):
        errors.append(f"ATF FAQ answer is {wc} words, expected 35-60 (spec 7.4.3)")

    # Reject content outside <details> (reasoning leakage)
    # Tolerate stray <h2> headings (common LLM pattern) by stripping them first
    soup_copy = BeautifulSoup(html, "html.parser")
    for h in soup_copy.find_all(re.compile(r"^h[1-6]$")):
        h.decompose()
    for d in soup_copy.find_all("details"):
        d.decompose()
    outside_text = soup_copy.get_text(strip=True)
    if len(outside_text) > 5:
        errors.append(
            f"Content outside <details> ({len(outside_text)} chars): "
            f"'{outside_text[:80]}' — likely LLM reasoning leakage"
        )

    return errors


def get_atf_questions(serp: SerpData, target_keyword: str) -> list[str]:
    """Get 3 ATF FAQ questions from SERP PAA or keyword-based fallback."""
    paa = serp.paa_questions[:3] if serp else []

    if len(paa) >= 3:
        return paa[:3]

    # Keyword-based fallback when PAA is sparse
    fallbacks = [
        f"What is {target_keyword}?",
        f"How does {target_keyword} work?",
        f"Who qualifies for {target_keyword}?",
        f"What are the requirements for {target_keyword}?",
        f"How much does {target_keyword} cost?",
    ]
    for fb in fallbacks:
        if len(paa) >= 3:
            break
        if fb not in paa:
            paa.append(fb)

    return paa[:3]


# ---------------------------------------------------------------------------
# BTF FAQ validation + question sourcing
# ---------------------------------------------------------------------------

def make_btf_validator(exclude_questions: list[str]):
    """Return a BTF FAQ validation function with bound exclude list."""

    def validate_btf_faq(html: str) -> list[str]:
        errors = []
        soup = BeautifulSoup(html, "html.parser")

        details_list = soup.find_all("details")
        if not (5 <= len(details_list) <= 12):
            errors.append(
                f"BTF FAQ has {len(details_list)} items, expected 5-12 (spec 14.1)"
            )

        exclude_lower = {q.lower().strip() for q in exclude_questions}
        seen_questions = set()
        for d in details_list:
            summary = d.find("summary")
            if summary:
                q_text = summary.get_text(strip=True).lower().strip()
                if q_text in exclude_lower:
                    errors.append(
                        f"BTF FAQ overlaps with ATF: '{q_text[:50]}' (spec 14.3.1)"
                    )
                if q_text in seen_questions:
                    errors.append(
                        f"Duplicate BTF FAQ question: '{q_text[:50]}'"
                    )
                seen_questions.add(q_text)

        # Reject content outside <details> (reasoning leakage)
        # Tolerate stray <h2> headings (common LLM pattern) by stripping them first
        soup_copy = BeautifulSoup(html, "html.parser")
        for h in soup_copy.find_all(re.compile(r"^h[1-6]$")):
            h.decompose()
        for d in soup_copy.find_all("details"):
            d.decompose()
        outside_text = soup_copy.get_text(strip=True)
        if len(outside_text) > 5:
            errors.append(
                f"Content outside <details> ({len(outside_text)} chars): "
                f"'{outside_text[:80]}' — likely LLM reasoning leakage"
            )

        return errors

    return validate_btf_faq


def build_btf_questions(
    serp: SerpData, exclude: list[str], target_keyword: str
) -> list[str]:
    """Build 5-12 BTF FAQ questions from PAA[3:] + gap-fill."""
    questions: list[str] = []
    exclude_lower = {q.lower().strip() for q in exclude}

    # PAA questions after the first 3
    for q in serp.paa_questions[3:]:
        if q.lower().strip() not in exclude_lower:
            questions.append(q)

    # Gap-fill from related searches
    for rs in serp.related_searches:
        if len(questions) >= 8:
            break
        q = rs.strip()
        if not q.endswith("?"):
            q = f"What about {q}?"
        if q.lower().strip() not in exclude_lower:
            questions.append(q)

    # Ensure minimum 5 questions with keyword-based gap-fill
    gap_fills = [
        f"How does {target_keyword} work in practice?",
        f"What are the common mistakes with {target_keyword}?",
        f"Who qualifies for {target_keyword}?",
        f"When should you consider {target_keyword}?",
        f"What are the alternatives to {target_keyword}?",
        f"What documents do you need for {target_keyword}?",
        f"How long does {target_keyword} take?",
    ]
    for gf in gap_fills:
        if len(questions) >= 5:
            break
        if gf.lower().strip() not in exclude_lower:
            questions.append(gf)

    return questions[:12]


# ---------------------------------------------------------------------------
# Build modes
# ---------------------------------------------------------------------------

def _build_atf(args, serp, brand_voice, topic_context, client):
    """Build 3 ATF FAQ items, one LLM call each."""
    questions = get_atf_questions(serp, args.target_keyword)
    template = load_prompt_template("atf-faq.md")

    all_html_parts = []
    for i, question in enumerate(questions):
        eprint(f"[build-faqs] ATF FAQ {i+1}/3: {question[:60]}")

        prompt = render_prompt(template, {
            "QUESTION": question,
            "TARGET_KEYWORD": args.target_keyword,
            "TOPIC_CONTEXT": topic_context,
            "INJECT_BRAND_VOICE": brand_voice,
        })

        cache_key = f"{args.site}|{args.target_keyword}|build-atf-faq|{i}"
        response = client.call(prompt, cache_key=cache_key)

        eprint(
            f"[build-faqs] FAQ {i+1} LLM: {response.input_tokens}in/"
            f"{response.output_tokens}out "
            f"(${response.cost_estimate:.4f}, cached={response.cached})"
        )

        html = extract_html(response.text)

        html = validate_or_retry(
            html, validate_atf_faq, client, prompt, cache_key,
            f"build-atf-faq-{i+1}", args.target_keyword,
        )

        all_html_parts.append(html)

    final_html = "\n".join(all_html_parts)
    eprint("[build-faqs] ATF FAQs built successfully (3 items).")
    write_output(final_html, args.output)


def _build_btf(args, serp, brand_voice, topic_context, client):
    """Build BTF FAQ section with single LLM call."""
    exclude: list[str] = []
    if args.exclude_questions:
        try:
            exclude = json.loads(Path(args.exclude_questions).read_text())
        except (json.JSONDecodeError, FileNotFoundError) as e:
            eprint(f"Warning: could not load exclude-questions: {e}")

    questions = build_btf_questions(serp, exclude, args.target_keyword)
    eprint(f"[build-faqs] BTF FAQ: {len(questions)} questions")

    questions_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
    exclude_text = "\n".join(f"- {q}" for q in exclude) if exclude else "(none)"

    template = load_prompt_template("btf-faq.md")
    prompt = render_prompt(template, {
        "QUESTIONS_LIST": questions_text,
        "ATF_FAQ_QUESTIONS_TO_EXCLUDE": exclude_text,
        "TARGET_KEYWORD": args.target_keyword,
        "TOPIC_CONTEXT": topic_context,
        "INJECT_BRAND_VOICE": brand_voice,
    })

    cache_key = f"{args.site}|{args.target_keyword}|build-btf-faq"

    eprint("[build-faqs] Calling LLM for BTF FAQs")
    response = client.call(prompt, cache_key=cache_key)
    eprint(
        f"[build-faqs] BTF LLM: {response.input_tokens}in/{response.output_tokens}out "
        f"(${response.cost_estimate:.4f}, cached={response.cached})"
    )

    html = extract_html(response.text)

    validator = make_btf_validator(exclude)
    html = validate_or_retry(
        html, validator, client, prompt, cache_key,
        "build-btf-faq", args.target_keyword,
    )

    eprint("[build-faqs] BTF FAQs built successfully.")
    write_output(html, args.output)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Build ATF FAQs (3 items) or BTF FAQs (5-12 items)"
    )
    parser.add_argument("--site", required=True, help="Site slug")
    parser.add_argument("--target-keyword", required=True, help="Target keyword")
    parser.add_argument(
        "--mode", required=True, choices=["atf", "btf"],
        help="FAQ mode: atf (3 items) or btf (5-12 items)",
    )
    parser.add_argument("--serp-json", required=True, help="Path to SERP JSON")
    parser.add_argument(
        "--exclude-questions",
        help="Path to JSON list of ATF questions to exclude (for btf mode)",
    )
    parser.add_argument("--output", help="Output file path (default: stdout)")
    args = parser.parse_args()

    eprint(f"[build-faqs] Mode: {args.mode} | Keyword: {args.target_keyword}")

    config = load_site_config(args.site)
    archetype = config.get("branding", {}).get("archetype", "")
    provider = config.get("AI_PROVIDER", "claude_cli")
    model = config.get("AI_MODEL") or None

    serp = SerpData(Path(args.serp_json))
    brand_voice = load_brand_voice(archetype) if archetype else ""
    topic_context = build_topic_context(serp, args.target_keyword)

    client = LLMClient(provider=provider, model=model)

    if args.mode == "atf":
        _build_atf(args, serp, brand_voice, topic_context, client)
    else:
        _build_btf(args, serp, brand_voice, topic_context, client)


if __name__ == "__main__":
    main()
