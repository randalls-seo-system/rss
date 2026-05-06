#!/usr/bin/env python3
"""
Add CSS rule aliases for class names that exist in HTML but not in source CSS.

Reads a YAML/JSON config defining alias mappings, finds the source rule
body, and appends aliased copies to the target CSS.

Usage:
    python3 add-css-aliases.py --target-css rl-base.css --aliases-yaml aliases.yaml
    python3 add-css-aliases.py --target-css rl-base.css --aliases-yaml aliases.yaml --dry-run

Aliases file format (YAML or JSON):
    {
        "rl-bullet-section--green": {"mirror": "bullet-section-green"},
        "rl-quick-head": {"mirror": "rl-hero-quick-head"},
        "rl-text-muted": {"rules": "color: var(--rl-muted, #475569);"}
    }

For "mirror" entries, the tool finds the source selector's rule body
and copies it with the new selector name.
For "rules" entries, the tool creates a new rule with the given CSS.
"""

import argparse
import json
import os
import re
import sys


def load_aliases(path: str) -> dict:
    """Load aliases from YAML or JSON file."""
    with open(path) as f:
        content = f.read()

    # Try JSON first
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Try simple YAML-like parsing (key: value pairs)
    aliases = {}
    current_key = None
    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Top-level key
        if not line.startswith(" ") and stripped.endswith(":"):
            current_key = stripped[:-1].strip().strip('"').strip("'")
            aliases[current_key] = {}
        elif current_key and ":" in stripped:
            k, v = stripped.split(":", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if v == "|":
                # Multi-line value follows (not fully implemented)
                pass
            else:
                aliases[current_key][k] = v

    return aliases


def find_rule_body(css_text: str, selector: str) -> str:
    """Find the CSS rule body for a given selector."""
    # Escape dots for regex
    escaped = re.escape(selector)
    # Match .selector { ... }
    pattern = rf"\.{escaped}\s*\{{([^}}]*)\}}"
    match = re.search(pattern, css_text)
    if match:
        return match.group(1).strip()
    return ""


def main():
    parser = argparse.ArgumentParser(
        description="Add CSS aliases for divergent class names.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --target-css rl-base.css --aliases-yaml lrg-aliases.yaml
  %(prog)s --target-css rl-base.css --aliases-yaml lrg-aliases.json --dry-run
        """,
    )

    parser.add_argument("--target-css", required=True, help="CSS file to append aliases to")
    parser.add_argument("--aliases-yaml", required=True, help="Aliases config (YAML or JSON)")
    parser.add_argument("--backup-suffix", default=".pre-aliases.bak", help="Backup suffix")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be added")
    args = parser.parse_args()

    if not os.path.exists(args.target_css):
        print(f"ERROR: Target CSS not found: {args.target_css}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(args.aliases_yaml):
        print(f"ERROR: Aliases file not found: {args.aliases_yaml}", file=sys.stderr)
        sys.exit(1)

    with open(args.target_css) as f:
        css = f.read()

    aliases = load_aliases(args.aliases_yaml)

    print(f"=== CSS Alias Generator ===", file=sys.stderr)
    print(f"Target: {args.target_css}", file=sys.stderr)
    print(f"Aliases: {len(aliases)}", file=sys.stderr)
    print(file=sys.stderr)

    alias_block = "\n/* ══════════════════════════════════════════\n"
    alias_block += "   CSS ALIASES (auto-generated)\n"
    alias_block += "   ══════════════════════════════════════════ */\n\n"

    added = 0
    skipped = 0

    for alias_class, config in aliases.items():
        if "mirror" in config:
            source_class = config["mirror"]
            body = find_rule_body(css, source_class)
            if body:
                alias_block += f".{alias_class} {{ {body} }}\n"
                print(f"  ALIAS: .{alias_class} ← .{source_class}", file=sys.stderr)
                added += 1
            else:
                print(f"  SKIP: .{alias_class} — source .{source_class} not found", file=sys.stderr)
                skipped += 1
        elif "rules" in config:
            rules = config["rules"]
            alias_block += f".{alias_class} {{ {rules} }}\n"
            print(f"  ALIAS: .{alias_class} (custom rules)", file=sys.stderr)
            added += 1
        else:
            print(f"  SKIP: .{alias_class} — no 'mirror' or 'rules' key", file=sys.stderr)
            skipped += 1

    print(f"\nAdded: {added}, Skipped: {skipped}", file=sys.stderr)

    if args.dry_run:
        print(f"\n[DRY RUN] Would append {len(alias_block)} chars to {args.target_css}", file=sys.stderr)
        print(f"\nPreview:\n{alias_block[:500]}", file=sys.stderr)
    else:
        # Backup
        import shutil
        backup_path = args.target_css + args.backup_suffix
        shutil.copy2(args.target_css, backup_path)
        print(f"Backup: {backup_path}", file=sys.stderr)

        # Append aliases
        with open(args.target_css, "a") as f:
            f.write(alias_block)
        print(f"Aliases appended to {args.target_css}", file=sys.stderr)


if __name__ == "__main__":
    main()
