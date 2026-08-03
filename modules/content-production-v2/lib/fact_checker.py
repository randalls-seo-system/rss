"""Fact-checker module — extract and verify specific claims from generated HTML.

Extracts checkable claims (proper nouns, numbers, named entities) from
generated content and verifies them against authoritative sources.

Design principles:
- AUTHORITATIVE sources only: gov/district/maps APIs, official HOA sites.
  Never competitor blogs or marketing pages.
- Tiered by consequence:
  HIGH-STAKES (verify): school attendance zones, tax/legal figures,
    HOA fees, named businesses/landmarks, statutory references
  LOW-STAKES (skip): descriptive color, lifestyle characterization
  SUBJECTIVE (human-flag): "best," "top-rated," "up-and-coming"
- Neighborhood official sites are authoritative ONLY for self-evident
  facts (amenities that physically exist, HOA fees, developer info).
  NOT for school quality, safety, values, or commute times.
"""

import re
from dataclasses import dataclass, field
from .tool_utils import eprint


@dataclass
class Claim:
    """A single checkable claim extracted from content."""
    text: str                  # The claim as stated in content
    category: str              # school, business, price, commute, tax, legal, amenity, subjective
    consequence: str           # high, low, human-flag
    source_type: str = ""      # What kind of source should verify this
    verified: bool | None = None   # True=verified, False=wrong, None=unverified
    note: str = ""             # Verification note or correction


@dataclass
class FactCheckReport:
    """Report from a fact-check run."""
    neighborhood: str
    city: str
    total_claims: int = 0
    verified: int = 0
    flagged_for_human: int = 0
    wrong: int = 0
    skipped_low_stakes: int = 0
    claims: list = field(default_factory=list)


# ── Claim extraction patterns ──

# School names: "X Elementary", "X Middle School", "X High School", "X ISD"
_SCHOOL_PATTERN = re.compile(
    r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+'
    r'(?:Elementary|Middle\s+School|High\s+School|ISD|Independent\s+School\s+District))\b'
)

# Specific dollar amounts: $NNN,NNN or $NNNk
_PRICE_PATTERN = re.compile(r'\$[\d,]+(?:\.\d{2})?(?:\s*(?:per|/)\s*\w+)?')

# Percentage figures
_PERCENT_PATTERN = re.compile(r'[\d.]+%')

# Named businesses/landmarks: sequences of 2+ capitalized words not matching schools
_PROPER_NOUN_PATTERN = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b')

# Commute time claims: "NN minutes", "NN-minute"
_COMMUTE_PATTERN = re.compile(r'(\d+)\s*(?:to\s+(\d+)\s*)?(?:minutes?|min)\b', re.IGNORECASE)

# Statutory references
_STATUTE_PATTERN = re.compile(
    r'(?:Section|§|Code)\s+[\d.]+|'
    r'(?:Texas|TX)\s+(?:Property|Tax|Family)\s+Code|'
    r'(?:HB|SB)\s+\d+',
    re.IGNORECASE
)

# "Opened YYYY", "built in YYYY", "established YYYY"
_YEAR_CLAIM_PATTERN = re.compile(
    r'(?:opened|built|established|founded|constructed)\s+(?:in\s+)?(\d{4})',
    re.IGNORECASE
)

# ZIP codes
_ZIP_PATTERN = re.compile(r'\b(78\d{3})\b')

# Volatile market stat indicators (should have been softened by durable-phrasing rules)
_VOLATILE_INDICATORS = [
    (re.compile(r'\$\d{3},\d{3}\s+median', re.I), "Hard-coded median price"),
    (re.compile(r'\d+\s+days?\s+on\s+market', re.I), "Hard-coded DOM"),
    (re.compile(r'\d+/10\b'), "Hard-coded rating score"),
    (re.compile(r'population\s+[\d,]+', re.I), "Hard-coded population"),
    (re.compile(r'[\d.]+%\s+(?:annual\s+)?appreciation', re.I), "Hard-coded appreciation"),
]

# Words that mark subjective claims
_SUBJECTIVE_MARKERS = [
    "best", "top-rated", "nicest", "most desirable", "premier",
    "up-and-coming", "hidden gem", "safest", "most prestigious",
]


def extract_claims(html: str, neighborhood: str, city: str) -> list[Claim]:
    """Extract all checkable claims from generated HTML.

    Returns a list of Claim objects categorized by type and consequence level.
    """
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()
    claims = []
    seen = set()

    def _add(claim_text, category, consequence, source_type=""):
        key = (claim_text.strip().lower(), category)
        if key not in seen:
            seen.add(key)
            claims.append(Claim(
                text=claim_text.strip(),
                category=category,
                consequence=consequence,
                source_type=source_type,
            ))

    nb_lower = neighborhood.lower()
    city_lower = city.lower()

    # Schools — distinguish "serves this neighborhood" from comparison mentions
    # Strip comparison table content to avoid flagging other neighborhoods' ISDs
    comparison_text = ""
    table_match = re.search(r'<table[^>]*>.*?</table>', html, re.DOTALL)
    if table_match:
        comparison_text = re.sub(r'<[^>]+>', ' ', table_match.group()).lower()

    for m in _SCHOOL_PATTERN.finditer(text):
        name = m.group(1)
        if name.lower() not in (nb_lower, city_lower):
            # Check if this school/ISD appears ONLY in comparison table context
            name_lower = name.lower()
            in_comparison = (name_lower in comparison_text and
                             name_lower not in neighborhood.lower() and
                             text.lower().count(name_lower) <= comparison_text.count(name_lower) + 1)
            if in_comparison:
                _add(name, "school_comparison", "low", "comparison context — skip verification")
            else:
                _add(name, "school", "high", "district boundary tool / TEA")

    # Statutory references
    for m in _STATUTE_PATTERN.finditer(text):
        _add(m.group(), "legal", "high", "state code / official gazette")

    # Year claims (opened, built, etc.)
    for m in _YEAR_CLAIM_PATTERN.finditer(text):
        context_start = max(0, m.start() - 80)
        context = text[context_start:m.end()]
        # Extract the entity name (proper noun sequence before the verb)
        entity_match = re.search(
            r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,4})\s+'
            r'(?:opened|built|established|founded|constructed)',
            context, re.IGNORECASE
        )
        entity_name = entity_match.group(1) if entity_match else ""
        year = m.group(1)
        claim_text = f"{entity_name} {'opened' if 'open' in context.lower() else 'founded'} {year}" if entity_name else context.strip()
        _add(claim_text, "year", "high", "official records / Wikipedia")

    # ZIP codes
    for m in _ZIP_PATTERN.finditer(text):
        _add(f"ZIP {m.group(1)}", "geography", "high", "USPS / county records")

    # Volatile market stats that slipped through durable-phrasing rules
    for pattern, label in _VOLATILE_INDICATORS:
        for m in pattern.finditer(text):
            _add(f"{label}: {m.group()}", "volatile", "human-flag",
                 "consider softening to durable phrasing")

    # Named businesses/landmarks (proper nouns not matching schools or the neighborhood)
    # Strip structural HTML that contains non-claim text: headings, table cells,
    # FAQ summaries, navigation, card labels, callout labels, scorecard values.
    structural_tags = (
        r'h[1-6]|th|td|summary|nav|header|footer|'
        r'div\s+class="[^"]*(?:sc-label|sc-val|m-label|m-val|nh-sec-kicker|'
        r'nh-rank-tagline|pb-name|ph2|nh-qs)[^"]*"'
    )
    prose_only = re.sub(
        rf'<(?:{structural_tags})[^>]*>.*?</(?:h[1-6]|th|td|summary|nav|header|footer|div)>',
        ' ', html, flags=re.DOTALL
    )
    prose_text = re.sub(r'<[^>]+>', ' ', prose_only)
    prose_text = re.sub(r'\s+', ' ', prose_text).strip()

    exclude_lower = {nb_lower, city_lower, "san antonio", "texas", "united states",
                     "north east", "bexar county", "travis county", "hill country"}
    # Noise patterns: non-entity phrases that regex mistakes for proper nouns
    noise_phrases = {
        'the bottom', 'the best', 'what is', 'how much', 'who qualifies',
        'guide stone', 'numbers property', 'asked first', 'category what',
        'available key', 'middle schools', 'private schools', 'youth activities',
        'family retail', 'where stone', 'other san', 'most stone', 'is stone',
        'does stone', 'file guidance', 'approval watchpoint', 'downtown key',
        'frequently asked', 'common questions', 'keep exploring',
        'parks stone', 'elementary schools', 'schools multiple', 'schools faith',
        'panther springs park playgrounds',
    }
    for m in _PROPER_NOUN_PATTERN.finditer(prose_text):
        name = m.group(1)
        name_l = name.lower()
        if (name_l not in exclude_lower and
            not _SCHOOL_PATTERN.match(name) and
            len(name) > 8 and
            not any(n in name_l for n in noise_phrases)):
            _add(name, "business_landmark", "high",
                 "Google Maps / business directory")

    # Subjective claims
    for marker in _SUBJECTIVE_MARKERS:
        idx = text.lower().find(marker)
        while idx != -1:
            context_start = max(0, idx - 30)
            context_end = min(len(text), idx + len(marker) + 30)
            context = text[context_start:context_end].strip()
            _add(context, "subjective", "human-flag", "editorial judgment")
            idx = text.lower().find(marker, idx + 1)

    # Specific dollar amounts in authoritative context (tax rates, HOA, loan limits)
    auth_context_words = ["tax", "exemption", "hoa", "dues", "fee", "limit",
                          "rate", "assessment", "deduction"]
    for m in _PRICE_PATTERN.finditer(text):
        surrounding = text[max(0, m.start()-40):m.end()+40].lower()
        if any(w in surrounding for w in auth_context_words):
            _add(m.group(), "financial_auth", "high",
                 "county assessor / HOA docs / federal register")

    return claims


def run_fact_check(
    html: str,
    neighborhood: str,
    city: str,
) -> FactCheckReport:
    """Run fact-check on generated HTML. Extract claims, categorize, report.

    This is the EXTRACTION + CATEGORIZATION step. Actual verification
    against external sources (NEISD boundary tool, Google Maps API, etc.)
    is flagged for human review with the specific source to check.

    The module does NOT call external APIs — it produces a structured
    checklist that a human (or future API integration) uses to verify.
    """
    report = FactCheckReport(neighborhood=neighborhood, city=city)
    claims = extract_claims(html, neighborhood, city)
    report.total_claims = len(claims)
    report.claims = claims

    for claim in claims:
        if claim.consequence == "high":
            claim.verified = None  # Needs verification
            report.flagged_for_human += 1
        elif claim.consequence == "human-flag":
            claim.verified = None
            report.flagged_for_human += 1
        else:
            report.skipped_low_stakes += 1

    return report


def format_fact_check_report(report: FactCheckReport) -> str:
    """Format the fact-check report as a human-readable checklist."""
    lines = [
        f"FACT-CHECK REPORT — {report.neighborhood}, {report.city}",
        f"{'=' * 60}",
        f"Total claims extracted: {report.total_claims}",
        f"  High-stakes (verify before publish): {report.flagged_for_human}",
        f"  Low-stakes (skipped): {report.skipped_low_stakes}",
        "",
    ]

    # Group by category
    by_cat = {}
    for c in report.claims:
        by_cat.setdefault(c.category, []).append(c)

    category_labels = {
        "school": "SCHOOLS (verify against district boundary tool)",
        "legal": "LEGAL/STATUTORY (verify against official code)",
        "year": "DATES/YEARS (verify against official records)",
        "geography": "ZIP CODES (verify against USPS/county)",
        "financial_auth": "FINANCIAL — AUTHORITATIVE (verify against county/HOA/federal)",
        "volatile": "VOLATILE STATS — SHOULD BE SOFTENED (durable phrasing check)",
        "business_landmark": "BUSINESSES/LANDMARKS (verify existence via Google Maps)",
        "subjective": "SUBJECTIVE CLAIMS (editorial judgment — human review)",
    }

    for cat, label in category_labels.items():
        items = by_cat.get(cat, [])
        if not items:
            continue
        lines.append(f"\n{label}")
        lines.append(f"{'─' * 60}")
        for c in items:
            status = "☐ VERIFY" if c.consequence == "high" else "⚠ FLAG"
            lines.append(f"  [{status}] {c.text}")
            if c.source_type:
                lines.append(f"           Source: {c.source_type}")

    lines.append(f"\n{'=' * 60}")
    lines.append("Review each ☐ VERIFY item against the listed source.")
    lines.append("Volatile stats (⚠) should be softened to durable phrasing.")
    lines.append("Subjective claims (⚠) need editorial judgment, not deletion.")

    return "\n".join(lines)
