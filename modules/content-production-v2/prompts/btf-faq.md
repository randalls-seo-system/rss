# BTF FAQ — Spec Section 14

You are writing the Below-The-Fold FAQ section for an article about **{{TARGET_KEYWORD}}**.

{{INJECT_BRAND_VOICE}}

## Inputs

- **Questions to answer:**
{{QUESTIONS_LIST}}

- **ATF FAQ questions to EXCLUDE (do not duplicate these):**
{{ATF_FAQ_QUESTIONS_TO_EXCLUDE}}

- **Target keyword:** {{TARGET_KEYWORD}}
- **Topic context:** {{TOPIC_CONTEXT}}

## Output

Produce exactly this HTML structure:

```
<section class="rl-faq">
  <h2>Frequently Asked Questions</h2>
  <details>
    <summary>{Question 1, ending in ?}</summary>
    <p>{Answer, 50-110 words}</p>
  </details>
  <details>
    <summary>{Question 2, ending in ?}</summary>
    <p>{Answer, 50-110 words}</p>
  </details>
  ... (5-12 items total)
</section>
```

## Constraints

- **5-12 FAQ items.** Target 5-8. Only go above 8 for dense topics (cost, comprehensive guides).
- **Each answer: 50-110 words.** These are deeper than ATF FAQ answers (which are 35-60 words). Use the extra space for specifics: form numbers, dollar amounts, edge cases, timelines.
- **Each question** must end with `?`.
- ZERO inline links. No `<a>` tags anywhere in the output.
- **ZERO overlap with ATF FAQs.** Compare each candidate question against {{ATF_FAQ_QUESTIONS_TO_EXCLUDE}}. If a question is identical or substantially similar to an excluded question, skip it entirely. Do not rephrase an excluded question.
- **No duplicate-topic FAQs.** If two questions in {{QUESTIONS_LIST}} effectively ask the same thing, keep only the more specific one.
- BTF FAQ answers CAN and SHOULD mention specific forms by number (e.g., "VA Form 26-1880"), specific dollar amounts, specific edge cases, and regulatory details. This is where the article's depth lives.
- Each answer must be self-contained. A reader who reads only one FAQ entry should understand the answer without context from other entries.
- Produce the items in a logical order: foundational questions first, edge cases and advanced topics later.

## Anti-patterns

Do NOT produce any of the following:

- Em dashes (use commas, periods, or parentheses instead)
- Filler words: "discover", "explore", "vibrant", "dive into", "let's", "we'll cover"
- AI-tells: "navigate the complexities", "in today's fast-paced world", "robust", "leverage", "delve into", "unlock", "unveil"
- "See the section above" or any reference to other parts of the article
- Two FAQ entries that ask the same question in different words
- Answers that are just one sentence (these are deeper than ATF FAQs, give them substance)
- Emoji
- Markdown code fences in the output

Return ONLY the HTML. No markdown fences. No preamble.

<!-- Implements docs/article-spec.md Section 14 -->
