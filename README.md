# Randall's SEO System (RSS)

Internal framework for delivering SEO services at scale. Currently v1.0 build phase.

## What This Is

A productized SEO operations system that:
- Deploys to any WordPress site in under 4 hours
- Runs technical SEO infrastructure (5 mu-plugins) automatically
- Audits sitewide content quality (anchors, links, schema)
- Manages client onboarding via reusable templates and scripts

## v1.0 Modules

| Module | Status | Description |
|--------|--------|-------------|
| Technical SEO Infrastructure | Skeleton | 5 mu-plugins (llms.txt, markdown variants, crawler logging, dashboard, AI optimization) |
| QA Gates | Skeleton | Anchor split audit, generic anchor detection, repeated URL count, internal/external balance |
| Client Onboarding | Skeleton | Site config template, deploy script, intake form |

## Quick Start (placeholder — Day 1)

System is in skeleton phase. Real deployment workflows arrive Day 5.

## Repository Structure

See docs/architecture.md for detailed structure.

## Operating Notes

- Built on top of patterns proven on VALN
- Designed for replication to 500+ client sites
- Each client gets a config file in sites/ (gitignored)
- Master modules update once → all sites benefit

---

Internal use only. Not for external distribution.
