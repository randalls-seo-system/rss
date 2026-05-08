# ATF FAQ — Spec Section 7

You are writing ONE ATF FAQ question-and-answer pair for an article about **{{TARGET_KEYWORD}}**.

{{INJECT_BRAND_VOICE}}

## Inputs

- **Question:** {{QUESTION}}
- **Target keyword:** {{TARGET_KEYWORD}}
- **Topic context:** {{TOPIC_CONTEXT}}

## Output

Produce exactly this HTML structure:

```
<details>
  <summary>{Question, ending in ?}</summary>
  <p>{Answer, 35-60 words, 1-2 sentences}</p>
</details>
```

## Constraints

- **Answer word count:** 35-60 words. Hard limits on both ends.
- **1-2 sentences only.** Not 3.
- The question in `<summary>` must end with a `?`.
- The answer must be **self-contained.** A reader who sees only this Q&A, without reading the full article, should understand the answer.
- ZERO inline links. No `<a>` tags anywhere in the output.
- Use the {{QUESTION}} as the question text. You may lightly rephrase for grammar or clarity, but do not change the meaning or topic.
- Ground the answer in facts from {{TOPIC_CONTEXT}}.
- Prefer concrete numbers and specifics over vague generalities.

## Anti-patterns

Do NOT produce any of the following:

- Em dashes (use commas, periods, or parentheses instead)
- Filler words: "discover", "explore", "vibrant", "dive into", "let's", "we'll cover"
- AI-tells: "navigate the complexities", "in today's fast-paced world", "robust", "leverage", "delve into", "unlock", "unveil"
- "See the section below" or any reference to other parts of the article
- Emoji
- Markdown code fences in the output

Return ONLY the HTML. No markdown fences. No preamble.

<!-- Implements docs/article-spec.md Section 7 -->
