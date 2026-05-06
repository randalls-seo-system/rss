#!/usr/bin/env python3
"""Generate cluster-optimized title and meta proposals using LLM per page."""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def load_site_conf(site_slug):
    conf_path = Path(__file__).resolve().parent.parent.parent.parent / 'sites' / f'{site_slug}.conf'
    if not conf_path.exists():
        sys.exit(f"Site config not found: {conf_path}")
    conf = {}
    with open(conf_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                conf[key.strip()] = val.strip().strip('"')
    return conf


def load_prompt_template():
    prompt_path = Path(__file__).resolve().parent.parent / 'prompts' / 'cluster-meta-generation.md'
    with open(prompt_path) as f:
        return f.read()


def build_prompt(template, conf, row):
    """Substitute cluster data into the prompt template."""
    variants = json.loads(row.get('top_5_variants', '[]'))
    gaps = json.loads(row.get('gap_queries', '[]'))
    modifiers = json.loads(row.get('common_modifiers', '[]'))

    variants_text = '\n'.join(
        f'  - "{v["query"]}" ({v["impressions"]} impressions, position {v["position"]})'
        for v in variants
    ) or '  (none)'

    gaps_text = '\n'.join(
        f'  - "{g["query"]}" ({g["impressions"]} impressions, position {g["position"]})'
        for g in gaps
    ) or '  (none with sufficient impressions)'

    prompt = template
    prompt = prompt.replace('{{SITE_NAME}}', conf.get('SITE_NAME', ''))
    prompt = prompt.replace('{{BRAND_TONE}}', conf.get('BRAND_TONE', conf.get('SPECIALTY', '')))
    prompt = prompt.replace('{{LOCATION_PRIMARY}}', conf.get('LOCATION_PRIMARY', conf.get('GEO_FOCUS', '')))
    prompt = prompt.replace('{{URL}}', row.get('url', ''))
    prompt = prompt.replace('{{CURRENT_TITLE}}', row.get('current_title', ''))
    prompt = prompt.replace('{{CURRENT_META}}', row.get('current_meta', '(none)'))
    prompt = prompt.replace('{{INTENT}}', row.get('dominant_intent', ''))
    prompt = prompt.replace('{{PARENT_QUERY}}', row.get('parent_query', ''))
    prompt = prompt.replace('{{PARENT_IMPRESSIONS}}', str(row.get('parent_impressions', '')))
    prompt = prompt.replace('{{PARENT_POSITION}}', str(row.get('parent_position', '')))
    prompt = prompt.replace('{{TOP_VARIANTS}}', variants_text)
    prompt = prompt.replace('{{GAP_QUERIES}}', gaps_text)
    prompt = prompt.replace('{{COMMON_MODIFIERS}}', ', '.join(modifiers) if modifiers else '(none)')

    return prompt


def call_openai(prompt, model='gpt-4o-mini', api_key=None):
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=model,
        messages=[{'role': 'user', 'content': prompt}],
        temperature=0.7,
        max_tokens=500,
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content, resp.usage


def call_anthropic(prompt, model='claude-haiku-4-5-20251001', api_key=None):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=model,
        max_tokens=500,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return resp.content[0].text, None


def parse_llm_response(text):
    """Parse JSON from LLM response, handling markdown fences."""
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1] if '\n' in text else text[3:]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()
    return json.loads(text)


def validate_proposal(data):
    """Returns (is_valid, issues list)."""
    issues = []
    title = data.get('title', '')
    meta = data.get('meta', '')
    if len(title) < 30:
        issues.append(f'title too short ({len(title)} chars)')
    if len(title) > 65:
        issues.append(f'title too long ({len(title)} chars)')
    if len(meta) < 100:
        issues.append(f'meta too short ({len(meta)} chars)')
    if len(meta) > 165:
        issues.append(f'meta too long ({len(meta)} chars)')
    return len(issues) == 0, issues


def main():
    parser = argparse.ArgumentParser(description='Generate meta proposals via LLM')
    parser.add_argument('--analysis-csv', required=True, help='Cluster analysis CSV')
    parser.add_argument('--site', required=True, help='Site slug')
    parser.add_argument('--output-csv', required=True, help='Output proposals CSV')
    parser.add_argument('--batch-size', type=int, default=50, help='Progress report interval')
    parser.add_argument('--provider', default='openai', choices=['openai', 'claude'],
                        help='LLM provider')
    parser.add_argument('--model', default=None, help='Model override')
    parser.add_argument('--dry-run', action='store_true', help='Validate inputs only')
    parser.add_argument('--resume', action='store_true', help='Skip URLs already in output')
    parser.add_argument('--limit', type=int, default=0, help='Max pages to process (0=all)')
    args = parser.parse_args()

    conf = load_site_conf(args.site)
    template = load_prompt_template()

    # Determine model
    if args.model:
        model = args.model
    elif args.provider == 'openai':
        model = conf.get('AI_MODEL', 'gpt-4o-mini')
    else:
        model = 'claude-haiku-4-5-20251001'

    # API key
    if args.provider == 'openai':
        api_key = os.environ.get(conf.get('AI_API_KEY_ENV_VAR', 'OPENAI_API_KEY'))
    else:
        api_key = os.environ.get('ANTHROPIC_API_KEY')

    # Load analysis
    with open(args.analysis_csv) as f:
        pages = list(csv.DictReader(f))

    # Resume support
    done_urls = set()
    if args.resume and os.path.exists(args.output_csv):
        with open(args.output_csv) as f:
            for row in csv.DictReader(f):
                done_urls.add(row.get('url', ''))
        print(f"Resuming: {len(done_urls)} already done")

    pages = [p for p in pages if p['url'] not in done_urls]
    if args.limit:
        pages = pages[:args.limit]

    print(f"Site: {args.site} | Model: {model} | Pages: {len(pages)}")

    if args.dry_run:
        print("Dry run — showing first prompt:")
        if pages:
            print(build_prompt(template, conf, pages[0])[:500])
        return

    fieldnames = ['post_id', 'url', 'current_title', 'proposed_title', 'title_length',
                  'current_meta', 'proposed_meta', 'meta_length',
                  'parent_query', 'dominant_intent', 'cluster_impressions',
                  'cluster_clicks', 'cluster_size', 'weighted_position',
                  'captures_variants', 'captures_gaps', 'rationale', 'status']

    write_header = not (args.resume and os.path.exists(args.output_csv))
    outfile = open(args.output_csv, 'a' if args.resume else 'w', newline='')
    writer = csv.DictWriter(outfile, fieldnames=fieldnames)
    if write_header:
        writer.writeheader()

    success = 0
    failures = 0
    total_tokens = 0

    for i, page in enumerate(pages):
        prompt = build_prompt(template, conf, page)

        result_row = {
            'post_id': page.get('post_id', ''),
            'url': page['url'],
            'current_title': page.get('current_title', ''),
            'current_meta': '',
            'parent_query': page.get('parent_query', ''),
            'dominant_intent': page.get('dominant_intent', ''),
            'cluster_impressions': page.get('total_cluster_impressions', ''),
            'cluster_clicks': page.get('total_cluster_clicks', ''),
            'cluster_size': page.get('cluster_size', ''),
            'weighted_position': page.get('weighted_position', ''),
        }

        for attempt in range(2):
            try:
                if args.provider == 'openai':
                    raw, usage = call_openai(prompt, model, api_key)
                    if usage:
                        total_tokens += usage.total_tokens
                else:
                    raw, _ = call_anthropic(prompt, model, api_key)

                data = parse_llm_response(raw)
                valid, issues = validate_proposal(data)

                if not valid and attempt == 0:
                    prompt += f"\n\nPREVIOUS ATTEMPT FAILED VALIDATION: {', '.join(issues)}. Fix these issues."
                    time.sleep(0.5)
                    continue

                result_row['proposed_title'] = data.get('title', '')
                result_row['title_length'] = len(data.get('title', ''))
                result_row['proposed_meta'] = data.get('meta', '')
                result_row['meta_length'] = len(data.get('meta', ''))
                result_row['captures_variants'] = json.dumps(data.get('captures_variants', []))
                result_row['captures_gaps'] = json.dumps(data.get('captures_gaps', []))
                result_row['rationale'] = data.get('rationale', '')
                result_row['status'] = 'ok' if valid else f'warn: {", ".join(issues)}'
                success += 1
                break

            except Exception as e:
                if attempt == 1:
                    result_row['proposed_title'] = ''
                    result_row['proposed_meta'] = ''
                    result_row['title_length'] = 0
                    result_row['meta_length'] = 0
                    result_row['rationale'] = f'ERROR: {str(e)[:200]}'
                    result_row['status'] = 'error'
                    result_row['captures_variants'] = '[]'
                    result_row['captures_gaps'] = '[]'
                    failures += 1
                time.sleep(1)

        writer.writerow(result_row)
        outfile.flush()

        if (i + 1) % args.batch_size == 0:
            print(f"  {i+1}/{len(pages)} | {success} ok, {failures} fail | ~{total_tokens} tokens")

        time.sleep(0.3)

    outfile.close()

    est_cost = total_tokens * 0.00000015 if args.provider == 'openai' else 0
    print(f"\nDone. {success} ok, {failures} failed.")
    print(f"Total tokens: ~{total_tokens} | Est. cost: ${est_cost:.4f}")
    print(f"Saved to {args.output_csv}")


if __name__ == '__main__':
    main()
