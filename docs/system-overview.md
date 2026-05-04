# System Overview

## Vision

Randall's SEO System is a productized framework that lets the agency operate 500+ client sites with a small team. The system absorbs the work that traditional agencies pay US labor to do — anchor management, audits, technical SEO, deploys, monitoring — and delivers it through automation managed by a team of Filipino contractors under Randall's operational lead.

## Architecture Model

Framework + per-site configuration:
- Master scripts live in this repo
- Each client has a config file (sites/*.conf)
- Update master scripts → all sites benefit on next sync
- Config-driven, not site-specific code

## Module Architecture

Each module follows this pattern:
```
modules/<module-name>/
├── README.md           # What this module does
├── deploy.sh           # How to deploy this module to a site
├── verify.sh           # How to verify it's working post-deploy
├── templates/          # Template files with config placeholders
└── lib/                # Shared library code
```

## v1.0 Scope (current build)

Three modules ship:
1. Technical SEO Infrastructure
2. QA Gates
3. Client Onboarding

## v1.0 Acceptance Criteria

System is "v1.0 done" when:
- A new WordPress site can be onboarded in under 4 hours of human time
- All 5 mu-plugins deploy and verify clean
- Initial audit produces actionable report
- Baseline metrics captured (crawler hits, indexation, rankings)
- Onboarding doc is complete enough that a contractor could follow it

## v1.1+ Roadmap (deferred)

- Content Generation Standards module
- Linking Architecture module (injector + dedup)
- Operational Tooling module (SSH wrappers, deploy automation)
- Performance Reporting module (auto-generated client reports)
- Multi-site monitoring dashboard

## Operating Constraints

- All sites assumed to be WordPress on shared/managed hosting (WP Engine primarily, others as needed)
- All sites assumed to use Yoast for SEO
- Mu-plugin pattern requires server filesystem access via SSH
- System is operated by Randall + Filipino contractors managed by Randall

## Out of Scope (forever)

- Non-WordPress sites
- Sites without SSH access
- Sites where client refuses standard infrastructure deployment
- Bespoke per-client custom development beyond config
