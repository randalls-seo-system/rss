You are writing a SEO title tag and meta description for one page on {{SITE_NAME}}, a {{BRAND_TONE}} real estate company serving {{LOCATION_PRIMARY}}.

The page is currently underperforming in click-through rate despite ranking for multiple keywords. Your job is to write a title and meta description that captures the full keyword cluster while reading naturally to humans.

PAGE INFORMATION:
- URL: {{URL}}
- Current title: {{CURRENT_TITLE}}
- Current meta: {{CURRENT_META}}
- Dominant intent: {{INTENT}}

KEYWORD CLUSTER (from Google Search Console, last 90 days):
- Parent query: "{{PARENT_QUERY}}" ({{PARENT_IMPRESSIONS}} impressions, position {{PARENT_POSITION}})
- Top variants users search:
{{TOP_VARIANTS}}
- Gap queries (high impressions, currently positions 11-30):
{{GAP_QUERIES}}
- Common modifiers users add: {{COMMON_MODIFIERS}}

WRITING RULES:

Title (50-60 characters):
1. Lead with the dominant phrase users search (parent query or its closest natural form)
2. Include 1-2 specific signals: year (if relevant), location (if local intent), or qualifier (Guide, Cost, vs)
3. Add brand suffix " | LRG" only if room (50-60 char total)
4. Front-load the keyword (first 30 chars matter most for SERP truncation)
5. Write for humans first, search engines second
6. Do NOT copy the query verbatim with quotes or operators
7. Do NOT stack the year twice ("2026" once is enough)

Meta description (150-160 characters):
1. First sentence answers the search intent in plain language
2. Second sentence addresses a specific concern, modifier, or gap query naturally
3. Use active voice
4. Include one specific benefit or differentiator (real numbers, local expertise, 2026 data, etc.)
5. End with implicit CTA verb (See, Get, Find, Compare, Read)
6. Avoid: "Click here", "Learn more", "Read more", "In this article"
7. Do NOT mechanically list keywords. Write as a person describing the page to a friend.

QUALITY CHECK before responding:
- Would I click this title in a search results page?
- Does the meta tell me what is specifically inside, or could it apply to any article?
- Is anything repeated awkwardly (year twice, location stacked, query phrasing duplicated)?
- Does it read naturally when spoken aloud?

OUTPUT FORMAT (strict JSON, no markdown fencing):
{"title": "<your title 50-60 chars>", "meta": "<your meta 150-160 chars>", "title_length": <int>, "meta_length": <int>, "captures_parent": true, "captures_variants": ["<variant1>", "<variant2>"], "captures_gaps": ["<gap1>"], "rationale": "<2-3 sentence explanation>"}
