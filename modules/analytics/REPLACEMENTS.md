# Analytics Module — Template Replacements

## Source Files

| Source | Template | Purpose |
|--------|----------|---------|
| valn-analytics-head.php | analytics-head.template.php | Consolidated GTM + Meta Pixel injection |
| valn-form-submit-guard.php | form-submit-guard.template.php | Form dedup + error handling |

## Variable Mappings

| VALN Original | Template Variable | Notes |
|---------------|-------------------|-------|
| `GTM-PFBDZC36` | `{{GTM_CONTAINER_ID}}` | Empty = GTM disabled |
| `787887528011596` | `{{META_PIXEL_ID}}` | Empty = Pixel disabled |
| Form ID `9` | `{{LEAD_FORM_ID}}` | Empty = form guard inactive |
| `valn_submit_uuid` | `{{SITE_PREFIX}}_submit_uuid` | POST field name |
| `valn_lead_uuid_` | `{{SITE_PREFIX}}_lead_uuid_` | Transient key prefix |
| `VALN Submit Guard` | `{{SITE_PREFIX_UPPER}} Submit Guard` | Log tag |
| `VA Loan Network Form 9` | `{{SITE_NAME}} Form {{LEAD_FORM_ID}}` | Pixel event content_name |

## Architectural Changes

1. **Conditional output**: GTM and Meta Pixel blocks check if their ID is empty and skip output if so. VALN always output both.
2. **Form guard JS dependency**: Removed `valn-form-tracker` dependency (that's VALN-specific abandon tracking). Base guard only requires jQuery.
3. **Companion JS**: The form-submit-guard.js client-side file is NOT templated here — it needs to be created per-client or use a generic version. The PHP mu-plugin references `<prefix>-form-submit-guard.js` in mu-plugins/.

## New Config Variables

```conf
GTM_CONTAINER_ID=""
META_PIXEL_ID=""
LEAD_FORM_ID=""
```
