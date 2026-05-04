# Onboarding Module

## Status: Complete (v1.0)

## What This Module Does

Orchestrates the full new-client workflow from intake form to live deployment with audits.

## Workflow

```
Intake Form → Config Generation → Baseline Audit → Render → Deploy → Post-Deploy Audit → Report
```

## Components

| Component | File | Purpose |
|---|---|---|
| Intake form | `templates/intake-form-template.md` | Structured data collection |
| Config converter | `modules/onboarding/intake-to-config.sh` | Parses intake → .conf + URLs skeleton |
| Orchestrator | `tools/new-client.sh` | Runs full pipeline end-to-end |
| 30-day template | `templates/first-30-days-template.md` | Post-onboarding task checklist |

## Integration

- **Step 3** calls `modules/qa-gates/run-audit.sh` for baseline audit
- **Step 4** calls `modules/technical-seo/render.sh` for template rendering
- **Step 5** calls `modules/technical-seo/deploy.sh` for deployment
- **Step 6** calls `modules/qa-gates/run-audit.sh` for post-deploy audit

## Output Structure

```
clients/<slug>/
├── intake.md
├── onboarding-complete-<date>.md
├── 30-day-tasks.md
└── audits/
    ├── baseline-<date>/
    └── post-deploy-<date>/
```

## Flags

- `--dry-run` — Pre-flight + render only, no SSH operations
- `--skip-deploy` — Run audits without deploying mu-plugins
- `--use-config <path>` — Skip intake parsing, use existing .conf

## Validation

Tested end-to-end on VALN with `--skip-deploy`:
- Config validation: PASS
- SSH + WP-CLI: PASS
- Baseline audit: 247 issues (matches Day 4 results)
- Render: 7 files
- Post-deploy audit: 247 issues (matches baseline — no deploy)
- Completion report + 30-day tasks: Generated
