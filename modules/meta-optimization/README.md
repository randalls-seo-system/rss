# Meta Optimization Module

Cluster-aware title tag and meta description optimization. Uses GSC keyword cluster data + LLM generation to produce editorial-quality meta proposals that capture each page's full search footprint.

## Why Cluster-Aware?

Most meta optimization looks at the #1 keyword. But pages rank for 10-100+ queries. This module:
1. Pulls the full keyword cluster per page from GSC
2. Identifies the parent query, variants, modifiers, and gap opportunities
3. Generates title + meta that capture the entire cluster naturally
4. Deploys via WP-CLI with rollback support

## Pipeline

```
Step 1: pull-keyword-clusters.py   → keyword-clusters.json
Step 2: analyze-clusters.py        → cluster-analysis.csv
Step 3: generate-meta-proposals.py → meta-proposals.csv     ← LLM per page
Step 4: [HUMAN REVIEW]
Step 5: deploy-meta-updates.sh     → backup.csv + live updates
Step 6: submit-gsc-recrawl.py      → Indexing API notifications
```

## Usage

```bash
# 1. Pull clusters (requires candidates CSV with 'url' column)
python3 tools/pull-keyword-clusters.py \
  --site lrg \
  --candidates-csv ~/lrg-rewrite/audits/22-meta-refresh-candidates.csv \
  --output-json ~/lrg-rewrite/audits/keyword-clusters.json

# 2. Analyze clusters
python3 tools/analyze-clusters.py \
  --clusters-json ~/lrg-rewrite/audits/keyword-clusters.json \
  --candidates-csv ~/lrg-rewrite/audits/22-meta-refresh-candidates.csv \
  --output-csv ~/lrg-rewrite/audits/cluster-analysis.csv

# 3. Generate proposals (LLM-driven)
python3 tools/generate-meta-proposals.py \
  --analysis-csv ~/lrg-rewrite/audits/cluster-analysis.csv \
  --site lrg \
  --output-csv ~/lrg-rewrite/audits/meta-proposals.csv

# 4. REVIEW proposals before deploying

# 5. Deploy approved proposals
bash tools/deploy-meta-updates.sh \
  --site lrg \
  --proposals-csv ~/lrg-rewrite/audits/meta-proposals.csv

# 6. Submit for re-crawl
python3 tools/submit-gsc-recrawl.py \
  --site lrg \
  --urls-csv ~/lrg-rewrite/audits/meta-proposals.csv \
  --max 50
```

## Site Config Requirements

The following fields in `sites/<slug>.conf` are used:

| Field | Used By | Example |
|-------|---------|---------|
| `SITE_DOMAIN` | GSC property | `lrgrealty.com` |
| `SITE_NAME` | LLM prompt | `Levi Rodgers Real Estate Group` |
| `SPECIALTY` | LLM prompt (brand tone) | `VA loans, military relocation` |
| `GEO_FOCUS` | LLM prompt (location) | `San Antonio, Austin, Killeen` |
| `SSH_HOST` | Deploy | `lrgrealtyblog.ssh.wpengine.net` |
| `SSH_USER` | Deploy | `lrgrealtyblog` |
| `SSH_KEY_PATH` | Deploy | `~/.ssh/wpengine_valn` |
| `AI_MODEL` | LLM generation | `gpt-4o-mini` |
| `AI_API_KEY_ENV_VAR` | LLM generation | `OPENAI_API_KEY` |

Optional: `GSC_PROPERTY`, `GSC_SERVICE_ACCOUNT`, `BRAND_TONE`, `LOCATION_PRIMARY`

## Cost

- GSC API: free (quota-based, ~1 req/sec)
- LLM generation: ~$0.001/page with gpt-4o-mini (~150 input + 100 output tokens per page)
- 374 pages = ~$0.40

## Rollback

`deploy-meta-updates.sh` automatically creates a backup CSV with previous Yoast values before any updates. To roll back:

```bash
# The backup CSV has columns: post_id, old_yoast_title, old_yoast_meta
# Use WP-CLI to restore each row
```

## Dependencies

- Python 3.8+
- `google-auth`, `google-api-python-client` (GSC API)
- `openai` (if using OpenAI provider)
- `anthropic` (if using Claude provider)
- WP-CLI on target server
- SSH access to target server
