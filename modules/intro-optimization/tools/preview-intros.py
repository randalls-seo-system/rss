#!/usr/bin/env python3
"""Generate side-by-side preview of current vs proposed intros.

Usage:
    python3 preview-intros.py --proposals-csv proposed.csv --output-md preview.md
"""

import argparse
import csv
import json


def main():
    parser = argparse.ArgumentParser(description='Preview intro proposals side-by-side')
    parser.add_argument('--proposals-csv', required=True)
    parser.add_argument('--output-md', required=True)
    parser.add_argument('--sample-size', type=int, default=20,
                        help='Max posts to include (default: 20)')
    args = parser.parse_args()

    with open(args.proposals_csv) as f:
        rows = list(csv.DictReader(f))

    rows = rows[:args.sample_size]

    lines = [
        '# Intro Optimization — Before/After Preview',
        f'Posts reviewed: {len(rows)}',
        '',
    ]

    for i, row in enumerate(rows):
        current_wc = row.get('current_word_count', '?')
        proposed_wc = row.get('proposed_word_count', '?')
        filler = row.get('removed_filler', '[]')
        try:
            filler_list = json.loads(filler)
        except (json.JSONDecodeError, TypeError):
            filler_list = []

        lines.append(f'---')
        lines.append(f'## {i+1}. Post {row["post_id"]}')
        lines.append(f'**URL:** {row.get("url", "N/A")}')
        lines.append('')

        lines.append(f'### Current intro ({current_wc} words)')
        lines.append(f'> {row.get("current_intro", "N/A")}')
        lines.append('')

        lines.append(f'### Proposed intro ({proposed_wc} words)')
        eyebrow = row.get('proposed_eyebrow', '').strip()
        if eyebrow:
            lines.append(f'**Eyebrow:** {eyebrow}')
        lines.append(f'> {row.get("proposed_intro", "N/A")}')

        disclaimer = row.get('proposed_disclaimer_callout', '').strip()
        if disclaimer:
            lines.append(f'')
            lines.append(f'**Disclaimer callout:** {disclaimer}')

        lines.append('')
        if filler_list:
            lines.append(f'**Filler removed:** {", ".join(filler_list)}')
        lines.append(f'**Rationale:** {row.get("rationale", "N/A")}')
        lines.append(f'**Captures parent query:** {row.get("captures_parent_query", "?")}')
        lines.append('')

    with open(args.output_md, 'w') as f:
        f.write('\n'.join(lines))

    print(f"Preview written to {args.output_md} ({len(rows)} posts)")


if __name__ == '__main__':
    main()
