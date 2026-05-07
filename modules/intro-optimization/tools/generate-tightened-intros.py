#!/usr/bin/env python3
"""Generate tightened intros via LLM, cluster-aware.

Usage:
    python3 generate-tightened-intros.py \
        --intros-csv intros.csv \
        --site lrg \
        --output-csv proposed.csv

Reads the prompt template from prompts/intro-tightening.md and fills in
per-page variables before sending to the LLM.
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT / 'lib'))

SITE_META = {
    'lrg': {
        'site_name': 'LRG Realty',
        'brand_tone': 'direct, expert-level',
        'location_primary': 'San Antonio, TX',
    },
}


def load_prompt_template():
    path = MODULE_ROOT / 'prompts' / 'intro-tightening.md'
    with open(path) as f:
        return f.read()


def load_clusters(path):
    """Load cluster data (post_id → parent query info). Returns dict."""
    if not path or not os.path.exists(path):
        return {}
    with open(path) as f:
        data = json.load(f)
    # Normalize: ensure post_id keys are strings
    out = {}
    if isinstance(data, list):
        for item in data:
            pid = str(item.get('post_id', item.get('ID', '')))
            out[pid] = item
    elif isinstance(data, dict):
        for k, v in data.items():
            out[str(k)] = v
    return out


def fill_prompt(template, row, cluster, site_meta):
    """Fill the prompt template with per-page variables."""
    cl = cluster or {}
    replacements = {
        '{{SITE_NAME}}': site_meta['site_name'],
        '{{BRAND_TONE}}': site_meta['brand_tone'],
        '{{LOCATION_PRIMARY}}': site_meta['location_primary'],
        '{{POST_TITLE}}': row.get('post_title', ''),
        '{{URL}}': row.get('url', ''),
        '{{PARENT_QUERY}}': cl.get('parent_query', cl.get('query', 'unknown')),
        '{{PARENT_IMPRESSIONS}}': str(cl.get('impressions', '?')),
        '{{PARENT_POSITION}}': str(cl.get('position', '?')),
        '{{INTENT}}': cl.get('intent', cl.get('dominant_intent', 'informational')),
        '{{CURRENT_WORD_COUNT}}': row.get('current_word_count', '?'),
        '{{CURRENT_INTRO}}': row.get('current_intro_text', ''),
    }
    prompt = template
    for key, val in replacements.items():
        prompt = prompt.replace(key, str(val))
    return prompt


def call_llm(prompt, provider, model):
    """Call LLM and return parsed JSON response."""
    if provider == 'openai':
        from openai import OpenAI
        client = OpenAI()
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': 'You are an expert content editor. Respond with valid JSON only.'},
                {'role': 'user', 'content': prompt},
            ],
            temperature=0.3,
            response_format={'type': 'json_object'},
        )
        return json.loads(resp.choices[0].message.content)
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'openai' with gpt-5.4-mini.")


def validate_output(result, target_wc):
    """Validate LLM output. Returns (ok, errors)."""
    errors = []
    intro = result.get('intro', '')
    wc = len(intro.split())

    if wc < 40 or wc > 85:
        errors.append(f"word count {wc} outside 40-85 range")

    filler = ['in this guide', 'we will explore', 'welcome to',
              'let\'s dive', 'there are many', 'if you are wondering']
    for phrase in filler:
        if phrase in intro.lower():
            errors.append(f"filler phrase detected: '{phrase}'")

    if not result.get('captures_parent_query', False):
        errors.append("LLM flagged: does not capture parent query")

    return len(errors) == 0, errors


def main():
    parser = argparse.ArgumentParser(description='Generate tightened intros via LLM')
    parser.add_argument('--intros-csv', required=True)
    parser.add_argument('--clusters-json', default='')
    parser.add_argument('--site', required=True, choices=SITE_META.keys())
    parser.add_argument('--output-csv', required=True)
    parser.add_argument('--provider', default='openai', choices=['openai'])
    parser.add_argument('--model', default='gpt-5.4-mini')
    parser.add_argument('--target-word-count', type=int, default=60)
    parser.add_argument('--batch-size', type=int, default=25)
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--sleep', type=float, default=1.0,
                        help='Seconds between LLM calls (default: 1)')
    args = parser.parse_args()

    template = load_prompt_template()
    clusters = load_clusters(args.clusters_json)
    site_meta = SITE_META[args.site]

    with open(args.intros_csv) as f:
        rows = list(csv.DictReader(f))

    # Resume support
    done_ids = set()
    if args.resume and os.path.exists(args.output_csv):
        with open(args.output_csv) as f:
            for r in csv.DictReader(f):
                done_ids.add(r['post_id'])
        print(f"Resuming: {len(done_ids)} already done")

    fieldnames = [
        'post_id', 'url', 'current_intro', 'proposed_intro',
        'proposed_eyebrow', 'proposed_disclaimer_callout',
        'current_word_count', 'proposed_word_count',
        'captures_parent_query', 'removed_filler', 'rationale',
    ]

    mode = 'a' if args.resume and done_ids else 'w'
    with open(args.output_csv, mode, newline='') as out:
        writer = csv.DictWriter(out, fieldnames=fieldnames)
        if mode == 'w':
            writer.writeheader()

        for i, row in enumerate(rows):
            pid = row['post_id']
            if pid in done_ids:
                continue

            print(f"[{i+1}/{len(rows)}] Post {pid}: {row.get('post_title', '')[:50]}")

            cluster = clusters.get(pid, {})
            prompt = fill_prompt(template, row, cluster, site_meta)

            # Call LLM with one retry on validation failure
            result = None
            for attempt in range(2):
                try:
                    result = call_llm(prompt, args.provider, args.model)
                    ok, errors = validate_output(result, args.target_word_count)
                    if ok:
                        break
                    print(f"  Validation errors (attempt {attempt+1}): {errors}",
                          file=sys.stderr)
                    if attempt == 0:
                        prompt += "\n\nPREVIOUS ATTEMPT FAILED VALIDATION: " + '; '.join(errors)
                except Exception as e:
                    print(f"  LLM error (attempt {attempt+1}): {e}", file=sys.stderr)
                    result = None

            if not result:
                print(f"  SKIP: LLM failed after retries", file=sys.stderr)
                continue

            writer.writerow({
                'post_id': pid,
                'url': row.get('url', ''),
                'current_intro': row.get('current_intro_text', ''),
                'proposed_intro': result.get('intro', ''),
                'proposed_eyebrow': result.get('eyebrow', ''),
                'proposed_disclaimer_callout': result.get('disclaimer_callout', ''),
                'current_word_count': row.get('current_word_count', ''),
                'proposed_word_count': result.get('intro_word_count', len(result.get('intro', '').split())),
                'captures_parent_query': result.get('captures_parent_query', ''),
                'removed_filler': json.dumps(result.get('removed_filler', [])),
                'rationale': result.get('rationale', ''),
            })
            out.flush()

            proposed_wc = result.get('intro_word_count', '?')
            print(f"  {row.get('current_word_count', '?')} → {proposed_wc} words")

            time.sleep(args.sleep)

    print(f"\nDone. Proposals written to {args.output_csv}")


if __name__ == '__main__':
    main()
