# LRG — Realtor Archetype Applied

## Base Archetype
`modules/brand-voice/archetypes/realtor.md`

## Site Config (branding section)
```ini
[branding]
archetype = realtor
market_primary = San Antonio
markets_secondary = Austin, Killeen, Central Texas
broker_name = Levi Rodgers
brand_name = LRG
brand_suffix_short = LRG
brand_suffix_long = Levi Rodgers Real Estate Group
audience_primary = homebuyers and homesellers in San Antonio, Austin, and Central Texas
audience_secondary = Military families and Veterans
specialties = Military and Veteran relocations, first-time buyers, San Antonio neighborhoods, Central Texas property taxes
```

## Rendered Prompt (after variable substitution)

The `{{MARKET_PRIMARY}}` becomes "San Antonio", `{{SPECIALTIES}}` becomes the full specialties string, etc. The rendered voice section gets injected at `{{INJECT_BRAND_VOICE}}` in any module's prompt template.

## Sample LLM Output — PASSES Voice Validation

Input page: "Is San Antonio a Good Place to Live?"
Parent query: "is san antonio a good place to live" (2,400 impressions, position 8.2)

```json
{
  "title": "Is San Antonio a Good Place to Live? Pros, Cons & 2026 Costs | LRG",
  "meta": "San Antonio ranks among the most affordable major Texas cities with median homes at $285K and no state income tax. See the real trade-offs by neighborhood, commute, and school district.",
  "title_length": 63,
  "meta_length": 159,
  "captures_parent": true,
  "captures_variants": ["san antonio pros and cons", "living in san antonio"],
  "captures_gaps": ["cost of living san antonio"],
  "rationale": "Led with the parent query verbatim since it's already natural language. Added specific price point and tax advantage as differentiators. Meta ends with implicit CTA verb 'See'."
}
```

Voice validation: **PASS** (0 violations)

## Sample LLM Output — FAILS Voice Validation

Same page, hypothetical bad output:

```json
{
  "title": "Discover the Best Reasons to Live in Vibrant San Antonio | LRG",
  "meta": "Explore our comprehensive guide to living in San Antonio. Get expert insights on neighborhoods, costs, and lifestyle. Find your ideal home in this charming Texas city today!",
  "title_length": 62,
  "meta_length": 162,
  "captures_parent": false,
  "rationale": "Highlighted the city's appeal."
}
```

Voice validation: **FAIL** (6 violations)
- title: opening_verbs ("discover the")
- title: filler_adjectives ("vibrant")
- meta: opening_verbs ("explore")
- meta: filler_adjectives ("comprehensive guide")
- meta: filler_adjectives ("expert insights")
- meta: generic_ctas ("find your ideal home")

## Retry Pattern

When voice validation fails, the system appends to the prompt:

```
PREVIOUS ATTEMPT FAILED VALIDATION: title: opening_verbs (discover the),
title: filler_adjectives (vibrant), meta: opening_verbs (explore),
meta: filler_adjectives (comprehensive guide), meta: filler_adjectives
(expert insights), meta: generic_ctas (find your ideal home). Fix these issues.
```

The LLM gets one retry. If it fails again, the row is flagged with `status=voice_warn` for human review.

## Integration Points

1. `render-prompt.py` injects voice rules into any module's prompt
2. `apply-voice-rules.py` validates any CSV of LLM output
3. `generate-meta-proposals.py` does both automatically when [branding] is configured
