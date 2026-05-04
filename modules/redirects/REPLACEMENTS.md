# Redirects Module — Template Replacements

## Source Files

| Source | Template | Purpose |
|--------|----------|---------|
| valn-redirect-engine.php (324 lines) | redirect-engine.template.php | Data-driven 301 handler |
| base-purge-410.php (60 lines) | purge-410.template.php | Data-driven 410 handler |
| force-enable-indexing.php (50 lines) | force-enable-indexing.template.php | Force blog_public=1 |

## Architectural Changes

1. **Redirect engine**: VALN had 200+ hardcoded redirects in a static array. Template loads from a companion PHP file (`<prefix>-redirect-map.php`) that returns an array. This separates code from data and makes redirects manageable per-client.

2. **410 handler**: VALN had hardcoded regex patterns for military-bases and guides. Template loads patterns from a companion PHP file (`<prefix>-410-patterns.php`). Supports both exact paths and regex patterns.

3. **Force indexing**: No changes needed — fully generic. Only template variable is the comment header.

## Companion Data Files

Each client gets two data files deployed alongside the mu-plugins:
- `<prefix>-redirect-map.php` — returns array of old_path => new_path
- `<prefix>-410-patterns.php` — returns array of pattern => true/false

These are generated as empty starters during render and populated per-client.

## Variable Mappings

| VALN Original | Template Variable | Notes |
|---------------|-------------------|-------|
| `valn-redirect-engine.php` filename | `{{SITE_PREFIX}}-redirect-engine.php` | Standard prefix |
| Hardcoded redirect array | External data file | Architectural change |
| `base-purge-410.php` VALN patterns | External data file | Architectural change |
