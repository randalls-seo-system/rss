# Client Onboarding Module

Status: Complete (v1.0)

Orchestrates the full new-client workflow: intake → config → baseline audit → render → deploy → post-deploy audit → completion report.

## Quick Start

```bash
# From intake form
../../tools/new-client.sh clients/<slug>/intake.md

# From existing config (skip intake parsing)
../../tools/new-client.sh --use-config ../../sites/<slug>.conf

# Dry-run (no server changes)
../../tools/new-client.sh clients/<slug>/intake.md --dry-run
```

## Contents

- `intake-to-config.sh` — Parses intake markdown → site .conf + URLs skeleton

See `docs/module-specs/onboarding.md` for full spec.
