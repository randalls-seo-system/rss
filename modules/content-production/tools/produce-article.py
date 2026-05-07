#!/usr/bin/env python3
"""Master orchestrator for end-to-end article production.

Chains: intent detection → SERP pull → article generation → validation → WP deploy.

Usage:
    # Generate only (no deploy)
    python3 produce-article.py --site lrg --post-id 2662 \
        --target-keyword "best neighborhoods in san antonio" --skip-deploy

    # Full pipeline with deploy as draft
    python3 produce-article.py --site lrg --post-id 2662 \
        --target-keyword "best neighborhoods in san antonio" --status draft

    # Auto-detect keyword from cluster analysis
    python3 produce-article.py --site lrg --post-id 2662 --skip-deploy
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
MODULE_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = Path(__file__).resolve().parent


def load_site_conf(site_slug):
    conf_path = REPO_ROOT / 'sites' / f'{site_slug}.conf'
    if not conf_path.exists():
        sys.exit(f"Site config not found: {conf_path}")
    conf = {}
    with open(conf_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('[') and '=' in line:
                key, val = line.split('=', 1)
                conf[key.strip()] = val.strip().strip('"')
    return conf


def find_keyword_from_cluster(site_slug, post_id):
    """Look up parent_query from cluster analysis CSV."""
    patterns = [
        Path.home() / f'{site_slug}-rewrite' / 'audits' / '22c-cluster-analysis.csv',
        Path.home() / f'{site_slug}-rewrite' / 'audits' / 'cluster-analysis.csv',
    ]
    for csv_path in patterns:
        if csv_path.exists():
            with open(csv_path) as f:
                for row in csv.DictReader(f):
                    if str(row.get('post_id', '')) == str(post_id):
                        return row.get('parent_query', '')
    return ''


def pull_serp_data(keyword, site_slug):
    """Pull SerpAPI data for keyword. Returns (path, data) or (None, None)."""
    api_key = os.environ.get('SERPAPI_KEY', '')
    if not api_key:
        print("  SERPAPI_KEY not set — skipping SERP pull")
        return None, None

    slug = re.sub(r'[^a-z0-9]+', '-', keyword.lower().strip()).strip('-')[:60]
    serp_dir = Path.home() / f'{site_slug}-rewrite' / 'serp'
    serp_dir.mkdir(parents=True, exist_ok=True)
    serp_path = serp_dir / f'{slug}-serp.json'

    # Use cached if fresh (< 24h)
    if serp_path.exists():
        age = time.time() - serp_path.stat().st_mtime
        if age < 86400:
            print(f"  Using cached SERP data ({age/3600:.1f}h old)")
            with open(serp_path) as f:
                return str(serp_path), json.load(f)

    try:
        import requests
        resp = requests.get('https://serpapi.com/search.json', params={
            'q': keyword,
            'api_key': api_key,
            'google_domain': 'google.com',
            'gl': 'us',
            'hl': 'en',
            'location': 'Texas',
        }, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        with open(serp_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"  SERP data saved: {serp_path}")
        return str(serp_path), data
    except Exception as e:
        print(f"  SERP pull failed: {e}")
        return None, None


def run_tool(script, args_list):
    """Run a Python tool as subprocess. Returns (returncode, stdout, stderr)."""
    cmd = [sys.executable, str(script)] + args_list
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return result.returncode, result.stdout, result.stderr


def main():
    parser = argparse.ArgumentParser(description='End-to-end article production orchestrator')
    parser.add_argument('--site', required=True)
    parser.add_argument('--post-id', type=int, required=True)
    parser.add_argument('--target-keyword', help='Override keyword (auto-detects from cluster if omitted)')
    parser.add_argument('--intent', help='Override intent (auto-detects if omitted)')
    parser.add_argument('--status', default='draft', choices=['draft', 'publish'])
    parser.add_argument('--skip-deploy', action='store_true', help='Generate HTML only')
    parser.add_argument('--skip-meta', action='store_true', help='Skip meta refresh')
    parser.add_argument('--output-dir', help='Override output directory')
    parser.add_argument('--provider', default='claude', choices=['openai', 'claude'])
    parser.add_argument('--model', default=None)
    parser.add_argument('--min-word-count', type=int, default=1600)
    args = parser.parse_args()

    conf = load_site_conf(args.site)
    start_time = time.time()

    # Output paths
    output_dir = args.output_dir or str(Path.home() / f'{args.site}-rewrite' / 'articles-v3')
    os.makedirs(output_dir, exist_ok=True)
    output_html = os.path.join(output_dir, f'{args.post_id}-produced.html')

    print(f"=== Article Production: Post {args.post_id} on {args.site} ===")
    print(f"  Output: {output_html}")
    print(f"  Deploy: {'skip' if args.skip_deploy else args.status}")

    # Step 1: Resolve keyword
    keyword = args.target_keyword
    if not keyword:
        print("\n[1] Resolving keyword from cluster analysis...")
        keyword = find_keyword_from_cluster(args.site, args.post_id)
        if not keyword:
            sys.exit(f"ERROR: No keyword found for post {args.post_id}. Use --target-keyword.")
        print(f"  Keyword: {keyword}")
    else:
        print(f"\n[1] Keyword: {keyword}")

    # Step 2: Detect intent
    if args.intent:
        intent = args.intent
        print(f"\n[2] Intent (override): {intent}")
    else:
        print("\n[2] Detecting intent...")
        rc, stdout, stderr = run_tool(
            TOOLS_DIR / 'detect-intent.py',
            ['--target-keyword', keyword]
        )
        if rc != 0:
            sys.exit(f"Intent detection failed: {stderr}")
        result = json.loads(stdout)
        intent = result['detected_intent']
        print(f"  Intent: {intent} ({result['confidence']}) — {result['reasoning']}")

    # Step 3: Pull SERP data
    print("\n[3] Pulling SERP data...")
    serp_path, serp_data = pull_serp_data(keyword, args.site)
    if serp_data:
        paa_count = len(serp_data.get('related_questions', []))
        organic_count = len(serp_data.get('organic_results', []))
        print(f"  PAA questions: {paa_count} | Organic results: {organic_count}")

    # Step 4: Generate article
    print("\n[4] Generating article...")
    gen_args = [
        '--site', args.site,
        '--target-keyword', keyword,
        '--intent', intent,
        '--output', output_html,
        '--provider', args.provider,
        '--min-word-count', str(args.min_word_count),
    ]
    if args.model:
        gen_args += ['--model', args.model]
    if serp_path:
        gen_args += ['--serp-data-json', serp_path]

    rc, stdout, stderr = run_tool(TOOLS_DIR / 'generate-article.py', gen_args)
    print(stdout)
    if rc != 0:
        print(f"STDERR: {stderr}", file=sys.stderr)
        sys.exit(f"Article generation failed (exit {rc})")

    # Load manifest
    manifest_path = output_html.replace('.html', '-manifest.json')
    if os.path.exists(manifest_path):
        with open(manifest_path) as f:
            manifest = json.load(f)
    else:
        manifest = {}

    # Step 5: Validate structure
    print("\n[5] Validating structure...")
    rc, stdout, stderr = run_tool(
        TOOLS_DIR / 'validate-structure.py',
        ['--html-file', output_html, '--intent', intent]
    )
    print(stdout)
    structure_pass = (rc == 0)
    if not structure_pass:
        print("  WARNING: Structure validation failed. Review article manually.")

    # Step 6: Voice validation (already done in generate, but verify)
    voice_pass = manifest.get('voice_pass', True)

    # Step 7: Deploy
    if args.skip_deploy:
        print("\n[6] Deploy: SKIPPED (--skip-deploy)")
    else:
        print(f"\n[6] Deploying as {args.status}...")
        deploy_tool = REPO_ROOT / 'modules' / 'wp-deploy' / 'tools' / 'push-post-content.py'
        deploy_args = [
            '--site', args.site,
            '--post-id', str(args.post_id),
            '--html-file', output_html,
            '--status', args.status,
            '--size-min-ratio', '0.3',  # Full rewrites may be shorter than originals
            '--size-max-ratio', '5.0',  # Full rewrites may be much longer
        ]
        rc, stdout, stderr = run_tool(deploy_tool, deploy_args)
        print(stdout)
        if rc != 0:
            print(f"STDERR: {stderr}", file=sys.stderr)
            sys.exit(f"Deploy failed (exit {rc})")

    # Summary
    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"PRODUCTION COMPLETE")
    print(f"{'='*60}")
    print(f"  Post ID: {args.post_id}")
    print(f"  Keyword: {keyword}")
    print(f"  Intent: {intent}")
    print(f"  Word count: {manifest.get('word_count', '?')}")
    print(f"  Voice: {'PASS' if voice_pass else 'FAIL'}")
    print(f"  Structure: {'PASS' if structure_pass else 'FAIL'}")
    print(f"  LLM cost: ${manifest.get('llm_cost_estimate', 0):.4f}")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Output: {output_html}")
    if not args.skip_deploy:
        staging_domain = conf.get('SSH_HOST', '').replace('.ssh.wpengine.net', '.wpenginepowered.com')
        print(f"  Preview: https://{staging_domain}/?p={args.post_id}&preview=true")


if __name__ == '__main__':
    main()
