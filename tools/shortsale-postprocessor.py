#!/usr/bin/env python3
"""Shortsale vertical postprocessor.

Mechanical fixes applied AFTER assemble-article.py output.
Does NOT strip content sections — off-topic sections are generation
failures that must be surfaced, not hidden.

Fixes applied:
  1. Em dash (U+2014) → hyphen or rephrased
  2. AI-lexicon word replacement
  3. CTA swap: generic → "Get My Free Home Equity Analysis"
  4. Internal link injection per article config
  5. Repetition thinning (phrases appearing 4+ times)
  6. Hardcoded methodology block injection
"""

import argparse
import json
import re
import sys
from pathlib import Path
from bs4 import BeautifulSoup


# --- AI lexicon words to replace ---
AI_LEXICON = {
    "leverage": "use",
    "leveraging": "using",
    "leveraged": "used",
    "utilize": "use",
    "utilizing": "using",
    "utilized": "used",
    "utilization": "use",
    "delve": "examine",
    "delving": "examining",
    "navigate": "work through",
    "navigating": "working through",
    "landscape": "market",
    "tapestry": "mix",
    "multifaceted": "complex",
    "holistic": "complete",
    "synergy": "combination",
    "robust": "strong",
    "paradigm": "model",
    "empower": "help",
    "empowering": "helping",
    "embark": "start",
    "embarking": "starting",
    "realm": "area",
    "pivotal": "important",
    "seamless": "smooth",
    "seamlessly": "smoothly",
    "nestled": "located",
    "boasts": "has",
    "elevate": "improve",
    "endeavor": "effort",
    "fostering": "building",
    "foster": "build",
    "cornerstone": "foundation",
    "standout": "notable",
}


def fix_em_dashes(html: str) -> tuple[str, int]:
    """Replace em dashes with hyphens. Return (fixed_html, count)."""
    count = html.count("\u2014")
    # Replace " — " (spaced em dash) with " - "
    fixed = html.replace(" \u2014 ", " - ")
    # Replace "—" (unspaced) with " - "
    fixed = fixed.replace("\u2014", " - ")
    return fixed, count


def fix_ai_lexicon(html: str) -> tuple[str, list[str]]:
    """Replace AI-lexicon words. Return (fixed_html, list of replacements made)."""
    replacements = []
    for word, replacement in AI_LEXICON.items():
        # Case-insensitive replacement preserving surrounding context
        pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
        matches = pattern.findall(html)
        if matches:
            for match in set(matches):
                # Preserve capitalization
                if match[0].isupper():
                    rep = replacement.capitalize()
                else:
                    rep = replacement
                html = html.replace(match, rep)
                replacements.append(f"{match} -> {rep}")
    return html, replacements


def fix_cta(html: str) -> tuple[str, int]:
    """Replace generic CTA with equity analysis CTA. Return (fixed, count)."""
    count = 0
    # Replace "Connect with LRG" text in CTA links
    old_patterns = [
        "Connect with LRG",
        "Connect With LRG",
        "Contact LRG",
        "Contact Us",
        "Get in Touch",
        "Reach Out to LRG",
    ]
    for old in old_patterns:
        if old in html:
            html = html.replace(old, "Get My Free Home Equity Analysis")
            count += 1
    # Also fix the CTA URL if pointing to connect-with-lrg
    html = html.replace("/lrg-blog/connect-with-lrg/", "/lrg-blog/connect-with-lrg/")
    return html, count


def inject_internal_links(html: str, links_config: dict) -> tuple[str, list[str]]:
    """Inject internal links per article config. Return (html, injections_log)."""
    injections = []
    soup = BeautifulSoup(html, "html.parser")

    # Check which links already exist
    existing_hrefs = set()
    for a in soup.find_all("a", href=True):
        existing_hrefs.add(a["href"].rstrip("/"))

    links_to = links_config.get("links_to", [])
    for link in links_to:
        url = link["url"].rstrip("/")
        if url in existing_hrefs:
            injections.append(f"ALREADY PRESENT: {url}")
            continue
        anchor = link.get("anchor", link.get("title", ""))
        # Find a paragraph containing a relevant keyword to inject the link
        target_text = link.get("match_text", anchor.lower())
        injected = False
        for p in soup.find_all("p"):
            if target_text.lower() in p.get_text().lower() and not p.find("a", href=True):
                # Find the text node and wrap the first occurrence
                text = p.get_text()
                idx = text.lower().find(target_text.lower())
                if idx >= 0:
                    matched = text[idx:idx + len(target_text)]
                    new_a = soup.new_tag("a", href=link["url"])
                    new_a.string = matched
                    # Replace in the paragraph's string content
                    for child in p.children:
                        if isinstance(child, str) and matched in child:
                            parts = child.split(matched, 1)
                            child.replace_with(parts[0])
                            p.insert(list(p.children).index(child) + 1 if child in p.children else len(list(p.children)), new_a)
                            if parts[1]:
                                new_a.insert_after(parts[1])
                            injected = True
                            injections.append(f"INJECTED: {anchor} -> {url}")
                            break
                if injected:
                    break
        if not injected:
            injections.append(f"COULD NOT INJECT (no matching paragraph): {anchor} -> {url}")

    return str(soup), injections


def inject_methodology_block(html: str) -> tuple[str, bool]:
    """Replace any pipeline-generated methodology block with the hardcoded
    version, or inject fresh if none exists. Never results in duplicates.
    Returns (html, was_injected)."""
    methodology = """<div class="rl-methodology">
<h3>How We Researched This Article</h3>
<p>This guide draws on Texas Property Code, IRS publications, and publicly available housing data. All legal references cite specific code sections. Market data uses ranges and qualitative descriptions rather than point-in-time numbers that change quarterly. We do not provide legal or tax advice. Consult a licensed Texas real estate attorney for legal questions and a CPA for tax questions specific to your situation.</p>
</div>"""

    # Strip ALL existing methodology blocks (pipeline may generate 1-2)
    soup = BeautifulSoup(html, "html.parser")
    strip_count = 0
    for div in soup.find_all("div", class_=lambda c: c and "rl-methodology" in c):
        div.decompose()
        strip_count += 1
    if strip_count:
        html = str(soup)

    # Insert before Resources section (may be section, div, or footer)
    resources_pattern = re.compile(r'(<(?:section|div|footer)[^>]*class="[^"]*rl-resources[^"]*")', re.IGNORECASE)
    match = resources_pattern.search(html)
    if match:
        html = html[:match.start()] + methodology + "\n" + html[match.start():]
        return html, True

    # Fallback: insert before closing Bottom Line
    bl_pattern = re.compile(r'(<(?:section|div)[^>]*class="[^"]*rl-bottom-line[^"]*")', re.IGNORECASE)
    match = bl_pattern.search(html)
    if match:
        html = html[:match.start()] + methodology + "\n" + html[match.start():]
        return html, True

    # Last fallback: before </article> or end
    if "</article>" in html:
        html = html.replace("</article>", methodology + "\n</article>")
        return html, True

    return html, False


def thin_repetition(html: str, threshold: int = 4) -> tuple[str, list[str]]:
    """Flag phrases repeated >= threshold times. Report only, do not auto-fix
    (repetition thinning requires semantic judgment)."""
    text = BeautifulSoup(html, "html.parser").get_text()
    words = text.lower().split()
    # Check 4-6 word phrases
    flags = []
    for n in range(4, 7):
        phrases = {}
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i:i + n])
            phrases[phrase] = phrases.get(phrase, 0) + 1
        for phrase, count in sorted(phrases.items(), key=lambda x: -x[1]):
            if count >= threshold:
                flags.append(f'"{phrase}" x{count}')
    return html, flags[:10]  # Top 10 only


def run_postprocessor(html_path: str, links_config: dict) -> dict:
    """Run all postprocessor passes. Returns a report dict."""
    with open(html_path) as f:
        html = f.read()

    original_len = len(html)
    report = {"changes": [], "warnings": [], "flags": []}

    # 1. Em dashes
    html, em_count = fix_em_dashes(html)
    if em_count:
        report["changes"].append(f"Em dashes replaced: {em_count}")

    # 2. AI lexicon
    html, lex_replacements = fix_ai_lexicon(html)
    if lex_replacements:
        report["changes"].append(f"AI lexicon: {', '.join(lex_replacements)}")

    # 3. CTA swap
    html, cta_count = fix_cta(html)
    if cta_count:
        report["changes"].append(f"CTA swapped to equity analysis: {cta_count}")
    else:
        report["warnings"].append("No generic CTA found to swap")

    # 4. Internal links
    html, link_log = inject_internal_links(html, links_config)
    for entry in link_log:
        if entry.startswith("INJECTED"):
            report["changes"].append(entry)
        elif entry.startswith("ALREADY"):
            pass  # silent
        else:
            report["warnings"].append(entry)

    # 5. Methodology block
    html, meth_injected = inject_methodology_block(html)
    if meth_injected:
        report["changes"].append("Methodology block injected")
    else:
        report["warnings"].append("Could not inject methodology block")

    # 6. Repetition check (report only)
    _, rep_flags = thin_repetition(html)
    if rep_flags:
        report["flags"].extend([f"REPETITION: {f}" for f in rep_flags])

    # 7. Final em dash re-check (methodology block or link injection might reintroduce)
    if "\u2014" in html:
        html = html.replace("\u2014", " - ")
        report["changes"].append("Em dash cleanup (second pass)")

    # Write back
    with open(html_path, "w") as f:
        f.write(html)

    report["bytes_before"] = original_len
    report["bytes_after"] = len(html)
    return report


def main():
    parser = argparse.ArgumentParser(description="Shortsale vertical postprocessor")
    parser.add_argument("--html", required=True, help="Path to article HTML file")
    parser.add_argument("--links-config", required=True, help="Path to links config JSON")
    args = parser.parse_args()

    with open(args.links_config) as f:
        links_config = json.load(f)

    report = run_postprocessor(args.html, links_config)

    print(json.dumps(report, indent=2))
    return 0 if not report["warnings"] else 0  # warnings are non-fatal


if __name__ == "__main__":
    sys.exit(main())
