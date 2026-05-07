# ATF Prompt — News/Update Intent

Generate an ATF section for a **time-sensitive update** article using rl-* component classes.

## Intent Signal
Article covers rate changes, market updates, regulation changes, seasonal events

## ATF Structure
- Hero with date-stamped H1
- Meta line with update date
- Lead paragraph: what changed and how it impacts readers
- 2 quick cards: What Changed, Who Is Affected
- 3 ATF FAQs from real People Also Ask data

## Card Rules
- Each card: 3 bullets with `<strong>Label:</strong>` format
- Include old vs new values, effective dates
- 14-18 words per bullet

## H1 Pattern
`{{Headline}} ({{Month}} {{Year}})`

## Eyebrow
`{{Topic}} · {{Month}} {{Year}} Update`

## Template
Use: `templates/intent-news.html`
