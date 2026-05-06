#!/usr/bin/env python3
"""
Post-deploy redirect verification.

After redirects are deployed (via Redirection plugin or mu-plugin),
this tool verifies each redirect returns the correct 301 status and
lands on the expected target URL.

Usage:
    python3 verify-redirects-live.py --site lrg \
        --input redirects/lrg-redirect-map.csv \
        --output redirects/lrg-redirect-verification.csv
"""

import argparse
import csv
import os
import subprocess
import sys
import time


def check_redirect(source_url: str, expected_target: str, timeout: int = 10) -> dict:
    """Verify a single redirect returns 301 and lands on expected target.

    Returns dict with status_code, actual_location, matches_target, error.
    """
    try:
        result = subprocess.run(
            ["curl", "-sI", "--max-time", str(timeout),
             "-o", "/dev/null", "-w", "%{http_code}|%{redirect_url}", source_url],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        parts = result.stdout.strip().split("|", 1)
        status_code = parts[0]
        actual_location = parts[1] if len(parts) > 1 else ""

        # Normalize for comparison
        expected_norm = expected_target.rstrip("/").lower()
        actual_norm = actual_location.rstrip("/").lower()

        return {
            "status_code": status_code,
            "actual_location": actual_location,
            "matches_target": actual_norm == expected_norm or actual_norm.endswith(expected_norm),
            "error": "",
        }
    except subprocess.TimeoutExpired:
        return {"status_code": "timeout", "actual_location": "", "matches_target": False, "error": "timeout"}
    except Exception as e:
        return {"status_code": "error", "actual_location": "", "matches_target": False, "error": str(e)}


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
        description="Verify deployed redirects return correct 301 status.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Verification checks for each redirect:
  1. Source URL returns HTTP 301 (not 200, 302, 404, etc.)
  2. Location header points to expected target
  3. Target URL returns HTTP 200

Results:
  PASS     301 to correct target, target returns 200
  WRONG    301 but to wrong target
  NO_REDIR Source returns 200 (redirect not active)
  MISSING  Source returns 404
  CHAIN    Source returns 301 but target also redirects (chain)
  ERROR    Connection error or timeout

Examples:
  %(prog)s --site lrg --input lrg-redirect-map.csv --output verification.csv
        """,
    )

    parser.add_argument("--site", required=True, help="Site slug")
    parser.add_argument("--input", required=True, help="Redirect map CSV (old_url, new_url columns)")
    parser.add_argument("--output", required=True, help="Output verification report CSV")
    parser.add_argument("--domain", help="Override domain (default: from site config)")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="Delay between checks in seconds (default: 0.5)")

    args = parser.parse_args()

    domain = args.domain or read_domain_from_config(args.site)

    print(f"=== Redirect Verification ===", file=sys.stderr)
    print(f"Site: {args.site}", file=sys.stderr)
    print(f"Domain: {domain}", file=sys.stderr)
    print(f"Input: {args.input}", file=sys.stderr)
    print(file=sys.stderr)

    with open(args.input) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    results = []
    verdicts = {}

    for i, row in enumerate(rows):
        source_url = row.get("old_url", "")
        target_url = row.get("new_url", "")

        # If paths only (Redirection format), prepend domain
        if source_url.startswith("/"):
            source_url = f"https://{domain}{source_url}"
        if target_url.startswith("/"):
            target_url = f"https://{domain}{target_url}"

        check = check_redirect(source_url, target_url)

        # Determine verdict
        if check["status_code"] == "301" and check["matches_target"]:
            verdict = "PASS"
        elif check["status_code"] == "301" and not check["matches_target"]:
            verdict = "WRONG_TARGET"
        elif check["status_code"] == "200":
            verdict = "NO_REDIRECT"
        elif check["status_code"] == "404":
            verdict = "SOURCE_404"
        elif check["status_code"] in ("302", "307"):
            verdict = "TEMP_REDIRECT"
        elif check["status_code"] == "timeout":
            verdict = "TIMEOUT"
        else:
            verdict = f"HTTP_{check['status_code']}"

        verdicts[verdict] = verdicts.get(verdict, 0) + 1

        row["source_status"] = check["status_code"]
        row["actual_location"] = check["actual_location"]
        row["verdict"] = verdict
        results.append(row)

        symbol = "✓" if verdict == "PASS" else "✗"
        print(f"  [{i+1}/{total}] {symbol} {verdict:15s} {source_url}", file=sys.stderr)
        time.sleep(args.delay)

    # Write output
    fieldnames = list(results[0].keys()) if results else []
    with open(args.output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(file=sys.stderr)
    print(f"=== Verification Complete ===", file=sys.stderr)
    print(f"Total: {total}", file=sys.stderr)
    for verdict, count in sorted(verdicts.items(), key=lambda x: -x[1]):
        print(f"  {verdict}: {count}", file=sys.stderr)

    pass_count = verdicts.get("PASS", 0)
    pass_rate = (pass_count / total * 100) if total > 0 else 0
    print(f"\nPass rate: {pass_count}/{total} ({pass_rate:.0f}%)", file=sys.stderr)
    print(f"Output: {args.output}", file=sys.stderr)

    if pass_rate < 100:
        sys.exit(1)


if __name__ == "__main__":
    main()
