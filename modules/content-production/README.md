# Content Production Module

Productized article rewrite pipeline using Rank Logic components and SERP-grounded content.

## Usage

```bash
./tools/rewrite-article.sh <site_slug> <post_id>
```

Requires `sites/<site_slug>.conf` to exist with SSH and brand config.

## Pipeline Steps

1. Pull post metadata (slug, title, status)
2. Backup original content to `~/SLUG-rewrite/backups/`
3. Pull SerpAPI data for SERP grounding (optional, needs SERPAPI_KEY)
4. Detect intent type (Decision / Process / Comparison / News / Definition)
5. Generate ATF + BTF article HTML using rl-* templates
6. Push as draft via WP-CLI (preserves URL, slug, author)

## Intent Detection

| Intent | Signal | Template | Prompt |
|--------|--------|----------|--------|
| Decision | "X vs Y", "which", "should I" | intent-decision.html | atf-decision.md |
| Process | "how to", "step by step", "guide" | intent-process.html | atf-process.md |
| Comparison | "best X", "top X", "ranked" | intent-comparison.html | atf-comparison.md |
| News | rates, updates, market changes | intent-news.html | atf-news.md |
| Definition | "what is", "explained" | intent-definition.html | atf-definition.md |

## File Structure

```
tools/rewrite-article.sh    Main pipeline script
prompts/atf-*.md             Intent-specific ATF generation prompts
lib/                         Shared utilities (TBD)
```

## Safety Rules

- Drafts only — never publishes
- Backs up original content before any write
- Single SSH connection at a time
- Sleep 3-5s between DB writes
- Log all output to ~/SLUG-rewrite/logs/
