# Redirect Management Module

Manages URL redirects for RSS client sites. Handles the full lifecycle:
discovery, validation, deployment, and verification.

## Tools

### generate-redirect-map.py

Analyzes GSC URL data to identify URLs needing redirects (date-path patterns,
hash suffixes, slug changes) and produces a redirect map CSV.

```bash
python3 tools/generate-redirect-map.py --site lrg \
    --gsc-csv gsc-export.csv --output redirects/lrg-redirect-map.csv
```

### validate-redirect-targets.py

Checks each redirect target returns HTTP 200. Run this BEFORE deploying.

```bash
python3 tools/validate-redirect-targets.py --site lrg \
    --input redirects/lrg-redirect-map.csv \
    --output redirects/lrg-redirect-map-VALIDATED.csv
```

Exit code 2 if any targets return 404.

### deploy-redirects.sh

Generates deployment artifacts (Redirection plugin CSV or mu-plugin PHP).

```bash
# Redirection plugin import (default):
./tools/deploy-redirects.sh sites/lrg.conf redirects/lrg-redirect-map.csv \
    --method plugin --group "LRG Squarespace cleanup"

# mu-plugin (server-side):
./tools/deploy-redirects.sh sites/lrg.conf redirects/lrg-redirect-map.csv \
    --method mu-plugin
```

### verify-redirects-live.py

Post-deploy verification. Confirms each redirect returns 301 to the correct target.

```bash
python3 tools/verify-redirects-live.py --site lrg \
    --input redirects/lrg-redirect-map.csv \
    --output redirects/lrg-verification.csv
```

## Workflow

```
GSC Export → generate-redirect-map.py → redirect-map.csv
                                            ↓
                              validate-redirect-targets.py
                                            ↓
                              All targets 200? ──No──→ Fix targets first
                                    ↓ Yes
                              deploy-redirects.sh (staging)
                                    ↓
                              verify-redirects-live.py (staging)
                                    ↓
                              deploy-redirects.sh (production)
                                    ↓
                              verify-redirects-live.py (production)
```

## Deployment Notes

**Do NOT deploy redirects if targets return 404.** A redirect to a 404 is
worse than no redirect — it burns the redirect equity and confuses crawlers.

**LRG status (2026-05-06):** 42 redirects generated, 41/42 targets return 404.
Blocked on WordPress permalink migration to `/lrg-blog/%postname%/`.
Re-validate after migration completes.

## File Structure

```
modules/redirect-management/
├── README.md
├── tools/
│   ├── generate-redirect-map.py
│   ├── validate-redirect-targets.py
│   ├── deploy-redirects.sh
│   └── verify-redirects-live.py
├── prompts/
│   └── redirect-strategy.md
└── examples/
    └── lrg-redirect-deployment.md
```
