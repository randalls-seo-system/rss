# Main Content — Definition Intent

{{INJECT_BRAND_VOICE}}

## Task

Generate the main article body for an **educational/definition** article. The user wants to understand a concept.

Target keyword: {{TARGET_KEYWORD}}
Location focus: {{LOCATION}}

## Structure Requirements

- 6-8 H2 sections
- At least 50% of H2s must be phrased as questions
- Each H2 section: open with a direct 1-2 sentence answer (≤30 words), then 50-70 words of supporting context
- Include at least 2 bullet-section blocks
- Include at least 1 table (class `rl-table`) for key facts or terms
- Include at least 1 callout box with a simplified explanation

## H2 Ideas (adapt to keyword)

1. What Is {{Term}} in Simple Terms?
2. How Does {{Term}} Work?
3. Why Does {{Term}} Matter for {{Audience}}?
4. What Are the Different Types of {{Term}}?
5. How Much Does {{Term}} Cost?
6. What Are Common Misconceptions About {{Term}}?
7. How Does {{Term}} Apply in {{Location}}?
8. What Should You Do Next?

## Content Rules

- Lead each section with the direct answer in ≤30 words
- Define jargon immediately after first use
- Use analogies where complex concepts need simplification
- Include local-specific implications for {{LOCATION}}
- Bullet sections: 4-6 items, `<strong>Term:</strong> definition` format
- Tables: use for "key facts at a glance" or "types compared"
- No filler. Every sentence must teach something new.

## HTML Output Format

Return ONLY the HTML between the `<article>` tags. Do not include the article tag itself.
Use these classes:
- `<section class="bullet-section-green">` for key facts/terms
- `<section class="bullet-section-blue">` for related concepts
- `<div class="rl-callout">` for simplified explanations
- `<table class="rl-table">` for fact tables
- `<h2>` for section headings
- Standard `<p>`, `<ul>`, `<li>`, `<strong>`
