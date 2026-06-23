#!/usr/bin/env python3
"""Safe WordPress post_content push using SCP + wp eval-file pattern.

CRITICAL: Never uses wp db query for content writes. WP Engine staging
silently fails on 60KB+ inline SQL (exit 0, no rows affected). This tool
uses the proven pattern: upload content file, then wp eval-file with PHP
that reads the file and calls wp_update_post().

Usage:
    # Single post
    python3 push-post-content.py --site lrg --post-id 2662 \
        --html-file /tmp/post-2662.html --status draft

    # Batch from CSV
    python3 push-post-content.py --site lrg \
        --batch-csv batch.csv --status draft

    # Dry run
    python3 push-post-content.py --site lrg --post-id 2662 \
        --html-file /tmp/post-2662.html --dry-run
"""

import argparse
import csv
import glob
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = MODULE_ROOT.parent.parent
sys.path.insert(0, str(MODULE_ROOT / 'lib'))
sys.path.insert(0, str(REPO_ROOT / 'modules' / '_shared'))

from ssh_session import SSHSession
from php_template import generate_post_update_script
from lib.deploy_lock import acquire_deploy_lock


REQUIRED_PHASES = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']


def validate_manifest(html_file, max_age_hours=168):
    """Find and validate a pipeline manifest alongside the HTML file.

    Returns (ok: bool, message: str, manifest: dict|None).
    """
    html_dir = os.path.dirname(os.path.abspath(html_file))
    manifests = glob.glob(os.path.join(html_dir, '*-manifest.json'))

    if not manifests:
        return False, f"No pipeline manifest found in {html_dir}", None

    # Prefer manifest matching the post_id from the HTML filename
    html_basename = os.path.basename(html_file)
    post_id_prefix = html_basename.split('-')[0]
    specific = [m for m in manifests if os.path.basename(m).startswith(f"{post_id_prefix}-manifest")]
    manifest_path = specific[0] if specific else max(manifests, key=os.path.getmtime)
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return False, f"Failed to read manifest {manifest_path}: {e}", None

    # Required fields
    errors = []
    for field in ('target_keyword', 'intent', 'site'):
        val = manifest.get(field)
        if not val or not isinstance(val, str) or not val.strip():
            errors.append(f"'{field}' missing or empty")

    phases = manifest.get('phases_completed', [])
    missing_phases = [p for p in REQUIRED_PHASES if p not in phases]
    if missing_phases:
        errors.append(f"phases_completed missing {missing_phases}")

    llm_calls = manifest.get('llm_calls_total', 0)
    if not isinstance(llm_calls, (int, float)) or llm_calls <= 0:
        errors.append("llm_calls_total must be > 0")

    ts_str = manifest.get('timestamp', '')
    if ts_str:
        try:
            ts = datetime.fromisoformat(ts_str)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            if age_hours > max_age_hours:
                errors.append(f"timestamp is {age_hours:.0f}h old (max {max_age_hours}h)")
        except ValueError:
            errors.append(f"timestamp '{ts_str}' is not valid ISO format")
    else:
        errors.append("'timestamp' missing")

    if errors:
        msg = (f"Manifest validation failed ({os.path.basename(manifest_path)}):\n"
               + '\n'.join(f"  - {e}" for e in errors))
        return False, msg, manifest

    age_str = f"{age_hours:.0f}h" if ts_str else "unknown"
    msg = (f"Manifest verified: target_keyword='{manifest['target_keyword']}', "
           f"intent='{manifest['intent']}', "
           f"phases_completed={manifest['phases_completed']}, "
           f"age={age_str}")
    return True, msg, manifest


def backup_post(ssh, post_id, backup_dir):
    """Pull current post_content and save locally as backup."""
    content = ssh.wp_get_field(post_id, 'post_content')
    if not content:
        return None

    os.makedirs(backup_dir, exist_ok=True)
    timestamp = time.strftime('%Y%m%d-%H%M%S')
    backup_path = os.path.join(backup_dir, f'{post_id}-original-{timestamp}.html')
    with open(backup_path, 'w') as f:
        f.write(content)
    return backup_path


def push_single_post(ssh, post_id, html_file, status, verify_greps,
                     forbid_greps, size_min_ratio, size_max_ratio,
                     backup_dir, dry_run):
    """Push content for a single post. Returns (success, details_dict)."""
    details = {'post_id': post_id, 'status': 'pending'}

    # Read local content
    with open(html_file) as f:
        new_content = f.read()
    new_len = len(new_content)
    details['new_content_len'] = new_len

    if new_len == 0:
        details['status'] = 'error'
        details['error'] = 'Empty content file'
        return False, details

    # Backup current content
    if not dry_run:
        backup_path = backup_post(ssh, post_id, backup_dir)
        if backup_path:
            details['backup_path'] = backup_path
            original_len = os.path.getsize(backup_path)
            details['original_content_len'] = original_len

            # Size ratio check
            if original_len > 0:
                ratio = new_len / original_len
                if ratio < size_min_ratio:
                    details['status'] = 'error'
                    details['error'] = f'Size ratio {ratio:.2f} below minimum {size_min_ratio}'
                    return False, details
                if ratio > size_max_ratio:
                    details['status'] = 'error'
                    details['error'] = f'Size ratio {ratio:.2f} above maximum {size_max_ratio}'
                    return False, details

    if dry_run:
        details['status'] = 'dry_run'
        details['would_push'] = f'{new_len} bytes as {status}'
        return True, details

    # WPE /tmp/ is session-ephemeral AND wp eval-file fails silently on large
    # (>8KB) PHP files. Solution: upload HTML to a PERSISTENT path, then use a
    # small PHP script that reads the file and calls wp_update_post().
    wp_path = ssh.conf.get('WP_PATH', '').rstrip('/')
    remote_html = f'{wp_path}/wp-content/rss-push-{post_id}.html'
    remote_php = f'{wp_path}/wp-content/rss-push-{post_id}.php'

    # Step 1: Upload HTML content to persistent path
    ssh.upload_content(html_file, remote_html)

    # Step 2: Build small PHP that reads the file (stays under 8KB)
    verify_block = ''
    for grep in verify_greps:
        safe = grep.replace("'", "\\'")
        verify_block += f"if(strpos($after->post_content,'{safe}')===false)echo 'VERIFY_FAIL={safe}|';\n"

    forbid_block = ''
    for grep in forbid_greps:
        safe = grep.replace("'", "\\'")
        forbid_block += f"if(strpos($after->post_content,'{safe}')!==false)echo 'FORBID_FAIL={safe}|';\n"

    php_script = f"""<?php
$content = file_get_contents('{remote_html}');
if(!$content){{ echo 'ERROR=Could not read content file|'; exit(1); }}
$now_local = current_time('mysql');
$now_gmt = current_time('mysql', true);
$result = wp_update_post([
    'ID'=>{post_id},
    'post_content'=>$content,
    'post_status'=>'{status}',
    'post_modified'=>$now_local,
    'post_modified_gmt'=>$now_gmt,
],true);
if(is_wp_error($result)){{ echo 'ERROR='.$result->get_error_message().'|'; exit(1); }}
$after = get_post({post_id});
echo 'STATUS='.$after->post_status.'|';
echo 'LEN='.strlen($after->post_content).'|';
echo 'MODIFIED='.$after->post_modified.'|';
echo 'MODIFIED_GMT='.$after->post_modified_gmt.'|';
{verify_block}{forbid_block}echo 'OK=1|';
@unlink('{remote_html}');
"""

    # Step 3: Upload PHP and execute (small file, works reliably)
    ssh.upload_string(php_script, remote_php)
    output = ssh.run(f'wp eval-file {remote_php} && rm -f {remote_php}', timeout=90).stdout.strip()
    parsed = ssh.parse_pipe_output(output)
    details['php_output'] = parsed

    # Check for errors
    if 'ERROR' in parsed:
        details['status'] = 'error'
        details['error'] = parsed['ERROR']
        return False, details

    if any(k.startswith('VERIFY_FAIL') for k in parsed):
        details['status'] = 'verify_fail'
        details['error'] = 'Required content not found after write'
        return False, details

    if any(k.startswith('FORBID_FAIL') for k in parsed):
        details['status'] = 'forbid_fail'
        details['error'] = 'Forbidden content found after write'
        return False, details

    if parsed.get('OK') == '1':
        details['status'] = 'ok'
        details['post_status'] = parsed.get('STATUS', '')
        details['content_length'] = parsed.get('LEN', '')
        ssh.log(f"OK post={post_id} status={status} len={parsed.get('LEN', '?')}")
        return True, details

    details['status'] = 'unknown'
    details['error'] = f'Unexpected output: {output[:200]}'
    return False, details


def _create_post(ssh, args):
    """Create a new post using the safe two-file pattern.

    Uploads article HTML to a separate file on the server, then runs a small
    PHP script that reads that file and calls wp_insert_post(). The PHP script
    and article HTML are NEVER in the same file — this prevents the deploy
    script's own code from leaking into post_content.

    Returns the new post ID, or None on failure.
    """
    import re

    html_file = args.html_file
    if not os.path.exists(html_file):
        print(f"ERROR: HTML file not found: {html_file}", file=sys.stderr)
        return None

    title = args.title
    slug = args.slug or re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    author = args.author or 1
    status = args.status
    excerpt = args.excerpt or ''

    # Auto-extract excerpt from intro if not provided
    if not excerpt:
        try:
            from bs4 import BeautifulSoup
            with open(html_file) as f:
                soup = BeautifulSoup(f.read(), 'html.parser')
            for p in soup.find_all('p'):
                text = p.get_text(strip=True)
                if len(text) > 80 and 'Connect with' not in text:
                    words = text.split()
                    excerpt = ' '.join(words[:30]) + ('...' if len(words) > 30 else '')
                    break
        except Exception:
            pass

    wp_path = ssh.conf.get('WP_PATH', '').rstrip('/')
    remote_html = f'{wp_path}/wp-content/rss-create-new.html'
    remote_php = f'{wp_path}/wp-content/rss-create-new.php'

    # Step 1: Upload HTML to a SEPARATE file
    ssh.upload_content(html_file, remote_html)

    # Step 2: Build small PHP that reads the SEPARATE HTML file
    safe_title = title.replace("'", "\\'")
    safe_slug = slug.replace("'", "\\'")
    safe_excerpt = excerpt.replace("'", "\\'")

    php_script = f"""<?php
$content = file_get_contents('{remote_html}');
if(!$content){{ echo 'ERROR=Could not read content file|'; exit(1); }}
$post_data = array(
    'post_title'   => '{safe_title}',
    'post_name'    => '{safe_slug}',
    'post_content' => $content,
    'post_excerpt' => '{safe_excerpt}',
    'post_status'  => '{status}',
    'post_type'    => 'post',
    'post_author'  => {author},
);
$post_id = wp_insert_post($post_data, true);
if(is_wp_error($post_id)){{ echo 'ERROR='.$post_id->get_error_message().'|'; exit(1); }}
$after = get_post($post_id);
// Auto-detect neighborhood guides and set the meta flag that triggers nh-* CSS
if(strpos($content, 'nh-hero') !== false) {{
    update_post_meta($post_id, '_lrg_neighborhood', '1');
    echo 'NH_META=1|';
}}
echo 'ID='.$post_id.'|';
echo 'STATUS='.$after->post_status.'|';
echo 'LEN='.strlen($after->post_content).'|';
echo 'SLUG='.$after->post_name.'|';
echo 'STARTS_WITH='.substr($after->post_content,0,30).'|';
echo 'OK=1|';
@unlink('{remote_html}');
@unlink('{remote_php}');
"""

    # Step 3: Upload PHP and execute
    ssh.upload_string(php_script, remote_php)
    output = ssh.run(f'wp eval-file {remote_php}', timeout=90).stdout.strip()
    parsed = ssh.parse_pipe_output(output)

    if 'ERROR' in parsed:
        print(f"CREATE ERROR: {parsed.get('ERROR', 'unknown')}", file=sys.stderr)
        return None

    new_id = int(parsed.get('ID', 0))
    content_len = int(parsed.get('LEN', 0))
    starts_with = parsed.get('STARTS_WITH', '')
    print(f"  Created post {new_id}: {content_len} chars, starts='{starts_with}...'")

    # Verify no PHP code leaked
    if any(leak in starts_with for leak in ['$self', 'file_get', 'PHPEOF', 'marker']):
        print(f"CRITICAL: PHP code leaked into post_content! starts_with='{starts_with}'", file=sys.stderr)
        return None

    return new_id


def main():
    parser = argparse.ArgumentParser(
        description='Safe WordPress post_content push (SCP + wp eval-file)')
    parser.add_argument('--site', required=True, help='Site slug')
    parser.add_argument('--post-id', type=int, help='Single post ID (for update)')
    parser.add_argument('--create', action='store_true',
                        help='Create a new post instead of updating. Requires --title and --html-file.')
    parser.add_argument('--title', help='Post title (required with --create)')
    parser.add_argument('--slug', help='Post slug (optional with --create, auto-derived if omitted)')
    parser.add_argument('--author', type=int, help='Post author user ID (for --create)')
    parser.add_argument('--excerpt', help='Post excerpt (for --create; auto-extracted from intro if omitted)')
    parser.add_argument('--batch-csv', help='CSV with post_id, html_path columns')
    parser.add_argument('--html-file', help='Content file (when using --post-id or --create)')
    parser.add_argument('--status', default='draft',
                        choices=['publish', 'draft', 'pending', 'private'])
    parser.add_argument('--backup-dir',
                        help='Backup directory (default: ~/<site>-rewrite/backups/)')
    parser.add_argument('--verify-greps', default='',
                        help='Comma-separated strings that must be present after write')
    parser.add_argument('--forbid-greps', default='',
                        help='Comma-separated strings that must be absent after write')
    parser.add_argument('--size-min-ratio', type=float, default=0.8)
    parser.add_argument('--size-max-ratio', type=float, default=1.2)
    parser.add_argument('--sleep-between', type=int, default=5)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--halt-on-fail', action='store_true', default=True)
    parser.add_argument('--allow-no-manifest', action='store_true',
                        help='Bypass manifest check (emergency rollback only)')
    parser.add_argument('--manifest-max-age-hours', type=int, default=168,
                        help='Maximum manifest age in hours (default: 168 = 7 days)')
    parser.add_argument('--sample-first', action='store_true', default=True,
                        help='For batches > 3: process first 3 rows, report, exit 42 (default: on)')
    parser.add_argument('--no-sample-first', action='store_true',
                        help='Disable sample-first gate')
    parser.add_argument('--sample-approved', action='store_true',
                        help='Resume after sample was approved — skip first 3, process remainder')
    args = parser.parse_args()

    if args.create:
        if not args.title:
            parser.error("--title required with --create")
        if not args.html_file:
            parser.error("--html-file required with --create")
    elif not args.post_id and not args.batch_csv:
        parser.error("Must provide --post-id, --batch-csv, or --create")
    if args.post_id and not args.html_file:
        parser.error("--html-file required when using --post-id")

    # P7: Deploy lock — block if another write tool is active on this site
    if not args.dry_run:
        acquire_deploy_lock(args.site, tool_name='push-post-content')

    # --create mode: create a new post, then exit
    if args.create:
        ssh = SSHSession(args.site)
        new_id = _create_post(ssh, args)
        if new_id:
            print(f"CREATED: post_id={new_id}")
        else:
            print("CREATE FAILED")
            sys.exit(1)
        return

    backup_dir = args.backup_dir or os.path.expanduser(
        f'~/{args.site}-rewrite/backups/')
    verify_greps = [g.strip() for g in args.verify_greps.split(',') if g.strip()]
    forbid_greps = [g.strip() for g in args.forbid_greps.split(',') if g.strip()]

    ssh = SSHSession(args.site, sleep_between=args.sleep_between)

    # Build task list
    tasks = []
    if args.post_id:
        tasks.append({'post_id': args.post_id, 'html_path': args.html_file})
    else:
        with open(args.batch_csv) as f:
            tasks = list(csv.DictReader(f))

    # P3: Sample-batch approval gate
    SAMPLE_SIZE = 3
    sample_mode = (args.sample_first and not args.no_sample_first
                   and len(tasks) > SAMPLE_SIZE
                   and not args.sample_approved
                   and not args.dry_run)
    resume_mode = args.sample_approved and len(tasks) > SAMPLE_SIZE

    if sample_mode:
        tasks_to_run = tasks[:SAMPLE_SIZE]
        print(f"SAMPLE-FIRST GATE: Processing {SAMPLE_SIZE} of {len(tasks)} posts.")
        print(f"After sample completes, review results and re-run with --sample-approved")
        print(f"to process the remaining {len(tasks) - SAMPLE_SIZE} posts.")
    elif resume_mode:
        tasks_to_run = tasks[SAMPLE_SIZE:]
        print(f"SAMPLE-APPROVED: Skipping first {SAMPLE_SIZE} (already processed).")
        print(f"Processing remaining {len(tasks_to_run)} posts.")
    else:
        tasks_to_run = tasks

    print(f"Site: {args.site} | Posts: {len(tasks_to_run)}"
          f" (of {len(tasks)} total) | Status: {args.status} | "
          f"Dry run: {args.dry_run}")

    success_count = 0
    fail_count = 0

    for i, task in enumerate(tasks_to_run):
        post_id = int(task['post_id'])
        html_path = task.get('html_path', task.get('html_file', ''))

        print(f"[{i+1}/{len(tasks)}] Post {post_id}", end=' ')

        # Layer 3: manifest check
        manifest_ok, manifest_msg, _ = validate_manifest(
            html_path, max_age_hours=args.manifest_max_age_hours)
        if not manifest_ok:
            if args.allow_no_manifest:
                print()
                print(f"  WARNING: Bypassing manifest check. This deploy has no proof of")
                print(f"  pipeline origin. Bypass should only be used for emergency")
                print(f"  rollbacks or redeploying pre-Layer-3 content.")
                print(f"  Reason: {manifest_msg}")
            else:
                print(f"→ DEPLOY REJECTED")
                print(f"  {manifest_msg}")
                print(f"  Layer 3 requires a manifest as proof the content came from the RSS pipeline.")
                print(f"  To bypass (rare cases like emergency rollback): pass --allow-no-manifest")
                fail_count += 1
                if args.halt_on_fail and not args.dry_run:
                    print(f"\nHALTED. {success_count} ok, {fail_count} failed.")
                    sys.exit(1)
                continue
        else:
            print()
            print(f"  {manifest_msg}")

        print(f"  Pushing...", end=' ')

        ok, details = push_single_post(
            ssh, post_id, html_path, args.status,
            verify_greps, forbid_greps,
            args.size_min_ratio, args.size_max_ratio,
            backup_dir, args.dry_run)

        if ok:
            success_count += 1
            print(f"→ {details['status']} "
                  f"({details.get('content_length', details.get('new_content_len', '?'))} bytes)")
        else:
            fail_count += 1
            print(f"→ FAIL: {details.get('error', 'unknown')}")
            ssh.log(f"FAIL post={post_id} error={details.get('error', '')}")

            if args.halt_on_fail and not args.dry_run:
                print(f"\nHALTED after failure. {success_count} ok, {fail_count} failed.")
                sys.exit(1)

    print(f"\nDone. {success_count} ok, {fail_count} failed.")
    print(f"Log: {ssh.log_path}")

    # P3: If sample mode, exit 42 = awaiting Randall's approval
    if sample_mode:
        print(f"\n{'=' * 60}")
        print(f"SAMPLE COMPLETE — {success_count}/{SAMPLE_SIZE} succeeded.")
        print(f"Review the results above. If acceptable, re-run with:")
        print(f"  --sample-approved")
        print(f"to process the remaining {len(tasks) - SAMPLE_SIZE} posts.")
        print(f"{'=' * 60}")
        sys.exit(42)


if __name__ == '__main__':
    main()
