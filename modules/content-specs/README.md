# Content Specs Module

Content production template library for client onboarding. NOT deployed to servers — these are customized per client and stored in `clients/<slug>/content-specs/`.

## Templates

| Template | Purpose |
|----------|---------|
| voice-guide-template.md | Brand voice definition (tone, vocabulary, do/don't) |
| qa-checklist-template.md | 50+ pass/fail checks for content QA |
| linking-policy-template.md | Internal linking rules, cluster map, constraints |
| article-structures/guide.md | Longform educational content structure |
| article-structures/comparison.md | X vs Y article structure |
| article-structures/process.md | Step-by-step / how-to structure |
| article-structures/calculator.md | Tool-supported article structure |

## Onboarding Usage

During `new-client.sh` onboarding, these templates are copied to `clients/<slug>/content-specs/` with client-specific values filled in where known, and `{{PLACEHOLDER}}` markers left for manual customization.

## Customization Variables

### Voice Guide
- `{{CLIENT_NAME}}` — client business name
- `{{INDUSTRY_ROLE}}` — "mortgage broker", "real estate agent", "financial advisor"
- `{{CASE_NOUN_PLURAL}}` — "loan files", "listings", "client portfolios"
- `{{AUDIENCE_NOUN}}` — "borrower", "buyer", "investor"
- `{{DOMAIN_SPECIFIC_FRICTION_POINTS}}` — industry-specific focus areas
- `{{SIGNATURE_LINE_1/2}}` — sparingly-used expert phrases
- `{{CALLOUT_TITLE_1-4}}` — approved callout box titles
- `{{FORBIDDEN_PHRASE_1/2}}` — phrases that must never appear

### QA Checklist
- `{{PROPER_NOUN_1/2}}` — words that must always be capitalized

### Linking Policy
- `{{CLUSTER_1-3_NAME}}` — topic cluster names
- `{{CLUSTER_1-3_PAGES}}` — pages in each cluster

## Source

Adapted from VA Loan Network's production content system:
- matt-forward-compact-v1.4.txt (voice guide)
- qa-checklist.txt (QA checks)
- internal-linking-policy.md (linking rules)
- CLAUDE.md article structure specs
