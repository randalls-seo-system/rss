#!/usr/bin/env python3
"""Rule-based keyword intent classifier.

Usage:
    python3 detect-intent.py --target-keyword "how to buy a house in san antonio"
    python3 detect-intent.py --target-keyword "best neighborhoods" --serp-data-json serp.json
"""

import argparse
import json
import re
import sys


INTENT_RULES = [
    # (intent, patterns, confidence)
    ('process', [
        r'^how\s+to\b', r'^how\s+long\b', r'^how\s+do\b',
        r'^when\s+to\b', r'^what\s+to\s+do\b',
        r'^steps?\s+to\b', r'^guide\s+to\b',
        r'\bstep[- ]by[- ]step\b', r'\bchecklist\b', r'\bprocess\b',
    ], 'high'),
    ('comparison', [
        r'\bvs\.?\b', r'\bversus\b', r'\bcompared\s+to\b',
        r'\bor\b.*\bwhich\b', r'\bwhich\s+is\s+better\b',
    ], 'high'),
    ('definition', [
        r'^what\s+(is|are)\b', r'^what\s+does\b', r'^define\b',
        r'\bdefinition\s+of\b', r'\bexplained\b', r'\bmeaning\s+of\b',
        r'^understanding\b',
    ], 'high'),
    ('decision', [
        r'^best\b', r'^top\s+\d+', r'\breview\b', r'\branked\b',
        r'\bworth\s+it\b', r'\bshould\s+i\b', r'^how\s+much\b',
        r'\bis\s+it\s+worth\b', r'\bgood\s+place\s+to\b',
    ], 'high'),
    ('news', [
        r'\b202[4-9]\b', r'\btoday\b', r'\blatest\b', r'\bnew\b',
        r'\bupdate[sd]?\b', r'\brates?\s+(today|now|this)\b',
        r'\bmarket\s+(update|report|trends?)\b',
    ], 'medium'),
]


def detect_intent(keyword, serp_data=None):
    kw_lower = keyword.lower().strip()

    for intent, patterns, confidence in INTENT_RULES:
        for pat in patterns:
            if re.search(pat, kw_lower):
                return {
                    'target_keyword': keyword,
                    'detected_intent': intent,
                    'confidence': confidence,
                    'reasoning': f"Matched pattern /{pat}/ → {intent}",
                }

    # SERP-based fallback: check PAA questions and featured snippet type
    if serp_data:
        paa = serp_data.get('related_questions', [])
        how_to_count = sum(1 for q in paa if q.get('question', '').lower().startswith('how'))
        what_count = sum(1 for q in paa if q.get('question', '').lower().startswith('what'))
        if how_to_count >= 2:
            return {
                'target_keyword': keyword,
                'detected_intent': 'process',
                'confidence': 'medium',
                'reasoning': f"PAA has {how_to_count} 'how' questions",
            }
        if what_count >= 2:
            return {
                'target_keyword': keyword,
                'detected_intent': 'definition',
                'confidence': 'medium',
                'reasoning': f"PAA has {what_count} 'what' questions",
            }

    # Default
    return {
        'target_keyword': keyword,
        'detected_intent': 'decision',
        'confidence': 'low',
        'reasoning': 'No pattern matched — defaulting to decision intent',
    }


def main():
    parser = argparse.ArgumentParser(description='Rule-based keyword intent classifier')
    parser.add_argument('--target-keyword', required=True)
    parser.add_argument('--serp-data-json', help='Optional SerpAPI response JSON')
    parser.add_argument('--output', help='Output path (default: stdout)')
    args = parser.parse_args()

    serp_data = None
    if args.serp_data_json:
        with open(args.serp_data_json) as f:
            serp_data = json.load(f)

    result = detect_intent(args.target_keyword, serp_data)
    output = json.dumps(result, indent=2)

    if args.output:
        with open(args.output, 'w') as f:
            f.write(output + '\n')
        print(f"Intent: {result['detected_intent']} ({result['confidence']})")
        print(f"Saved: {args.output}")
    else:
        print(output)


if __name__ == '__main__':
    main()
