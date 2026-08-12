"""prompt_strip.py — Conditional prompt-text removal for unsourced data fields.

When price_range or commute is null, strip prompt language that cues the
LLM to invent numbers. This is removal, not a ban — the model never
sees the concept rather than being told not to use it.
"""

import re


def strip_number_cues(brand_voice: str, vertical_rules: str,
                      strip_price: bool = False,
                      strip_commute: bool = False,
                      ) -> tuple[str, str, list[str]]:
    """Strip price/commute cues from brand voice and vertical rules.

    Returns (cleaned_brand_voice, cleaned_vertical_rules, log_entries).
    """
    log = []

    if strip_price:
        # Brand voice: remove the "Numbers when possible" directive and
        # price-specific examples that instruct the model to use dollar amounts
        lines = brand_voice.split('\n')
        filtered = []
        for line in lines:
            lower = line.lower()
            # Skip lines that instruct price/number usage
            if any(phrase in lower for phrase in [
                'median sale price',
                'real prices',
                'numbers when possible',
                'numbers signal expertise',
                'price range',
                'days on market',
                'inventory levels',
            ]):
                log.append(f"Prompt strip (price): removed brand-voice line: {line.strip()[:60]}")
                continue
            filtered.append(line)
        brand_voice = '\n'.join(filtered)

        # Vertical rules: remove dollar-amount examples
        # Strip lines containing $XXX patterns that serve as examples
        vr_lines = vertical_rules.split('\n')
        vr_filtered = []
        for line in vr_lines:
            if re.search(r'\$\d+K', line) and ('example' in line.lower() or 'wrong' in line.lower() or 'right' in line.lower()):
                log.append(f"Prompt strip (price): removed vertical-rule example: {line.strip()[:60]}")
                continue
            vr_filtered.append(line)
        vertical_rules = '\n'.join(vr_filtered)

    if strip_commute:
        # Brand voice: remove commute-specific directives
        lines = brand_voice.split('\n')
        filtered = []
        for line in lines:
            lower = line.lower()
            if any(phrase in lower for phrase in [
                'average commute',
                'commute time',
            ]):
                log.append(f"Prompt strip (commute): removed brand-voice line: {line.strip()[:60]}")
                continue
            filtered.append(line)
        brand_voice = '\n'.join(filtered)

        # Vertical rules: remove drive-time examples
        vr_lines = vertical_rules.split('\n')
        vr_filtered = []
        for line in vr_lines:
            if re.search(r'\d+\s*minutes?\s+to\s+', line) and ('example' in line.lower() or 'wrong' in line.lower() or 'right' in line.lower()):
                log.append(f"Prompt strip (commute): removed vertical-rule example: {line.strip()[:60]}")
                continue
            vr_filtered.append(line)
        vertical_rules = '\n'.join(vr_filtered)

    if not log:
        log.append("Prompt strip: no changes (price and commute data present)")

    return brand_voice, vertical_rules, log


def strip_serp_prices(serp_context: str) -> str:
    """Remove dollar amounts from SERP context snippets.

    Replaces $XXX patterns with empty string and cleans up artifacts.
    Does not remove the entire snippet — just the price references.
    """
    # Remove $XXX,XXX and $XXXK patterns
    cleaned = re.sub(r'\$[\d,]+K?\+?', '', serp_context)
    # Remove "pricey" / "affordable" / "budget" value-signaling words
    cleaned = re.sub(r'\b(?:pricey|affordable|budget|cheap|expensive)\b', '', cleaned, flags=re.IGNORECASE)
    # Clean up double spaces and orphaned punctuation
    cleaned = re.sub(r'  +', ' ', cleaned)
    cleaned = re.sub(r' +([,.])', r'\1', cleaned)
    return cleaned
