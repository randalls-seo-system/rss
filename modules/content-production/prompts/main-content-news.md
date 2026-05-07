# Main Content — News/Update Intent

{{INJECT_BRAND_VOICE}}

## Task

Generate the main article body for a **time-sensitive news/update** article. The user wants to know what changed and how it affects them.

Target keyword: {{TARGET_KEYWORD}}
Location focus: {{LOCATION}}

## Structure Requirements

- 5-7 H2 sections
- At least 50% of H2s must be phrased as questions
- Each H2 section: open with a direct 1-2 sentence answer (≤30 words), then 50-70 words of supporting context
- Include at least 1 bullet-section block with key changes
- Include at least 1 table (class `rl-table`) showing old vs new values
- Include at least 1 callout box with action items

## H2 Ideas (adapt to keyword)

1. What Changed in {{Month}} {{Year}}?
2. How Does This Affect {{Audience}} in {{Location}}?
3. What Were the Previous Numbers?
4. When Does This Take Effect?
5. What Should You Do Now?
6. Will This Trend Continue?
7. How Does {{Location}} Compare to National Averages?

## Content Rules

- Lead each section with the direct answer in ≤30 words
- Include specific dates: "effective January 1, 2026"
- Include old vs new values in table format
- Reference local impact for {{LOCATION}}
- Bullet sections: use for "key changes" or "action items"
- Callouts: use for "what to do right now" action boxes
- Cite data sources (government, MLS, official reports)

## HTML Output Format

Return ONLY the HTML between the `<article>` tags. Do not include the article tag itself.
Use these classes:
- `<section class="bullet-section-green">` for key changes
- `<section class="bullet-section-blue">` for action items
- `<div class="rl-callout">` for urgent action boxes
- `<table class="rl-table">` for before/after data
- `<h2>` for section headings
- Standard `<p>`, `<ul>`, `<li>`, `<strong>`
