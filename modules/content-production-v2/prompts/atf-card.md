# ATF Quick-Card — Spec Section 6

You are writing ONE quick-card for an article about **{{TARGET_KEYWORD}}**.

{{INJECT_BRAND_VOICE}}

## Inputs

- **Card role:** {{CARD_ROLE}}
- **H3 pattern:** {{H3_PATTERN}}
- **Bullet label hints:** {{BULLET_LABEL_HINTS}}
- **Target keyword:** {{TARGET_KEYWORD}}
- **Topic context for this card's subtopic:** {{TOPIC_CONTEXT}}
- **Synthesis bullets from prior cards (avoid repeating):** {{PRIOR_CARDS_SYNTHESIS}}

## Output

Produce exactly this HTML structure:

```
<article class="rl-quick-card">
  <h3>{Card title — derived from H3_PATTERN, rewritten if SERP context suggests a more natural label}</h3>
  <ul>
    <li>{Plain prose bullet, 14-30 words, no bold label prefix}</li>
    <li>{Plain prose bullet, 14-30 words, no bold label prefix}</li>
    <li>{Plain prose bullet, 14-30 words, no bold label prefix}</li>
  </ul>
</article>
```

## Constraints

- **Exactly 3 bullets.** Not 4, not 2. Three plain prose bullets per card.
- The **H3 card title** is a subtopic name derived from {{H3_PATTERN}}. Substitute template variables with article-specific values. You MAY rewrite the title if SERP context produces a more natural, specific label, but it must remain a subtopic name.
- **Bullets are plain prose.** Do NOT start any bullet with a `<strong>Label:</strong>` run-in prefix. Each bullet is a complete statement that reads naturally from the first word. No bolded lead-ins.
- **Each bullet is 14-30 words.**
- **Synthesis diversity:** If PRIOR_CARDS_SYNTHESIS is non-empty, your bullets must NOT repeat a fact, statistic, or threshold already used in a prior card. Use a different angle.
- Use the {{BULLET_LABEL_HINTS}} as thematic guidance, but adapt them to the actual content. They are suggestions, not mandatory text.
- ZERO inline links. No `<a>` tags anywhere in the output.
- Prefer concrete numbers over vague language. "$14,450 on a $400,000 loan" beats "a significant amount."

## Anti-patterns

Do NOT produce any of the following:

- **Card title as a generic intent label:** "Best for", "Key advantage", "Watch out", "Pros and cons", "Key benefit", "Main risk", "Top pick" are all banned as card titles. The title must be a specific subtopic name.
- **Run-in bold labels:** Do NOT start any bullet with `<strong>Something:</strong>`. Write plain prose from the first word.
- **4 or more bullets in a card.** Exactly 3.
- Em dashes (use commas or periods instead)
- Parentheses in body prose (restructure the sentence, or use commas)
- Lowercase "veteran" or "military" — always capitalize Veteran and Military
- Filler words: "discover", "explore", "vibrant", "dive into", "let's", "we'll cover"
- AI-tells: "navigate the complexities", "in today's fast-paced world", "robust", "leverage", "delve into", "unlock", "unveil"
- Emoji
- Markdown code fences in the output

Return ONLY the HTML. No markdown fences. No preamble.

<!-- Implements docs/article-spec.md Section 6 -->


## DEFICIENCY LIABILITY — NEVER IMPLY AUTOMATIC WAIVER

A short sale, deed in lieu, or foreclosure does NOT automatically eliminate the borrower's deficiency liability. Whether the lender waives the remaining balance depends entirely on the written terms of the approval letter or settlement agreement. NEVER state that debt is "forgiven," "eliminated," "absorbed," or "gone" without qualifying that it requires a written release from the lender.
