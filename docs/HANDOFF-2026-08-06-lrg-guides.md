# Handoff: lrg-guides branch — 2026-08-06

## Working rules

- One worktree per workstream: LRG = ~/rss-lrg only.
- Commit after each piece. Never two sessions in one tree.

## Commits this session (~/rss-lrg, branch lrg-guides)

| Hash | Description |
|------|-------------|
| `bd6fb0f` | Publish guard — hard abort on publish status or protected posts (2794, 2790, 2797, 2095) |
| `3601faa` | Generator swap — batch runner calls generate-neighborhood-guide.py (nh-* format) |
| `e5cea06` | Source-relevance filter — pre-gen SERP cleanup, rejects off-topic results |
| `6ac125c` | Confabulation guard — post-gen advisory, flags unsupported heritage/history H2s |
| `cdab5a8` | Fair Housing scanner — advisory, validated against 30 live guides (35 hits, 23/30) |
| `0934204` | Content quality gate wiring — advisory defense-in-depth |
| `e041e98` | qstat consistency check + prompt-only labels |
| `20b5926` | vertical_block fix — threads Fair Housing rules into generator prose prompts |
| `4640163` | Stylesheet capture — live lrg-article-styles.php v1.0.4 (prod-ahead, DO NOT DEPLOY) |
| `3c1e989` | Null-feeder campus hallucination check — HARD/SOFT, per-level, tested 5 cases |

## Still open

1. **Verified-data script** — build semi-automated script for TEA district lookup + county CAD tax rates. Run for the 10 replacement guides first, show data files for approval before the 39 net-new.

2. **Queue approval** — queue JSON at ~/lrg-rewrite/batch-rebuild-queue.json. Split: 10 replace / 39 net-new / 24 deferred. Waiting for Randall's approval before any generation.

3. **Post 2095 sidebar styling** — likely cause: 2095 has `_et_pb_page_layout=et_right_sidebar` (2794 does not). `nh-qstats` is a 4-col CSS grid; in the sidebar-narrowed content column it collapses to stacked rows. Not visible via curl (computed layout, not markup). NEXT: confirm whether working guides (Sonterra 9500, Belton 9605, Stone Oak 2736) have the sidebar meta set. If only 2095 does, fix = back up 2095, remove/change the meta to match 2794, add `_lrg_no_wpautop=1`, purge cache, verify visually. Do NOT touch the stylesheet.

4. **Stylesheet reconciliation** — live v1.0.4 captured into repo but marked prod-authoritative in CLAUDE.md. Repo must not be deployed back until reconciled.

5. **First 3-5 guide generation** — not started. Requires verified-data files + queue approval first.

## 30 live July 29-31 guides — HIGHEST-STAKES OPEN ITEM

30 guides published live July 29-31 via the OLD pipeline. The FH scanner found 35 hits across 23 of them (steering language in fit-section `<dt>` items and body prose). Only 10 are replaced by this queue; the other 20 remain live and unremediated regardless of this batch. In-place FH remediation was scoped and deferred — separate task, not blocked by the batch. Plan: backup + full read of all 30 (regex is a floor — 7 showed no automated hits, 2 were spot-checked and confirmed genuinely clean), drafted replacement language for approval, then one scripted pass.

## Queue breakdown (from ~/lrg-rewrite/batch-rebuild-queue.json)

**10 REPLACE** (fresh Aug 3-4 SERP + existing live July 29-31 guide):
Universal City (9499), Buda (9554), Hutto (9556), Kyle (9562), Manor (9555), Taylor (9563), Belton (9605), Nolanville (9609), Salado (9611), Temple (9607)

**39 NET-NEW** (fresh SERP, no existing guide, placeholder post_id=0):
SA: Alamo Heights, Alamo Ranch, Alta Vista, Bergheim, Boerne, Braun Station, Bulverde, Castle Hills, Castroville, Cibolo, Converse, Encino Park, Fair Oaks Ranch, Fischer, Garden Ridge, Kallison Ranch, Schertz, New Braunfels, Quarry District, Redbird Ranch, San Marcos, Seguin, Selma, Shavano Park, Southtown, Stone Oak, Tobin Hill, Westover Hills, Windcrest
Austin: Avery Ranch, Circle C Ranch, Dripping Springs, Georgetown, Lakeway, Liberty Hill, Lockhart, Pflugerville, Round Rock
Killeen: Killeen

**24 DEFERRED** (no fresh SERP, or pre-July decent quality — need new SERP research before regeneration):
No fresh SERP (20 July 29-31 guides): Beacon Hill (9505), Berry Creek (9553), Blanco Vista (9565), Cross Mountain (9508), Davis Ranch (9507), Easton Park (9558), Falcon Pointe (9559), Government Hill (9501), Highlands at Saegert Ranch (9613), King William (9502), Mahncke Park (9503), Oak Park Northwood (9504), Paloma Lake (9560), Rancho Sienna (9564), Sonterra (9500), Steiner Ranch (9557), Sunfield (9566), Whisper Valley (9561), Woodlawn Lake (9506), Yowell Ranch (9615)
Pre-July decent quality (4): East Austin (5118), South Austin (5130), Live Oak (8211), Copperas Cove (5198)
