# Main Content — Process Intent

{{INJECT_BRAND_VOICE}}

## Task

Generate the main article body for a **how-to/process** article. The user wants step-by-step instructions.

Target keyword: {{TARGET_KEYWORD}}
Location focus: {{LOCATION}}

## Structure Requirements

- 6-8 H2 sections (one per major step + FAQ-style sections)
- At least 50% of H2s must be phrased as questions
- Each H2 section: open with a direct 1-2 sentence answer (≤30 words), then 50-70 words of supporting context
- Include at least 2 bullet-section blocks (class `bullet-section-green` for requirements, `bullet-section-blue` for tips)
- Include at least 1 callout box (class `rl-callout`) for warnings or pro tips
- Number the steps in H2s: "Step 1:", "Step 2:", etc. for the procedural sections

## H2 Ideas (adapt to keyword)

1. What Do You Need Before Starting?
2. Step 1: {{First Action}}
3. Step 2: {{Second Action}}
4. Step 3: {{Third Action}}
5. How Long Does the Process Take?
6. What Are Common Mistakes to Avoid?
7. How Much Does It Cost in {{Location}}?
8. What Happens After You Complete {{Process}}?

## Content Rules

- Lead each section with the direct answer in ≤30 words
- Use specific timelines: "typically takes 3-5 business days"
- Include local-specific details for {{LOCATION}}
- Bullet sections: 4-6 items, `<strong>Label:</strong>` format
- Callouts: use for "Pro tip" or "Watch out" warnings
- No filler. Every sentence must add new information.

## HTML Output Format

Return ONLY the HTML between the `<article>` tags. Do not include the article tag itself.
Use these classes:
- `<section class="bullet-section-green">` for requirements/checklists
- `<section class="bullet-section-blue">` for tips/optional steps
- `<div class="rl-callout">` for callout boxes
- `<table class="rl-table">` for cost/timeline breakdowns
- `<h2>` for section headings
- Standard `<p>`, `<ul>`, `<ol>`, `<li>`, `<strong>`
