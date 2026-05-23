# H2 Section — Spec Section 9

You are writing ONE body H2 section for an article about **{{TARGET_KEYWORD}}**.

{{INJECT_BRAND_VOICE}}

## Inputs

- **H2 title:** {{H2_TITLE}}
- **Section role:** {{SECTION_ROLE}}
- **LOCKED structural element:** {{STRUCTURAL_ELEMENT_PREFERENCE}}
- **Template role hint:** {{TEMPLATE_HINT}}
- **Callout key (if structural element is callout):** {{CALLOUT_KEY}}
- **Callout label (if structural element is callout):** {{CALLOUT_LABEL}}
- **Target word count for this section:** {{TARGET_WORD_COUNT}}
- **Topic context for this subtopic:** {{TOPIC_CONTEXT}}
- **Prior sections summary (what the article has already covered):** {{PRIOR_SECTIONS_SUMMARY}}

## Output

Produce exactly this HTML structure:

```
<section>
  <h2>{H2_TITLE}</h2>
  <p>{Intro paragraph: 50-70 words, answer-first}</p>
  <p>{Optional body paragraph: 60-100 words. Include if target word count requires it. May omit for shorter sections.}</p>
  {ONE structural element — LOCKED to {{STRUCTURAL_ELEMENT_PREFERENCE}}, see instructions below}
  <p>{Optional closing paragraph: 40-80 words. Often a scenario, deal math application, or practical implication.}</p>
</section>
```

### STRUCTURAL ELEMENT — HARD LOCK (you MUST use {{STRUCTURAL_ELEMENT_PREFERENCE}})

The structural element for this section is **locked by the article template**. You do NOT get to choose. Follow the instruction for "{{STRUCTURAL_ELEMENT_PREFERENCE}}" below:

**If "table":**
This section MUST be built around a TABLE. Use the role hint to design it: "{{TEMPLATE_HINT}}". Do NOT use bullets or callouts as the primary structure. Surrounding prose of 1-2 paragraphs is fine to frame the table.
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

**If "callout":**
This section MUST be built around a CALLOUT block. The callout is the centerpiece. Role hint: "{{TEMPLATE_HINT}}". Use the archetype voice. Do NOT use a table or bullets as the primary structure.
```
<div class="rl-callout rl-callout--{{CALLOUT_KEY}}">
  <strong>{{CALLOUT_LABEL}}</strong>
  <p>{Callout content, 30-100 words}</p>
</div>
```
The callout type label goes inside `<strong>`. The content provides a concrete example, warning, or expert insight relevant to the section topic.

**If "bullets":**
This section MUST use BULLETS as the primary structure. Role hint: "{{TEMPLATE_HINT}}". Do NOT use a table or callout as the primary structure.
```
<ul>
  <li>...</li>
  ...
</ul>
```
Lists should have 3-7 bullets. Each bullet is a substantive point, not a single word.

**If "prose_optional_table":**
Use prose. A table is OPTIONAL if the content benefits from one; otherwise just prose. Role hint: "{{TEMPLATE_HINT}}".

## Constraints

- **Intro paragraph is REQUIRED.** 50-70 words. Answer-first: the first sentence directly states what this H2's topic resolves to.
- **Do NOT include any internal links in the section HTML.** No `<a>` tags. Internal linking is handled by a separate post-processing step. Your job is content only.
- **Optional body paragraph:** 60-100 words. Include when the section needs more depth to hit {{TARGET_WORD_COUNT}}.
- **EXACTLY ONE structural element.** It MUST be {{STRUCTURAL_ELEMENT_PREFERENCE}}. Do not substitute a different type.
- **Optional closing paragraph:** 40-80 words. Include when the section benefits from a practical application or scenario.
- **Section total:** 200-450 words (all paragraphs combined, not counting structural element text).
- ZERO links of any kind. No `<a>` tags anywhere in the section.
- If {{STRUCTURAL_ELEMENT_PREFERENCE}} is "callout", use {{CALLOUT_KEY}} for the CSS class modifier and {{CALLOUT_LABEL}} for the visible heading text.
- **Cross-section continuity:** If PRIOR_SECTIONS_SUMMARY is non-empty, do NOT re-state facts already covered in those sections. Pick up where the prior sections left off. Refer back to prior context if useful, but don't waste words re-establishing what the reader just read.

## Anti-patterns

Do NOT produce any of the following:

- "In this section we'll cover...", "Let's look at...", "Below we'll examine..." or any meta-narrative opener
- More than one structural element (no table + bullets, no table + callout)
- Empty sections with only an H2 and no structural element
- Using a DIFFERENT structural element than {{STRUCTURAL_ELEMENT_PREFERENCE}} — this is a hard constraint, not a suggestion
- Em dashes (use commas, periods, or parentheses instead)
- Filler words: "discover", "explore", "vibrant", "dive into", "let's", "we'll cover"
- AI-tells: "navigate the complexities", "in today's fast-paced world", "robust", "leverage", "delve into", "unlock", "unveil"
- Emoji
- Markdown code fences in the output
- Any links (`<a>` tags) — internal or external

Return ONLY the HTML. No markdown fences. No preamble.

<!-- Implements docs/article-spec.md Section 9 -->
