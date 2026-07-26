#!/usr/bin/env python3
"""Build the rl-qstats strip (four-stat strip).

Mechanical builder — no LLM call. Takes exactly 4 stat entries from a
JSON file and emits the rl-qstats HTML block.

Each stat entry must have: {value, label, source_url}.
Values are spec-approved verbatim from verified sources. This builder
NEVER generates, rounds, reformats, or infers a stat value.  If fewer
than 4 entries exist, the builder exits nonzero with a clear message
and emits nothing — no partial strips.

Placement contract (CLAUDE.md): after ATF lede, before quick-card grid.

Usage:
    python3 build-qstats.py \\
        --stats-json /path/to/stats.json \\
        [--output /path/to/qstats.html]

stats.json format:
    [
      {"value": "$25,000", "label": "Tax Exemption", "source_url": "https://..."},
      {"value": "100%",    "label": "Disability Rating", "source_url": "https://..."},
      ...
    ]
"""

import argparse
import json
import sys
from html import escape
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
MODULE_DIR = TOOLS_DIR.parent
sys.path.insert(0, str(MODULE_DIR))

from lib.tool_utils import eprint, write_output


def validate_stats(stats: list) -> list[str]:
    """Validate stat entries. Returns list of error strings (empty = valid)."""
    errors = []
    if not isinstance(stats, list):
        errors.append("Stats JSON must be a list")
        return errors
    if len(stats) != 4:
        errors.append(
            f"Expected exactly 4 stats, got {len(stats)}. "
            "No partial strips — provide all 4 or omit the component."
        )
        return errors
    for i, s in enumerate(stats, 1):
        if not isinstance(s, dict):
            errors.append(f"Stat {i}: not a dict")
            continue
        for field in ("value", "label", "source_url"):
            val = s.get(field, "")
            if not isinstance(val, str) or not val.strip():
                errors.append(f"Stat {i}: missing or empty '{field}'")
    return errors


def build_qstats_html(stats: list) -> str:
    """Build the rl-qstats HTML from 4 validated stat entries.

    Uses .rl-qs / .v / .l classes matching the deployed CSS in
    lrg-article-styles.php (lines 385-391).
    """
    boxes = []
    for s in stats:
        value = escape(s["value"].strip())
        label = escape(s["label"].strip())
        boxes.append(
            f'<div class="rl-qs">'
            f'<div class="v">{value}</div>'
            f'<div class="l">{label}</div>'
            f'</div>'
        )
    return '<div class="rl-qstats">\n' + "\n".join(boxes) + "\n</div>"


def main():
    parser = argparse.ArgumentParser(
        description="Build the rl-qstats strip (spec: 4 stat boxes)"
    )
    parser.add_argument(
        "--stats-json", required=True,
        help="Path to JSON file with exactly 4 stat entries "
             "[{value, label, source_url}, ...]",
    )
    parser.add_argument("--output", help="Output file path (default: stdout)")
    args = parser.parse_args()

    eprint("[build-qstats] Loading stats")
    stats_path = Path(args.stats_json)
    if not stats_path.exists():
        eprint(f"Error: stats file not found: {stats_path}")
        sys.exit(1)

    try:
        stats = json.loads(stats_path.read_text())
    except json.JSONDecodeError as exc:
        eprint(f"Error: invalid JSON in {stats_path}: {exc}")
        sys.exit(1)

    errors = validate_stats(stats)
    if errors:
        for e in errors:
            eprint(f"  ERROR: {e}")
        eprint("[build-qstats] FAILED — cannot build strip with invalid stats")
        sys.exit(1)

    html = build_qstats_html(stats)

    eprint("[build-qstats] Stats sourced from:")
    for i, s in enumerate(stats, 1):
        eprint(f"  {i}. {s['value']} ({s['label']}) — {s['source_url']}")

    eprint("[build-qstats] Strip built successfully (4 boxes).")
    write_output(html, args.output)


if __name__ == "__main__":
    main()
