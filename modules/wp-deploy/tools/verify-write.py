#!/usr/bin/env python3
"""Standalone post-write verification tool.

Usage:
    python3 verify-write.py --site lrg --post-id 2662 \
        --expected-status draft --verify-greps 'rl-page,rl-quick-grid'
"""

import argparse
import json
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT / 'lib'))

from ssh_session import SSHSession


def main():
    parser = argparse.ArgumentParser(description='Verify WordPress post state')
    parser.add_argument('--site', required=True)
    parser.add_argument('--post-id', type=int, required=True)
    parser.add_argument('--expected-status', default='')
    parser.add_argument('--verify-greps', default='',
                        help='Comma-separated strings that must be present')
    parser.add_argument('--forbid-greps', default='',
                        help='Comma-separated strings that must be absent')
    parser.add_argument('--min-content-length', type=int, default=0)
    parser.add_argument('--max-content-length', type=int, default=0)
    parser.add_argument('--output-format', default='text', choices=['text', 'json'])
    args = parser.parse_args()

    ssh = SSHSession(args.site, sleep_between=1)
    results = {'post_id': args.post_id, 'checks': [], 'passed': True}

    # Get post status
    status = ssh.wp_get_field(args.post_id, 'post_status')
    results['post_status'] = status
    if args.expected_status and status != args.expected_status:
        results['checks'].append({
            'check': 'status', 'passed': False,
            'expected': args.expected_status, 'actual': status})
        results['passed'] = False
    elif args.expected_status:
        results['checks'].append({'check': 'status', 'passed': True})

    # Get content
    content = ssh.wp_get_field(args.post_id, 'post_content')
    content_len = len(content)
    results['content_length'] = content_len

    # Length checks
    if args.min_content_length and content_len < args.min_content_length:
        results['checks'].append({
            'check': 'min_length', 'passed': False,
            'expected': f'>={args.min_content_length}', 'actual': content_len})
        results['passed'] = False

    if args.max_content_length and content_len > args.max_content_length:
        results['checks'].append({
            'check': 'max_length', 'passed': False,
            'expected': f'<={args.max_content_length}', 'actual': content_len})
        results['passed'] = False

    # Grep checks
    verify_greps = [g.strip() for g in args.verify_greps.split(',') if g.strip()]
    for grep in verify_greps:
        present = grep in content
        results['checks'].append({
            'check': f'verify:{grep}', 'passed': present})
        if not present:
            results['passed'] = False

    forbid_greps = [g.strip() for g in args.forbid_greps.split(',') if g.strip()]
    for grep in forbid_greps:
        absent = grep not in content
        results['checks'].append({
            'check': f'forbid:{grep}', 'passed': absent})
        if not absent:
            results['passed'] = False

    # Output
    if args.output_format == 'json':
        print(json.dumps(results, indent=2))
    else:
        status_icon = 'PASS' if results['passed'] else 'FAIL'
        print(f"{status_icon} — Post {args.post_id} (status={status}, "
              f"length={content_len})")
        for check in results['checks']:
            icon = '+' if check['passed'] else 'X'
            print(f"  [{icon}] {check['check']}")
            if not check['passed'] and 'expected' in check:
                print(f"      expected: {check['expected']}, actual: {check['actual']}")

    sys.exit(0 if results['passed'] else 1)


if __name__ == '__main__':
    main()
