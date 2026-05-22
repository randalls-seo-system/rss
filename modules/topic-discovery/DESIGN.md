# Topic Discovery Module — Design Document

**Status:** Design complete, awaiting implementation (Session 2).
**Author:** Claude Opus / Randall
**Date:** 2026-05-22

---

## Architecture

### Purpose

The topic-discovery module produces a ranked, scored queue of topics a site
should write about, based on seed terms, competitor coverage analysis, and SERP
gap detection. Its output feeds directly into content-production-v2's
`assemble-article.py` as the `--target-keyword` and `--intent` inputs.

### What It Produces

A SQLite database (`data/topics.db`) containing scored topic candidates per
site, plus a CSV export (`topic-queue-{site}.csv`) for human review. Each row
includes: keyword, detected intent, estimated search volume, competition score,
priority score, whether the site already covers it, how many competitors rank
for it, suggested word count, and suggested archetype.

### Non-Goals (Explicit)

- **Not a ranking predictor.** Priority score estimates editorial value, not
  predicted SERP position.
- **Not a content generator.** This module discovers and scores topics. It does
  not write articles — that is content-production-v2's job.
- **Not a scheduler.** It does not decide when to publish or manage a content
  calendar. It produces a ranked queue; humans decide execution order.
- **Not a keyword tracker.** It does not monitor ranking changes over time.
  That belongs in a future analytics module.

---

## Data Storage

### Why SQLite (not CSV)

SQLite supports dedup via UNIQUE constraints, indexed queries across thousands
of candidates, and atomic updates — none of which are possible with flat CSV
files that grow stale and collide during concurrent runs. The database lives at
`modules/topic-discovery/data/topics.db` and is gitignored; the CSV export is
a read-only snapshot for human review.

### Schema: `topics` Table

```sql
CREATE TABLE IF NOT EXISTS topics (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    site_slug       TEXT    NOT NULL,
    keyword         TEXT    NOT NULL,
    keyword_normal  TEXT    NOT NULL,  -- lowercase, stripped, for dedup
    intent          TEXT,              -- definition|process|decision|cost|comparison
    est_volume      INTEGER DEFAULT 0,
    competition_score REAL  DEFAULT 0.0,  -- 0.0-1.0, higher = harder
    we_have_it      INTEGER DEFAULT 0,    -- boolean: site already covers this
    existing_url    TEXT,              -- URL if we_have_it = 1
    competitors_with_it INTEGER DEFAULT 0,
    competitor_urls TEXT,              -- JSON array of competitor URLs covering this
    priority_score  REAL    DEFAULT 0.0,
    suggested_wc    INTEGER DEFAULT 0,
    suggested_archetype TEXT,
    status          TEXT    NOT NULL DEFAULT 'new'
                    CHECK(status IN ('new','queued','drafting','published','rejected')),
    source          TEXT,              -- how discovered: seed|expansion|competitor|paa
    discovered_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
    last_scored_at  TEXT,
    notes           TEXT,

    UNIQUE(site_slug, keyword_normal)
);

CREATE INDEX IF NOT EXISTS idx_topics_site_status ON topics(site_slug, status);
CREATE INDEX IF NOT EXISTS idx_topics_site_priority ON topics(site_slug, priority_score DESC);
CREATE INDEX IF NOT EXISTS idx_topics_keyword_normal ON topics(keyword_normal);
```

### Schema: `competitor_pages` Table

```sql
CREATE TABLE IF NOT EXISTS competitor_pages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    site_slug   TEXT    NOT NULL,
    competitor  TEXT    NOT NULL,  -- domain (e.g., veteransunited.com)
    url         TEXT    NOT NULL,
    title       TEXT,
    h1          TEXT,
    crawled_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),

    UNIQUE(site_slug, url)
);

CREATE INDEX IF NOT EXISTS idx_comp_pages_site ON competitor_pages(site_slug, competitor);
```

### Schema: `seed_terms` Table

```sql
CREATE TABLE IF NOT EXISTS seed_terms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    site_slug   TEXT    NOT NULL,
    term        TEXT    NOT NULL,
    added_at    TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S','now')),
    last_expanded_at TEXT,

    UNIQUE(site_slug, term)
);
```

### Dedup: Canonical Keyword Normalization

Dedup uses the `keyword_normal` column, computed by:

1. Lowercase the keyword.
2. Strip leading/trailing whitespace.
3. Collapse internal whitespace to single spaces.
4. Remove trailing punctuation (`?`, `.`, `!`).
5. Singular/plural normalization is NOT applied (too error-prone for
   domain-specific terms like "VA loans" vs "VA loan").

Two candidates with the same `keyword_normal` for a site are considered
duplicates. The first-discovered row wins; subsequent matches update
`competitors_with_it` and `competitor_urls` but do not create new rows.

---

## Config Additions (Per Site)

New `[topic_discovery]` INI section appended to `sites/<slug>.conf`:

```ini
[topic_discovery]
seed_terms =
    VA loan
    VA mortgage
    VA funding fee
    certificate of eligibility
    IRRRL
    VA refinance
    VA jumbo
    VA cash-out
    VA loan limits
    VA appraisal
    VA loan credit requirements
    getting a VA loan with bad credit
    VA manual underwriting

competitors =
    veteransunited.com
    navyfederal.org
    veteransfirstmortgage.com

serp_mode = money_pages_only
max_candidates_per_run = 200
refresh_cadence = on_demand

excluded_keywords =
    VA loan network
    valoannetwork
    veterans united reviews

# Priority scoring weights (sum to 1.0)
w_competitor_coverage = 0.35
w_volume = 0.25
w_intent_value = 0.25
w_competition_inverse = 0.15
```

### Field Definitions

| Field | Type | Description |
|---|---|---|
| `seed_terms` | multi-line | One seed keyword per line. Drives Stage 1 expansion. |
| `competitors` | multi-line | One domain per line. Drives Stage 2 crawl. |
| `serp_mode` | enum | `always`: SERP every candidate. `money_pages_only`: SERP only candidates with transactional/cost/decision intent. `never`: skip SERP (fastest, least accurate). |
| `max_candidates_per_run` | int | Cap on total candidates processed per invocation. Prevents runaway SERP costs. |
| `refresh_cadence` | enum | `on_demand`: run only when invoked. `weekly`: future cron support (not in v0). |
| `excluded_keywords` | multi-line | Keywords to never surface as candidates (brand terms, irrelevant). |
| `w_competitor_coverage` | float | Weight for competitor coverage factor in priority score. |
| `w_volume` | float | Weight for estimated volume factor. |
| `w_intent_value` | float | Weight for intent commercial value factor. |
| `w_competition_inverse` | float | Weight for inverse competition factor. |

---

## Data Flow (Pipeline Stages)

### Stage 1: Seed Expansion

**Purpose:** Expand seed terms into a broad candidate list using SERP autocomplete, related searches, and People Also Ask.

| | |
|---|---|
| **Input** | `seed_terms` from site config |
| **Output** | Candidate keyword list (written to `topics` table with `source='expansion'`) |
| **Dependencies** | Serper API (related searches + PAA endpoints) |
| **LLM** | None |
| **Est. cost/run** | ~15-40 Serper queries (1-3 per seed term). Free tier: 2500/month. |
| **Est. runtime** | 30-90 seconds |

Method:
1. For each seed term, query Serper for `related_searches` and `paa`.
2. Also query Serper autocomplete (`q={seed} a`, `q={seed} b`, ... through
   high-value prefixes like "how", "best", "cost", "vs").
3. Collect all unique expansions. Normalize and insert into `topics` table.

### Stage 2: Competitor Crawl

**Purpose:** Discover what topics competitors cover by parsing their sitemaps and key category pages.

| | |
|---|---|
| **Input** | `competitors` from site config |
| **Output** | `competitor_pages` table populated; `topics` table updated with `competitors_with_it` counts |
| **Dependencies** | HTTP requests (requests library), XML parsing (lxml) |
| **LLM** | None |
| **Est. cost/run** | 0 API cost. 3-10 HTTP requests per competitor. |
| **Est. runtime** | 30-60 seconds |

Method:
1. Fetch `https://{competitor}/sitemap.xml` (follow sitemap index if present).
2. Extract all page URLs and titles from `<url><loc>` entries.
3. Insert into `competitor_pages` table.
4. For each competitor page title, normalize and check against `topics` table.
   If match found, increment `competitors_with_it` and append URL to
   `competitor_urls`.

### Stage 3: Candidate Dedup + Canonicalization

**Purpose:** Merge duplicates, apply exclusion list, enforce `max_candidates_per_run`.

| | |
|---|---|
| **Input** | Raw candidates in `topics` table |
| **Output** | Deduped, filtered candidate set |
| **Dependencies** | None (pure SQL/Python) |
| **LLM** | None |
| **Est. cost/run** | $0 |
| **Est. runtime** | <5 seconds |

Method:
1. Apply `keyword_normal` dedup (UNIQUE constraint handles inserts;
   this stage merges any edge cases).
2. Remove candidates matching `excluded_keywords`.
3. If candidate count exceeds `max_candidates_per_run`, keep all
   with `competitors_with_it > 0` first, then fill remaining slots
   by diversity of source.

### Stage 4: Existing-Content Scrape

**Purpose:** Determine which candidates the site already covers.

| | |
|---|---|
| **Input** | Deduped candidates in `topics` table, site domain from config |
| **Output** | `we_have_it` and `existing_url` updated in `topics` table |
| **Dependencies** | Site's `sitemap.xml` or WP REST API |
| **LLM** | None |
| **Est. cost/run** | 0 API cost. 1-3 HTTP requests to own site. |
| **Est. runtime** | 15-30 seconds |

Method:
1. Fetch the site's own `sitemap.xml` (or use WP REST API
   `/wp-json/wp/v2/posts?per_page=100&page=N` to get all post slugs/titles).
2. For each candidate keyword, check if a site URL's slug or title
   contains the normalized keyword (fuzzy match on slug tokens).
3. Set `we_have_it = 1` and `existing_url` for matches.

### Stage 5: SERP Fetch for Top Candidates

**Purpose:** Get SERP data (top 10 organic results) for candidates that need scoring.

| | |
|---|---|
| **Input** | Candidates where `we_have_it = 0` and status is `new` |
| **Output** | SERP results cached to disk (same `~/.cache/rss-llm/` pattern as content-production-v2) |
| **Dependencies** | Serper API (primary) + SerpAPI (fallback) |
| **LLM** | None |
| **Est. cost/run** | Up to `max_candidates_per_run` Serper queries. At 200 candidates, ~200 queries (~8% of free monthly quota). |
| **Est. runtime** | 3-8 minutes (rate-limited to ~1 req/sec) |

Method:
1. Filter candidates by `serp_mode`:
   - `always`: SERP all candidates where `we_have_it = 0`.
   - `money_pages_only`: SERP only cost/decision/comparison intent candidates.
   - `never`: skip entirely (Stage 6 uses defaults).
2. For each candidate, query Serper for top 10 organic results.
3. Cache results to `~/.cache/rss-serp/{site_slug}/{keyword_hash}.json`.
4. Rate limit: 1 request per second, back off to 5s on 429.

### Stage 6: Intent Classification + Priority Scoring

**Purpose:** Classify each candidate's search intent and compute priority score.

| | |
|---|---|
| **Input** | Candidates from `topics` table + cached SERP data |
| **Output** | `intent`, `competition_score`, `priority_score`, `suggested_wc`, `suggested_archetype` updated |
| **Dependencies** | LLM (OpenAI gpt-5.4-mini) for intent classification |
| **LLM** | gpt-5.4-mini via openai provider. Batched: up to 20 keywords per prompt. |
| **Est. cost/run** | ~10 batched LLM calls at 200 candidates. ~$0.02-0.05 total. |
| **Est. runtime** | 30-90 seconds |

Method:
1. **Intent classification:** Batch candidates in groups of 20. Prompt
   gpt-5.4-mini to classify each keyword into one of the 5 intent types
   (definition, process, decision, cost, comparison) per article-spec
   Section 1.
2. **Competition score:** From SERP top 10, compute average domain authority
   proxy (count of .gov, major brands, established competitors in top 5).
   Scale 0.0 (all small sites) to 1.0 (all authoritative domains). If no
   SERP data, default to 0.5.
3. **Priority score:** Apply the scoring formula (see below).
4. **Suggested word count:** Based on intent defaults from article-spec
   Section 9.5.3 (1800-2400 for no-SERP; SERP average ±15% when available).
5. **Suggested archetype:** From site config `[branding] archetype`.
6. Update `last_scored_at`.

### Stage 7: Write Queue + Dump CSV

**Purpose:** Finalize database state and export human-readable report.

| | |
|---|---|
| **Input** | Scored `topics` table |
| **Output** | Updated SQLite DB + `topic-queue-{site}.csv` in `data/` |
| **Dependencies** | None |
| **LLM** | None |
| **Est. cost/run** | $0 |
| **Est. runtime** | <5 seconds |

Method:
1. Mark all newly-scored candidates as status `new` (ready for human review).
2. Export CSV sorted by `priority_score DESC`, columns:
   keyword, intent, est_volume, competition_score, competitors_with_it,
   we_have_it, priority_score, suggested_wc, status, source, discovered_at.
3. Print summary to stdout: total candidates, new discoveries, already-covered,
   top 10 by priority score.

---

## Priority Scoring Formula

```
priority_score = (w_cc * competitor_coverage_norm)
               + (w_vol * volume_norm)
               + (w_iv * intent_value_norm)
               + (w_ci * competition_inverse_norm)
```

Where:

| Factor | Computation | Range |
|---|---|---|
| `competitor_coverage_norm` | `competitors_with_it / num_competitors` | 0.0 - 1.0 |
| `volume_norm` | `min(est_volume, 10000) / 10000` | 0.0 - 1.0 |
| `intent_value_norm` | Lookup: cost=1.0, decision=0.9, comparison=0.8, process=0.6, definition=0.4 | 0.0 - 1.0 |
| `competition_inverse_norm` | `1.0 - competition_score` | 0.0 - 1.0 |

Default weights (configurable per site in `[topic_discovery]`):

| Weight | Default | Config key |
|---|---|---|
| `w_cc` | 0.35 | `w_competitor_coverage` |
| `w_vol` | 0.25 | `w_volume` |
| `w_iv` | 0.25 | `w_intent_value` |
| `w_ci` | 0.15 | `w_competition_inverse` |

**Bonus modifier:** If `we_have_it = 1`, multiply final score by 0.1 (deprioritize
topics already covered). If `we_have_it = 0` AND `competitors_with_it >= 2`,
multiply final score by 1.25 (boost topics competitors cover that we don't).

---

## Module Structure

```
modules/topic-discovery/
  __init__.py
  README.md
  DESIGN.md                          # this document
  lib/
    __init__.py
    db.py                            # SQLite connection, schema migrations, query helpers
    serper_client.py                 # Serper API wrapper with fallback key pattern
    sitemap_parser.py                # Parse XML sitemaps (own site + competitors)
    classifier.py                    # LLM intent classification (openai/gpt-5.4-mini)
    scorer.py                        # Priority scoring formula
  stages/
    __init__.py
    stage1_expand_seeds.py           # Seed term expansion via Serper
    stage2_crawl_competitors.py      # Competitor sitemap crawl
    stage3_dedup.py                  # Candidate dedup + canonicalization
    stage4_existing_content.py       # Existing-content detection
    stage5_fetch_serp.py             # SERP fetch for candidates
    stage6_classify_and_score.py     # Intent classification + priority scoring
    stage7_write_queue.py            # Write DB + dump CSV report
  tools/
    __init__.py
    discover_topics.py               # CLI entry point (--site, runs all stages)
    dump_queue.py                    # Export topic-queue CSV for a site
  data/
    .gitkeep                         # topics.db lives here, gitignored
```

---

## Dependencies

Beyond what content-production-v2 already uses (`requests`, `openai`,
`beautifulsoup4`, `python-dotenv`):

| Package | Purpose | Already in use? |
|---|---|---|
| `lxml` | Fast XML sitemap parsing | No — install needed |
| `sqlite3` | Database | Yes (stdlib) |
| `requests` | HTTP for sitemaps/SERP | Yes |
| `openai` | LLM classification calls | Yes |

Only **`lxml`** is a new dependency. Install: `pip install lxml`.

---

## Open Questions (Resolve Before Session 2)

1. **SERP result caching duration.** Should we cache SERP results for a fixed
   period (e.g., 7 days, 30 days) and skip re-fetching within that window?
   Longer cache saves quota but risks stale competition data. What's the right
   TTL?

2. **Existing-content matching strategy.** How do we decide that the site
   "already covers" a topic? Options: (a) slug-token overlap (fast, misses
   semantic matches), (b) title substring match (catches more, some false
   positives), (c) content embedding similarity (accurate, requires embedding
   API calls and storage). Which level of accuracy is worth the cost?

3. **Minimum volume threshold.** Should candidates below a certain estimated
   search volume (e.g., <50 monthly searches) be auto-rejected before scoring,
   or should they still score and let the human reviewer decide? Low-volume
   long-tail terms can be high-conversion for VA lending.

4. **Volume estimation source.** Serper does not return search volume natively.
   Options: (a) use a third-party API like Keywords Everywhere or DataForSEO
   ($), (b) estimate volume from SERP competition signals as a rough proxy
   (free but imprecise), (c) leave `est_volume = 0` and let the user manually
   populate volume for top candidates. Which approach?

5. **Competitor crawl depth.** Should we only parse `sitemap.xml`, or also
   crawl key category/hub pages (e.g., veteransunited.com/va-loans/) and
   extract linked article URLs that might not be in the sitemap? Deeper crawl
   catches more pages but adds complexity and request volume.
