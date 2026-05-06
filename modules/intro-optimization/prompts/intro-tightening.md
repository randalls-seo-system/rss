You are tightening the intro of an article on {{SITE_NAME}}, a {{BRAND_TONE}} real estate company serving {{LOCATION_PRIMARY}}.

The current intro is too long and buries the answer. Your job is to rewrite it as a tight, direct intro (50-70 words total) that answers the search intent in the first 1-2 sentences.

ARTICLE INFO:
- Title: {{POST_TITLE}}
- URL: {{URL}}
- Primary search intent: {{PARENT_QUERY}} ({{PARENT_IMPRESSIONS}} impressions, position {{PARENT_POSITION}})
- Dominant intent type: {{INTENT}}

CURRENT INTRO ({{CURRENT_WORD_COUNT}} words):
"""
{{CURRENT_INTRO}}
"""

WRITING RULES:

Eyebrow line (8-15 words, optional):
- Single sentence above the intro
- Establishes context: who this is for, when updated, or specific angle
- Examples: "Updated for 2026 buyers." or "For veterans using their VA loan benefit."

Intro paragraph (50-70 words total):
1. FIRST 1-2 sentences must directly answer "{{PARENT_QUERY}}" — what it is, what to do, what's true
2. Maximum 30 words for the direct answer
3. Following sentences add context, key trade-offs, or what the reader will find
4. NO filler phrases:
   - "In this guide we will explore..."
   - "Welcome to our comprehensive guide on..."
   - "If you are wondering about..."
   - "There are many things to consider when..."
   - "Let's dive into..."
5. Active voice, present tense
6. Specific, not vague — use real numbers, real names, real places where possible

Disclaimer callout (only if original had one):
- If the current intro contains a legal/financial disclaimer ("not legal advice", "consult a lender", etc.)
- Pull it out into a separate callout that goes AFTER the intro
- This becomes a Lender Reality Check or Approval Watchpoint callout
- Format: short, factual, 1-2 sentences

QUALITY CHECK before responding:
- Does the first sentence answer the parent query directly?
- Could a busy reader get the answer in 10 seconds?
- Is anything still throat-clearing (filler before substance)?
- Is the word count between 50-70?

OUTPUT FORMAT (strict JSON):
{
  "eyebrow": "<8-15 word eyebrow line, or empty string if not applicable>",
  "intro": "<50-70 word tightened intro>",
  "disclaimer_callout": "<callout content if original had disclaimer, or empty>",
  "intro_word_count": <int>,
  "captures_parent_query": true/false,
  "removed_filler": ["<filler phrase 1 from original>", "<filler phrase 2>"],
  "rationale": "<2-3 sentence explanation of strategic choices>"
}
