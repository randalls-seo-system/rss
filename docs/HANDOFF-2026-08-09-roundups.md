# Handoff: Roundup Deploy — 2026-08-09

## What shipped

23 roundup pages deployed in nh-rank format (matching flagships 2794/2790/2797/2095):

**5 NEW DRAFTS (market gaps):**
- 9732 Belton, 9733 Buda, 9734 Hutto, 9735 Kyle, 9736 Temple
- Status: draft. Ready for review + publish.

**18 LIVE CONVERSIONS (flat nh-* → nh-rank):**
- 1722 Fair Oaks Ranch, 1725 Cibolo, 1730 Alamo Heights, 1733 Boerne,
  1739 Converse, 1742 Dripping Springs, 1744 Georgetown, 1753 Lockhart,
  1764 Schertz, 1769 Seguin, 1789 Bulverde, 1806 Pflugerville,
  1813 Round Rock, 1897 Castle Hills, 2812 New Braunfels, 2814 San Marcos,
  9272 Liberty Hill, 9499 Universal City
- Status: publish (unchanged). Content replaced in place.
- All byte-exact verified. All _lrg_no_wpautop=1 set.

## Backups

- Market gap drafts: no prior content (new posts)
- 18 conversions: `~/lrg-rewrite/backups/pre-roundup-convert-20260809-151836/`
  18 HTML + meta-individual.jsonl. Round-trip verified on 1744.

## Generator

`generate-roundup.py` committed on lrg-guides branch. Produces:
hero, quick-match table, price bars, N×rank blocks, methodology,
4 topical Q&A sections, fit panel, closing, FAQ. Pipeline markers
added to all LLM prompts to prevent CLAUDE.md refusals.

## Post-hoc fixes NOT yet in the generator

These were applied as manual passes after generation. Next batch
needs them folded into generate-roundup.py:

1. **FH scan + replace** — "young families" → "buyers with school-age children", "family-friendly" → "community-oriented", etc.
2. **Em dash strip** — prose only, skip style/script/JSON-LD
3. **Stray markdown conversion** — `**bold**` → `<strong>bold</strong>`
4. **Whitespace collapse fix** — re-insert spaces where link removal collapsed words
5. **Link validation** — check injected hrefs against live slugs, drop 404s

## Open items

1. **Post 1733 slug typo:** "best-neighborhoods-in-borne-tx" should be "best-neighborhoods-in-boerne-tx". Requires 301 redirect. Decision needed from Randall.

2. **5 drafts need publish:** 9732-9736 (Belton, Buda, Hutto, Kyle, Temple) are draft. Need featured images + review before publish.

3. **33 remaining roundups** need fresh SERP research before conversion. These are the flat-template roundups without Aug 3-4 SERP data.

4. **4 below-floor cities** deferred: Fischer, Bergheim, Garden Ridge, Selma — too small for 5-neighborhood roundups.

5. **Killeen roundup (2797):** Protected flagship, excluded from this batch.

6. **Single-guide pipeline:** Parked. generate-neighborhood-guide.py + batch-neighborhood-rebuild.py + all guards committed on lrg-guides but not deployed. Campus strip, sentinel handling, null-feeder check all functional.

## Working rules

- One worktree per workstream: LRG = ~/rss-lrg only
- Commit after each piece, never two sessions in one tree
- Backups before any content replacement, verified restore round-trip
- Wave deploys: 3 first, read on front end, then the rest
