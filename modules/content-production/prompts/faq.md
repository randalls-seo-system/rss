# FAQ Section Generation

{{INJECT_BRAND_VOICE}}

## Task

Generate an FAQ section using the People Also Ask questions provided. Each answer must be direct, factual, and locally relevant.

Target keyword: {{TARGET_KEYWORD}}
Location focus: {{LOCATION}}

## PAA Questions to Answer

{{PAA_QUESTIONS}}

## Rules

- Answer each question in 50-100 words
- Lead with the direct answer in the first sentence (≤20 words)
- Follow with 2-3 sentences of supporting context
- Include specific numbers, dates, or place names where applicable
- Reference {{LOCATION}} at least once across all answers
- Do NOT restate the question in the answer
- Do NOT use "In conclusion" or "To summarize"

## HTML Output Format

Return ONLY the FAQ items. Do not include a wrapper div.

```html
<div class="rl-faq-item">
  <h3 class="rl-faq-q">{{Question verbatim from PAA}}</h3>
  <div class="rl-faq-a">
    <p>{{Direct answer, 50-100 words}}</p>
  </div>
</div>
```

Generate one `rl-faq-item` per question. Minimum 4, maximum 6.
If fewer than 4 PAA questions are provided, generate additional relevant questions for the keyword.
