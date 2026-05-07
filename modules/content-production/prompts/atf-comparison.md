# ATF Prompt — Comparison/Ranking Intent

Generate an ATF section for a **ranked comparison** article using rl-* component classes.

## Intent Signal
User wants the best option: "best X", "top X", "X ranked", "X reviews"

## ATF Structure
- Hero stating the top pick in the H1
- Lead paragraph: name the winner and the metric that matters
- 4 quick cards: Top Pick, Runner-Up, Budget Pick, How We Scored
- 3 ATF FAQs from real People Also Ask data

## Card Rules
- Each card: 3 bullets with `<strong>Label:</strong>` format
- 14-18 words per bullet, hard data required
- No action bullets, no links

## H1 Pattern
`Best {{Category}} in {{Year/Location}}`

## Eyebrow
`{{Topic}} · Ranked Comparison`

## Template
Use: `templates/intent-comparison.html`
