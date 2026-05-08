
## Article spec is the source of truth

For ANY work in modules/content-production-v2/, read these first:
- docs/article-spec.md (the canonical Article Spec)
- docs/v2-module-architecture.md (file structure and module relationships)

When the spec and the code disagree, the spec wins. When the spec is unclear,
flag it for Randall — do not improvise.

## Frozen modules

The following modules are frozen during v2 build and MUST NOT be modified:
- modules/content-production/ (v1, kept as baseline)
- All mu-plugin modules (technical-seo, schema, redirects, linking, qa-gates, analytics)

If a v2 task seems to require modifying a frozen module, stop and ask.
