# Main Content — Decision Intent

{{INJECT_BRAND_VOICE}}

## Task

Generate the main article body for a **decision/ranking** article. The user is choosing the best option from a set.

Target keyword: {{TARGET_KEYWORD}}
Location focus: {{LOCATION}}

## Structure Requirements

- 6-8 H2 sections
- At least 50% of H2s must be phrased as questions
- Each H2 section: open with a direct 1-2 sentence answer (≤30 words), then 50-70 words of supporting context
- Include at least 2 bullet-section blocks (use class `bullet-section-green` or `bullet-section-blue`)
- Include at least 1 comparison table (class `rl-table`)
- Include at least 1 callout box (class `rl-callout`)

## H2 Ideas (adapt to keyword)

1. What Makes {{Topic}} the Best Choice?
2. How Does {{Option A}} Compare to {{Option B}}?
3. What Are the Pros and Cons of {{Topic}}?
4. Who Benefits Most from {{Topic}}?
5. What Should You Watch Out For?
6. How Much Does {{Topic}} Cost?
7. What Do Local Experts Say About {{Topic}}?
8. Is {{Topic}} Worth It in {{Year}}?

## Content Rules

- Lead each section with the direct answer in ≤30 words
- Use specific numbers: prices, percentages, distances, dates
- Reference specific place names relevant to {{LOCATION}}
- No filler. Every sentence must add new information.
- Tables: use for side-by-side comparisons (≥3 rows, ≥3 columns)
- Bullet sections: 4-6 items each, `<strong>Label:</strong>` format

## HTML Output Format

Return ONLY the HTML between the `<article>` tags. Do not include the article tag itself.
Use these classes:
- `<section class="bullet-section-green">` with `<ul>` inside
- `<div class="rl-callout">` for callout boxes
- `<table class="rl-table">` for comparison tables
- `<h2>` for section headings (no class needed)
- Standard `<p>`, `<ul>`, `<li>`, `<strong>`
