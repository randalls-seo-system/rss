# Randall's SEO System (RSS)

Internal framework for delivering SEO services at scale. **v1.0 complete.**

## What This Is

A productized SEO operations system that:
- Deploys to any WordPress site in under 4 hours
- Runs technical SEO infrastructure (6 mu-plugins) automatically
- Audits sitewide content quality (anchors, links, balance)
- Manages client onboarding via reusable templates and scripts

## v1.0 Modules

| Module | Status | Description |
|--------|--------|-------------|
| Technical SEO Infrastructure | Complete | 6 mu-plugins (llms.txt, llms-full.txt, markdown variants, crawler logging, dashboard, URL config) |
| QA Gates | Complete | 4 audits: anchor splits, generic anchors, repeated URLs, link balance |
| Client Onboarding | Complete | Intake → config → render → deploy → audit → report pipeline |

## Quick Start

```bash
# Onboard a new client (full pipeline)
./tools/new-client.sh clients/<slug>/intake.md

# Deploy technical SEO to a configured site
./tools/deploy-to-site.sh sites/<slug>.conf

# Run QA audit suite
./tools/audit-runner.sh sites/<slug>.conf

# Dry-run (no server changes)
./tools/new-client.sh clients/<slug>/intake.md --dry-run
```

## Repository Structure

See `docs/architecture.md` for detailed structure.

## Operating Notes

- Built on top of patterns proven on VALN (valoannetwork.com)
- Validated on VALN and TLN (thelendersnetwork.com)
- Designed for replication to 500+ client sites
- Each client gets a config file in `sites/` (gitignored)
- Master modules update once → all sites benefit on next render+deploy

---

Internal use only. Not for external distribution.
