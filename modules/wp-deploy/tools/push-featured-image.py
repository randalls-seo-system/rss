#!/usr/bin/env python3
"""Push a featured image from a local file to a WordPress post.

Uploads the image file via SCP, creates a WP attachment via wp eval-file,
and sets _thumbnail_id on the target post. Idempotent: skips if target
already has a thumbnail with the same filename.

Usage:
    # Dry run (default)
    python3 push-featured-image.py --site lrg --post-id 9265 \
        --image-file ~/randalls-seo-system/featured-images/lrg/post-9265-final.jpg

    # Execute
    python3 push-featured-image.py --site lrg --post-id 9265 \
        --image-file ~/randalls-seo-system/featured-images/lrg/post-9265-final.jpg \
        --execute

    # Batch from post IDs
    python3 push-featured-image.py --site lrg --batch-ids 9265,9268,9269 \
        --image-dir ~/randalls-seo-system/featured-images/lrg/ \
        --execute
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT / 'lib'))

from ssh_session import SSHSession


def push_image(ssh, post_id, image_path, execute=False, expect_slug=None):
    """Push a single featured image to a WordPress post.

    Returns dict with status and details.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        return {"post_id": post_id, "status": "error", "message": f"Image file not found: {image_path}"}

    # Safety: verify the target post exists and slug matches expectation
    slug_check = ssh.run(f"wp post get {post_id} --field=post_name", timeout=30, check=False)
    actual_slug = slug_check.stdout.strip() if slug_check and slug_check.returncode == 0 else ""
    if not actual_slug:
        return {"post_id": post_id, "status": "error", "message": f"Post {post_id} does not exist on target install"}
    if expect_slug and actual_slug != expect_slug:
        return {"post_id": post_id, "status": "error",
                "message": f"Slug mismatch: expected '{expect_slug}', got '{actual_slug}'. Wrong post ID?"}

    filename = image_path.name
    file_size = image_path.stat().st_size

    # Check if target already has a thumbnail with this filename
    check_result = ssh.run(
        f'wp eval \'$tid = get_post_meta({post_id}, "_thumbnail_id", true); '
        f'if ($tid) {{ $f = get_post_meta($tid, "_wp_attached_file", true); '
        f'echo "HAS_THUMB:$tid:$f"; }} else {{ echo "NO_THUMB"; }}\'',
        timeout=30, check=False
    )
    check_out = check_result.stdout.strip() if check_result else ""

    if check_out.startswith("HAS_THUMB:"):
        parts = check_out.split(":", 2)
        existing_id = parts[1]
        existing_file = parts[2] if len(parts) > 2 else ""
        if filename in existing_file:
            return {"post_id": post_id, "status": "skip",
                    "message": f"Already has thumbnail {existing_id} with matching filename {existing_file}"}
        else:
            return {"post_id": post_id, "status": "skip_different",
                    "message": f"Already has thumbnail {existing_id} ({existing_file}), different from {filename}. Remove existing first if replacement intended."}

    if not execute:
        return {"post_id": post_id, "status": "dry_run",
                "message": f"Would upload {filename} ({file_size:,} bytes) and set as thumbnail for post {post_id}"}

    # Upload image to persistent staging inbox
    remote_dir = "/nas/content/live/" + ssh.install + "/_staging-inbox/"
    remote_path = remote_dir + filename

    ssh.log(f"Uploading {filename} ({file_size:,} bytes)")
    ssh.run(f"mkdir -p {remote_dir}", check=False)
    ssh.upload_content(str(image_path), remote_path)

    # Create attachment and set thumbnail via PHP
    post_title = filename.replace('.jpg', '').replace('.png', '').replace('-', ' ').title()
    alt_text = post_title

    php = f"""<?php
$file = '{remote_path}';
$post_id = {post_id};

if (!file_exists($file)) {{
    echo "ERROR: File not found: $file\\n";
    exit(1);
}}

$file_data = file_get_contents($file);
$upload = wp_upload_bits('{filename}', null, $file_data);

if (!empty($upload['error'])) {{
    echo "ERROR: Upload failed: " . $upload['error'] . "\\n";
    exit(1);
}}

$attach_id = wp_insert_attachment([
    'post_mime_type' => '{_guess_mime(filename)}',
    'post_title'     => '{post_title}',
    'post_content'   => '',
    'post_status'    => 'inherit',
], $upload['file'], $post_id);

if (is_wp_error($attach_id)) {{
    echo "ERROR: Attachment creation failed: " . $attach_id->get_error_message() . "\\n";
    exit(1);
}}

require_once ABSPATH . 'wp-admin/includes/image.php';
$metadata = wp_generate_attachment_metadata($attach_id, $upload['file']);
wp_update_attachment_metadata($attach_id, $metadata);
update_post_meta($attach_id, '_wp_attachment_image_alt', '{alt_text}');

set_post_thumbnail($post_id, $attach_id);

// Clean up staging inbox
@unlink($file);

echo "OK:$attach_id:" . $upload['file'] . "\\n";
"""

    result = ssh.upload_and_eval(php, timeout=60)
    output = result.stdout.strip() if result else ""

    if output.startswith("OK:"):
        parts = output.split(":", 2)
        attach_id = parts[1]
        uploaded_path = parts[2] if len(parts) > 2 else ""
        return {"post_id": post_id, "status": "ok", "attach_id": attach_id,
                "message": f"Uploaded {filename}, attachment {attach_id}, thumbnail set"}

    return {"post_id": post_id, "status": "error", "message": f"PHP output: {output}"}


def _guess_mime(filename):
    ext = filename.rsplit('.', 1)[-1].lower()
    return {'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'png': 'image/png',
            'webp': 'image/webp', 'gif': 'image/gif'}.get(ext, 'image/jpeg')


def main():
    parser = argparse.ArgumentParser(description="Push featured image to WordPress post")
    parser.add_argument("--site", required=True, help="Site slug (e.g. lrg)")
    parser.add_argument("--post-id", type=int, help="Target post ID")
    parser.add_argument("--image-file", help="Path to image file")
    parser.add_argument("--batch-ids", help="Comma-separated post IDs for batch mode")
    parser.add_argument("--image-dir", help="Directory containing post-{id}-final.jpg files")
    parser.add_argument("--expect-slug", help="Expected post slug (safety check, fails if mismatch)")
    parser.add_argument("--execute", action="store_true", help="Actually execute (default is dry-run)")
    args = parser.parse_args()

    mode = "EXECUTE" if args.execute else "DRY RUN"
    print(f"push-featured-image.py | site={args.site} | mode={mode}")
    print(f"{'=' * 60}")

    ssh = SSHSession(args.site)

    results = []

    if args.batch_ids:
        ids = [int(x.strip()) for x in args.batch_ids.split(",")]
        image_dir = Path(args.image_dir) if args.image_dir else Path(".")
        for pid in ids:
            img = image_dir / f"post-{pid}-final.jpg"
            r = push_image(ssh, pid, img, execute=args.execute)
            print(f"  [{r['status']}] Post {pid}: {r['message']}")
            results.append(r)
    elif args.post_id and args.image_file:
        r = push_image(ssh, args.post_id, args.image_file, execute=args.execute, expect_slug=args.expect_slug)
        print(f"  [{r['status']}] Post {args.post_id}: {r['message']}")
        results.append(r)
    else:
        print("ERROR: Provide --post-id + --image-file, or --batch-ids + --image-dir")
        sys.exit(1)

    ok = sum(1 for r in results if r['status'] in ('ok', 'skip'))
    dry = sum(1 for r in results if r['status'] == 'dry_run')
    err = sum(1 for r in results if r['status'] == 'error')
    print(f"\nSummary: {ok} ok/skip, {dry} dry-run, {err} errors")


if __name__ == "__main__":
    main()
