#!/usr/bin/env python3
"""Validate rl-page HTML structure for content production QA.

Usage:
    python3 validate-structure.py --html-file article.html --intent decision
    python3 validate-structure.py --html-file article.html --intent process --strict
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("ERROR: beautifulsoup4 required. Install: pip install beautifulsoup4")


def count_words(text):
    return len(re.findall(r'\b\w+\b', text))


def validate(html_path, intent, strict=False):
    with open(html_path) as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')
    checks = []

    # 1. rl-page wrapper
    rl_page = soup.find(class_=re.compile(r'\brl-page\b'))
    checks.append({
        'check': 'rl-page wrapper',
        'passed': rl_page is not None,
    })

    # 2. rl-wrap inside rl-page
    rl_wrap = rl_page.find(class_=re.compile(r'\brl-wrap\b')) if rl_page else None
    checks.append({
        'check': 'rl-wrap inside rl-page',
        'passed': rl_wrap is not None,
    })

    # 3. rl-hero with H1
    rl_hero = soup.find(class_=re.compile(r'\brl-hero\b'))
    hero_h1 = rl_hero.find('h1') if rl_hero else None
    checks.append({
        'check': 'rl-hero with H1',
        'passed': hero_h1 is not None,
    })

    # 4. rl-quick-grid with cards
    grid = soup.find(class_=re.compile(r'\brl-quick-grid\b'))
    cards = grid.find_all(class_=re.compile(r'\brl-quick-card\b')) if grid else []
    min_cards = 2 if intent == 'news' else 4
    checks.append({
        'check': f'rl-quick-grid with >={min_cards} cards',
        'passed': len(cards) >= min_cards,
        'actual': len(cards),
    })

    # 5. rl-faq with items
    faq = soup.find(class_=re.compile(r'\brl-faq\b'))
    faq_items = faq.find_all(class_=re.compile(r'\brl-faq-item\b')) if faq else []
    checks.append({
        'check': 'rl-faq with >=3 items',
        'passed': len(faq_items) >= 3,
        'actual': len(faq_items),
    })

    # 6. H2 count in main content (exclude structural headings)
    structural_h2s = {'frequently asked questions', 'resources used', 'resources'}
    all_h2s = [h for h in soup.find_all('h2')
               if h.get_text().strip().lower() not in structural_h2s]
    checks.append({
        'check': '>=5 H2 sections',
        'passed': len(all_h2s) >= 5,
        'actual': len(all_h2s),
    })

    # 7. H2s in question format (50%+)
    question_h2s = [h for h in all_h2s if h.get_text().strip().endswith('?')]
    pct = (len(question_h2s) / len(all_h2s) * 100) if all_h2s else 0
    checks.append({
        'check': '>=50% H2s in question format',
        'passed': pct >= 50,
        'actual': f'{pct:.0f}% ({len(question_h2s)}/{len(all_h2s)})',
    })

    # 8. Word count
    text = soup.get_text(separator=' ')
    wc = count_words(text)
    checks.append({
        'check': 'word count >= 1600',
        'passed': wc >= 1600,
        'actual': wc,
    })

    # 9. No lrg* class remnants
    lrg_classes = soup.find_all(class_=re.compile(r'\blrg[A-Z]'))
    checks.append({
        'check': 'no lrg* class remnants',
        'passed': len(lrg_classes) == 0,
        'actual': len(lrg_classes),
    })

    # 10. No vln* class remnants
    vln_classes = soup.find_all(class_=re.compile(r'\bvln[A-Z]'))
    checks.append({
        'check': 'no vln* class remnants',
        'passed': len(vln_classes) == 0,
        'actual': len(vln_classes),
    })

    # 11. All <a> tags have href
    links = soup.find_all('a')
    bad_links = [a for a in links if not a.get('href')]
    checks.append({
        'check': 'all <a> have href',
        'passed': len(bad_links) == 0,
        'actual': f'{len(bad_links)} missing',
    })

    # 12. Images have alt text
    imgs = soup.find_all('img')
    bad_imgs = [img for img in imgs if not img.get('alt')]
    checks.append({
        'check': 'all <img> have alt text',
        'passed': len(bad_imgs) == 0 or len(imgs) == 0,
        'actual': f'{len(bad_imgs)} missing' if imgs else 'no images',
    })

    # 13. Resources/footer section
    has_resources = bool(soup.find(class_=re.compile(r'\brl-resources\b'))) or \
                    bool(soup.find('footer'))
    checks.append({
        'check': 'resources/footer section exists',
        'passed': has_resources,
    })

    # Summary
    all_passed = all(c['passed'] for c in checks)
    result = {
        'html_file': str(html_path),
        'intent': intent,
        'word_count': wc,
        'h2_count': len(all_h2s),
        'faq_count': len(faq_items),
        'all_passed': all_passed,
        'checks': checks,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description='Validate rl-page structure')
    parser.add_argument('--html-file', required=True)
    parser.add_argument('--intent', required=True,
                        choices=['decision', 'process', 'comparison', 'definition', 'news'])
    parser.add_argument('--strict', action='store_true',
                        help='Fail on warnings too')
    parser.add_argument('--output-format', default='text', choices=['text', 'json'])
    args = parser.parse_args()

    result = validate(args.html_file, args.intent, args.strict)

    if args.output_format == 'json':
        print(json.dumps(result, indent=2))
    else:
        icon = 'PASS' if result['all_passed'] else 'FAIL'
        print(f"{icon} — {args.html_file}")
        print(f"  Intent: {result['intent']} | Words: {result['word_count']} | "
              f"H2s: {result['h2_count']} | FAQs: {result['faq_count']}")
        for check in result['checks']:
            mark = '+' if check['passed'] else 'X'
            extra = f" (actual: {check['actual']})" if 'actual' in check and not check['passed'] else ''
            print(f"  [{mark}] {check['check']}{extra}")

    sys.exit(0 if result['all_passed'] else 1)


if __name__ == '__main__':
    main()
