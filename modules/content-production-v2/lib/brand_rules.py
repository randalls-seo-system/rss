"""Per-site brand rules enforcement for LLM prompts and post-generation validation.

Loads BRAND_VOICE_NOTES, COMPETITOR_MENTION_POLICY, PRICE_POLICY,
FORBIDDEN_TERMS, and REQUIRED_TONE from the site config and produces:

1. A formatted BRAND RULES block for injection into every LLM prompt.
2. A list of forbidden terms for post-generation validation.
3. A validation function that checks assembled HTML for violations.
"""

import re
from pathlib import Path


def load_brand_rules_block(config: dict) -> str:
    """Build the BRAND RULES prompt block from site config fields.

    Args:
        config: Site config dict (from load_site_config).

    Returns:
        Formatted string to prepend to LLM prompts.
        Empty string if no brand rules are configured.
    """
    site_name = config.get("SITE_NAME", "")
    brand_voice = config.get("BRAND_VOICE_NOTES", "")
    competitor_policy = config.get("COMPETITOR_MENTION_POLICY", "")
    price_policy = config.get("PRICE_POLICY", "")
    forbidden_raw = config.get("FORBIDDEN_TERMS", "")
    required_tone = config.get("REQUIRED_TONE", "")

    # If no rules configured, return empty (site has no guardrails)
    if not any([brand_voice, competitor_policy, price_policy, forbidden_raw, required_tone]):
        return ""

    never_rules = []
    always_rules = []

    # Competitor policy
    if competitor_policy == "never_recommend":
        never_rules.append(
            "Name, recommend, praise, or positively describe competitor "
            "businesses. Do not list competitors as 'top picks,' 'hidden gems,' "
            "'worth visiting,' or 'recommended.' You may briefly acknowledge "
            "that a competitive market exists, but never name specific competitors."
        )

    # Price policy
    if price_policy == "no_specific_prices":
        never_rules.append(
            "Include specific dollar prices (e.g. '$13.99', '$4 per slice', "
            "'$25 minimum'). Price RANGES are acceptable when necessary "
            "(e.g. 'under $20', '$15 to $35 range'), but never exact prices, "
            "delivery fees, per-item costs, or minimum order amounts."
        )

    # Forbidden terms
    forbidden_list = [t.strip() for t in forbidden_raw.split(",") if t.strip()]
    if forbidden_list:
        terms_str = ", ".join(forbidden_list)
        never_rules.append(
            f"Use any of these forbidden terms anywhere in your output: {terms_str}"
        )

    # Required tone
    if required_tone:
        always_rules.append(required_tone)

    # Brand voice notes
    if brand_voice:
        always_rules.append(brand_voice)

    # Build the block
    lines = [
        "=== BRAND RULES (NON-NEGOTIABLE) ===",
        f"You are writing for {site_name}.",
        "",
    ]

    if never_rules:
        lines.append("NEVER do these things:")
        for rule in never_rules:
            lines.append(f"- {rule}")
        lines.append("")

    if always_rules:
        lines.append("ALWAYS do these things:")
        for rule in always_rules:
            lines.append(f"- {rule}")
        lines.append("")

    lines.append(
        "If your output would violate any of these rules, rewrite the "
        "section to comply before returning it."
    )
    lines.append("=== END BRAND RULES ===")

    return "\n".join(lines)


def get_forbidden_terms(config: dict) -> list[str]:
    """Return the list of forbidden terms from site config.

    Args:
        config: Site config dict.

    Returns:
        List of forbidden term strings (may be empty).
    """
    raw = config.get("FORBIDDEN_TERMS", "")
    return [t.strip() for t in raw.split(",") if t.strip()]


def validate_brand_rules(html: str, config: dict) -> list[str]:
    """Validate assembled HTML against brand rules.

    Returns a list of violation strings. Empty list = clean.
    """
    violations = []

    # 1. Forbidden terms check
    forbidden = get_forbidden_terms(config)
    for term in forbidden:
        pattern = re.compile(re.escape(term), re.IGNORECASE)
        matches = pattern.findall(html)
        if matches:
            # Find context around first match
            match = pattern.search(html)
            start = max(0, match.start() - 40)
            end = min(len(html), match.end() + 40)
            context = html[start:end].replace("\n", " ")
            violations.append(
                f"FORBIDDEN TERM: '{term}' found {len(matches)} time(s). "
                f"Context: ...{context}..."
            )

    # 2. Specific price check (if policy is no_specific_prices)
    price_policy = config.get("PRICE_POLICY", "")
    if price_policy == "no_specific_prices":
        # Match $X, $X.XX, $X,XXX patterns
        price_pattern = re.compile(r'\$\d[\d,]*(?:\.\d{1,2})?')
        price_matches = price_pattern.findall(html)

        # Filter: allow price RANGES (two prices connected by "to", dash,
        # en-dash, em-dash, or ndash/mdash entities)
        # We check each match's surrounding context
        for price in price_matches:
            # Find all occurrences
            for m in re.finditer(re.escape(price), html):
                pos = m.start()
                # Get surrounding context (100 chars each side)
                ctx_start = max(0, pos - 60)
                ctx_end = min(len(html), pos + len(price) + 60)
                context = html[ctx_start:ctx_end]

                # Check if this price is part of a range pattern
                range_patterns = [
                    r'\$\d[\d,]*(?:\.\d{2})?\s*(?:to|–|—|&ndash;|&mdash;|-)\s*\$\d',
                    r'\$\d[\d,]*(?:\.\d{2})?\s+range',
                    r'under\s+\$\d',
                    r'(?:around|about|approximately|roughly|nearly)\s+\$\d',
                ]
                is_range = any(re.search(p, context, re.IGNORECASE) for p in range_patterns)

                if not is_range:
                    clean_ctx = context.replace("\n", " ").strip()
                    violations.append(
                        f"SPECIFIC PRICE: '{price}' (not in a range). "
                        f"Context: ...{clean_ctx}..."
                    )
                    break  # One violation per unique price is enough

    return violations
