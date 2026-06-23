# ATF Lede — Spec Section 5

You are writing the opening lede paragraph for an article about **{{TARGET_KEYWORD}}**.

{{INJECT_BRAND_VOICE}}

## Inputs

- **Target keyword:** {{TARGET_KEYWORD}}
- **Topic noun:** {{TOPIC_NOUN}}
- **Top SERP result ledes:** {{SERP_TOP_RESULT_LEDES}}
- **AI Overview text:** {{AI_OVERVIEW_TEXT}}

## Output

Produce a single `<p>` element (preferred). Two `<p>` elements are acceptable only for genuinely complex topics.

```
<p>{Lede paragraph}</p>
```

## Constraints

- **Single paragraph:** 40-110 words. Target 50-60 words.
- **Two paragraphs (if needed):** 80-200 words combined. Each paragraph 40-100 words.
- **Sentence 1** states the conclusion or direct answer to the query. Declarative only. No question.
- **Sentence 2** introduces concrete numbers, ranges, or a list size (e.g., "the three biggest pressure points").
- **Sentence 3** introduces the wrinkle, exception, or "the catch."
- ZERO inline links. No `<a>` tags anywhere in the output.
- ZERO questions anywhere in the lede. No `?` character.
- Do not reference the article structure ("we'll cover", "in this article").
- Do not repeat the H1 verbatim as the first sentence.
- Use information from the SERP top results and AI Overview to ground the lede in current facts.

## Anti-patterns

Do NOT produce any of the following:

- Em dashes (use commas or periods instead)
- Parentheses in body prose (restructure the sentence, or use commas)
- Lowercase "veteran" or "military" — always capitalize Veteran and Military
- Filler words: "discover", "explore", "vibrant", "dive into", "let's", "we'll cover"
- "In this article/section we'll..."
- AI-tells: "navigate the complexities", "in today's fast-paced world", "robust", "leverage", "delve into", "unlock", "unveil"
- Emoji
- Markdown code fences in the output
- Any question mark in the text

Return ONLY the HTML. No markdown fences. No preamble.

<!-- Implements docs/article-spec.md Section 5 -->
