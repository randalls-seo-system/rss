#!/usr/bin/env python3
"""
Validate redirect targets by checking HTTP status codes.

Reads a redirect map CSV (or Redirection plugin import CSV) and verifies
each target URL returns HTTP 200. Adds a target_status column.

Usage:
    python3 validate-redirect-targets.py --site lrg \
        --input redirects/lrg-redirect-map.csv \
        --output redirects/lrg-redirect-map-VALIDATED.csv

    # Or validate a Redirection plugin import CSV:
    python3 validate-redirect-targets.py --site lrg \
        --input redirects/lrg-301-redirects-import.csv \
        --format redirection \
        --output redirects/lrg-301-redirects-VALIDATED.csv
"""

import argparse
import csv
import os
import subprocess
import sys
import time


def check_url(url: str, timeout: int = 10) -> str:
    """Check HTTP status of a URL via curl. Returns status code string."""
    try:
        result = subprocess.run(
            ["curl", "-sI", "-o", "/dev/null", "-w", "%{http_code}",
             "--max-time", str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, Exception):
        return "timeout"


def read_domain_from_config(site_slug: str) -> str:
    """Read SITE_DOMAIN from sites/<slug>.conf."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(script_dir)))
    conf_path = os.path.join(root_dir, "sites", f"{site_slug}.conf")

    if os.path.exists(conf_path):
        with open(conf_path) as f:
            for line in f:
                if line.startswith("SITE_DOMAIN="):
                    return line.split("=", 1)[1].strip().strip('"')

    return ""


def main():
    parser = argparse.ArgumentParser(
        description="Validate redirect targets with HTTP status checks.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Formats:
  redirect-map    Expects columns: old_url, new_url (full URLs)
  redirection     Expects columns: source, target (paths only, needs --domain)

Status codes:
  200    Target exists and is accessible
  301    Target itself redirects (chain risk)
  404    Target does not exist (needs fix before deploy)
  5xx    Server error (retry later)
  timeout  Connection timed out

Examples:
  %(prog)s --site lrg --input map.csv --output validated.csv
  %(prog)s --site lrg --input import.csv --format redirection --output validated.csv
        """,
    )

    parser.add_argument("--site", required=True, help="Site slug")
    parser.add_argument("--input", required=True, help="Input redirect CSV")
    parser.add_argument("--output", required=True, help="Output validated CSV")
    parser.add_argument("--format", choices=["redirect-map", "redirection"], default="redirect-map",
                        help="Input CSV format (default: redirect-map)")
    parser.add_argument("--domain", help="Production domain (default: from site config)")
    parser.add_argument("--delay", type=float, default=0.3,
                        help="Delay between requests in seconds (default: 0.3)")
    parser.add_argument("--timeout", type=int, default=10,
                        help="Per-request timeout in seconds (default: 10)")

    args = parser.parse_args()

    domain = args.domain or read_domain_from_config(args.site)
    if not domain and args.format == "redirection":
        print("ERROR: --domain required for redirection format (or set in site config)", file=sys.stderr)
        sys.exit(1)

    print(f"=== Redirect Target Validator ===", file=sys.stderr)
    print(f"Site: {args.site}", file=sys.stderr)
    print(f"Domain: {domain}", file=sys.stderr)
    print(f"Input: {args.input}", file=sys.stderr)
    print(f"Format: {args.format}", file=sys.stderr)
    print(file=sys.stderr)

    with open(args.input) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    status_counts = {}

    for i, row in enumerate(rows):
        # Extract target URL
        if args.format == "redirection":
            target_path = row.get("target", "")
            target_url = f"https://{domain}{target_path}"
        else:
            target_url = row.get("new_url", "")

        status = check_url(target_url, args.timeout)
        row["target_status"] = status
        status_counts[status] = status_counts.get(status, 0) + 1

        label = "OK" if status == "200" else status
        print(f"  [{i+1}/{total}] {label} {target_url}", file=sys.stderr)
        time.sleep(args.delay)

    # Write output
    fieldnames = list(rows[0].keys()) if rows else []
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(file=sys.stderr)
    print(f"=== Validation Complete ===", file=sys.stderr)
    print(f"Total: {total}", file=sys.stderr)
    for code, count in sorted(status_counts.items()):
        label = {"200": "OK", "301": "Chain", "404": "Missing", "timeout": "Timeout"}.get(code, code)
        print(f"  {code} ({label}): {count}", file=sys.stderr)
    print(f"\nOutput: {args.output}", file=sys.stderr)

    # Exit with error if any 404s found
    if "404" in status_counts:
        print(f"\nWARNING: {status_counts['404']} targets return 404. Fix before deploying.", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
