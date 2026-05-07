#!/usr/bin/env python3
"""Surgical post_status updates with backup and safety flags.

Usage:
    python3 push-post-status.py --site lrg --post-ids 1234,5678 --target-status publish
    python3 push-post-status.py --site lrg --batch-csv posts.csv --target-status draft
    python3 push-post-status.py --site lrg --post-ids 999 --target-status trash --confirm-trash
"""

import argparse
import csv
import os
import sys
import time
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT / 'lib'))

from ssh_session import SSHSession
from php_template import generate_status_update_script


def main():
    parser = argparse.ArgumentParser(description='Surgical post_status updates')
    parser.add_argument('--site', required=True)
    parser.add_argument('--post-ids', help='Comma-separated post IDs')
    parser.add_argument('--batch-csv', help='CSV with post_id column')
    parser.add_argument('--target-status', required=True,
                        choices=['publish', 'draft', 'trash', 'future', 'pending', 'private'])
    parser.add_argument('--backup-csv', help='Backup CSV path')
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--confirm-trash', action='store_true',
                        help='Required for trash operations')
    args = parser.parse_args()

    if not args.post_ids and not args.batch_csv:
        parser.error("Must provide --post-ids or --batch-csv")

    if args.target_status == 'trash' and not args.confirm_trash:
        parser.error("--confirm-trash required for trash operations")

    ssh = SSHSession(args.site, sleep_between=2)

    post_ids = []
    if args.post_ids:
        post_ids = [int(x.strip()) for x in args.post_ids.split(',')]
    else:
        with open(args.batch_csv) as f:
            post_ids = [int(row['post_id']) for row in csv.DictReader(f)]

    timestamp = time.strftime('%Y%m%d-%H%M%S')
    backup_path = args.backup_csv or os.path.expanduser(
        f'~/{args.site}-rewrite/backups/status-backup-{timestamp}.csv')
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)

    print(f"Site: {args.site} | Posts: {len(post_ids)} | Target: {args.target_status} | "
          f"Dry run: {args.dry_run}")

    backup_rows = []
    success = 0

    for i, post_id in enumerate(post_ids):
        print(f"[{i+1}/{len(post_ids)}] Post {post_id}", end=' ')

        if args.dry_run:
            current = ssh.wp_get_field(post_id, 'post_status')
            print(f"[DRY RUN] {current} → {args.target_status}")
            continue

        php = generate_status_update_script(post_id, args.target_status)
        output = ssh.upload_and_eval(php)
        parsed = ssh.parse_pipe_output(output)

        backup_rows.append({
            'post_id': post_id,
            'old_status': parsed.get('OLD_STATUS', ''),
            'new_status': parsed.get('NEW_STATUS', ''),
        })

        if parsed.get('OK') == '1':
            success += 1
            print(f"{parsed.get('OLD_STATUS', '?')} → {parsed.get('NEW_STATUS', '?')}")
        else:
            print(f"FAIL: {parsed.get('ERROR', output[:100])}")

    if backup_rows:
        with open(backup_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['post_id', 'old_status', 'new_status'])
            writer.writeheader()
            writer.writerows(backup_rows)

    print(f"\nDone. {success}/{len(post_ids)} updated. Backup: {backup_path}")


if __name__ == '__main__':
    main()
