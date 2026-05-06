#!/usr/bin/env python3
"""Analyze keyword clusters: identify parent query, variants, gaps, modifiers, intent."""

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path


def classify_intent(queries):
    all_text = ' '.join(q['query'].lower() for q in queries)
    scores = {
        'informational': sum(1 for s in
            ['how', 'what', 'why', 'when', 'guide', 'tips', 'explained', 'understanding']
            if s in all_text),
        'transactional': sum(1 for s in
            ['buy', 'for sale', 'homes for sale', 'cost', 'price', 'rates', 'calculator']
            if s in all_text),
        'decision': sum(1 for s in
            ['best', 'top', 'vs', 'compare', 'pros and cons', 'worth', 'should']
            if s in all_text),
    }
    dominant = max(scores, key=scores.get)
    if scores[dominant] == 0:
        dominant = 'informational'

    local_signals = ['near me', 'san antonio', 'austin', 'killeen', 'texas', 'tx',
                     'new braunfels', 'corpus christi']
    if any(s in all_text for s in local_signals):
        dominant = f"local-{dominant}"
    return dominant


def extract_modifiers(queries):
    mods = Counter()
    for q in queries:
        query = q['query'].lower()
        imp = q['impressions']
        if re.search(r'\b202[4-6]\b', query): mods['year'] += imp
        if 'near me' in query: mods['near me'] += imp
        if 'best' in query: mods['best'] += imp
        if 'how to' in query or 'how do' in query: mods['how to'] += imp
        if 'cost' in query or 'price' in query: mods['cost/price'] += imp
        if 'for sale' in query: mods['for sale'] += imp
        if 'va ' in query or 'va loan' in query or 'veteran' in query: mods['va/military'] += imp
        if 'first time' in query or 'first-time' in query: mods['first-time'] += imp
    return [m for m, _ in mods.most_common(5)]


def main():
    parser = argparse.ArgumentParser(description='Analyze keyword clusters')
    parser.add_argument('--clusters-json', required=True, help='Keyword clusters JSON from pull step')
    parser.add_argument('--output-csv', required=True, help='Output cluster analysis CSV')
    parser.add_argument('--candidates-csv', help='Optional candidates CSV for post_id/title mapping')
    parser.add_argument('--min-impressions', type=int, default=50, help='Min impressions for gap queries')
    parser.add_argument('--gap-position-range', default='11-30', help='Position range for gaps (default: 11-30)')
    args = parser.parse_args()

    gap_min, gap_max = map(int, args.gap_position_range.split('-'))

    with open(args.clusters_json) as f:
        clusters = json.load(f)

    # Optional candidate metadata
    cand_map = {}
    if args.candidates_csv:
        with open(args.candidates_csv) as f:
            for row in csv.DictReader(f):
                cand_map[row['url']] = row

    results = []
    for url, queries in clusters.items():
        if not queries:
            continue

        meta = cand_map.get(url, {})
        sorted_q = sorted(queries, key=lambda x: -(x['impressions'] + x['clicks'] * 50))
        parent = sorted_q[0]
        variants = sorted_q[1:6]

        gaps = sorted(
            [q for q in queries if gap_min <= q['position'] <= gap_max
             and q['impressions'] >= args.min_impressions],
            key=lambda x: -x['impressions']
        )[:5]

        modifiers = extract_modifiers(queries)
        intent = classify_intent(queries)
        total_imp = sum(q['impressions'] for q in queries)
        total_clicks = sum(q['clicks'] for q in queries)
        weighted_pos = (sum(q['position'] * q['impressions'] for q in queries) / total_imp
                        if total_imp else 0)

        results.append({
            'post_id': meta.get('post_id', ''),
            'url': url,
            'current_title': meta.get('current_title', ''),
            'parent_query': parent['query'],
            'parent_clicks': parent['clicks'],
            'parent_impressions': parent['impressions'],
            'parent_position': parent['position'],
            'top_5_variants': json.dumps([
                {'query': v['query'], 'impressions': v['impressions'], 'position': v['position']}
                for v in variants
            ]),
            'gap_queries': json.dumps([
                {'query': g['query'], 'impressions': g['impressions'], 'position': g['position']}
                for g in gaps
            ]),
            'common_modifiers': json.dumps(modifiers),
            'dominant_intent': intent,
            'total_cluster_impressions': total_imp,
            'total_cluster_clicks': total_clicks,
            'cluster_size': len(queries),
            'weighted_position': round(weighted_pos, 1),
        })

    results.sort(key=lambda x: -x['total_cluster_impressions'])

    with open(args.output_csv, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=results[0].keys())
        w.writeheader()
        w.writerows(results)

    print(f"Analyzed {len(results)} pages. Saved to {args.output_csv}")


if __name__ == '__main__':
    main()
