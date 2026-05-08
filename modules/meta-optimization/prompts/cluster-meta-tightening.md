You are tightening a SEO title tag and meta description for one page on {{SITE_NAME}}, a {{BRAND_TONE}} real estate company serving {{LOCATION_PRIMARY}}.

A prior LLM pass generated a proposal that is OUT OF TARGET CHARACTER RANGE. Your job is to revise it to hit the exact targets while preserving the keyword strategy.

PAGE INFORMATION:
- URL: {{URL}}
- Current title: {{CURRENT_TITLE}}
- Dominant intent: {{INTENT}}

KEYWORD CLUSTER:
- Parent query: "{{PARENT_QUERY}}" ({{PARENT_IMPRESSIONS}} impressions, position {{PARENT_POSITION}})
- Top variants:
{{TOP_VARIANTS}}
- Gap queries:
{{GAP_QUERIES}}
- Common modifiers: {{COMMON_MODIFIERS}}

PRIOR PROPOSAL (needs revision):
- Title: "{{V2_TITLE}}" ({{V2_TITLE_LENGTH}} chars)
- Meta: "{{V2_META}}" ({{V2_META_LENGTH}} chars)

ISSUES TO FIX:
{{ISSUES}}

REVISION RULES:

TITLE must be 50-60 characters (hard requirement):
- If too short: add specificity — location ("San Antonio", "TX"), year ("2026"), qualifier ("Guide", "Costs", "Tips"), or brand suffix (" | LRG")
- If too long: drop brand suffix first, then qualifiers, then year. Preserve the parent query phrasing.
- Meaning and keyword coverage must stay the same.

META must be 150-160 characters (hard requirement):
- If too short: add a specific benefit, mention a gap query naturally, or add an implicit CTA verb (See, Get, Find, Compare).
- If too long: tighten filler words, cut from middle sentences, preserve the first sentence and the closing CTA.
- Do NOT pad with generic phrases ("Learn more", "Click here").

Count characters carefully. Spaces count. Punctuation counts.

OUTPUT FORMAT (strict JSON, no markdown fencing):
{"title": "<revised title 50-60 chars>", "meta": "<revised meta 150-160 chars>", "title_length": <int>, "meta_length": <int>, "rationale": "<1-2 sentences on what changed>"}
