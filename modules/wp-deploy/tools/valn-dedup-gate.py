#!/usr/bin/env python3
"""
VALN Dedup Gate — Pre-publish collision checker.
Blocks post creation if slug or title overlaps with existing prod content.
Standalone script: called by both pipeline (valn-postprocess.py) and
brief-driven article creation paths.

Usage:
  python3 valn-dedup-gate.py --slug my-new-slug --title "My New Title" [--override]
  python3 valn-dedup-gate.py --check-file slugs.csv  # CSV: slug,title per line

Exit codes:
  0 = CLEAN (no collisions)
  1 = COLLISION (blocked, details printed)
  2 = ERROR (could not pull inventory)

Requires: SSH access to prod (valoannetwork@valoannetwork.ssh.wpengine.net)
"""

import argparse
import csv
import io
import re
import subprocess
import sys

SSH_CMD = [
    'ssh', '-i', '/Users/esv211/.ssh/wpengine_valn',
    '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
    'valoannetwork@valoannetwork.ssh.wpengine.net'
]

def pull_prod_inventory():
    """Pull published slug+title inventory from prod."""
    cmd = SSH_CMD + [
        'wp post list --post_type=post,page --post_status=publish,draft,pending '
        '--fields=ID,post_name,post_title --format=csv 2>/dev/null'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        print(f"ERROR: Could not pull prod inventory: {result.stderr}", file=sys.stderr)
        sys.exit(2)
    reader = csv.DictReader(io.StringIO(result.stdout))
    return list(reader)

def normalize_slug(slug):
    """Strip year prefixes, trailing plurals, extra hyphens."""
    s = slug.lower().strip('/')
    # Strip leading year patterns: 2024-, 2025-, 2026-
    s = re.sub(r'^20\d{2}-', '', s)
    # Strip trailing -s for plural
    s = re.sub(r'-s$', '', s)
    # Collapse multiple hyphens
    s = re.sub(r'-+', '-', s)
    return s

def title_keywords(title):
    """Extract significant keywords from title (lowercase, stop words removed)."""
    stops = {'a','an','the','and','or','but','in','on','at','to','for','of',
             'is','it','by','with','from','as','this','that','how','what',
             'when','where','why','can','do','does','your','you','my','our',
             'va','loan','loans','home','2024','2025','2026'}
    words = re.findall(r'[a-z]+', title.lower())
    return set(w for w in words if w not in stops and len(w) > 2)

def check_collision(slug, title, inventory):
    """Check a single slug+title against inventory. Returns list of collisions."""
    collisions = []
    norm_new = normalize_slug(slug)
    kw_new = title_keywords(title)

    for row in inventory:
        prod_slug = row.get('post_name', '')
        prod_title = row.get('post_title', '')
        prod_id = row.get('ID', '?')

        # Exact slug match
        if prod_slug == slug:
            collisions.append({
                'type': 'EXACT_SLUG',
                'prod_id': prod_id,
                'prod_slug': prod_slug,
                'prod_title': prod_title,
            })
            continue

        # Normalized slug match
        if normalize_slug(prod_slug) == norm_new:
            collisions.append({
                'type': 'NORMALIZED_SLUG',
                'prod_id': prod_id,
                'prod_slug': prod_slug,
                'prod_title': prod_title,
            })
            continue

        # Title keyword overlap >= 60%
        kw_prod = title_keywords(prod_title)
        if kw_new and kw_prod:
            overlap = len(kw_new & kw_prod)
            max_len = max(len(kw_new), len(kw_prod))
            if max_len > 0 and (overlap / max_len) >= 0.60:
                collisions.append({
                    'type': 'TITLE_OVERLAP',
                    'prod_id': prod_id,
                    'prod_slug': prod_slug,
                    'prod_title': prod_title,
                    'overlap': f"{overlap}/{max_len} ({100*overlap//max_len}%)",
                })

    return collisions

def main():
    parser = argparse.ArgumentParser(description='VALN Dedup Gate')
    parser.add_argument('--slug', help='Slug to check')
    parser.add_argument('--title', help='Title to check')
    parser.add_argument('--check-file', help='CSV file with slug,title per line')
    parser.add_argument('--override', action='store_true',
                        help='Log collision but exit 0 (explicit override)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be checked without pulling inventory')
    args = parser.parse_args()

    if not args.slug and not args.check_file:
        parser.error('Provide --slug/--title or --check-file')

    # Build check list
    checks = []
    if args.slug:
        checks.append((args.slug, args.title or args.slug))
    if args.check_file:
        with open(args.check_file) as f:
            for line in f:
                parts = line.strip().split(',', 1)
                if len(parts) == 2:
                    checks.append((parts[0], parts[1]))

    print(f"VALN Dedup Gate — checking {len(checks)} slug(s) against prod inventory")
    print("=" * 60)

    inventory = pull_prod_inventory()
    print(f"Prod inventory: {len(inventory)} posts/pages loaded\n")

    any_collision = False
    for slug, title in checks:
        collisions = check_collision(slug, title, inventory)
        if collisions:
            any_collision = True
            print(f"BLOCKED: {slug}")
            print(f"  Title: {title}")
            for c in collisions:
                print(f"  Collision: {c['type']}")
                print(f"    Prod ID: {c['prod_id']}")
                print(f"    Prod slug: {c['prod_slug']}")
                print(f"    Prod title: {c['prod_title']}")
                if 'overlap' in c:
                    print(f"    Overlap: {c['overlap']}")
            print()
        else:
            print(f"CLEAN: {slug}")
            print(f"  Title: {title}\n")

    if any_collision and not args.override:
        print("RESULT: COLLISION DETECTED — blocked. Use --override to proceed.")
        sys.exit(1)
    elif any_collision and args.override:
        print("RESULT: COLLISION DETECTED — override flag set, proceeding with warning.")
        sys.exit(0)
    else:
        print("RESULT: ALL CLEAN — no collisions detected.")
        sys.exit(0)

if __name__ == '__main__':
    main()
