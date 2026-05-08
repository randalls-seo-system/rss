# ATF Quick-Card — Spec Section 6

You are writing ONE quick-card for an article about **{{TARGET_KEYWORD}}**.

{{INJECT_BRAND_VOICE}}

## Inputs

- **Card role:** {{CARD_ROLE}}
- **H3 pattern:** {{H3_PATTERN}}
- **Bullet label hints:** {{BULLET_LABEL_HINTS}}
- **Target keyword:** {{TARGET_KEYWORD}}
- **Topic context for this card's subtopic:** {{TOPIC_CONTEXT}}

## Output

Produce exactly this HTML structure:

```
<article class="rl-quick-card">
  <h3>{Card title — derived from H3_PATTERN, rewritten if SERP context suggests a more natural label}</h3>
  <ul>
    <li><strong>{Bullet label 1}:</strong> {Bullet content, 14-30 words}</li>
    <li><strong>{Bullet label 2}:</strong> {Bullet content, 14-30 words}</li>
    <li><strong>{Bullet label 3}:</strong> {Bullet content, 14-30 words}</li>
    <li><strong>{Bullet label 4 — synthesis}:</strong> {Synthesis content, 18-35 words}</li>
  </ul>
</article>
```

## Constraints

- **Exactly 4 bullets.** Not 3, not 5.
- The **H3 card title** is a subtopic name derived from {{H3_PATTERN}}. Substitute template variables with article-specific values. You MAY rewrite the title if SERP context produces a more natural, specific label, but it must remain a subtopic name.
- **Bullet labels** are 1-4 words each, end in a colon, wrapped in `<strong>`. Each label describes the bullet's specific content.
- **Bullets 1-3:** 14-30 words each.
- **Bullet 4 is the synthesis bullet:** 18-35 words. Usually contains a concrete number, threshold, break-even point, or consequence-rule that ties the card together. Use synthesis-flavored labels like "Bottom line:", "Break-even:", "Worth noting:", "Main takeaway:".
- **Bullet labels** are unique within the card. No two labels should be identical or near-identical.
- Use the {{BULLET_LABEL_HINTS}} as starting points, but adapt them to the actual content. The hints are suggestions, not mandatory text.
- ZERO inline links. No `<a>` tags anywhere in the output.
- Prefer concrete numbers over vague language. "$14,450 on a $400,000 loan" beats "a significant amount."

## Anti-patterns

Do NOT produce any of the following:

- **Card title as a generic intent label:** "Best for", "Key advantage", "Watch out", "Pros and cons", "Key benefit", "Main risk", "Top pick" are all banned as card titles. The title must be a specific subtopic name.
- **Identical or near-identical bullet labels** within the same card.
- Em dashes (use commas, periods, or parentheses instead)
- Filler words: "discover", "explore", "vibrant", "dive into", "let's", "we'll cover"
- AI-tells: "navigate the complexities", "in today's fast-paced world", "robust", "leverage", "delve into", "unlock", "unveil"
- Emoji
- Markdown code fences in the output

Return ONLY the HTML. No markdown fences. No preamble.

<!-- Implements docs/article-spec.md Section 6 -->
