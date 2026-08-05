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

---

## Ratified by Safi (SME) — Closed-Set Qualification Facts

Source: Safi's voice captures (topics 1-3 qualify facets + topic 7 story),
June 2026. These are SOURCE-backed for D2 claims verification. Numbers
Safi stated with confidence are ratified; hedged numbers are marked
TODO-confirm.

### Credit Score

- Minimum: **580+** for Islamic financing (Safi states this consistently across topics)
- Preferred: **620+** for smoother approval (stated in topics 2, 3, 7)
- Ideal: **680+** helps significantly with approval and terms (topic 2)
- "The higher the better" — Safi's framing. No hard ceiling stated.

### Down Payment

- Minimum: **5%** (stated consistently across all qualify responses)
- PMI / mortgage insurance required under 20% (topic 7)
- "The higher the better — 10%, 20%, 30% — it helps with approval and monthly payment" (topic 2)
- Down payment assistance available through some institutions (topic 7)

### Income

- **24 months / 2 years** employment history in the same field required (topics 1, 2, 7)
- W-2, self-employed, and business owners all qualify (topic 2)
- Self-employed: may qualify on **last 1 year** tax return if established business (topic 2)
- Income must be "stable and verified" (consistent across topics)

### DTI (Debt-to-Income Ratio)

- Standard range: **40-45%** (topic 2)
- Can stretch to **49-50%** depending on file strength (topics 2, 7)
- "They could stretch slightly as well, you know, up to 50%, depending on the strength of the file" (topic 2 verbatim)

### Timeline

- Pre-approval: **1-3 days** (topic 3)
- Full process: **30-45 days** (topic 3)
- Clean files with timely documentation: can close **under 30 days** (topic 3)
- TODO-confirm: manual underwriting for self-employed adds time (Safi mentions but doesn't quantify)

### Property Eligibility

- Primary residence and investment property both eligible (topic 2)
- Farm and ranch: **case-by-case** — some eligible, some not (topic 2 — Safi has direct experience with both outcomes)
- Bardominium on farm/ranch: **not eligible** per his experience (topic 2)
- No blanket restriction on property type beyond institutional guidelines

### Who Can Use Islamic Financing

- **Not restricted to Muslim families** — "everyone can use the Islamic financing" (topic 1)
- Requires: US citizen, green card holder, or eligible visa holder (topic 3)
- Safi's stated clientele: primarily Afghan and Muslim families in the US

### Real Examples (Safi's Direct Experience — Assertable)

- $400,000 home purchase: buyer in trucking business (5 years), $90,000 income,
  $60,000 down payment (15%), monthly payment ~$2,500 before homestead exemption (topic 1)
- $300,000 Musharaka example: buyer 20% ($60,000), financier 80% ($240,000) (topic 2)
- Farm/ranch: 10+ acres approved; separate farm/ranch with bardominium denied (topic 2)
- New-build contract where Safi negotiated the profit rate (topic 5 — details in transcript)

### TODO-Confirm (Safi hedged or was imprecise)

- Exact PMI rates for Islamic financing (mentioned but no numbers given)
- Whether all three structures (Musharaka, Ijara, Murabaha) have identical qualification requirements or if they differ by provider
- Whether the 580 minimum applies uniformly or varies by institution
- Self-employed "last 1 year" qualification: is this institution-specific or standard?
