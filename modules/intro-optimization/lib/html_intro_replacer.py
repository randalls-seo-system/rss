"""Surgical intro replacement in WP post_content HTML.

Identifies the intro section (everything between the hero header and first
body H2) and replaces it without touching anything below.
"""

from bs4 import BeautifulSoup, NavigableString
import re


def find_intro_boundary(soup):
    """Return the first H2 element in the content body (not inside the hero).

    The intro is defined as all content between the opening wrapper and
    this H2.  If no H2 exists, fall back to the first .rl-section or
    .vlnSection element.
    """
    # Skip H2s that are inside Quick Answers or hero blocks
    hero_classes = {'rl-hero', 'rl-quick', 'rl-quick-head', 'vlnHero',
                    'vlnHero-quick', 'vlnHero-quickHead', 'lrgHero',
                    'lrgHero-quick', 'lrgQuick'}

    for h2 in soup.find_all('h2'):
        inside_hero = False
        for parent in h2.parents:
            if parent.get('class'):
                if hero_classes & set(parent.get('class', [])):
                    inside_hero = True
                    break
            if parent.name == 'header':
                inside_hero = True
                break
        if not inside_hero:
            return h2

    # Fallback: first section card
    section = soup.find(class_=re.compile(r'rl-section|vlnSection|lrgSection'))
    return section


def extract_intro(html):
    """Extract the intro section from post_content HTML.

    Returns (intro_html, intro_text, paragraph_count, word_count,
             has_disclaimer, has_eyebrow).
    """
    soup = BeautifulSoup(html, 'html.parser')
    boundary = find_intro_boundary(soup)

    if not boundary:
        return '', '', 0, 0, False, False

    # Collect intro paragraphs.
    # LRG structure: intro <p> tags live INSIDE the hero <header>.
    # VALN structure: intro <p> tags are siblings AFTER the hero.
    # Handle both.
    intro_parts = []
    hero = soup.find(class_=re.compile(r'rl-hero|vlnHero|lrgHero'))
    if not hero:
        hero = soup.find('header')

    if hero:
        # Strategy A: look for <p> tags inside the hero (LRG pattern)
        # Intro = all <p> children between the title (h1/h2) and first
        # non-<p> block (CTAs, quick-answers, etc.)
        # If no title exists, collect all leading <p> tags.
        title_el = hero.find(re.compile(r'^h[12]$'))
        found_title = title_el is None  # if no title, start collecting immediately
        for child in hero.children:
            if not hasattr(child, 'name') or not child.name:
                continue
            if child == title_el:
                found_title = True
                continue
            if not found_title:
                continue
            # Once past title (or from start if no title), collect <p> tags
            if child.name == 'p':
                intro_parts.append(child)
            else:
                # Hit a non-<p> element (CTAs div, section, etc.) — stop
                break

        # Strategy B: if no <p> tags found inside hero, try siblings after hero
        if not intro_parts:
            current = hero.next_sibling
            while current and current != boundary:
                if hasattr(current, 'name') and current.name:
                    cls = ' '.join(current.get('class', []))
                    if re.search(r'rl-section|vlnSection|lrgSection', cls):
                        break
                    intro_parts.append(current)
                current = current.next_sibling
    else:
        # No hero — collect everything before boundary
        for child in soup.children:
            if child == boundary:
                break
            if hasattr(child, 'name') and child.name:
                intro_parts.append(child)

    intro_html = '\n'.join(str(p) for p in intro_parts)
    intro_text = ' '.join(p.get_text(strip=True) for p in intro_parts)
    para_count = sum(1 for p in intro_parts if getattr(p, 'name', '') == 'p')
    word_count = len(intro_text.split())

    disclaimer_patterns = [
        r'not\s+(legal|financial)\s+advice',
        r'consult\s+(a\s+)?lender',
        r'does\s+not\s+constitute',
        r'for\s+informational\s+purposes',
    ]
    has_disclaimer = bool(re.search('|'.join(disclaimer_patterns),
                                     intro_text, re.IGNORECASE))

    eyebrow_classes = {'rl-eyebrow', 'rl-meta', 'vlnEyebrow', 'vlnMeta'}
    has_eyebrow = any(
        eyebrow_classes & set(p.get('class', []))
        for p in intro_parts if hasattr(p, 'get')
    )

    return intro_html, intro_text, para_count, word_count, has_disclaimer, has_eyebrow


def replace_intro(html, new_eyebrow, new_intro, new_disclaimer_callout=''):
    """Replace the intro section in post_content with new content.

    Preserves everything from the first H2 onward.  Returns the full
    modified HTML string.
    """
    soup = BeautifulSoup(html, 'html.parser')
    boundary = find_intro_boundary(soup)

    if not boundary:
        return html  # no boundary found, return unchanged

    hero = soup.find(class_=re.compile(r'rl-hero|vlnHero|lrgHero'))
    if not hero:
        hero = soup.find('header')

    if not hero:
        return html  # can't find hero, return unchanged

    # Remove old intro paragraphs.
    # Same dual strategy as extract: check inside hero first, then siblings.
    to_remove = []
    title_el = hero.find(re.compile(r'^h[12]$'))

    if title_el:
        # Strategy A: remove <p> tags inside hero after the title
        found_title = False
        for child in list(hero.children):
            if child == title_el:
                found_title = True
                continue
            if not found_title:
                continue
            if hasattr(child, 'name') and child.name == 'p':
                to_remove.append(child)
            elif hasattr(child, 'name') and child.name:
                break  # hit non-<p> (CTAs, quick, etc.)

    if not to_remove:
        # Strategy B: siblings after hero
        current = hero.next_sibling
        while current and current != boundary:
            nxt = current.next_sibling
            if hasattr(current, 'get'):
                cls = ' '.join(current.get('class', []))
                if re.search(r'rl-section|vlnSection|lrgSection', cls):
                    break
            to_remove.append(current)
            current = nxt

    for el in to_remove:
        el.extract()

    # Build new intro elements
    new_parts = []

    if new_eyebrow.strip():
        eyebrow_tag = soup.new_tag('p', **{'class': 'rl-meta'})
        eyebrow_tag.string = new_eyebrow.strip()
        new_parts.append(eyebrow_tag)

    if new_intro.strip():
        intro_tag = soup.new_tag('p')
        intro_tag.append(BeautifulSoup(new_intro.strip(), 'html.parser'))
        new_parts.append(intro_tag)

    if new_disclaimer_callout.strip():
        callout_tag = soup.new_tag('div', **{'class': 'rl-callout rl-callout--warn'})
        callout_p = soup.new_tag('p')
        callout_p.string = new_disclaimer_callout.strip()
        callout_tag.append(callout_p)
        new_parts.append(callout_tag)

    # Insert new parts after title inside hero (LRG) or after hero (VALN)
    if title_el and title_el.parent == hero:
        insert_point = title_el
    else:
        insert_point = hero
    for part in new_parts:
        insert_point.insert_after(part)
        insert_point = part

    return str(soup)
