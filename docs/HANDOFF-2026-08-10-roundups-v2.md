# Handoff: Roundup Pipeline v2 — 2026-08-10

## Working rules

- LRG work happens ONLY in ~/rss-lrg on branch lrg-guides
- Commit after each piece. Never two sessions in the same worktree.
- Backups before any content replacement, verified restore round-trip.
- Wave deploys: 3 first, read on front end, then the rest.

## Commits this session

| Hash | Description |
|------|-------------|
| `36270ac` | generate-roundup.py — multi-neighborhood nh-rank format |
| `35fe341` | Q&A sections + inline link injection |
| `9543045` | Pipeline marker fix (CLAUDE.md refusal prevention) |
| `64d7924` | LLM cache bust after marker addition |
| `cb3e278` | Year-stripped slugs (_slug_no_year) |
| `d81b0b4` | --city parameter (separate from --metro) + a/an grammar |
| `9610989` | 6 post-assembly cleanup passes folded into generator |
| `66f8489` | Honest methodology, price note, commute label |
| `eb23b99` | build-roundup-data.py — semi-automated neighborhoods.json builder |

## What's live

**23 roundups deployed in nh-rank format:**

5 NEW POSTS (market gaps, published with featured images):
- 9732 Belton, 9733 Buda, 9734 Hutto, 9735 Kyle, 9736 Temple

18 LIVE CONVERSIONS (flat nh-* → nh-rank, status unchanged):
- 1722 Fair Oaks Ranch, 1725 Cibolo, 1730 Alamo Heights, 1733 Boerne,
  1739 Converse, 1742 Dripping Springs, 1744 Georgetown, 1753 Lockhart,
  1764 Schertz, 1769 Seguin, 1789 Bulverde, 1806 Pflugerville,
  1813 Round Rock, 1897 Castle Hills, 2812 New Braunfels, 2814 San Marcos,
  9272 Liberty Hill, 9499 Universal City

All: author Jason Szakel (28), _lrg_neighborhood=1, _lrg_no_wpautop=1,
honest methodology, "Commute (off-peak)" labels, meter caveats.

## Backups

- 18 conversions: `~/lrg-rewrite/backups/pre-roundup-convert-20260809-151836/`
  18 HTML + meta-individual.jsonl. Round-trip verified on 1744.
- 5 new posts: no prior content (created fresh).

## Generator state (generate-roundup.py)

**6 post-assembly cleanup passes are IN the generator** (not manual):
1. FH scan + replace
2. Em dash strip (prose only)
3. Markdown ** → <strong> conversion
4. Whitespace collapse fix
5. Link validation (drops 404 hrefs against slug cache)
6. Author assignment (default 28 Jason Szakel per lane map)

**Methodology is HARDCODED** — not LLM-generated. This is intentional.
The LLM invented false MLS/CAD sourcing claims on 20 of 24 pages.
The template accurately describes: SERP research, TEA verification,
editorial assessment, publicly available listings.

**--city and --metro are separate.** City drives hero, CTAs, listings URL.
Metro drives regional context only.

**Author: automatic.** Default post_author=28 via --author arg (or lane
map default). No longer needs manual setting.

## Builder state (build-roundup-data.py)

Extracts neighborhood names from SERP data via LLM, verifies districts
via TEA API. Every field carries a source label:
- `tea-verified`: district (proven 46/46)
- `serp-extracted`: neighborhood names, taglines
- `serp-estimated`: price ranges (from competitor snippets, NOT MLS)
- `editorial`: meters (midpoint defaults), walk_label, rank order
- `NEEDS_HUMAN`: any field the LLM couldn't extract

**Test results (3-city diff):**
- Bulverde: 8 names extracted (vs 5 shipped) — different set, both valid
- Belton: 0 names — SERP was metro-level, not city-specific
- Round Rock: 2 names — SERP too broad

**Key finding:** Builder depends on SERP quality. City-specific queries
("best neighborhoods in [City] TX") work. Metro-level queries don't
surface subdivision names.

How to run:
```
python3 modules/content-production-v2/tools/build-roundup-data.py \
  --city "Georgetown" --metro "Austin" \
  --serp-json ~/lrg-rewrite/serp/georgetown-best-neighborhoods-serp.json \
  --output-dir ~/lrg-rewrite/roundup-data/
```

## What's verified vs editorial in neighborhoods.json

| Field | Source | Status |
|---|---|---|
| district | TEA ArcGIS API | Verified (46/46) |
| name | SERP extraction | Semi-automated |
| price_range | SERP competitor snippets | Estimated — NOT MLS |
| commute | Editorial estimate | Plausible but unverified, labeled "off-peak" |
| walk_label | Editorial | Default "Car-dependent" |
| meters (4 values) | Editorial midpoint defaults | NOT measurements, labeled in methodology |
| rank | Editorial | Human judgment |
| tagline | SERP-extracted or editorial | Varies |

## SERP research for 33 remaining roundups

**NOT STARTED.** The existing Aug 3-4 SERP files used metro-level
queries that don't surface subdivision names. New SERP research needs
city-specific queries: "best neighborhoods in [City] TX".

Run via analyze-serp.py (Serper.dev API, 2500/month quota). ~2 min
per query, 33 queries = ~66 min. Can run overnight unattended.

**33 cities needing SERP:**
The flat-template roundups without fresh city-specific SERP. See the
full inventory in HANDOFF-2026-08-09-roundups.md.

## Still open

1. **33 roundup conversions** pending: need city-specific SERP research,
   then builder → human review → generation → deploy.

2. **Post 1733 slug typo:** "best-neighborhoods-in-borne-tx" should be
   "best-neighborhoods-in-boerne-tx". Requires 301 redirect. Decision
   from Randall.

3. **4 below-floor cities deferred:** Fischer, Bergheim, Garden Ridge,
   Selma — too small for 5-neighborhood roundups.

4. **Killeen roundup (2797):** Protected flagship, excluded from all
   batches.

5. **Single-guide pipeline:** PARKED. generate-neighborhood-guide.py +
   batch-neighborhood-rebuild.py + all guards (FH, feeder strip, tax
   rate, em dash, confabulation, qstat) committed on lrg-guides. Not
   deployed because: the single-guide format produced flat 20KB output
   that was a downgrade vs existing content, and the roundup format
   (nh-rank, 28-32KB) proved to be the right content type for these
   pages. Single guides may be appropriate for individual
   neighborhood deep-dives later, but the priority is roundup coverage.
