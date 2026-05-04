# QA Gates Module

## Status: Complete (v1.0)

## What This Module Does

Read-only audit suite that scans a WordPress site's content for link quality issues. Never modifies content — detection only.

## The 4 Audits

### 1. Sub-Word Anchor Splits (`anchor-splits`)

Detects `</a>` immediately followed by lowercase letters — indicates the link injector matched a substring instead of a whole word.

**Examples:**
- `bec<a>aus</a>e` — acronym "aus" matched inside "because" (critical)
- `<a>closing cost</a>ss` — doubled suffix (high)
- `<a>credit score</a>s` — plural split (medium)

**Severity:** critical > high > medium > low based on visibility of corruption.

### 2. Generic / Non-Descriptive Anchors (`generic-anchors`)

Flags anchor text that provides no SEO or user value:
- Generic phrases: "click here", "read more", "learn more", "here", "this"
- Single-word anchors under 4 characters
- Bare unexpanded acronyms: DTI, COE, MPR, AUS, BAH (except IRRRL which is a product name)

### 3. Repeated URL Count (`repeated-urls`)

Flags posts where the same URL is linked 3+ times. Best practice: each URL appears at most twice (first contextual mention + Resources Used section).

Exception: `/compare-loan-offers/` allowed up to 3 times (CTA pattern).

### 4. Internal vs External Link Balance (`link-balance`)

Flags posts where external links outnumber internal links (with 5+ external link minimum threshold). Sorted by gap size, worst offenders first.

## How To Run

```bash
# Full suite on any configured site
./tools/audit-runner.sh sites/<slug>.conf

# Single audit
./tools/audit-runner.sh sites/<slug>.conf --audit anchor-splits

# Custom output directory
./tools/audit-runner.sh sites/<slug>.conf --output ~/reports/
```

## Output Format

Each audit produces a CSV file. Reports saved to:
```
modules/qa-gates/reports/<site-slug>/<YYYY-MM-DD>/
├── anchor-splits.csv
├── generic-anchors.csv
├── repeated-urls.csv
├── link-balance.csv
└── summary.md
```

### CSV Schemas

**anchor-splits.csv:**
`post_id, slug, issue_type, anchor_text, trailing_chars, target_url, severity`

**generic-anchors.csv:**
`post_id, slug, issue_type, anchor_text, target_url, severity`

**repeated-urls.csv:**
`post_id, slug, repeated_url, count, is_internal, severity`

**link-balance.csv:**
`post_id, slug, internal_count, external_count, gap, severity`

## Severity Guide

- **critical** — Visible content corruption or major SEO damage
- **high** — Garbled text or significant quality issue
- **medium** — Suboptimal but not visually broken
- **low** — Minor, likely cosmetic

## How It Works

1. Scripts are built locally (helpers inlined into each audit PHP)
2. Combined script piped to target via SSH (single session)
3. `wp eval-file` runs the audit in WordPress context with `$wpdb` access
4. CSV output streamed back, saved locally
5. Remote `/tmp` cleaned up after each run

## Known Limitations

- Audits scan `post_content` only — doesn't detect issues in Divi Theme Builder layouts
- Link extraction uses regex, not DOM parsing — may miss edge cases with malformed HTML
- Runs sequentially (one audit at a time) to avoid server load
- No fix capability in v1.0 — detection only

## Validation

First run against VALN (2026-05-04):

| Audit | Issues |
|---|---|
| anchor-splits | 10 |
| generic-anchors | 65 |
| repeated-urls | 35 |
| link-balance | 137 |

Results match expectations from earlier manual audit (most anchor splits were fixed, repeated URLs partially cleaned, link balance largely unchanged).
