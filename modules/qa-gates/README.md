# QA Gates Module

Status: Complete (v1.0)

4 read-only audit checks that scan any WordPress site for link quality issues via SSH + WP-CLI.

## Quick Start

```bash
# Run all 4 audits
./run-audit.sh ../../sites/<slug>.conf

# Run single audit
./run-audit.sh ../../sites/<slug>.conf --audit anchor-splits
```

## Audits

1. **anchor-splits** — Sub-word anchor splits (e.g., `<a>cost</a>s`)
2. **generic-anchors** — Non-descriptive anchors ("click here", bare acronyms)
3. **repeated-urls** — Same URL linked 3+ times per page
4. **link-balance** — External links outnumbering internal links

## Contents

- `audits/` — 4 PHP audit scripts (run via `wp eval-file`)
- `lib/` — Shared helpers (inlined at build time)
- `run-audit.sh` — Orchestrator: builds, uploads, runs, pulls results
- `reports/` — Output directory per site/date (gitignored)
- `source-from-valn/` — Reference audit artifacts from VALN

See `docs/module-specs/qa-gates.md` for full spec.
