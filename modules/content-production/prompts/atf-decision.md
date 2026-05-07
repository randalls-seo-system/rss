# ATF Prompt — Decision Intent

Generate an ATF (Above The Fold) section for a **decision/comparison** article using rl-* component classes.

## Intent Signal
User is choosing between options: "X vs Y", "which is better", "should I choose A or B"

## ATF Structure
- Hero with comparison framing in H1 (state both options)
- Lead paragraph: state the winner upfront with key differentiator
- 2 quick cards (one per option) with: Best for, Key advantage, Watch out
- 3 ATF FAQs from real People Also Ask data

## Card Rules
- Cards 1-2: sourced from AI Overview or top SERP results
- Each bullet: `<strong>Label:</strong>` + 14-18 word fact
- No action bullets, no links inside cards

## H1 Pattern
`{{Option A}} vs {{Option B}}: {{Verdict Framing}}`

## Eyebrow
`{{Topic}} · Comparison`

## Template
Use: `templates/intent-decision.html`
