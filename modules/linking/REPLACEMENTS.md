# Linking Module — Template Replacements

## Source Files

| Source | Template | Purpose |
|--------|----------|---------|
| link-injector-v3.php (VALN) | link-injector.template.php | Contextual link injection with word-boundary matching |
| (new) | dedup-runner.template.php | Scan + strip repeated internal link URLs |

## Variable Mappings

| VALN Original | Template Variable | Notes |
|---------------|-------------------|-------|
| `https://valoannetwork.com` | `{{SITE_URL}}` | Already-linked detection needs full URL |
| Function names `is_restricted`, `try_inject` | `rss_link_is_restricted`, `rss_link_try_inject` | Prefixed to avoid collisions |

## Key Features

1. **Word-boundary matching**: Uses `\b` regex boundaries to prevent injecting inside longer words
2. **Restricted zone awareness**: Skips bullet-sections, callouts, tables, FAQs, headings
3. **Self-link prevention**: Compares source permalink to target URL
4. **Already-linked detection**: Checks for both relative and absolute URL forms
5. **Anchor fallback**: Tries stripped version (no leading "VA", "the", etc.) if exact match fails
6. **Streaming CSV output**: Logs every decision for audit trail

## Companion Data

- Each client needs an `anchor-map.csv` in their client directory
- Starter template: `templates/anchor-map-starter.csv`
- Format: `source_id,source_slug,target_url,anchor_text`
