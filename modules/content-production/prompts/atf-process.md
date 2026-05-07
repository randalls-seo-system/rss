# ATF Prompt — Process Intent

Generate an ATF section for a **process/how-to** article using rl-* component classes.

## Intent Signal
User wants to accomplish something: "how to", "step by step", "guide to", "checklist"

## ATF Structure
- Hero with action-oriented H1
- Lead paragraph: state timeline and key requirement upfront
- 4 quick cards: Prerequisites, What You Need, Timeline, Costs
- 3 ATF FAQs from real People Also Ask data

## Card Rules
- Each card: 3 bullets with `<strong>Label:</strong>` format
- 14-18 words per bullet, hard data required
- No action bullets, no links

## H1 Pattern
`How To {{Process Name}}`

## Eyebrow
`{{Topic}} · Step-by-Step Guide`

## Template
Use: `templates/intent-process.html`
