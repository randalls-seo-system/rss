#!/usr/bin/env python3
"""Validate LLM output against brand voice rules.

Reads a CSV of LLM-generated content (titles, metas, intros) and validates
each row against the archetype's forbidden phrases and required signals.
Outputs the same CSV with voice_pass and voice_violations columns added.

Usage:
    python3 apply-voice-rules.py \
        --archetype realtor \
        --input-csv proposals.csv \
        --columns title,meta \
        --output-csv validated.csv

    python3 apply-voice-rules.py \
        --archetype realtor \
        --input-csv proposals.csv \
        --columns title,meta \
        --output-csv validated.csv \
        --strict
"""

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'lib'))
from voice_validator import validate_full


def main():
    parser = argparse.ArgumentParser(
        description='Validate LLM output against brand voice rules')
    parser.add_argument('--archetype', required=True,
                        help='Archetype name (for reporting)')
    parser.add_argument('--input-csv', required=True,
                        help='CSV with LLM-generated content')
    parser.add_argument('--columns', required=True,
                        help='Comma-separated column names to validate')
    parser.add_argument('--output-csv', required=True,
                        help='Output CSV with voice_pass and voice_violations added')
    parser.add_argument('--strict', action='store_true',
                        help='Exit with error code if any row fails')
    args = parser.parse_args()

    columns_to_check = [c.strip() for c in args.columns.split(',')]

    with open(args.input_csv) as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    if not rows:
        print("ERROR: empty input CSV", file=sys.stderr)
        sys.exit(1)

    # Validate column names exist
    for col in columns_to_check:
        if col not in fieldnames:
            print(f"ERROR: column '{col}' not found in CSV (available: {fieldnames})",
                  file=sys.stderr)
            sys.exit(1)

    # Add output columns
    out_fieldnames = list(fieldnames) + ['voice_pass', 'voice_violations']

    passed = 0
    failed = 0

    with open(args.output_csv, 'w', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=out_fieldnames)
        writer.writeheader()

        for row in rows:
            all_violations = []

            for col in columns_to_check:
                text = row.get(col, '')
                if not text:
                    continue
                ok, violations = validate_full(text)
                for v in violations:
                    v['column'] = col
                    all_violations.append(v)

            row_pass = len(all_violations) == 0
            row['voice_pass'] = row_pass
            row['voice_violations'] = json.dumps(
                [{'col': v['column'], 'cat': v['category'], 'match': v['match']}
                 for v in all_violations]
            ) if all_violations else ''

            writer.writerow(row)

            if row_pass:
                passed += 1
            else:
                failed += 1

    print(f"Archetype: {args.archetype}")
    print(f"Columns checked: {columns_to_check}")
    print(f"Results: {passed} passed, {failed} failed ({len(rows)} total)")
    print(f"Output: {args.output_csv}")

    if args.strict and failed > 0:
        print(f"\nSTRICT MODE: {failed} rows failed voice validation", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
