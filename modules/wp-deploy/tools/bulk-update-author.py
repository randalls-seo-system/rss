#!/usr/bin/env python3
"""Bulk author update with backup, filtering, and verification.

Productized from tonight's LRG author fix (1,158 posts updated).

Usage:
    # Dry run (shows what would change)
    python3 bulk-update-author.py --site lrg --target-author 1 --dry-run

    # Real run (all published posts by user 2 → user 1)
    python3 bulk-update-author.py --site lrg --target-author 1 \
        --filter-by-current-author 2
"""

import argparse
import os
import sys
import time
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT / 'lib'))

from ssh_session import SSHSession


def main():
    parser = argparse.ArgumentParser(description='Bulk author update with safety')
    parser.add_argument('--site', required=True)
    parser.add_argument('--target-author', required=True,
                        help='Target user ID, email, or login')
    parser.add_argument('--filter-post-type', default='post')
    parser.add_argument('--filter-post-status', default='publish,draft,future,pending')
    parser.add_argument('--filter-by-current-author', default='',
                        help='Only update posts currently authored by this user')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    ssh = SSHSession(args.site, sleep_between=2)

    # Resolve target author to user ID
    result = ssh.run(f'wp user get {args.target_author} --field=ID', check=False)
    if result.returncode != 0:
        print(f"ERROR: Could not resolve target author '{args.target_author}'")
        sys.exit(1)
    target_id = result.stdout.strip()
    print(f"Target author: user ID {target_id}")

    # Build post list query
    statuses = args.filter_post_status.split(',')
    post_ids_to_update = []

    for status in statuses:
        cmd = (f'wp post list --post_type={args.filter_post_type} '
               f'--post_status={status.strip()} '
               f'--field=ID --format=csv')
        if args.filter_by_current_author:
            cmd += f' --author={args.filter_by_current_author}'

        result = ssh.run(cmd, check=False, timeout=60)
        if result.returncode == 0:
            ids = [line.strip() for line in result.stdout.strip().split('\n')
                   if line.strip() and line.strip() != 'ID']
            post_ids_to_update.extend(ids)

    # Filter out posts already authored by target
    needs_update = []
    already_correct = 0

    for pid in post_ids_to_update:
        result = ssh.run(f'wp post get {pid} --field=post_author', check=False)
        if result.returncode == 0:
            current_author = result.stdout.strip()
            if current_author != target_id:
                needs_update.append(pid)
            else:
                already_correct += 1

    print(f"Posts scanned: {len(post_ids_to_update)}")
    print(f"Already correct: {already_correct}")
    print(f"Need update: {len(needs_update)}")

    if not needs_update:
        print(f"\n0 posts would be updated (all already authored by user {target_id})")
        return

    if args.dry_run:
        print(f"\n[DRY RUN] Would update {len(needs_update)} posts to author {target_id}")
        if len(needs_update) <= 20:
            print(f"Post IDs: {', '.join(needs_update)}")
        return

    # Execute bulk update via single SQL (much faster than per-post)
    id_list = ','.join(needs_update)
    sql = f"UPDATE wp_posts SET post_author = {target_id} WHERE ID IN ({id_list});"
    timestamp = time.strftime('%Y%m%d-%H%M%S')

    # Backup
    backup_dir = os.path.expanduser(f'~/{args.site}-rewrite/backups/')
    os.makedirs(backup_dir, exist_ok=True)
    backup_sql = os.path.join(backup_dir, f'pre-author-update-{timestamp}.sql')
    backup_query = f"SELECT ID, post_author FROM wp_posts WHERE ID IN ({id_list});"
    result = ssh.run(f"wp db query \"{backup_query}\"", timeout=60)
    with open(backup_sql, 'w') as f:
        f.write(f"-- Pre-author-update backup {timestamp}\n")
        f.write(f"-- Target author: {target_id}\n")
        f.write(result.stdout)
    print(f"Backup: {backup_sql}")

    # Execute update
    result = ssh.run(f"wp db query \"{sql}\"", timeout=60)
    print(f"SQL executed. Verifying...")

    # Verify spot check (5 random posts)
    import random
    sample = random.sample(needs_update, min(5, len(needs_update)))
    verified = 0
    for pid in sample:
        check = ssh.run(f'wp post get {pid} --field=post_author', check=False)
        if check.stdout.strip() == target_id:
            verified += 1

    print(f"Verified: {verified}/{len(sample)} spot-checked posts correct")
    print(f"Done. {len(needs_update)} posts updated to author {target_id}.")
    ssh.log(f"AUTHOR BULK: {len(needs_update)} posts → author {target_id}")


if __name__ == '__main__':
    main()
