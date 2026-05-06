# Audit Module

Read-only content audit workflow that orchestrates WordPress inventory +
GSC traffic analysis to produce actionable triage reports.

**Safety:** This module never modifies WordPress content. All operations
are read-only. SSH calls include 1-second sleep between WP-CLI commands.

## Quick Start

```bash
# Full audit with GSC export:
bash modules/audit/tools/run-audit.sh \
    --site lrg \
    --skip-gsc-pull \
    --gsc-export ~/Downloads/lrgrealty.com-Performance-on-Search-2026-05-06.zip

# Rerun analysis only (skip inventory pull):
bash modules/audit/tools/run-audit.sh \
    --site lrg --skip-inventory --skip-gsc-pull \
    --gsc-export ~/Downloads/lrgrealty.com-Performance-on-Search-2026-05-06.zip
```

## Workflow

```
                    sites/<slug>.conf
                          │
                          ▼
              ┌─── pull-content-inventory.py ───┐
              │                                  │
              │         pull-gsc-data.py ────────┤
              │              │                   │
              ▼              ▼                   ▼
    ┌─────────────┐  ┌──────────────┐  ┌────────────────┐
    │ all-posts   │  │ gsc-pages    │  │ gsc-queries    │
    │ .csv        │  │ .csv         │  │ .csv           │
    └──────┬──────┘  └──────┬───────┘  └────────┬───────┘
           │                │                    │
     ┌─────┴────────────────┴────────────────────┘
     │
     ├──→ identify-deletes.py      → delete-candidates.csv
     ├──→ identify-slug-issues.py  → slug-issues.csv
     ├──→ identify-meta-candidates.py → meta-candidates.csv
     ├──→ identify-priority-rewrites.py → priority-rewrites.csv
     ├──→ identify-cannibalization.py → cannibalization.csv
     └──→ triage-classify.py       → triage.csv
                    │
                    ▼
          generate-summary.py → 00-AUDIT-SUMMARY.md
```

## Tools

| Tool | Purpose | Requires SSH |
|------|---------|-------------|
| run-audit.sh | Master orchestrator | - |
| pull-content-inventory.py | WP post inventory | Yes |
| pull-gsc-data.py | GSC data extraction | No |
| identify-deletes.py | Zero-traffic delete candidates | No |
| identify-slug-issues.py | Date-prefix/hash slug detection | No |
| identify-meta-candidates.py | High-impression low-CTR pages | No |
| identify-priority-rewrites.py | Page 2-3 ranking opportunities | No |
| identify-cannibalization.py | Near-duplicate pair detection | No |
| triage-classify.py | Tier A/B classification | Yes |
| generate-summary.py | Summary report builder | No |

## Site Config Requirements

The `sites/<slug>.conf` file must have:
- `SSH_HOST`, `SSH_USER`, `SSH_KEY_PATH` — for WP-CLI access
- `SITE_NAME`, `SITE_DOMAIN` — for reports

## Output Format

All tools output standard CSVs with headers. The summary report is
markdown. Outputs go to `--output-dir` (default: `~/<site>-rewrite/audits/`).

## Shared Library

`lib/wp_cli_client.py` provides a reusable WP-CLI SSH client used by
inventory and triage tools. Can be imported by other RSS modules.

## File Structure

```
modules/audit/
├── README.md
├── tools/
│   ├── run-audit.sh
│   ├── pull-content-inventory.py
│   ├── pull-gsc-data.py
│   ├── identify-deletes.py
│   ├── identify-slug-issues.py
│   ├── identify-meta-candidates.py
│   ├── identify-priority-rewrites.py
│   ├── identify-cannibalization.py
│   ├── triage-classify.py
│   └── generate-summary.py
├── lib/
│   └── wp_cli_client.py
└── examples/
    └── lrg-audit-2026-05-06.md
```
