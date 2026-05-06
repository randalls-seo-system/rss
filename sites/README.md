# Client Site Configurations

This directory holds per-client configuration files. All actual configs are gitignored to keep client data private.

Each client gets a `<client-slug>.conf` file matching the format in `templates/site-config-template.conf`.

Current clients (manually tracked, configs not in git):
- valn (Randall's primary)
- lrg (Levi Rodgers Real Estate Group)
- tln (Randall's, future migration)
- canopy (Randall's, future migration)
- gfp (Randall's pizza site)

## Brand Voice Section

Every site config that uses LLM-generated content must include a `[branding]` INI section at the bottom of the file. This is read by `modules/brand-voice/tools/render-prompt.py` to inject voice rules into LLM prompts.

Required fields:
```ini
[branding]
archetype = realtor          # Which archetype from modules/brand-voice/archetypes/
market_primary = San Antonio # Primary market for locale-specific language
markets_secondary = Austin, Killeen  # Additional markets
broker_name = Levi Rodgers   # Agent/broker name
brand_name = LRG             # Short brand name
brand_suffix_short = LRG     # For title tags (short form)
brand_suffix_long = Levi Rodgers Real Estate Group  # For formal contexts
audience_primary = homebuyers and homesellers in San Antonio
audience_secondary = Military families and Veterans
specialties = Military relocations, first-time buyers, neighborhoods
```

Available archetypes: `realtor` (more coming: `insurance-agent`, `mortgage-lender`)
