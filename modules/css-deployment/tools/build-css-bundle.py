#!/usr/bin/env python3
"""
Build CSS deployment bundle from rl-components base + site theme.

Combines base CSS and site-specific theme overrides into a deploy-ready
package with mu-plugin loader.

Usage:
    python3 build-css-bundle.py --site lrg --output-dir /tmp/lrg-css-bundle/
    python3 build-css-bundle.py --site lrg --version 1.0.5 --dry-run
"""

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
from css_validator import parse_css, validate_css_syntax


def read_site_config(site_slug: str) -> dict:
    """Read site config values."""
    root = os.path.expanduser("~/randalls-seo-system")
    conf_path = os.path.join(root, "sites", f"{site_slug}.conf")
    config = {}
    if os.path.exists(conf_path):
        with open(conf_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                config[key.strip()] = val.strip().strip('"')
    return config


def render_template(template_path: str, replacements: dict) -> str:
    """Render PHP template with {{KEY}} replacements."""
    with open(template_path) as f:
        content = f.read()
    for key, val in replacements.items():
        content = content.replace(f"{{{{{key}}}}}", val)
    return content


def main():
    parser = argparse.ArgumentParser(
        description="Build CSS deployment bundle.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Output structure:
  <output-dir>/
    rl-base.css              Base rl-components CSS
    rl-<slug>-theme.css      Site-specific theme overrides
    rl-css-loader.php        mu-plugin loader
    manifest.json            Build metadata

Examples:
  %(prog)s --site lrg --output-dir ~/lrg-rewrite/css-deploy/
  %(prog)s --site lrg --version 1.0.5 --dry-run
        """,
    )

    parser.add_argument("--site", required=True, help="Site slug")
    parser.add_argument("--output-dir", help="Output directory (default: ~/<site>-rewrite/css-deploy/)")
    parser.add_argument("--base-css", help="Base CSS path (default: modules/rl-components/css/rl-base.css)")
    parser.add_argument("--theme-css", help="Theme CSS path (default: sites/<slug>/rl-theme.css)")
    parser.add_argument("--version", default="1.0.0", help="Version string (default: 1.0.0)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be built")
    args = parser.parse_args()

    root = os.path.expanduser("~/randalls-seo-system")
    config = read_site_config(args.site)
    site_name = config.get("SITE_NAME", args.site)

    # Resolve paths
    output_dir = args.output_dir or os.path.expanduser(f"~/{args.site}-rewrite/css-deploy/")
    base_css = args.base_css or os.path.join(root, "modules", "rl-components", "css", "rl-base.css")
    theme_css = args.theme_css or os.path.join(root, "sites", args.site, "rl-theme.css")
    template_path = os.path.join(root, "modules", "css-deployment", "templates", "rl-css-loader.php.template")

    print(f"=== CSS Bundle Builder ===", file=sys.stderr)
    print(f"Site: {site_name} ({args.site})", file=sys.stderr)
    print(f"Version: {args.version}", file=sys.stderr)
    print(f"Base CSS: {base_css}", file=sys.stderr)
    print(f"Theme CSS: {theme_css}", file=sys.stderr)
    print(f"Output: {output_dir}", file=sys.stderr)
    print(f"Dry run: {args.dry_run}", file=sys.stderr)
    print(file=sys.stderr)

    # Validate base CSS exists
    if not os.path.exists(base_css):
        print(f"ERROR: Base CSS not found: {base_css}", file=sys.stderr)
        sys.exit(1)

    # Validate and analyze base CSS
    with open(base_css) as f:
        base_content = f.read()
    base_errors = validate_css_syntax(base_content)
    if base_errors:
        print(f"WARNING: Base CSS issues: {base_errors}", file=sys.stderr)
    base_stats = parse_css(base_content, base_css)
    print(f"Base CSS: {base_stats.file_size:,} bytes, {base_stats.selector_count} selectors", file=sys.stderr)

    # Theme CSS (optional — generate stub if missing)
    theme_content = ""
    if os.path.exists(theme_css):
        with open(theme_css) as f:
            theme_content = f.read()
        theme_errors = validate_css_syntax(theme_content)
        if theme_errors:
            print(f"WARNING: Theme CSS issues: {theme_errors}", file=sys.stderr)
        theme_stats = parse_css(theme_content, theme_css)
        print(f"Theme CSS: {theme_stats.file_size:,} bytes, {theme_stats.selector_count} selectors", file=sys.stderr)
    else:
        print(f"Theme CSS not found, generating stub with brand variables", file=sys.stderr)
        primary = config.get("PRIMARY_COLOR", "#1a1a2e")
        accent = config.get("SECONDARY_COLOR", "#e94560")
        theme_content = f"""/* rl-{args.site}-theme.css — Brand overrides for {site_name} */
:root {{
    --rl-primary: {primary};
    --rl-accent: {accent};
}}
"""

    # Render mu-plugin loader
    if os.path.exists(template_path):
        loader_content = render_template(template_path, {
            "SITE_NAME": site_name,
            "SITE_SLUG": args.site,
            "VERSION": args.version,
        })
    else:
        print(f"WARNING: Template not found: {template_path}", file=sys.stderr)
        loader_content = f"""<?php
/*
Plugin Name: Rank Logic CSS Loader ({site_name})
Version: {args.version}
*/
if (!defined('ABSPATH')) exit;
function rl_{args.site}_enqueue_styles() {{
    $v = '{args.version}';
    $base = plugin_dir_url(__FILE__) . 'rl-css-loader/css/';
    wp_enqueue_style('rl-base', $base . 'rl-base.css', [], $v);
    wp_enqueue_style('rl-{args.site}-theme', $base . 'rl-{args.site}-theme.css', ['rl-base'], $v);
}}
add_action('wp_enqueue_scripts', 'rl_{args.site}_enqueue_styles', 9999);
"""

    # Build manifest
    manifest = {
        "site": args.site,
        "site_name": site_name,
        "version": args.version,
        "built_at": datetime.utcnow().isoformat() + "Z",
        "files": {
            "rl-base.css": len(base_content.encode("utf-8")),
            f"rl-{args.site}-theme.css": len(theme_content.encode("utf-8")),
            "rl-css-loader.php": len(loader_content.encode("utf-8")),
        },
        "base_selectors": base_stats.selector_count,
    }

    if args.dry_run:
        print(f"\n[DRY RUN] Would write to {output_dir}/:", file=sys.stderr)
        for fname, size in manifest["files"].items():
            print(f"  {fname}: {size:,} bytes", file=sys.stderr)
        print(f"  manifest.json: {len(json.dumps(manifest)):,} bytes", file=sys.stderr)
    else:
        os.makedirs(output_dir, exist_ok=True)

        with open(os.path.join(output_dir, "rl-base.css"), "w") as f:
            f.write(base_content)
        with open(os.path.join(output_dir, f"rl-{args.site}-theme.css"), "w") as f:
            f.write(theme_content)
        with open(os.path.join(output_dir, "rl-css-loader.php"), "w") as f:
            f.write(loader_content)
        with open(os.path.join(output_dir, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)

        print(f"\nBundle built: {output_dir}", file=sys.stderr)
        for fname, size in manifest["files"].items():
            print(f"  {fname}: {size:,} bytes", file=sys.stderr)

    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
