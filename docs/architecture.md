# Repository Architecture

## Directory Structure
```
randalls-seo-system/
├── docs/                # Documentation
├── modules/             # Functional modules (Technical SEO, QA, etc.)
├── templates/           # Reusable templates (anchor map, intake, etc.)
├── tools/               # Top-level scripts (deploy, audit, onboard)
└── sites/               # Per-client configs (gitignored)
```

## Why This Structure

- **modules/** isolates functional concerns. Technical SEO module knows nothing about QA module. Both are composed by tools/ scripts.
- **templates/** holds reusable starting points for new clients. Each new client copies a template, customizes, and saves to sites/.
- **tools/** holds the integration layer. Scripts here orchestrate modules to perform full workflows (onboard a client, audit a client, etc.).
- **sites/** holds client-specific config. Gitignored so client data never enters version control.

## How a New Client is Onboarded (target workflow)

1. Run tools/new-client.sh
2. Fills out intake template
3. Generates sites/<client-slug>.conf
4. Runs tools/deploy-to-site.sh sites/<client-slug>.conf
5. Runs tools/audit-runner.sh sites/<client-slug>.conf
6. Reports generated, baseline captured, system live

## How Modules Get Updated

1. Update template/lib in modules/<module-name>/
2. Test on VALN (or designated dev site)
3. Run tools/sync-all-sites.sh (planned for v1.1)
4. All client sites get the update
