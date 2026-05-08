# H2 Section — Spec Section 9

You are writing ONE body H2 section for an article about **{{TARGET_KEYWORD}}**.

{{INJECT_BRAND_VOICE}}

## Inputs

- **H2 title:** {{H2_TITLE}}
- **Section role:** {{SECTION_ROLE}}
- **Structural element preference:** {{STRUCTURAL_ELEMENT_PREFERENCE}}
- **Callout key (if structural element is callout):** {{CALLOUT_KEY}}
- **Callout label (if structural element is callout):** {{CALLOUT_LABEL}}
- **Target word count for this section:** {{TARGET_WORD_COUNT}}
- **Topic context for this subtopic:** {{TOPIC_CONTEXT}}
- **Anchor pool candidates (for inline links):** {{ANCHOR_POOL_CANDIDATES}}

  (Format: each candidate appears on its own line as `anchor text -> URL`.)

## Output

Produce exactly this HTML structure:

```
<section>
  <h2>{H2_TITLE}</h2>
  <p>{Intro paragraph: 50-70 words, answer-first, with 1-3 inline internal links}</p>
  <p>{Optional body paragraph: 60-100 words. Include if target word count requires it. May omit for shorter sections.}</p>
  {ONE structural element — see options below}
  <p>{Optional closing paragraph: 40-80 words. Often a scenario, deal math application, or practical implication.}</p>
</section>
```

### Structural element options (use the one matching {{STRUCTURAL_ELEMENT_PREFERENCE}}):

**If "table":**
```
<table>
  <thead><tr><th>...</th><th>...</th></tr></thead>
  <tbody>
    <tr><td>...</td><td>...</td></tr>
    ...
  </tbody>
</table>
```
Tables should have 3-7 columns and 3-12 rows. Include a header row. Data should be specific (numbers, rates, timelines), not vague.

**If "bullets":**
```
<ul>
  <li>...</li>
  ...
</ul>
```
Lists should have 3-7 bullets. Each bullet is a substantive point, not a single word.

**If "callout":**
```
<div class="rl-callout rl-callout--{{CALLOUT_KEY}}">
  <strong>{{CALLOUT_LABEL}}</strong>
  <p>{Callout content, 30-100 words}</p>
</div>
```
The callout type label goes inside `<strong>`. The content provides a concrete example, warning, or expert insight relevant to the section topic.

## Constraints

- **Intro paragraph is REQUIRED.** 50-70 words. Answer-first: the first sentence directly states what this H2's topic resolves to.
- **Intro has 1-3 inline internal links** from {{ANCHOR_POOL_CANDIDATES}}. Format: `<a href="{url}">{anchor text}</a>`. Use only candidates that fit naturally in the sentence. Not all candidates need to be used. If no candidates fit, include zero links.
- **Optional body paragraph:** 60-100 words. Include when the section needs more depth to hit {{TARGET_WORD_COUNT}}.
- **EXACTLY ONE structural element.** Match {{STRUCTURAL_ELEMENT_PREFERENCE}}.
- **Optional closing paragraph:** 40-80 words. Include when the section benefits from a practical application or scenario.
- **Section total:** 200-450 words (all paragraphs combined, not counting structural element text).
- ZERO external links anywhere in the section. Internal links only, from the anchor pool.
- If {{STRUCTURAL_ELEMENT_PREFERENCE}} is "callout", use {{CALLOUT_KEY}} for the CSS class modifier and {{CALLOUT_LABEL}} for the visible heading text.

## Anti-patterns

Do NOT produce any of the following:

- "In this section we'll cover...", "Let's look at...", "Below we'll examine..." or any meta-narrative opener
- More than one structural element (no table + bullets, no table + callout)
- Empty sections with only an H2 and no structural element
- Em dashes (use commas, periods, or parentheses instead)
- Filler words: "discover", "explore", "vibrant", "dive into", "let's", "we'll cover"
- AI-tells: "navigate the complexities", "in today's fast-paced world", "robust", "leverage", "delve into", "unlock", "unveil"
- Emoji
- Markdown code fences in the output
- External links (links to domains outside the site)

Return ONLY the HTML. No markdown fences. No preamble.

<!-- Implements docs/article-spec.md Section 9 -->
