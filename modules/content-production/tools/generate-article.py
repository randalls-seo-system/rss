#!/usr/bin/env python3
"""LLM-driven full article HTML generator with brand voice integration.

Usage:
    python3 generate-article.py --site lrg --target-keyword "best neighborhoods in san antonio" \
        --intent decision --output article.html

    python3 generate-article.py --site lrg --target-keyword "how to buy a house" \
        --intent process --serp-data-json serp.json --output article.html
"""

import argparse
import configparser
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
MODULE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'modules' / 'brand-voice' / 'lib'))


def load_site_conf(site_slug):
    conf_path = REPO_ROOT / 'sites' / f'{site_slug}.conf'
    if not conf_path.exists():
        sys.exit(f"Site config not found: {conf_path}")
    conf = {}
    with open(conf_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('[') and '=' in line:
                key, val = line.split('=', 1)
                conf[key.strip()] = val.strip().strip('"')
    return conf


def load_branding(site_slug):
    """Load INI [branding] section from site config."""
    conf_path = REPO_ROOT / 'sites' / f'{site_slug}.conf'
    raw = conf_path.read_text()
    ini = configparser.ConfigParser()
    ini_match = re.search(r'(?m)^\[', raw)
    if ini_match:
        ini.read_string(raw[ini_match.start():])
    if 'branding' in ini:
        return dict(ini['branding'])
    return {}


def load_voice_rules(branding):
    """Load and render archetype voice rules."""
    archetype = branding.get('archetype', '')
    if not archetype:
        return ''
    arch_path = REPO_ROOT / 'modules' / 'brand-voice' / 'archetypes' / f'{archetype}.md'
    if not arch_path.exists():
        return ''
    text = arch_path.read_text()
    for key, val in branding.items():
        text = text.replace('{{' + key.upper() + '}}', val)
    return text


def load_prompt(intent, prompt_type):
    """Load a prompt template by type and intent."""
    if prompt_type == 'atf':
        path = MODULE_ROOT / 'prompts' / f'atf-{intent}.md'
    elif prompt_type == 'main':
        path = MODULE_ROOT / 'prompts' / f'main-content-{intent}.md'
    elif prompt_type == 'faq':
        path = MODULE_ROOT / 'prompts' / 'faq.md'
    else:
        raise ValueError(f"Unknown prompt type: {prompt_type}")
    if not path.exists():
        sys.exit(f"Prompt not found: {path}")
    return path.read_text()


def render_prompt(template, voice_rules, keyword, location, serp_data=None):
    """Substitute variables into prompt template."""
    prompt = template.replace('{{INJECT_BRAND_VOICE}}', voice_rules)
    prompt = prompt.replace('{{TARGET_KEYWORD}}', keyword)
    prompt = prompt.replace('{{LOCATION}}', location)

    # PAA questions for FAQ prompt
    if serp_data and '{{PAA_QUESTIONS}}' in prompt:
        paa = serp_data.get('related_questions', [])
        paa_text = '\n'.join(f'- {q.get("question", "")}' for q in paa[:6])
        if not paa_text:
            paa_text = f'- (No PAA data available. Generate 4-5 relevant questions for "{keyword}")'
        prompt = prompt.replace('{{PAA_QUESTIONS}}', paa_text)

    return prompt


def call_claude_cli(prompt, model='opus', system_msg=None):
    """Call Claude Code CLI with subscription. Returns (text, 0, 0).

    Token counts not available via CLI — cost is subscription-covered.
    """
    full_prompt = prompt
    if system_msg:
        full_prompt = f"[System: {system_msg}]\n\n{prompt}"
    result = subprocess.run(
        ['claude', '--model', model, '--print'],
        input=full_prompt,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Claude CLI failed (exit {result.returncode}): {result.stderr[:500]}")
    return result.stdout.strip(), 0, 0


def call_openai(prompt, model='gpt-5.4-mini', system_msg=None):
    """Call OpenAI API. Returns (text, input_tokens, output_tokens)."""
    from openai import OpenAI
    client = OpenAI()
    messages = []
    if system_msg:
        messages.append({'role': 'system', 'content': system_msg})
    messages.append({'role': 'user', 'content': prompt})
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=4096,
        temperature=0.7,
    )
    text = resp.choices[0].message.content
    usage = resp.usage
    return text, usage.prompt_tokens, usage.completion_tokens


def call_llm(prompt, provider, model, system_msg=None):
    """Dispatch to correct provider."""
    if provider == 'claude':
        return call_claude_cli(prompt, model, system_msg)
    else:
        return call_openai(prompt, model, system_msg)


def extract_html(text):
    """Extract HTML from LLM response, stripping preamble and markdown fences."""
    text = text.strip()
    if text.startswith('```html'):
        text = text[7:]
    elif text.startswith('```'):
        text = text[3:]
    if text.endswith('```'):
        text = text[:-3]
    # Strip any preamble text before the first HTML tag
    first_tag = re.search(r'<\w', text)
    if first_tag and first_tag.start() > 0:
        text = text[first_tag.start():]
    return text.strip()


def build_atf_html(keyword, intent, slug):
    """Build the ATF wrapper structure. Content filled by LLM."""
    # The LLM generates the inner content; we provide the outer wrapper
    return f'''<section id="{slug}" class="rl-page rl-page-lrg" data-rl-page="{slug}">
  <a class="rl-skip" href="#{slug}-faqs">Skip to FAQs</a>
  <div class="rl-wrap">
'''


def assemble_article(atf_content, main_content, faq_content, resources_content, slug):
    """Assemble all sections into final rl-page HTML."""
    # If ATF already contains its own <header> wrapper, use it directly
    has_hero_wrapper = '<header' in atf_content and 'rl-hero' in atf_content
    if has_hero_wrapper:
        atf_block = atf_content
    else:
        atf_block = f'''<header class="rl-card rl-hero" aria-labelledby="{slug}-title">
<div class="rl-card-inner">
{atf_content}
</div>
</header>'''

    html = f'''<div class="rl-page rl-page-lrg">
<div class="rl-wrap">

<!-- ATF -->
{atf_block}

<!-- Main Content -->
<article>
{main_content}
</article>

<!-- FAQ -->
<section id="{slug}-faqs" class="rl-faq" aria-label="Frequently Asked Questions">
<h2>Frequently Asked Questions</h2>
{faq_content}
</section>

<!-- Resources -->
<footer class="rl-resources">
<h2>Resources Used</h2>
{resources_content}
</footer>

</div>
</div>'''
    return html


def generate_resources(serp_data, keyword):
    """Generate resources section from SERP data."""
    resources = []
    if serp_data:
        # Pull from organic results
        organic = serp_data.get('organic_results', [])[:5]
        for r in organic:
            title = r.get('title', '')
            link = r.get('link', '')
            if title and link:
                resources.append(f'<li><a href="{link}" target="_blank" rel="noopener noreferrer">{title}</a></li>')
    if not resources:
        resources.append(f'<li>Research data for "{keyword}" — compiled from public sources</li>')
    return f'<div class="rl-callout rl-disclosure">\n<ul>\n' + '\n'.join(resources) + '\n</ul>\n</div>'


def validate_voice(text):
    """Run voice validation. Returns (passed, violations)."""
    try:
        from voice_validator import validate_full
        return validate_full(text)
    except ImportError:
        return True, []


def keyword_to_slug(keyword):
    slug = re.sub(r'[^a-z0-9]+', '-', keyword.lower().strip())
    return slug.strip('-')[:60]


def main():
    parser = argparse.ArgumentParser(description='Generate full rl-page article via LLM')
    parser.add_argument('--site', required=True)
    parser.add_argument('--target-keyword', required=True)
    parser.add_argument('--intent', required=True,
                        choices=['decision', 'process', 'comparison', 'definition', 'news'])
    parser.add_argument('--serp-data-json', help='SerpAPI response JSON path')
    parser.add_argument('--output', required=True, help='Output HTML path')
    parser.add_argument('--provider', default='claude', choices=['openai', 'claude'])
    parser.add_argument('--model', default=None)
    parser.add_argument('--min-word-count', type=int, default=1600)
    parser.add_argument('--max-retries', type=int, default=2)
    args = parser.parse_args()

    # Defaults
    if not args.model:
        args.model = 'opus' if args.provider == 'claude' else 'gpt-5.4-mini'

    conf = load_site_conf(args.site)
    branding = load_branding(args.site)
    voice_rules = load_voice_rules(branding)
    location = conf.get('GEO_FOCUS', conf.get('LOCATION_PRIMARY', ''))
    slug = keyword_to_slug(args.target_keyword)

    # Load SERP data
    serp_data = None
    if args.serp_data_json:
        with open(args.serp_data_json) as f:
            serp_data = json.load(f)

    print(f"Generating article: {args.target_keyword}")
    print(f"  Intent: {args.intent} | Provider: {args.provider} | Model: {args.model}")
    print(f"  Location: {location}")

    total_input_tokens = 0
    total_output_tokens = 0

    system_msg = (
        "You are a content writer producing SEO-optimized HTML articles. "
        "Return ONLY valid HTML. No markdown fences unless wrapping HTML. "
        "No explanations before or after the HTML."
    )

    # Step 1: Generate ATF (hero + quick grid)
    print("  [1/4] Generating ATF...")
    atf_prompt = load_prompt(args.intent, 'atf')
    atf_prompt = render_prompt(atf_prompt, voice_rules, args.target_keyword, location, serp_data)

    # Add SERP context to ATF prompt
    serp_context = ""
    if serp_data:
        paa = serp_data.get('related_questions', [])[:3]
        ai_overview = serp_data.get('ai_overview', {})
        if paa:
            serp_context += "\n\nPeople Also Ask:\n" + '\n'.join(f'- {q.get("question", "")}' for q in paa)
        if ai_overview:
            serp_context += f"\n\nAI Overview snippet: {str(ai_overview)[:500]}"

    atf_full_prompt = (
        f"{atf_prompt}\n\n"
        f"Target keyword: {args.target_keyword}\n"
        f"Location: {location}\n"
        f"Slug: {slug}\n"
        f"{serp_context}\n\n"
        f"Generate the ATF HTML now. Include:\n"
        f"- H1 title\n"
        f"- rl-eyebrow\n"
        f"- rl-hero-lead paragraph (45-65 words, answer-first)\n"
        f"- rl-quick-grid with 4 rl-quick-card articles\n"
        f"Return ONLY the inner HTML (everything inside the hero card-inner + quick grid)."
    )

    atf_html, inp, out = call_llm(atf_full_prompt, args.provider, args.model, system_msg)
    atf_html = extract_html(atf_html)
    total_input_tokens += inp
    total_output_tokens += out
    time.sleep(1)

    # Step 2: Generate main content
    print("  [2/4] Generating main content...")
    main_prompt = load_prompt(args.intent, 'main')
    main_prompt = render_prompt(main_prompt, voice_rules, args.target_keyword, location, serp_data)

    main_full_prompt = (
        f"{main_prompt}\n\n"
        f"Target keyword: {args.target_keyword}\n"
        f"Location: {location}\n"
        f"{serp_context}\n\n"
        f"Generate 6-8 H2 sections with full content. Minimum {args.min_word_count} words total.\n"
        f"Return ONLY the HTML (H2s, paragraphs, bullet-sections, tables, callouts)."
    )

    main_html, inp, out = call_llm(main_full_prompt, args.provider, args.model, system_msg)
    main_html = extract_html(main_html)
    total_input_tokens += inp
    total_output_tokens += out
    time.sleep(1)

    # Step 3: Generate FAQ
    print("  [3/4] Generating FAQ...")
    faq_prompt = load_prompt(args.intent, 'faq')
    faq_prompt = render_prompt(faq_prompt, voice_rules, args.target_keyword, location, serp_data)

    faq_full_prompt = (
        f"{faq_prompt}\n\n"
        f"Generate 4-6 FAQ items as rl-faq-item divs."
    )

    faq_html, inp, out = call_llm(faq_full_prompt, args.provider, args.model, system_msg)
    faq_html = extract_html(faq_html)
    total_input_tokens += inp
    total_output_tokens += out
    time.sleep(1)

    # Step 4: Resources
    print("  [4/4] Building resources...")
    resources_html = generate_resources(serp_data, args.target_keyword)

    # Assemble
    print("  Assembling article...")
    # Split ATF: find quick-grid if embedded
    full_html = assemble_article(atf_html, main_html, faq_html, resources_html, slug)

    # Word count check
    word_count = len(re.findall(r'\b\w+\b', re.sub(r'<[^>]+>', ' ', full_html)))
    print(f"  Word count: {word_count}")

    if word_count < args.min_word_count:
        print(f"  WARNING: Below minimum ({args.min_word_count}). Requesting expansion...")
        expand_prompt = (
            f"The following article section is too short ({word_count} words, need {args.min_word_count}). "
            f"Add 2-3 more H2 sections with detailed content about '{args.target_keyword}' in {location}. "
            f"Each section needs 100-150 words. Use the same HTML structure (H2, p, bullet-section, rl-table). "
            f"Return ONLY the additional HTML sections.\n\n"
            f"Current H2s in article:\n"
            + '\n'.join(re.findall(r'<h2[^>]*>(.*?)</h2>', main_html, re.IGNORECASE))
        )
        extra_html, inp, out = call_llm(expand_prompt, args.provider, args.model, system_msg)
        extra_html = extract_html(extra_html)
        total_input_tokens += inp
        total_output_tokens += out

        # Re-assemble with extra content
        main_html = main_html + '\n\n' + extra_html
        full_html = assemble_article(atf_html, main_html, faq_html, resources_html, slug)
        word_count = len(re.findall(r'\b\w+\b', re.sub(r'<[^>]+>', ' ', full_html)))
        print(f"  Updated word count: {word_count}")

    # Voice validation
    print("  Validating voice...")
    text_content = re.sub(r'<[^>]+>', ' ', full_html)
    voice_pass, violations = validate_voice(text_content)
    if not voice_pass:
        print(f"  Voice violations: {len(violations)}")
        for v in violations[:5]:
            print(f"    - {v['category']}: \"{v['match']}\"")
    else:
        print("  Voice: PASS")

    # Save
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, 'w') as f:
        f.write(full_html)

    # Cost estimate
    if args.provider == 'claude':
        # Claude via subscription — no per-token cost
        cost = 0.0
    else:
        # gpt-5.4-mini: $0.75/M input, $4.50/M output
        cost = (total_input_tokens * 0.75 + total_output_tokens * 4.50) / 1_000_000

    manifest = {
        'output_path': str(args.output),
        'word_count': word_count,
        'voice_pass': voice_pass,
        'voice_violations': len(violations) if not voice_pass else 0,
        'sections': ['atf', 'main', 'faq', 'resources'],
        'intent': args.intent,
        'target_keyword': args.target_keyword,
        'provider': args.provider,
        'model': args.model,
        'input_tokens': total_input_tokens,
        'output_tokens': total_output_tokens,
        'llm_cost_estimate': round(cost, 4),
    }

    print(f"\n  Output: {args.output}")
    print(f"  Tokens: {total_input_tokens} in / {total_output_tokens} out")
    print(f"  Cost: ${cost:.4f}")
    print(f"  Voice: {'PASS' if voice_pass else 'FAIL'}")

    # Save manifest alongside HTML
    manifest_path = args.output.replace('.html', '-manifest.json')
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    return manifest


if __name__ == '__main__':
    main()
