#!/usr/bin/env python3
"""Extract current intros from WP posts for optimization analysis.

Usage:
    python3 extract-current-intros.py --site lrg \
        --post-list-csv posts.csv --output-csv intros.csv

Requires SSH access to WP Engine and BeautifulSoup4.
"""

import argparse
import csv
import json
import subprocess
import sys
import time

sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1] / 'lib'))
from html_intro_replacer import extract_intro

SITE_CONFIG = {
    'lrg': {
        'ssh_host': 'lrgrealtyblog@lrgrealtyblog.ssh.wpengine.net',
        'ssh_key': '~/.ssh/wpengine_valn',
        'domain': 'lrgrealtyblog.wpenginepowered.com',
    },
}


def wp_get_post(site_cfg, post_id, field='post_content'):
    """Fetch a post field via WP-CLI over SSH."""
    cmd = [
        'ssh', '-i', site_cfg['ssh_key'], '-o', 'IdentitiesOnly=yes',
        site_cfg['ssh_host'],
        f'wp post get {post_id} --field={field}'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"  ERROR fetching post {post_id}: {result.stderr.strip()}", file=sys.stderr)
        return ''
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description='Extract current intros from WP posts')
    parser.add_argument('--site', required=True, choices=SITE_CONFIG.keys())
    parser.add_argument('--post-list-csv', required=True,
                        help='CSV with post_id column (and optionally post_title, url)')
    parser.add_argument('--output-csv', required=True)
    parser.add_argument('--intro-end-marker', default='first-h2',
                        help='How to detect intro end (default: first-h2)')
    parser.add_argument('--sleep', type=float, default=3.0,
                        help='Seconds between WP-CLI calls (default: 3)')
    args = parser.parse_args()

    cfg = SITE_CONFIG[args.site]

    # Read post list
    with open(args.post_list_csv) as f:
        reader = csv.DictReader(f)
        posts = list(reader)

    if not posts:
        print("ERROR: no posts in input CSV", file=sys.stderr)
        sys.exit(1)

    # Determine column names
    id_col = 'post_id' if 'post_id' in posts[0] else 'ID'

    fieldnames = [
        'post_id', 'post_title', 'url',
        'current_intro_html', 'current_intro_text',
        'current_word_count', 'current_paragraph_count',
        'has_disclaimer', 'has_eyebrow',
    ]

    with open(args.output_csv, 'w', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=fieldnames)
        writer.writeheader()

        for i, post in enumerate(posts):
            post_id = post[id_col]
            title = post.get('post_title', post.get('title', ''))
            url = post.get('url', post.get('post_name', ''))

            print(f"[{i+1}/{len(posts)}] Post {post_id}: {title[:60]}")

            content = wp_get_post(cfg, post_id)
            if not content:
                print(f"  SKIP: empty content")
                continue

            intro_html, intro_text, para_count, word_count, has_disc, has_eye = \
                extract_intro(content)

            writer.writerow({
                'post_id': post_id,
                'post_title': title,
                'url': url,
                'current_intro_html': intro_html,
                'current_intro_text': intro_text,
                'current_word_count': word_count,
                'current_paragraph_count': para_count,
                'has_disclaimer': has_disc,
                'has_eyebrow': has_eye,
            })

            print(f"  {word_count} words, {para_count} paragraphs, "
                  f"disclaimer={'Y' if has_disc else 'N'}, eyebrow={'Y' if has_eye else 'N'}")

            if i < len(posts) - 1:
                time.sleep(args.sleep)

    print(f"\nDone. {len(posts)} posts extracted to {args.output_csv}")


if __name__ == '__main__':
    main()
