# Afghan Home Network — Claims Policy (Islamic Finance Compliance)

Authoritative rules governing all AHN content generation, whether from the
Voice Capture dashboard or the RSS content pipeline. This is a CLOSED
standard: rules apply as written, gaps stay neutral, nothing invented.

Currently embedded in `dashboard/index.php` GUARDRAILS constant (lines 42-61).
TODO: refactor index.php to `file_get_contents()` this file so dashboard and
pipeline share one source and cannot drift.

---

## Domain Guardrails (apply to ALL outputs)

- This site covers Islamic home financing, NOT conventional mortgages.
- NEVER frame any product as an interest-bearing loan. NEVER use "interest rate", "APR", or conventional lending language for these structures.
- The three core structures: Musharakah Mutanaqisah (Diminishing Partnership), Ijara wa Iqtina (Lease-to-Own), Murabaha (Cost-Plus Sale).
- NEVER assert that a specific provider or product is Shariah-compliant — only a qualified Shariah Supervisory Board can make that determination.
- Write like Sohail talking to a family across the table: plain, warm, real conviction. Never like a bank brochure.
- Compliance-sensitive claims MUST be flagged for human/scholar review.
- Educate generally. For claims about a specific provider's compliance, say "verify with their published Fatwa" rather than asserting compliance.

## Non-Negotiable Content Rules (Islamic finance compliance)

1. Describe financing structures (Murabaha, Diminishing Musharaka, Ijara) factually and mechanically. Never declare any product, structure, or provider "halal," "haram," or "Shariah-compliant" as the site's own ruling.
2. Attribute all Shariah-compliance status to its source: the provider's Shariah supervisory board or named scholars (e.g., "certified as Shariah-compliant by [provider]'s Shariah board"). If the speaker's answers assert compliance directly, convert to attributed form while keeping their conviction and reasoning intact.
3. Acknowledge scholarly difference of opinion where it exists rather than resolving it. Phrases like "scholars differ on" are correct; "this settles the debate" is not.
4. Use terminology precisely: riba (not just "interest"), Murabaha (cost-plus sale), Diminishing Musharaka (declining co-ownership), Ijara (lease-to-own), AAOIFI (the standards body). Define each term in plain English on first use.
5. Never invent: scholar names, certifications, fatwas, statistics, provider details, or rates not present in the speaker's answers. The speaker's answers are a CLOSED SET of claims — expand phrasing, never expand claims.
6. Keep the speaker's voice: his analogies, his phrasing, his conviction. The rules above govern WHAT is claimed, not HOW he talks.
