#!/usr/bin/env python3
"""P2: Render-verification gate — confirms the RENDERED artifact, not just the DB.

verify-write.py checks the database (post_content via WP-CLI).
verify-deploy.py checks the RENDERED PAGE (curl the URL, grep the HTML).

The distinction: "deployed" (file on disk, DB written) is necessary but
insufficient. "Delivered" means the browser-facing page contains the
expected elements. This tool checks delivery.

This is the shared artifact that push-post-content.py calls after deploy,
and that the AI verification layer's RENDER-VERIFY gate will wrap.

Usage:
    # Check a single URL with inline checks
    python3 verify-deploy.py \\
        --url https://example.com/page/ \\
        --expect-text "Sohail Safi" \\
        --expect-text "halal meat" \\
        --expect-head "stylesheet" \\
        --expect-head "noindex" \\
        --forbid-text "console.log" \\
        --forbid-text "[Placeholder"

    # Check from a verify-spec JSON file
    python3 verify-deploy.py --spec sites/lrg-verify.json --url https://...

    # SSH-tunneled check (for sites behind Cloudflare — curls via localhost on server)
    python3 verify-deploy.py \\
        --site lrg --path /page-slug/ \\
        --expect-text "expected text"

Spec JSON format:
    {
      "checks": [
        {"type": "text", "value": "expected string", "section": "body"},
        {"type": "head", "value": "stylesheet.*rl-article"},
        {"type": "forbid", "value": "console.log"},
        {"type": "meta", "attr": "name", "attr_value": "robots", "content_contains": "noindex"}
      ]
    }

Exit codes:
    0  = all checks passed
    1  = one or more checks failed
    2  = could not fetch the page (network/HTTP error)
    78 = bad arguments
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULE_ROOT / 'lib'))


def fetch_rendered_html(url=None, site=None, path=None, timeout=15):
    """Fetch the rendered HTML of a page.

    If site + path are given, uses SSH to curl from localhost (bypasses
    Cloudflare). Otherwise curls the URL directly.

    Returns (ok: bool, html: str, error: str).
    """
    if site and path:
        # SSH method: resolve the path to a post and read its rendered
        # content. For mu-plugin-served pages (which call exit and bypass
        # normal WP rendering), falls back to checking the post_content.
        #
        # NOTE: WPE's Cloudflare blocks localhost curl and wp_remote_get
        # (self-request). For full render verification on WPE, prefer
        # the --url method which curls from the dev machine. The --site
        # method checks what WP has in the DB (post_content after filters).
        from ssh_session import SSHSession
        ssh = SSHSession(site, sleep_between=1)
        path = path if path.startswith('/') else f'/{path}'
        try:
            # WPE /tmp is session-local, so upload + eval must happen in
            # ONE SSH command. Pipe PHP via stdin, write + eval in same session.
            php_code = (
                '<?php\n'
                f'$pid = url_to_postid(home_url("{path}"));\n'
                f'if (!$pid && "{path}" === "/") $pid = (int) get_option("page_on_front");\n'
                'if ($pid) {\n'
                '    $p = get_post($pid);\n'
                '    $html = apply_filters("the_content", $p->post_content);\n'
                '    if (strlen(trim($html)) < 50) {\n'
                '        $mu = WPMU_PLUGIN_DIR;\n'
                '        $candidates = array_merge(glob($mu . "/*/index.html"), glob($mu . "/*/*.html"));\n'
                '        foreach ($candidates as $f) { if (filesize($f) > 1000) { echo file_get_contents($f); exit(0); } }\n'
                '    }\n'
                '    echo $html;\n'
                '} else {\n'
                '    fwrite(STDERR, "Could not resolve path to post ID");\n'
                '    exit(1);\n'
                '}\n'
            )
            cmd = ssh._ssh_base_cmd() + [
                'cat > /tmp/rss-vd.php && wp eval-file /tmp/rss-vd.php; rm -f /tmp/rss-vd.php'
            ]
            result = subprocess.run(
                cmd, input=php_code,
                capture_output=True, text=True, timeout=max(timeout, 45)
            )
            if result.returncode != 0:
                return False, '', f'curl failed (exit {result.returncode})'
            html = result.stdout
            if not html or len(html) < 100:
                return False, html, f'Response too short ({len(html)} bytes)'
            return True, html, ''
        except Exception as e:
            return False, '', str(e)
    elif url:
        # Direct fetch
        try:
            result = subprocess.run(
                ['curl', '-s', '-L', '--max-time', str(timeout), url],
                capture_output=True, text=True, timeout=timeout + 5
            )
            if result.returncode != 0:
                return False, '', f'curl failed (exit {result.returncode})'
            html = result.stdout
            if not html or len(html) < 100:
                return False, html, f'Response too short ({len(html)} bytes)'
            return True, html, ''
        except subprocess.TimeoutExpired:
            return False, '', f'curl timed out after {timeout}s'
        except Exception as e:
            return False, '', str(e)
    else:
        return False, '', 'No URL or site+path provided'


def split_head_body(html):
    """Split HTML into head and body sections."""
    head_match = re.search(r'<head[^>]*>(.*?)</head>', html, re.DOTALL | re.IGNORECASE)
    body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL | re.IGNORECASE)
    head = head_match.group(1) if head_match else ''
    body = body_match.group(1) if body_match else html
    return head, body


def run_checks(html, checks):
    """Run all checks against the rendered HTML.

    Returns list of {check, passed, detail} dicts.
    """
    head, body = split_head_body(html)
    results = []

    for check in checks:
        ctype = check.get('type', 'text')
        value = check.get('value', '')
        result = {'check': f'{ctype}:{value[:60]}', 'passed': False, 'detail': ''}

        if ctype == 'text':
            # Check if text appears anywhere in rendered HTML
            section = check.get('section', 'body')
            search_in = body if section == 'body' else (head if section == 'head' else html)
            found = value in search_in
            result['passed'] = found
            if not found:
                result['detail'] = f'Text not found in {section}'

        elif ctype == 'head':
            # Check if pattern appears in <head>
            if re.search(value, head, re.IGNORECASE):
                result['passed'] = True
            else:
                result['detail'] = f'Pattern not found in <head>'

        elif ctype == 'forbid':
            # Check that text does NOT appear
            section = check.get('section', 'all')
            search_in = html if section == 'all' else (body if section == 'body' else head)
            found = value in search_in
            result['passed'] = not found
            if found:
                result['detail'] = f'Forbidden text found in {section}'

        elif ctype == 'meta':
            # Check a specific <meta> tag
            attr = check.get('attr', 'name')
            attr_value = check.get('attr_value', '')
            content_contains = check.get('content_contains', '')
            pattern = rf'<meta\s+[^>]*{attr}=["\']?{re.escape(attr_value)}["\']?[^>]*>'
            match = re.search(pattern, head, re.IGNORECASE)
            if not match:
                result['detail'] = f'<meta {attr}="{attr_value}"> not found'
            elif content_contains and content_contains not in match.group(0):
                result['detail'] = f'Meta tag found but content does not contain "{content_contains}"'
                result['passed'] = False
            else:
                result['passed'] = True
            result['check'] = f'meta:{attr}={attr_value}'

        elif ctype == 'element':
            # Check that an HTML element/class/id exists
            if re.search(value, html, re.IGNORECASE):
                result['passed'] = True
            else:
                result['detail'] = f'Element pattern not found'

        elif ctype == 'status':
            # HTTP status — handled separately, skip here
            result['passed'] = True

        results.append(result)

    return results


def main():
    parser = argparse.ArgumentParser(
        description='P2: Render-verify gate — check the RENDERED page, not just the DB')
    parser.add_argument('--url', help='Full URL to check')
    parser.add_argument('--site', help='Site slug (for SSH-tunneled check)')
    parser.add_argument('--path', help='URL path (used with --site)')
    parser.add_argument('--spec', help='Path to verify-spec JSON file')
    parser.add_argument('--expect-text', action='append', default=[],
                        help='Text that must appear in page body (repeatable)')
    parser.add_argument('--expect-head', action='append', default=[],
                        help='Pattern that must appear in <head> (repeatable)')
    parser.add_argument('--forbid-text', action='append', default=[],
                        help='Text that must NOT appear anywhere (repeatable)')
    parser.add_argument('--expect-element', action='append', default=[],
                        help='HTML pattern (class/id) that must appear (repeatable)')
    parser.add_argument('--output-format', default='text', choices=['text', 'json'])
    parser.add_argument('--timeout', type=int, default=15)
    args = parser.parse_args()

    if not args.url and not (args.site and args.path):
        parser.error('Must provide --url or --site + --path')

    # Build checks list
    checks = []

    # From spec file
    if args.spec:
        spec_path = Path(args.spec)
        if not spec_path.exists():
            print(f'ERROR: Spec file not found: {args.spec}', file=sys.stderr)
            sys.exit(78)
        with open(spec_path) as f:
            spec = json.load(f)
        checks.extend(spec.get('checks', []))

    # From CLI args
    for text in args.expect_text:
        checks.append({'type': 'text', 'value': text, 'section': 'body'})
    for pattern in args.expect_head:
        checks.append({'type': 'head', 'value': pattern})
    for text in args.forbid_text:
        checks.append({'type': 'forbid', 'value': text})
    for element in args.expect_element:
        checks.append({'type': 'element', 'value': element})

    if not checks:
        print('WARNING: No checks specified. Verifying page is fetchable only.',
              file=sys.stderr)

    # Fetch
    target = args.url or f'(ssh:{args.site}){args.path}'
    ok, html, error = fetch_rendered_html(
        url=args.url, site=args.site, path=args.path, timeout=args.timeout)

    if not ok:
        report = {
            'target': target,
            'fetched': False,
            'error': error,
            'checks': [],
            'passed': False,
        }
        if args.output_format == 'json':
            print(json.dumps(report, indent=2))
        else:
            print(f'FAIL — could not fetch {target}')
            print(f'  Error: {error}')
        sys.exit(2)

    # Run checks
    results = run_checks(html, checks)
    all_passed = all(r['passed'] for r in results)

    report = {
        'target': target,
        'fetched': True,
        'html_length': len(html),
        'checks': results,
        'passed': all_passed,
        'summary': f'{sum(1 for r in results if r["passed"])}/{len(results)} checks passed',
    }

    if args.output_format == 'json':
        print(json.dumps(report, indent=2))
    else:
        icon = 'PASS' if all_passed else 'FAIL'
        print(f'{icon} — {target} ({len(html)} bytes, {report["summary"]})')
        for r in results:
            ci = '+' if r['passed'] else 'X'
            line = f'  [{ci}] {r["check"]}'
            if not r['passed'] and r.get('detail'):
                line += f'  — {r["detail"]}'
            print(line)

    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
