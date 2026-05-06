"""Shared validation logic for brand voice enforcement.

Validates text content against an archetype's forbidden phrases and
required signals. Used by apply-voice-rules.py and any module that
needs inline voice checking.
"""

import re
from pathlib import Path

# Forbidden phrase patterns — grouped by category.
# Each is a tuple of (category, compiled_regex).
FORBIDDEN_PATTERNS = {
    'opening_verbs': [
        r'\b(discover|explore|unlock|dive into|embark on)\s+the\b',
        r'\b(welcome to|step into)\b',
    ],
    'filler_adjectives': [
        r'\bvibrant\s+(communit|cit|neighborhood)',
        r'\b(ideal|dream|perfect)\s+home\b',
        r'\bperfect for you\b',
        r'\bsafe,?\s*family[- ]friendly\b',
        r'\b(comprehensive|ultimate|complete)\s+guide\b',
        r'\bexpert\s+(insights?|tips?)\b',
        r'\b(bustling|charming|picturesque|quaint)\b',
    ],
    'generic_ctas': [
        r'\bget started today\b',
        r'\bfind out more\b',
        r'\blearn about\b',
        r'\bclick here\b',
        r'\bread on\b',
        r'\bcontinue reading\b',
        r'\btake the next step\b',
        r'\bbegin your journey\b',
        r'\bcontact us today\b',
    ],
    'empty_qualifiers': [
        r'\b(amazing|incredible|unbelievable|fantastic)\b',
        r'\b(elevate|transform|revolutionize|streamline)\b',
    ],
}


def load_archetype(name, archetypes_dir=None):
    """Load archetype markdown. Returns the raw text."""
    if archetypes_dir is None:
        archetypes_dir = Path(__file__).resolve().parents[1] / 'archetypes'
    path = Path(archetypes_dir) / f'{name}.md'
    if not path.exists():
        raise FileNotFoundError(f"Archetype not found: {path}")
    return path.read_text()


def validate_text(text, strict=False):
    """Check text against forbidden patterns.

    Returns list of violations: [{'category': str, 'match': str, 'pattern': str}]
    """
    violations = []
    text_lower = text.lower()

    for category, patterns in FORBIDDEN_PATTERNS.items():
        for pat in patterns:
            matches = re.finditer(pat, text_lower)
            for m in matches:
                violations.append({
                    'category': category,
                    'match': m.group(0),
                    'pattern': pat,
                })

    return violations


def check_capitalization(text):
    """Check that Military, Veteran, VA Loan are capitalized correctly.

    Returns list of violations where these words appear lowercase.
    """
    violations = []

    # Check for lowercase 'military' that's not inside a URL or code block
    for m in re.finditer(r'\bmilitary\b', text):
        # Ensure it's not part of a URL or in title case already
        if text[m.start():m.start()+1] == 'm':
            violations.append({
                'category': 'capitalization',
                'match': 'military (should be Military)',
                'position': m.start(),
            })

    for m in re.finditer(r'\bveteran\b', text):
        if text[m.start():m.start()+1] == 'v':
            violations.append({
                'category': 'capitalization',
                'match': 'veteran (should be Veteran)',
                'position': m.start(),
            })

    for m in re.finditer(r'\bva loan\b', text, re.IGNORECASE):
        actual = text[m.start():m.end()]
        if actual != 'VA Loan' and actual != 'VA loan':
            violations.append({
                'category': 'capitalization',
                'match': f'"{actual}" (should be "VA Loan")',
                'position': m.start(),
            })

    return violations


def validate_full(text, check_caps=True):
    """Run all validations. Returns (passed: bool, violations: list)."""
    violations = validate_text(text)
    if check_caps:
        violations.extend(check_capitalization(text))
    return len(violations) == 0, violations
