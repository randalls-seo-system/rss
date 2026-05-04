# Schema Module — Template Replacements

## Source Files (VALN production, pulled 2026-05-04)

| Source | Template | Lines |
|--------|----------|-------|
| valn-faq-schema.php | faq-schema.template.php | 175 → 148 |
| valn-schema-cleaner.php | schema-cleaner.template.php | 93 → 80 |
| valn-org-id.php | org-id.template.php | 12 → 16 |

## Variable Mappings

| VALN Original | Template Variable | Example (VALN) | Example (LRG) |
|---------------|-------------------|----------------|----------------|
| `VALN_FAQSC_*` | `{{SITE_PREFIX_UPPER}}_FAQSC_*` | `VALN_FAQSC_TTL` | `LRG_FAQSC_TTL` |
| `valn_faqsc_*` | `{{SITE_PREFIX}}_faqsc_*` | `valn_faqsc_get_freq` | `lrg_faqsc_get_freq` |
| `valn_faq_schema_freq` | `{{SITE_PREFIX}}_faq_schema_freq` | wp_options key | wp_options key |
| `VALN_Schema_Cleaner` | `{{SITE_PREFIX_UPPER}}_Schema_Cleaner` | class name | `LRG_Schema_Cleaner` |
| `VA Loan Network` | `{{SITE_NAME}}` | org name in schema | `LRG Realty Blog` |
| `is_page(385)` | `{{FORM_PAGE_SLUG}}` slug check | Hardcoded post ID | Slug-based (portable) |

## Architectural Changes from Source

1. **Form page exclusion**: Changed from hardcoded `is_page(385)` to slug-based `$post->post_name === $skip_slug`. Slug-based is portable across environments.
2. **Divi filter in cleaner**: Kept `et_builder_render_layout` filter. Non-Divi sites will simply never trigger it (no performance cost).
3. **vlnFaq CSS class dependency**: FAQ schema depends on content using `class="vlnFaq"` markup. Sites using the RSS content system will have this; others need the FAQ detection pattern updated.
