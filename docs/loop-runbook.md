# RSS Loop Runbook

How to seed, run, review, and manage autonomous article generation.

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
rss queue seed --site tln --from-gsc --min-impressions 50 --limit 30
# Review the list, then:
rss queue seed --site tln --from-gsc --min-impressions 50 --limit 30 --confirm
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

Outcomes: `done`, `done-retry`, `done-repair`, `parked`

## Managing Parked Items

```bash
# View parked items with failure reasons
rss queue list --site tln --status parked

# After fixing the underlying issue, retry:
rss queue park --site tln --id <item_id>   # explicit park
rss queue retry --site tln --id <item_id>  # reset to pending
```

## Safety Rules

- The loop NEVER deploys above `--status draft` unless you explicitly pass `--status publish`
- The repair agent has `--max-turns 5` — it cannot run indefinitely
- The repair agent has no permission bypass — it can only use pipeline commands
- Queue writes are atomic (temp + rename) — safe for concurrent access
- Every iteration runs `rss doctor` preflight — unready sites abort immediately
