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

## Remaining roundup conversions — enumerated (2026-08-11)

The original "33 remaining" was never enumerated and included county,
military, and audience roundups that are separate content types. Actual
city roundup conversion candidates: 15.

**Tier 1 — Viable (pop > 10K, SERP completed):**

| City | Metro | Pop | Existing post | SERP file |
|------|-------|-----|--------------|-----------|
| Cedar Park | Austin | ~82K | 1734/5133 | best-neighborhoods-in-cedar-park-tx.json |
| Harker Heights | Killeen | ~35K | 5135 | best-neighborhoods-in-harker-heights-tx.json |
| Copperas Cove | Killeen | ~35K | 5198 | best-neighborhoods-in-copperas-cove-tx.json |
| Taylor | Austin | ~25K | 9563 (guide) | best-neighborhoods-in-taylor-tx.json |
| Canyon Lake | SA | ~22K | 1791 | best-neighborhoods-in-canyon-lake-tx.json |
| Lakeway | Austin | ~19K | 1800 | best-neighborhoods-in-lakeway-tx.json |
| Live Oak | SA | ~18K | 1750 | best-neighborhoods-in-live-oak-tx.json |
| Manor | Austin | ~15K | 9555 (guide) | best-neighborhoods-in-manor-tx.json |
| Helotes | SA | ~12K | 1747 | best-neighborhoods-in-helotes-tx.json |
| Leon Valley | SA | ~12K | 1820 | best-neighborhoods-in-leon-valley-tx.json |
| Bastrop | Austin | ~11K | 4929 | best-neighborhoods-in-bastrop-tx.json |

**Tier 2 — Borderline (might work, might fail floor):**

| City | Metro | Pop | SERP file |
|------|-------|-----|-----------|
| Pleasanton | SA | ~10K | best-neighborhoods-in-pleasanton-tx.json |
| Spring Branch | SA | CDP | best-neighborhoods-in-spring-branch-tx.json |
| Nolanville | Killeen | ~7.4K | 9609 (guide only) |
| Windcrest | SA | ~5.8K | best-neighborhoods-in-windcrest-tx.json |

**Single-neighborhood deep-dive candidates (NOT roundups):**
Olmos Park (~2.3K), Terrell Hills (~5K), Balcones Heights (~3K),
Hollywood Park (~3.5K), Shavano Park (~4.1K) — these are enclaves
inside San Antonio. They ARE neighborhoods, not cities containing
neighborhoods. Correct content type is a single-guide or an entry in
the SA flagship roundup, not a standalone roundup.

**Deferred (too small as standalone towns):**
Poteet (~3.5K), Castroville (~3K), Salado (~2.4K) — join Fischer,
Bergheim, Garden Ridge, Selma in the deferred pool.

**Not part of the city conversion program:**
County roundups (Bexar, Travis, Williamson, Comal, Guadalupe,
Atascosa), military roundups (JBSA, Randolph, Lackland, Camp Bullis,
Fort Hood, NAS CC), and audience pages (Austin families, SA families,
Fort Sam) are separate content types. They may get refreshed but not
via the city roundup pipeline.

## Still open

1. **10 roundup conversions ready** (editorial review in progress):
   Cedar Park (7), Harker Heights (5), Taylor (6), Canyon Lake (5),
   Lakeway (6), Live Oak (6), Manor (6), Helotes (5), Leon Valley (6),
   Bastrop (6). Total: 59 neighborhoods. Builder output at
   `~/lrg-rewrite/roundup-data/`. Editorial review file at
   `~/lrg-rewrite/roundup-final-review.txt` (38 fields to edit).
   Grey Forest Estates dropped from Helotes (separate incorporated city).
   13 thin-SERP entries dropped across all cities.

2. **5 deferred (thin SERP):** Copperas Cove (1 substantive), Pleasanton
   (2), Spring Branch (3), Nolanville (3), Windcrest (2). SERP surfaced
   fewer than 5 neighborhoods with real descriptive evidence. They need
   better research (targeted SERP queries per subdivision, or local
   knowledge), not a lower floor.

3. **7 deferred (too small):** Fischer, Bergheim, Garden Ridge, Selma,
   Poteet, Castroville, Salado.

4. **Post 1733 slug typo:** "best-neighborhoods-in-borne-tx" should be
   "best-neighborhoods-in-boerne-tx". Requires 301 redirect. Decision
   from Randall.

4. **Killeen roundup (2797):** Protected flagship, excluded from all
   batches.

4b. **AUTHOR_LANE_MAP is broken in the config loader.** `load_site_config`
   cannot parse multi-line values from `.conf` files — `AUTHOR_LANE_MAP`
   returns empty string. `resolve_author()` in `lib/post_assembly.py`
   falls through to the fallback (user 27, Karishma) for every call.
   The roundup generator hardcodes `override_id=28` (Jason Szakel) as a
   workaround. Any other generator using `resolve_author()` without an
   explicit override will silently mis-assign to the fallback. Fix
   requires updating `lib/site_config.py` to handle multi-line quoted
   values, or moving the lane map to a separate JSON file.

5. **Single-guide pipeline: PARKED — scaffold-only, not production.**
   generate-neighborhood-guide.py + batch-neighborhood-rebuild.py + all
   guards committed on lrg-guides. Settled decision (2026-08-10):
   - Cannot beat hand-built content on established guides — verified data
     is thinner than the editorial knowledge behind the originals
   - Regenerated Stone Oak (2736) was a downgrade on every metric: 50%
     fewer links, 100% of bold-lead callouts lost, generic H2s, doubled
     sentinel text ("the zoned high school and the zoned high school"),
     fabricated $475K median with no data source
   - Existing guides get refreshed in place (fix facts, links, schema)
   - Net-new deep-dives get hand-built from a template copy
   - Revisit only if net-new volume changes
   - 6 post-assembly passes extracted to lib/post_assembly.py (shared
     with roundup generator) — FH scan, em dash, markdown, whitespace,
     link validation, author resolution
   - build_default_data() Census/FEMA sources removed (was root cause
     of 9 pages citing sources the generator never consulted)

6. **FH regex is a FLOOR, not a detector.** Semantic review of 9 pages
   found 32 FH hits; the regex caught 7. Categories missed: "for
   families" (demographic targeting), "family-oriented/family-friendly"
   without hyphen variants, "budget-conscious" (socioeconomic framing),
   "retirees" (age-based targeting), fit-panel demographic steering,
   FAQ questions targeting familial status. The "23 of 30 guides
   flagged" figure from the July batch therefore understates the
   problem — those 30 need the same full semantic read.

7. **9-page remediation completed (2026-08-10).** Posts 9554, 9555,
   9556, 9562, 9563, 9605, 9607, 9609, 9611: replaced fabricated
   Census/FEMA sources with honest methodology disclosure, fixed 32
   FH phrases (semantic, not regex), fixed doubled school names
   (Buda, Manor), fixed broken href="None" CTAs (Salado). Backups at
   `/nas/content/live/lrgrealtyblog/backups/guide-remediation-20260810/`.
   Cache purged, curl-verified on 9554 + 9607.
