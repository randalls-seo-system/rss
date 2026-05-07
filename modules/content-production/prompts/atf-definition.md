# ATF Prompt — Definition Intent

Generate an ATF section for a **"what is X?"** educational article using rl-* component classes.

## Intent Signal
User wants to understand a concept: "what is", "explained", "guide to", "understanding"

## ATF Structure
- Hero with "What Is {{Term}}?" H1
- Lead paragraph: one-sentence definition + why it matters
- 4 quick cards: Definition, Key Facts, Why It Matters, Related Terms
- 3 ATF FAQs (first one always "What is {{term}} in simple terms?")

## Card Rules
- Each card: 3 bullets with `<strong>Label:</strong>` format
- 14-18 words per bullet, hard data required
- Definition card must include: What it is, Also called, Category
- No action bullets, no links

## H1 Pattern
`What Is {{Term}}?` or `{{Term}} Explained`

## Eyebrow
`{{Topic}} · Key Concepts`

## Template
Use: `templates/intent-definition.html`
