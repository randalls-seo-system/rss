# BLUF (Bottom Line Up Front) — Spec Section 8

You are writing the Bottom Line Up Front section for an article about **{{TARGET_KEYWORD}}**.

{{INJECT_BRAND_VOICE}}

## Inputs

- **Target keyword:** {{TARGET_KEYWORD}}
- **Topic context:** {{TOPIC_CONTEXT}}
- **Friction point:** {{FRICTION_POINT}}
## Output

Produce exactly this HTML structure:

```
<section class="rl-bluf">
  <h2>The Bottom Line Up Front</h2>
  <p><strong>{Lead paragraph: 50-70 words}</strong></p>
  <p>{Body paragraph: 70-100 words}</p>
  <ul>
    <li>{Capstone bullet 1, 12-20 words}</li>
    <li>{Capstone bullet 2, 12-20 words}</li>
    <li>{Capstone bullet 3, 12-20 words}</li>
    <li>{Capstone bullet 4, 12-20 words}</li>
    <li>{Capstone bullet 5, 12-20 words}</li>
  </ul>
</section>
```

## Constraints

- **Lead paragraph:** 50-70 words. The ENTIRE `<p>` is wrapped in `<strong>`. States the central claim about {{TARGET_KEYWORD}} AND identifies the friction point from {{FRICTION_POINT}}.
- **Body paragraph:** 70-100 words. NOT bolded. Provides concrete numbers, edge cases, and named exceptions that support the lead's claim.
- **Exactly 5 capstone bullets.** Not 4, not 6. Each bullet is 12-20 words.
- **Capstone bullets** distill the article's key takeaways into scannable points. Each bullet stands alone as a fact.
- **Do NOT include any links in the BLUF HTML.** No `<a>` tags. Internal linking is handled by a separate post-processing step.
- **Capstone bullets have ZERO inline links.** No `<a>` tags in the `<li>` elements.
- Do NOT repeat the heading "The Bottom Line Up Front" in the body text.
- The BLUF sets up what the article will prove. It is forward-looking, not a recap.

## Anti-patterns

Do NOT produce any of the following:

- Em dashes (use commas, periods, or parentheses instead)
- Filler words: "discover", "explore", "vibrant", "dive into", "let's", "we'll cover"
- "In this article/section we'll..."
- AI-tells: "navigate the complexities", "in today's fast-paced world", "robust", "leverage", "delve into", "unlock", "unveil"
- Emoji
- Markdown code fences in the output
- Links inside capstone bullets
- Body paragraph wrapped in `<strong>` (only the lead is bolded)

Return ONLY the HTML. No markdown fences. No preamble.

<!-- Implements docs/article-spec.md Section 8 -->
