# RSS Loop Runbook

How to seed, run, review, and manage autonomous article generation and refresh.

## Prerequisites

1. Run `tools/setup-env.sh` (installs dependencies + NLTK data)
2. Run `rss doctor --site <slug>` — must be green (WARNs OK, FAILs block)
3. The site must have a config at `sites/<slug>/config.json` with no TODO-verify in required fields

## First Batch Protocol

**For a new site or after any pipeline change:**

1. Seed 3-5 topics: `rss queue add --site tln --topic "your topic"`
2. Run `tools/rss-loop --site tln --max-articles 3 --status draft`
3. Review ALL 3 drafts in WordPress (structure, facts, voice, links)
4. Fix any systemic issues in the pipeline before running larger batches
5. Only then: seed more topics and run `--max-articles 10+`

## Seeding the Queue

### Manual add
```bash
rss queue add --site tln --topic "VA loan closing costs guide"
```

### Seed from GSC (shows candidates for review first)
```bash
rss queue seed --site tln --min-impressions 50 --limit 30
# Review the list, then:
rss queue seed --site tln --min-impressions 50 --limit 30 --confirm
```

### View queue
```bash
rss queue list --site tln
rss queue list --site tln --status pending
```

## Running the Loop

```bash
# Standard run — 10 articles as draft
tools/rss-loop --site tln --max-articles 10

# Cautious run — 3 articles, draft only
tools/rss-loop --site tln --max-articles 3

# Dry run — pipeline runs but doesn't deploy to WordPress
tools/rss-loop --site tln --max-articles 5 --dry-run
```

### Stop conditions
- Queue empty
- `--max-articles` reached
- N consecutive failures (default 3) — prints the common failure
- Usage limit from Claude CLI — sleeps 30 min, retries once

### What happens on failure
1. Pipeline fails (gate, validation, D2)
2. Loop invokes `claude -p` with the failure report for one repair attempt
3. If repair succeeds → done
4. If repair fails → item is **parked** with the failure reason

## Reading the Log

```bash
cat logs/loop-tln.log
```

Each line: `timestamp  item_id  outcome  duration  cost`

Outcomes: `done`, `done-retry`, `done-repair`, `parked`, `awaiting`

## Managing Parked Items

```bash
# View parked items with failure reasons
rss queue list --site tln --status parked

# After fixing the underlying issue, retry:
rss queue park --site tln --id <item_id>   # explicit park
rss queue retry --site tln --id <item_id>  # reset to pending
```

## Audit → Refresh Workflow

For sites with existing content (e.g., TLN's 215 posts), the audit-refresh
workflow replaces whitespace seeding:

### Step 1: Audit existing posts (read-only)

```bash
# Audit top 50 posts by GSC impressions
rss audit-batch --site tln --top 50

# Single post audit
rss audit --site tln --post-id 1471

# Force Tier 2 (claims check) on all posts
rss audit-batch --site tln --top 50 --full
```

Output: `docs/tln-audit-YYYYMMDD.md` (scorecard) + `.json` (machine-readable).
**Zero writes to the live site.**

### Step 2: Seed refresh candidates from audit

```bash
# Show ranked candidates (severity × opportunity)
rss queue seed-refresh --site tln

# Write candidates to queue after review
rss queue seed-refresh --site tln --confirm
```

Posts with verdict PASS are excluded. Ranking: gate failures > low validator
score > unsourced claims, weighted by position (11-30 highest priority).

### Step 3: Run the loop (refresh items stop at pending draft)

```bash
tools/rss-loop --site tln --max-articles 3
```

Refresh items produce a `[REFRESH pending]` draft and go to status
`awaiting_approval`. The loop NEVER runs `refresh-approve` — approval
is always human.

### Step 4: Side-by-side review

In WordPress, compare the pending draft against the live post:
- Structure (H2s, components, CTA placement)
- Facts (numbers, claims, sources)
- Voice (brand consistency)
- Internal links preserved

### Step 5: Approve or park

```bash
# Approve — swap draft content onto original post
rss refresh-approve --site tln --job <job_id>

# Rollback — restore original HTML from job dir backup
rss refresh-rollback --site tln --job <job_id>
```

Approve re-runs gates before swapping. Original publish date is preserved.

### Manual refresh (single post)

```bash
# Start a refresh job
rss refresh --site tln --post-id 1471

# Override the keyword (default: top GSC query for the post)
rss refresh --site tln --post-id 1471 --keyword "fha 203k loan requirements"
```

### Add refresh items to queue manually

```bash
rss queue add --site tln --refresh --post-id 1471
```

## Topic Graph: Pending Links, Spokes, and Backfill

After each article is generated and linked, the pipeline discovers topics
that WANTED a link but had no destination. These become pending links.

### View the topic graph
```bash
rss topic-graph --site tln
```

### Resolve pending links
```bash
# See what would happen (dry run)
python3 modules/content-production-v2/tools/resolve-pending-links.py --site tln --all-jobs

# Actually write to pool/queue
python3 modules/content-production-v2/tools/resolve-pending-links.py --site tln --all-jobs --confirm
```

Resolution outcomes:
- **Topic matches existing page** → anchor pool enriched with new keyword variants
- **No existing page** → queued as new-article spoke with `origin: pending_link` and backlink notes

### View spoke articles (queued from pending links)
```bash
rss queue list --site tln --origin pending_link
```

### Backfill links after a spoke page is published
```bash
# Dry run (no --live = won't touch published posts)
python3 modules/content-production-v2/tools/backfill-links.py --site tln --queue-id <id>

# With --live flag: backfill into published source articles
python3 modules/content-production-v2/tools/backfill-links.py --site tln --queue-id <id> --live
```

Safety rules for backfill:
- Anchor phrase must still exist in the source article (no forced insertion)
- Per-post link cap respected
- `--live` required for published posts; drafts patch automatically
- Gates run on modified HTML before pushing

### Pending link discovery sources
- `corpus`: multi-word phrases in article body that don't match any pool entry
- `paa`: People Also Ask questions from SERP research
- `gsc`: GSC-derived subtopic queries
- `ai_mode`: (future) AI Mode related questions — TODO: wire when feat/ai-mode lands

## Safety Rules

- The loop NEVER deploys above `--status draft` unless you explicitly pass `--status publish`
- Refresh mode NEVER modifies the live post — only creates a pending draft
- `refresh-approve` re-runs all gates before swapping — post-generation edits are caught
- `refresh-rollback` restores original HTML from the job dir backup
- The repair agent has `--max-turns 5` and scoped `--allowedTools` — no permission bypass
- Queue writes are atomic (temp + rename) — safe for concurrent access
- Every iteration runs `rss doctor` preflight — unready sites abort immediately
