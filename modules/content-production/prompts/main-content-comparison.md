# Main Content — Comparison Intent

{{INJECT_BRAND_VOICE}}

## Task

Generate the main article body for a **head-to-head comparison** article. The user is weighing two specific options.

Target keyword: {{TARGET_KEYWORD}}
Location focus: {{LOCATION}}

## Structure Requirements

- 6-8 H2 sections
- At least 50% of H2s must be phrased as questions
- Each H2 section: open with a direct 1-2 sentence answer (≤30 words), then 50-70 words of supporting context
- Include at least 2 comparison tables (class `rl-table`)
- Include at least 1 bullet-section block per option
- Include a clear verdict section

## H2 Ideas (adapt to keyword)

1. What's the Key Difference Between {{A}} and {{B}}?
2. How Do Costs Compare?
3. Which One Is Better for {{Use Case 1}}?
4. Which One Is Better for {{Use Case 2}}?
5. What Are the Pros and Cons of Each?
6. How Do They Compare in {{Location}}?
7. What Do Buyers/Users Prefer?
8. Our Verdict: {{A}} or {{B}}?

## Content Rules

- Lead each section with the direct answer in ≤30 words
- Use specific numbers for both options side by side
- Tables: minimum 4 rows comparing specific attributes
- Reference local context where applicable
- Bullet sections: use `bullet-section-green` for pros, `bullet-section-blue` for cons
- Verdict must be definitive — name the winner and explain why in one sentence

## HTML Output Format

Return ONLY the HTML between the `<article>` tags. Do not include the article tag itself.
Use these classes:
- `<section class="bullet-section-green">` for pros/advantages
- `<section class="bullet-section-blue">` for cons/limitations
- `<div class="rl-callout">` for verdict/summary boxes
- `<table class="rl-table">` for comparison tables
- `<h2>` for section headings
- Standard `<p>`, `<ul>`, `<li>`, `<strong>`
