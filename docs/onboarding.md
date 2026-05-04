# Client Onboarding

## Overview

The full process of bringing a new client onto RSS infrastructure. Target: under 4 hours human time from intake to live.

## Prerequisites

- Client has signed engagement
- SSH access provided to their hosting
- WP admin credentials secured (in password manager, not in repo)

## Step-by-Step

1. **Receive intake** — Client/sales fills `templates/intake-form-template.md`
2. **Save to** `clients/<slug>/intake.md`
3. **Generate config** — `./modules/onboarding/intake-to-config.sh clients/<slug>/intake.md`
4. **Map content** — Fill in `sites/<slug>-llms-urls.php` with site's top pages
5. **Run onboarding** — `./tools/new-client.sh clients/<slug>/intake.md`
6. **Review baseline audit** — Identify quick wins in `clients/<slug>/audits/baseline-*/`
7. **Verify deployment** — Spot-check /llms.txt, ?format=md, AI Crawlers dashboard
8. **Begin 30-day plan** — Follow `clients/<slug>/30-day-tasks.md`

## One-Command Onboarding

```bash
# Full pipeline (after intake is filled out):
./tools/new-client.sh clients/<slug>/intake.md

# With existing config:
./tools/new-client.sh --use-config sites/<slug>.conf

# Dry-run (pre-flight only):
./tools/new-client.sh clients/<slug>/intake.md --dry-run

# Skip deploy (audits only):
./tools/new-client.sh --use-config sites/<slug>.conf --skip-deploy
```

## Time Budget

| Step | Time |
|---|---|
| Intake processing | 15 min |
| Pre-flight + baseline audit | 30 min |
| Technical SEO render + deploy | 30 min |
| Post-deploy verification | 15 min |
| llms-urls.php content mapping | 60-90 min (manual) |
| 30-day task customization | 30 min |
| **Total** | **3-4 hours** |

## What Happens After Onboarding

- **Week 1:** Active engagement, daily check-ins, content mapping
- **Weeks 2-4:** Per the 30-day task list
- **Day 30+:** Steady state — weekly QA audits, monthly reports
