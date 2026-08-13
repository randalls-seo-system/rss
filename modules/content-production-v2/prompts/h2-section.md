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

{{EVIDENCE_BLOCK}}

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

## CRITICAL CONSTRAINT — NO PROSE WALLS

No single paragraph in any section may exceed **100 words**. This is a hard cap. If you have content that would exceed this, break it into bullets, a table, or multiple paragraphs. A paragraph between 80-100 words is acceptable but should be the exception, not the norm. A paragraph at 150+ words is a structural failure and will be rejected. **Count your words per paragraph before submitting.**

## PARAGRAPH CAP — HARD LIMIT

Maximum **3 prose paragraphs** per section. Structure:
- **Paragraph 1 (REQUIRED):** the answer paragraph (see ANSWER LENGTH below)
- **Paragraph 2 (optional):** supporting detail or context
- **Paragraph 3 (optional):** closing note, scenario, or transition

Do NOT write a fourth paragraph. If a section needs more content, add a bullet list, table, or callout — not more prose. Three back-to-back paragraphs of prose is the absolute ceiling.

## STRUCTURAL ELEMENT DOMINANCE — PER-TYPE PROSE CAPS

The structural_type assigned to each section determines what element is the visual centerpiece. Prose must NOT bury the structural element. These caps OVERRIDE the 3-paragraph maximum above for specific types:

**If structural_type = 'callout':**
- Maximum **2 prose paragraphs** in the section
- **Per-paragraph word limit: 80 words target, 100 words HARD CAP.** No single paragraph may exceed 100 words.
- If you have more content than fits in 2 paragraphs of 80-100 words, USE BULLETS — bullets are the correct structure for multi-facet content.
- One paragraph BEFORE the callout (the answer paragraph)
- The callout block (the visual centerpiece)
- Optionally one paragraph AFTER (transition or closing note)
- Do NOT pad with 3-4 prose paragraphs around the callout

**If structural_type = 'table':**
- Maximum **2 prose paragraphs** in the section
- **Per-paragraph word limit: 80 words target, 100 words HARD CAP.** No single paragraph may exceed 100 words.
- If you have more content than fits in 2 paragraphs of 80-100 words, USE BULLETS alongside the table.
- One paragraph BEFORE the table (the answer paragraph)
- The table (the visual centerpiece)
- Optionally one paragraph AFTER
- Do NOT pad with 3-4 prose paragraphs around the table

**If structural_type = 'bullets':**
- Maximum **1 prose paragraph** (the answer paragraph only)
- **Per-paragraph word limit: 80 words target, 100 words HARD CAP.**
- Then 3-4 bullets
- Bullets are the dominant element
- No closing prose paragraph after the bullets

**If structural_type = 'prose' or 'prose_optional_table':**
- Standard 3-paragraph cap applies
- **Per-paragraph word limit: 80 words target, 100 words HARD CAP.**
- No required structural element

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

## NUMBER SOURCING — EVIDENCE-ONLY

Use specific numbers ONLY when they appear in the evidence store or the provided data JSON. When no sourced number is available, use qualitative language. A number that does not trace to an item in the EVIDENCE_BLOCK or TOPIC_CONTEXT above is an unsourced assertion and will be rejected.

## NUMBER PRECISION — VOLATILE vs FIXED

Numbers in content fall into two categories. Treat them differently:

**VOLATILE numbers** change over time and go stale within months. Use DURABLE PHRASING — ranges, qualitative language, or "as of [date]" framing. Do NOT hard-code a specific figure.
- Market prices → "homes generally range from the $400s to $600s" NOT "$485,000 median"
- Days on market → "homes here tend to sell within a few weeks" NOT "12 days on market"
- School rating scores → "consistently well-rated in the district" NOT "8/10 on GreatSchools"
- Inventory counts → "active inventory stays moderate" NOT "91 homes for sale"
- Population estimates → "a growing community" NOT "population 7,391"
- Appreciation percentages → "has appreciated steadily" NOT "4.2% annual appreciation"

**FIXED AUTHORITATIVE facts** are defined by statute, regulation, or institutional authority. Keep these EXACT — do NOT soften them to ranges or vague phrasing. Precision is the point.
- Tax exemption amounts and rules → "100% total property tax exemption for 100% disabled Veterans" (exact, verified)
- Conforming loan limits → "$766,550 for a single-family home in 2026" (exact, from FHFA)
- Statutory references → "Texas Property Code §5.008" (exact)
- Program eligibility figures → "3.5% minimum down payment for FHA" (exact, from HUD)
- Tax rates set by jurisdiction → "Bexar County base rate of $0.2763 per $100" (exact, from county)
- HOA fees → state the specific amount if sourced from the HOA
- School attendance zones → name the specific school and district (verified from district boundary tool)
- Specific deadlines → "option period typically runs 7-10 days" (standard practice, stated as range)

**The rule is NOT "numbers bad / ranges good."** It is: volatile market stats → durable ranges; fixed authoritative facts → exact and verified. A legal exemption amount that is softened to a range is WRONG. A median home price that is hard-coded will go stale in months.

When you are unsure whether a number is volatile or fixed, default to durable phrasing.

## AMENITY RESTRAINT

Never assert specific physical amenities (playgrounds, splash pads, pool types, courts, gated access, trail surfaces, trail lengths, specific park features) unless that amenity is explicitly stated in the SERP context, topic context, or verified data injected above. If a business or landmark is mentioned, use its full canonical name as it appears in the source data. Omission is better than invention. A park exists? Say it exists. It has "playgrounds, pavilions, and sports fields"? Only if the source data says so.

## NARRATIVE RESTRAINT — NO UNSOURCED HISTORY/HERITAGE/CULTURE

Do NOT generate historical narrative, heritage stories, cultural origin stories, or founding mythology unless the SERP research or verified data above contains SOURCED material for them. "German settlers founded the town and brought the barbecue tradition" is a fabrication if the research didn't say that. When SERP data is thin, write a SHORTER guide covering verifiable specifics (prices, schools, commute, lot sizes). Graceful degradation = get shorter, never fill gaps with invented narrative. A 1,500-word guide with all facts verified is better than a 3,000-word guide with invented heritage sections.

## FAQ RESTRAINT — NEIGHBORHOOD-SPECIFIC ONLY

FAQ questions must be about THIS specific neighborhood/city, not generic broad questions. Do NOT answer "What is the nicest neighborhood in Texas?" or "What makes the nicest neighborhood stand out?" in a Lockhart guide — those are Texas-wide questions, not Lockhart questions. If SERP gap analysis only surfaces broad queries, use FEWER neighborhood-specific FAQs rather than padding with generic ones. Three strong Lockhart-specific FAQs beat six generic Texas FAQs.

## DEFICIENCY LIABILITY — NEVER IMPLY AUTOMATIC WAIVER

A short sale, deed in lieu, or foreclosure does NOT automatically eliminate the borrower's deficiency liability. Whether the lender waives the remaining balance depends entirely on the written terms of the approval letter or settlement agreement.

CORRECT framing:
- "A short sale may include a written release of the remaining balance, but only if the lender's approval letter explicitly waives deficiency rights."
- "Whether you owe a deficiency after a deed in lieu depends on the lender's written agreement."
- "Request an explicit written release of liability before closing."

NEVER write:
- "The lender absorbs the shortfall" (without qualifying "if the approval letter releases you")
- "A short sale eliminates your liability"
- "Walk away clean" / "walk away free"
- "The debt is gone after a short sale"
- "Deficiency is forgiven" (without specifying it requires written release)

This applies to ALL verticals that touch distressed sales, not just the short-sale cluster.

## NO UNSUPPORTED SUPERLATIVES

"Highest-rated," "no other neighborhood matches," "best value," "strongest," "safest" as bald claims are prohibited. Either ATTRIBUTE ("in our agents' assessment") or make MEASURABLE with a cited source. No unsourced absolutes.

## INTERNAL CONSISTENCY

Numbers and counts stated in one part of the article must match every other mention. If the intro says "5 options," the body must list exactly 5. If a stat strip says "3 districts," body and FAQs must agree. Contradictions between sections are a hard fail.

{{VERTICAL_RULES}}

## Anti-patterns

Do NOT produce any of the following:

- "In this section we'll cover...", "Let's look at...", "Below we'll examine..." or any meta-narrative opener
- More than one structural element (no table + bullets, no table + callout)
- Empty sections with only an H2 and no structural element
- Using a DIFFERENT structural element than {{STRUCTURAL_ELEMENT_PREFERENCE}} — this is a hard constraint, not a suggestion
- **4+ paragraphs of prose** — use bullets, tables, or callouts for density instead
- Em dashes (use commas or periods instead)
- Parentheses in body prose (restructure the sentence, or use commas)
- Lowercase "veteran" or "military" — always capitalize Veteran and Military
- Filler words: "discover", "explore", "vibrant", "dive into", "let's", "we'll cover"
- AI-tells: "navigate the complexities", "in today's fast-paced world", "robust", "leverage", "delve into", "unlock", "unveil"
- Emoji
- Markdown code fences in the output
- Any links (`<a>` tags) — internal or external

Return ONLY the HTML. No markdown fences. No preamble.

<!-- Implements docs/article-spec.md Section 9 -->
