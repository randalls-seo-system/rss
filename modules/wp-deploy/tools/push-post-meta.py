#!/usr/bin/env python3
"""Safe WordPress post meta push with backup and verification.

Usage:
    # Single meta update
    python3 push-post-meta.py --site lrg --post-id 2662 \
        --meta-key _yoast_wpseo_title --meta-value "New Title | LRG"

    # Batch from CSV (columns: post_id, meta_key, meta_value)
    python3 push-post-meta.py --site lrg --batch-csv meta-updates.csv
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
from php_template import generate_meta_update_script


def main():
    parser = argparse.ArgumentParser(description='Safe WordPress post meta push')
    parser.add_argument('--site', required=True)
    parser.add_argument('--post-id', type=int, help='Single post ID')
    parser.add_argument('--batch-csv', help='CSV: post_id, meta_key, meta_value')
    parser.add_argument('--meta-key', help='Meta key (with --post-id)')
    parser.add_argument('--meta-value', help='Meta value (with --post-id)')
    parser.add_argument('--backup-csv',
                        help='Backup CSV path (auto-generated if not set)')
    parser.add_argument('--sleep-between', type=int, default=3)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    if not args.post_id and not args.batch_csv:
        parser.error("Must provide --post-id or --batch-csv")
    if args.post_id and not (args.meta_key and args.meta_value):
        parser.error("--meta-key and --meta-value required with --post-id")

    ssh = SSHSession(args.site, sleep_between=args.sleep_between)

    tasks = []
    if args.post_id:
        tasks.append({
            'post_id': str(args.post_id),
            'meta_key': args.meta_key,
            'meta_value': args.meta_value,
        })
    else:
        with open(args.batch_csv) as f:
            tasks = list(csv.DictReader(f))

    # Backup setup
    timestamp = time.strftime('%Y%m%d-%H%M%S')
    backup_path = args.backup_csv or os.path.expanduser(
        f'~/{args.site}-rewrite/backups/meta-backup-{timestamp}.csv')
    os.makedirs(os.path.dirname(backup_path), exist_ok=True)

    print(f"Site: {args.site} | Updates: {len(tasks)} | Dry run: {args.dry_run}")

    backup_rows = []
    success = 0
    failed = 0

    for i, task in enumerate(tasks):
        post_id = int(task['post_id'])
        meta_key = task['meta_key']
        meta_value = task['meta_value']

        print(f"[{i+1}/{len(tasks)}] Post {post_id} → {meta_key}", end=' ')

        if args.dry_run:
            print(f"[DRY RUN] would set to: {meta_value[:60]}")
            continue

        # Generate and execute PHP (uses persistent path, not /tmp/)
        php = generate_meta_update_script(post_id, meta_key, meta_value)
        output = ssh.upload_and_eval(php, timeout=30)
        parsed = ssh.parse_pipe_output(output)

        # Record backup
        backup_rows.append({
            'post_id': post_id,
            'meta_key': meta_key,
            'old_value': parsed.get('OLD_VALUE', ''),
            'new_value': parsed.get('NEW_VALUE', ''),
            'status': 'ok' if parsed.get('OK') == '1' else 'fail',
        })

        if parsed.get('OK') == '1':
            success += 1
            print(f"OK")
            ssh.log(f"META OK post={post_id} key={meta_key}")
        else:
            failed += 1
            print(f"FAIL: {parsed.get('ERROR', 'unknown')}")
            ssh.log(f"META FAIL post={post_id} key={meta_key}")

    # Write backup CSV
    if backup_rows:
        with open(backup_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['post_id', 'meta_key', 'old_value', 'new_value', 'status'])
            writer.writeheader()
            writer.writerows(backup_rows)
        print(f"\nBackup: {backup_path}")

    print(f"Done. {success} ok, {failed} failed.")


if __name__ == '__main__':
    main()
