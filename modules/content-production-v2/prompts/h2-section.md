# H2 Section — Spec Section 9

You are writing ONE body H2 section for an article about **{{TARGET_KEYWORD}}**.

{{INJECT_BRAND_VOICE}}

## Inputs

- **H2 title:** {{H2_TITLE}}
- **H2 format:** {{H2_FORMAT}} (question or statement — determines answer length)
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
  <p>{ANSWER paragraph — see ANSWER LENGTH rules below}</p>
  <p>{Optional supporting paragraph — include only if needed}</p>
  {ONE structural element — LOCKED to {{STRUCTURAL_ELEMENT_PREFERENCE}}, see instructions below}
  <p>{Optional closing paragraph — only if needed for practical application}</p>
</section>
```

## PARAGRAPH CAP — HARD LIMIT

Maximum **3 prose paragraphs** per section. Structure:
- **Paragraph 1 (REQUIRED):** the answer paragraph (see ANSWER LENGTH below)
- **Paragraph 2 (optional):** supporting detail or context
- **Paragraph 3 (optional):** closing note, scenario, or transition

Do NOT write a fourth paragraph. If a section needs more content, add a bullet list, table, or callout — not more prose. Three back-to-back paragraphs of prose is the absolute ceiling.

## ANSWER LENGTH BY H2 FORMAT

If H2_FORMAT='question': the first paragraph IS the AEO snippet. Google extracts featured snippets and People Also Ask answers from this paragraph specifically. The snippet field on Google's results page is 50-60 words.

**STRICT REQUIREMENTS for question H2s:**
- Word count: **50-60 words. HARD LIMIT at 60.**
- Count your words before submitting. If over 60, cut.
- Lead with the answer in the first sentence.
- This paragraph IS the answer, not a setup for the answer.
- **BANNED openers:** 'There are several ways...', 'When it comes to...', 'It depends on...', or any throat-clearing.
- Required: the **first 12 words** contain the actual answer.

If H2_FORMAT='statement': first paragraph is **50-70 words**, answer-first prose. Less strict because statement H2s typically catalog or explain rather than answer a specific question.

### STRUCTURAL ELEMENT — HARD LOCK (you MUST use {{STRUCTURAL_ELEMENT_PREFERENCE}})

The structural element for this section is **locked by the article template**. You do NOT get to choose. Follow the instruction for "{{STRUCTURAL_ELEMENT_PREFERENCE}}" below:

**If "table":**
This section MUST be built around a TABLE. Use the role hint to design it: "{{TEMPLATE_HINT}}". Do NOT use bullets or callouts as the primary structure. Surrounding prose of 1-2 paragraphs is fine to frame the table. A bullet list is NOT needed alongside the table unless the prose genuinely warrants additional scannable points.
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
This section MUST be built around a CALLOUT block. The callout is the centerpiece. Role hint: "{{TEMPLATE_HINT}}". Use the archetype voice. Do NOT use a table or bullets as the primary structure. A bullet list is NOT needed alongside the callout.
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
Bullet rules:
- **3-4 bullets** (not 5-7). Quality over quantity.
- Each bullet **18+ words** — a substantive operational point, not a fragment.
- Use **bold lead-ins** for scannability (e.g., `<strong>Documentation:</strong> ...`).

**If "prose_optional_table":**
Use prose. A table is OPTIONAL if the content benefits from one; otherwise just prose. Role hint: "{{TEMPLATE_HINT}}".

## Constraints

- **Answer paragraph is REQUIRED.** Word count per H2_FORMAT rules above.
- **Do NOT include any internal links in the section HTML.** No `<a>` tags. Internal linking is handled by a separate post-processing step.
- **EXACTLY ONE structural element.** It MUST be {{STRUCTURAL_ELEMENT_PREFERENCE}}. Do not substitute a different type.
- **Maximum 3 paragraphs.** Do not write 4+ paragraphs of prose.
- **Section total:** 200-450 words (all paragraphs combined, not counting structural element text).
- ZERO links of any kind. No `<a>` tags anywhere in the section.
- If {{STRUCTURAL_ELEMENT_PREFERENCE}} is "callout", use {{CALLOUT_KEY}} for the CSS class modifier and {{CALLOUT_LABEL}} for the visible heading text.
- **Cross-section continuity:** If PRIOR_SECTIONS_SUMMARY is non-empty, do NOT re-state facts already covered. Pick up where prior sections left off.

## Anti-patterns

Do NOT produce any of the following:

- "In this section we'll cover...", "Let's look at...", "Below we'll examine..." or any meta-narrative opener
- More than one structural element (no table + bullets, no table + callout)
- Empty sections with only an H2 and no structural element
- Using a DIFFERENT structural element than {{STRUCTURAL_ELEMENT_PREFERENCE}} — this is a hard constraint, not a suggestion
- **4+ paragraphs of prose** — use bullets, tables, or callouts for density instead
- Em dashes (use commas, periods, or parentheses instead)
- Filler words: "discover", "explore", "vibrant", "dive into", "let's", "we'll cover"
- AI-tells: "navigate the complexities", "in today's fast-paced world", "robust", "leverage", "delve into", "unlock", "unveil"
- Emoji
- Markdown code fences in the output
- Any links (`<a>` tags) — internal or external

Return ONLY the HTML. No markdown fences. No preamble.

<!-- Implements docs/article-spec.md Section 9 -->
