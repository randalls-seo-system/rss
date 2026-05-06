#!/usr/bin/env python3
"""
Verify CSS is rendering on a sample page after deployment.

Checks that CSS files are linked, accessible, and expected classes exist.

Usage:
    python3 verify-css-rendered.py --site lrg \
        --sample-url "https://lrgrealtyblog.wpenginepowered.com/?p=2662" \
        --expected-classes "rl-page,rl-quick-grid,rl-faq"
"""

import argparse
import os
import re
import subprocess
import sys


def read_site_config(site_slug: str) -> dict:
    """Read site config."""
    root = os.path.expanduser("~/randalls-seo-system")
    conf = os.path.join(root, "sites", f"{site_slug}.conf")
    config = {}
    if os.path.exists(conf):
        with open(conf) as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                config[key.strip()] = val.strip().strip('"')
    return config


def fetch_url(url: str, timeout: int = 15) -> tuple[int, str]:
    """Fetch URL, return (status_code, body)."""
    try:
        result = subprocess.run(
            ["curl", "-sL", "--max-time", str(timeout), "-w", "\n%{http_code}", url],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        parts = result.stdout.rsplit("\n", 1)
        body = parts[0] if len(parts) > 1 else result.stdout
        code = int(parts[-1]) if len(parts) > 1 else 0
        return code, body
    except Exception as e:
        return 0, str(e)


def check_http_status(url: str, timeout: int = 10) -> str:
    """Check HTTP status code."""
    try:
        result = subprocess.run(
            ["curl", "-sI", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        return result.stdout.strip()
    except Exception:
        return "error"


def main():
    parser = argparse.ArgumentParser(
        description="Verify CSS is rendering on a sample page.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Checks performed:
  1. Sample page returns HTTP 200
  2. <link> tags reference rl-base.css and rl-<slug>-theme.css
  3. CSS file URLs return HTTP 200
  4. Expected CSS classes appear in page HTML
  5. Expected CSS variables present in linked stylesheets

Examples:
  %(prog)s --site lrg --sample-url "https://lrgrealtyblog.wpenginepowered.com/?p=2662"
  %(prog)s --site lrg --sample-url "https://lrgrealty.com/lrg-blog/some-post/"
        """,
    )

    parser.add_argument("--site", required=True, help="Site slug")
    parser.add_argument("--sample-url", required=True, help="URL of a page with rl-* classes")
    parser.add_argument("--expected-classes", default="rl-page",
                        help="Comma-separated list of expected CSS classes (default: rl-page)")
    parser.add_argument("--expected-vars", default="--rl-primary",
                        help="Comma-separated list of expected CSS variables")
    args = parser.parse_args()

    config = read_site_config(args.site)
    expected_classes = [c.strip() for c in args.expected_classes.split(",")]
    expected_vars = [v.strip() for v in args.expected_vars.split(",")]

    results = []
    all_pass = True

    print(f"=== CSS Rendering Verification ===", file=sys.stderr)
    print(f"Site: {args.site}", file=sys.stderr)
    print(f"Sample URL: {args.sample_url}", file=sys.stderr)
    print(file=sys.stderr)

    # Check 1: Page returns 200
    print("1. Fetching sample page...", file=sys.stderr)
    status, html = fetch_url(args.sample_url)
    if status == 200:
        print(f"   PASS: HTTP {status}", file=sys.stderr)
        results.append(("Page HTTP status", "PASS", str(status)))
    else:
        print(f"   FAIL: HTTP {status}", file=sys.stderr)
        results.append(("Page HTTP status", "FAIL", str(status)))
        all_pass = False

    # Check 2: <link> tags for rl-base.css and theme CSS
    print("2. Checking <link> tags...", file=sys.stderr)
    base_link = re.search(r'href=["\']([^"\']*rl-base\.css[^"\']*)["\']', html)
    theme_link = re.search(rf'href=["\']([^"\']*rl-{args.site}-theme\.css[^"\']*)["\']', html)

    if base_link:
        print(f"   PASS: rl-base.css linked", file=sys.stderr)
        results.append(("rl-base.css <link>", "PASS", base_link.group(1)[:80]))
    else:
        print(f"   FAIL: rl-base.css not found in <link> tags", file=sys.stderr)
        results.append(("rl-base.css <link>", "FAIL", "not found"))
        all_pass = False

    if theme_link:
        print(f"   PASS: rl-{args.site}-theme.css linked", file=sys.stderr)
        results.append((f"rl-{args.site}-theme.css <link>", "PASS", theme_link.group(1)[:80]))
    else:
        print(f"   FAIL: rl-{args.site}-theme.css not found in <link> tags", file=sys.stderr)
        results.append((f"rl-{args.site}-theme.css <link>", "FAIL", "not found"))
        all_pass = False

    # Check 3: CSS files return 200
    print("3. Checking CSS file access...", file=sys.stderr)
    for link_match, name in [(base_link, "rl-base.css"), (theme_link, f"rl-{args.site}-theme.css")]:
        if link_match:
            css_url = link_match.group(1)
            if css_url.startswith("//"):
                css_url = "https:" + css_url
            elif css_url.startswith("/"):
                from urllib.parse import urlparse
                parsed = urlparse(args.sample_url)
                css_url = f"{parsed.scheme}://{parsed.netloc}{css_url}"
            css_status = check_http_status(css_url)
            if css_status == "200":
                print(f"   PASS: {name} HTTP 200", file=sys.stderr)
                results.append((f"{name} HTTP", "PASS", "200"))
            else:
                print(f"   FAIL: {name} HTTP {css_status}", file=sys.stderr)
                results.append((f"{name} HTTP", "FAIL", css_status))
                all_pass = False

    # Check 4: Expected classes in HTML
    print("4. Checking expected classes...", file=sys.stderr)
    for cls in expected_classes:
        if cls in html:
            print(f"   PASS: class '{cls}' found", file=sys.stderr)
            results.append((f"class '{cls}'", "PASS", "present"))
        else:
            print(f"   FAIL: class '{cls}' not found", file=sys.stderr)
            results.append((f"class '{cls}'", "FAIL", "missing"))
            all_pass = False

    # Check 5: CSS variables in stylesheets
    if base_link:
        print("5. Checking CSS variables...", file=sys.stderr)
        css_url = base_link.group(1)
        if css_url.startswith("//"):
            css_url = "https:" + css_url
        elif css_url.startswith("/"):
            from urllib.parse import urlparse
            parsed = urlparse(args.sample_url)
            css_url = f"{parsed.scheme}://{parsed.netloc}{css_url}"
        _, css_content = fetch_url(css_url)
        for var in expected_vars:
            if var in css_content:
                print(f"   PASS: variable '{var}' defined", file=sys.stderr)
                results.append((f"var '{var}'", "PASS", "defined"))
            else:
                print(f"   WARN: variable '{var}' not found in base CSS", file=sys.stderr)
                results.append((f"var '{var}'", "WARN", "not in base"))

    # Summary
    print(file=sys.stderr)
    passes = sum(1 for _, s, _ in results if s == "PASS")
    fails = sum(1 for _, s, _ in results if s == "FAIL")
    warns = sum(1 for _, s, _ in results if s == "WARN")

    print(f"=== Results: {passes} pass, {fails} fail, {warns} warn ===", file=sys.stderr)

    if all_pass:
        print("VERDICT: ALL CHECKS PASSED", file=sys.stderr)
    else:
        print("VERDICT: SOME CHECKS FAILED", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
