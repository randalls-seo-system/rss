#!/usr/bin/env python3
"""Convert an existing rl-bluf <ul> block to rl-kcards.

Standalone retrofit converter. Does NOT modify build-bluf.py or bluf.md.
New-build pipeline behavior is unchanged.

Takes HTML containing a <section class="rl-bluf"> with a <ul> of >=2
<li> elements, plus a --labels JSON file with one short label string per
bullet (in order).  Labels are supplied by the human — this converter
NEVER generates, truncates, or infers a label.

SCOPE: only the <ul> inside <section class="rl-bluf"> is touched.  Every
other <ul> in the document — including bullet-section-* wrappers — must
be byte-identical before vs after.

LINK PRESERVATION: all <a> tags inside <li> elements are preserved.
Assertion: count of <a> tags in input <ul> == count in output kcards,
and every href survives unchanged.

Usage:
    python3 convert-bluf-kcards.py \\
        --input /path/to/article.html \\
        --labels /path/to/labels.json \\
        [--output /path/to/converted.html]
"""

import json
import re
import argparse
import sys
from html import escape
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
MODULE_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(MODULE_DIR))

from bs4 import BeautifulSoup

from lib.tool_utils import eprint, write_output


def _extract_hrefs(html: str) -> list[str]:
    """Extract all href attribute values from <a> tags in order."""
    return re.findall(r'<a[^>]+href="([^"]*)"', html)


def _count_a_tags(html: str) -> int:
    """Count <a> opening tags."""
    return len(re.findall(r"<a[\s>]", html))


def _snapshot_non_bluf_uls(soup: BeautifulSoup) -> list[str]:
    """Snapshot every <ul> in the document EXCEPT the one inside rl-bluf."""
    bluf = soup.find("section", class_="rl-bluf")
    bluf_ul = bluf.find("ul") if bluf else None
    result = []
    for ul in soup.find_all("ul"):
        if ul is bluf_ul:
            continue
        result.append(str(ul))
    return result


def convert(html: str, labels: list[str]) -> str:
    """Convert the rl-bluf <ul> to rl-kcards within the given HTML."""
    soup = BeautifulSoup(html, "html.parser")

    # Snapshot all non-BLUF <ul> elements for scope assertion
    pre_uls = _snapshot_non_bluf_uls(soup)

    bluf = soup.find("section", class_="rl-bluf")
    if bluf is None:
        eprint("Error: no <section class='rl-bluf'> found in input")
        sys.exit(1)

    ul = bluf.find("ul")
    if ul is None:
        eprint("Error: no <ul> found inside rl-bluf section")
        sys.exit(1)

    lis = ul.find_all("li", recursive=False)
    li_count = len(lis)

    if li_count < 2:
        eprint(f"Error: BLUF has {li_count} bullet(s), need at least 2")
        sys.exit(1)

    eprint(f"[convert-bluf-kcards] BLUF bullet count: {li_count}")

    # Label count assertion
    if len(labels) != li_count:
        eprint(
            f"Error: label count ({len(labels)}) != bullet count ({li_count}). "
            "Supply exactly one label per bullet."
        )
        sys.exit(1)

    # Snapshot input link state
    input_ul_html = str(ul)
    input_hrefs = _extract_hrefs(input_ul_html)
    input_a_count = _count_a_tags(input_ul_html)

    # Build kcards with .k (label) and .t (bullet content) matching deployed CSS
    cards = []
    for li, label in zip(lis, labels):
        inner = li.decode_contents()
        escaped_label = escape(label.strip())
        cards.append(
            f'<div class="rl-kcard">'
            f'<div class="k">{escaped_label}</div>'
            f'<div class="t">{inner}</div>'
            f'</div>'
        )

    kcards_html = '<div class="rl-kcards">\n' + "\n".join(cards) + "\n</div>"

    # Link preservation assertion
    output_hrefs = _extract_hrefs(kcards_html)
    output_a_count = _count_a_tags(kcards_html)

    if input_a_count != output_a_count:
        eprint(
            f"ASSERTION FAILED: input <ul> had {input_a_count} <a> tags, "
            f"output kcards has {output_a_count}"
        )
        sys.exit(1)

    if input_hrefs != output_hrefs:
        eprint("ASSERTION FAILED: href values changed during conversion")
        eprint(f"  Input hrefs:  {input_hrefs}")
        eprint(f"  Output hrefs: {output_hrefs}")
        sys.exit(1)

    eprint(
        f"[convert-bluf-kcards] Link assertion passed: "
        f"{input_a_count} <a> tag(s), {len(input_hrefs)} href(s) preserved"
    )

    # Replace <ul> with kcards in the DOM
    kcards_soup = BeautifulSoup(kcards_html, "html.parser")
    ul.replace_with(kcards_soup)

    # Scope assertion: all non-BLUF <ul> elements unchanged
    post_uls = _snapshot_non_bluf_uls(soup)

    if pre_uls != post_uls:
        eprint("ASSERTION FAILED: non-BLUF <ul> elements were modified")
        eprint(f"  Before: {len(pre_uls)} <ul> elements")
        eprint(f"  After:  {len(post_uls)} <ul> elements")
        for i, (a, b) in enumerate(zip(pre_uls, post_uls)):
            if a != b:
                eprint(f"  Diff at <ul> index {i}")
        sys.exit(1)

    eprint(
        f"[convert-bluf-kcards] Scope assertion passed: "
        f"{len(post_uls)} non-BLUF <ul> element(s) unchanged"
    )

    return str(soup)


def main():
    parser = argparse.ArgumentParser(
        description="Convert rl-bluf <ul> to rl-kcards with human-supplied labels"
    )
    parser.add_argument(
        "--input", required=True,
        help="Input HTML file path, or '-' for stdin",
    )
    parser.add_argument(
        "--labels", required=True,
        help='JSON file with one label string per bullet: ["Label 1", "Label 2", ...]',
    )
    parser.add_argument("--output", help="Output file path (default: stdout)")
    args = parser.parse_args()

    # Load labels
    labels_path = Path(args.labels)
    if not labels_path.exists():
        eprint(f"Error: labels file not found: {labels_path}")
        sys.exit(1)
    try:
        labels = json.loads(labels_path.read_text())
    except json.JSONDecodeError as exc:
        eprint(f"Error: invalid JSON in {labels_path}: {exc}")
        sys.exit(1)
    if not isinstance(labels, list) or not all(isinstance(l, str) for l in labels):
        eprint("Error: labels JSON must be a list of strings")
        sys.exit(1)

    # Load input HTML
    if args.input == "-":
        html = sys.stdin.read()
    else:
        input_path = Path(args.input)
        if not input_path.exists():
            eprint(f"Error: input file not found: {input_path}")
            sys.exit(1)
        html = input_path.read_text()

    eprint("[convert-bluf-kcards] Converting BLUF <ul> → rl-kcards")
    result = convert(html, labels)
    eprint("[convert-bluf-kcards] Conversion complete.")

    write_output(result, args.output)


if __name__ == "__main__":
    main()
