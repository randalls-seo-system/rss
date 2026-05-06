#!/usr/bin/env python3
"""Render an LLM prompt with brand voice rules injected.

Reads an archetype, reads site config variables, and injects the voice
rules into a base prompt template at the {{INJECT_BRAND_VOICE}} marker.

Usage:
    python3 render-prompt.py \
        --archetype realtor \
        --site-config sites/lrg.conf \
        --base-prompt modules/meta-optimization/prompts/cluster-meta-generation.md \
        --output /tmp/rendered-prompt.md

Integration:
    Any module that uses LLMs calls this tool to build a voice-aware prompt
    before passing it to the LLM. This keeps voice rules centralized in the
    archetype and site config, not scattered across module prompts.
"""

import argparse
import configparser
import sys
from pathlib import Path

MODULE_ROOT = Path(__file__).resolve().parents[1]


def load_archetype(name):
    path = MODULE_ROOT / 'archetypes' / f'{name}.md'
    if not path.exists():
        print(f"ERROR: archetype not found: {path}", file=sys.stderr)
        sys.exit(1)
    return path.read_text()


def load_site_config(path):
    """Load [branding] section from site config.

    Site configs are hybrid: shell-style KEY=VALUE at the top (no section
    header) plus INI [sections] at the bottom. ConfigParser chokes on the
    headerless top, so we prepend a dummy [_shell] header before parsing.
    """
    raw = Path(path).read_text()
    # Prepend a dummy section so configparser can parse the shell vars
    config = configparser.ConfigParser()
    config.read_string('[_shell]\n' + raw)
    if 'branding' not in config:
        print(f"ERROR: [branding] section missing from {path}", file=sys.stderr)
        sys.exit(1)
    return dict(config['branding'])


def render_archetype(archetype_text, site_vars):
    """Replace {{PLACEHOLDER}} tokens in archetype with site config values."""
    mapping = {
        '{{MARKET_PRIMARY}}': site_vars.get('market_primary', ''),
        '{{MARKETS_SECONDARY}}': site_vars.get('markets_secondary', ''),
        '{{AUDIENCE_PRIMARY}}': site_vars.get('audience_primary', ''),
        '{{AUDIENCE_SECONDARY}}': site_vars.get('audience_secondary', ''),
        '{{SPECIALTIES}}': site_vars.get('specialties', ''),
        '{{BROKER_NAME}}': site_vars.get('broker_name', ''),
        '{{BRAND_NAME}}': site_vars.get('brand_name', ''),
        '{{BRAND_SUFFIX_SHORT}}': site_vars.get('brand_suffix_short', ''),
        '{{BRAND_SUFFIX_LONG}}': site_vars.get('brand_suffix_long', ''),
    }
    result = archetype_text
    for key, val in mapping.items():
        result = result.replace(key, val)
    return result


def inject_into_prompt(base_prompt_text, rendered_voice):
    """Replace {{INJECT_BRAND_VOICE}} in base prompt with rendered voice rules."""
    marker = '{{INJECT_BRAND_VOICE}}'
    if marker not in base_prompt_text:
        # No marker — prepend voice rules at the top
        return rendered_voice + '\n\n---\n\n' + base_prompt_text
    return base_prompt_text.replace(marker, rendered_voice)


def main():
    parser = argparse.ArgumentParser(
        description='Render an LLM prompt with brand voice rules injected')
    parser.add_argument('--archetype', required=True,
                        help='Archetype name (e.g., realtor)')
    parser.add_argument('--site-config', required=True,
                        help='Path to site .conf file with [branding] section')
    parser.add_argument('--base-prompt', required=True,
                        help='Path to base prompt template')
    parser.add_argument('--output', required=True,
                        help='Output path for rendered prompt')
    parser.add_argument('--voice-only', action='store_true',
                        help='Output only the rendered voice section (no base prompt)')
    args = parser.parse_args()

    archetype_text = load_archetype(args.archetype)
    site_vars = load_site_config(args.site_config)
    rendered_voice = render_archetype(archetype_text, site_vars)

    if args.voice_only:
        output = rendered_voice
    else:
        base_prompt = Path(args.base_prompt).read_text()
        output = inject_into_prompt(base_prompt, rendered_voice)

    Path(args.output).write_text(output)

    print(f"Archetype: {args.archetype}")
    print(f"Site: {site_vars.get('brand_name', 'unknown')}")
    print(f"Voice rules: {len(rendered_voice)} chars")
    print(f"Output: {len(output)} chars → {args.output}")


if __name__ == '__main__':
    main()
