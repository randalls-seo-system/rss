# Final Handoff: LRG Neighborhood Roundup Program — 2026-08-13

## What shipped

### 28 roundup conversions live (Aug 9 + Aug 12)

**Aug 9 — 18 conversions + 5 new market pages:**
- Conversions: Fair Oaks Ranch (1722), Cibolo (1725), Alamo Heights (1730),
  Boerne (1733), Converse (1739), Dripping Springs (1742), Georgetown (1744),
  Lockhart (1753), Schertz (1764), Seguin (1769), Bulverde (1789),
  Pflugerville (1806), Round Rock (1813), Castle Hills (1897),
  New Braunfels (2812), San Marcos (2814), Liberty Hill (9272),
  Universal City (9499)
- New posts: Belton (9732), Buda (9733), Hutto (9734), Kyle (9735),
  Temple (9736)

**Aug 12 — 5 conversions (Group A roundup-intent titles):**
- Canyon Lake (1791), Lakeway (1800), Live Oak (1750), Helotes (1747),
  Leon Valley (1820)

All: nh-rank format, author Jason Szakel (28), _lrg_no_wpautop=1,
honest methodology, commute data sourced via OSRM routing engine.

### 9 single-guide pages remediated (Aug 10)

Posts 9554 (Buda), 9555 (Manor), 9556 (Hutto), 9562 (Kyle),
9563 (Taylor), 9605 (Belton), 9607 (Temple), 9609 (Nolanville),
9611 (Salado): fabricated Census/FEMA sources replaced with honest
methodology disclosure, 32 FH phrases fixed (semantic review, not
regex), doubled school names fixed, broken Salado CTAs fixed.

### Quality fixes across all neighborhood content (Aug 13)

- 43 unsourced "top-rated" school claims cut across 14 posts
- 18 scorecard placeholders ("See guide", "See below", "Varies")
  removed from 9 July single-guide pages
- Live Oak (1750) tagline rewritten from filler to feature-based

## Reverted

- **Manor (9555):** Deployed as roundup, restored within session.
  Post is "Manor, TX: 2026 Neighborhood Guide" — guide intent, not
  roundup intent.
- **Taylor (9563):** Same pattern, same result.

## Skipped

- **Bastrop (4929):** Live page is 40K with 10 neighborhoods,
  flood/wildfire hazard section (Lost Pines, 2011 Complex Fire,
  Colorado River floodplain). Roundup generator produces 26K with 6
  neighborhoods. Refresh in place, don't regenerate.
- **Stone Oak (2736):** Same class. Live page has 12 internal links,
  bold-lead callouts, narrative H2s. Regeneration was a downgrade on
  every metric.
- **Cedar Park:** Two competing posts — 1734 (slug "cedar-creek-tx",
  wrong city name, 4 clicks/90d) and 5133 (slug "cedar-park-
  neighborhood-guide", 8 clicks/90d). Deploy roundup to 5133, 301
  cedar-creek URL. Blocked on redirect implementation.
- **Harker Heights (5135):** Guide-intent title, Group B. Roundup
  file parked at `~/lrg-rewrite/roundup-output/`.

## Standing rules added to CLAUDE.md

1. **Title determines content type.** "Best Neighborhoods in X" =
   roundup intent. "X: Neighborhood Guide" = guide intent. Never
   convert a guide to a roundup. Classify by title before any batch.

2. **Positive sourcing constraints over negative bans.** "Use numbers
   ONLY from the evidence store" works; "do NOT state dollar amounts"
   doesn't. Tested: positive constraint cut fabrication 15→2; negative
   ban only got 15→9.

3. **Every prompt rule needs a mechanical backstop.** Tested failure
   rates: em dash ban ~5%, campus ban ~60%, dollar ban 100%. A prompt
   rule without a post-gen check is a suggestion.

## Pipeline gates (all HARD FAIL)

| Gate | Added | Catches |
|------|-------|---------|
| REVIEW: placeholders | Aug 12 | Unfilled editorial fields shipping to prod |
| Scorecard placeholders | Aug 13 | "See guide", "See below", "Varies", "TBD" in scorecard values |
| Unsourced school claims | Aug 13 | "top-rated"/"highly rated" near district/school without TEA year+score |
| Unsourced numbers | Aug 12 | $ amounts and drive times not in verified data (hard fail when set is empty) |
| FH phrase scan | Aug 10 | 20+ demographic/safety patterns, expanded from original 7 |
| Safety deletion | Aug 11 | "safest", "low crime", "crime-free" — delete, don't substitute |
| District contradiction | Aug 12 | "multiple ISDs" when data has one district |
| Fort Hood naming | existing | "Fort Cavazos" → "Fort Hood" |

## Open debt

1. **52 generic taglines** across 37 pages. Editorial rewriting,
   ~1 hour. Quality not compliance. Inventory at
   `~/lrg-rewrite/filler-scan-report.txt`.

2. **TEA accountability rating lookup.** Pipeline verifies district
   boundaries but not ratings. Adding a lookup would let guides make
   sourced quality claims. Currently cutting "top-rated" instead.

3. **Cedar Park consolidation.** Deploy to 5133, 301 cedar-creek URL.

4. **Post 1733 slug typo.** "best-neighborhoods-in-borne-tx" should be
   "best-neighborhoods-in-boerne-tx". Requires 301.

5. **5 deferred cities (thin SERP):** Copperas Cove, Pleasanton,
   Spring Branch, Nolanville, Windcrest.

6. **7 deferred cities (too small):** Fischer, Bergheim, Garden Ridge,
   Selma, Poteet, Castroville, Salado.

7. **5 SA enclaves (wrong content type):** Olmos Park, Terrell Hills,
   Balcones Heights, Hollywood Park, Shavano Park — single-guide or
   SA flagship entry, not standalone roundups.

8. **Price data pull.** Would restore 4-row scorecards and price bars.
   ~10 min/city from listings.

9. **AUTHOR_LANE_MAP config parser.** Multi-line values return empty
   string. Roundup generator hardcodes override_id=28.

10. **FH semantic review of 30 July-batch roundups.** Regex caught 7
    of 32 on the 9 tested. The other 30 need the same full read.

## Backups

| Backup | Location |
|--------|----------|
| Aug 9 conversions (18) | `~/lrg-rewrite/backups/pre-roundup-convert-20260809-151836/` |
| Aug 10 source/FH remediation (9) | `/nas/.../backups/guide-remediation-20260810/` |
| Aug 12 roundup conversions (8) | `/nas/.../backups/pre-roundup-batch2-20260812/` |
| Aug 13 top-rated + scorecard (22) | `/nas/.../backups/fix-top-rated-20260813/` |
