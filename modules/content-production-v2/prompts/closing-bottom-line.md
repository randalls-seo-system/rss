# Closing Bottom Line — Spec Section 13

You are writing the closing "The Bottom Line" recap section for an article about **{{TARGET_KEYWORD}}**.

{{INJECT_BRAND_VOICE}}

## Inputs

- **Target keyword:** {{TARGET_KEYWORD}}
- **Article summary (H2 titles + intro paragraphs from each body section):**
{{ARTICLE_SUMMARY}}

## Output

Produce exactly this HTML structure:

```
<section>
  <h2>The Bottom Line</h2>
  <p>{Recap paragraph 1}</p>
  <p>{Recap paragraph 2 (optional)}</p>
  <p>{Recap paragraph 3 (optional)}</p>
</section>
```

## Constraints

- **100-150 words total.** Hard limits on both ends. Default to 2 paragraphs.
- **1-3 paragraphs allowed.** Prefer 2.
- ZERO bullets. No `<ul>` or `<li>` elements.
- ZERO external links. No `<a>` tags with external URLs.
- ZERO internal links. No `<a>` tags at all.
- ZERO new information. Every claim in the closing must already appear in {{ARTICLE_SUMMARY}}. This is a recap, not new content.
- **Distinguishable from BLUF:** The BLUF (if present earlier in the article) is forward-looking ("here's what you need to know going in"). The closing is a backward-looking recap ("here's what the article showed you"). Use recap language: "the key factors are", "what matters most is", "the bottom line comes down to".
- Do not start with "In conclusion" or "To summarize."
- The closing should leave the reader with a clear, actionable takeaway synthesized from the article's body sections.

## Anti-patterns

Do NOT produce any of the following:

- Em dashes (use commas or periods instead)
- Parentheses in body prose (restructure the sentence, or use commas)
- Lowercase "veteran" or "military" — always capitalize Veteran and Military
- Filler words: "discover", "explore", "vibrant", "dive into", "let's", "we'll cover"
- "In this article we covered..."
- AI-tells: "navigate the complexities", "in today's fast-paced world", "robust", "leverage", "delve into", "unlock", "unveil"
- Emoji
- Markdown code fences in the output
- Bullet lists of any kind
- Any links

Return ONLY the HTML. No markdown fences. No preamble.

<!-- Implements docs/article-spec.md Section 13 -->
