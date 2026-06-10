# `rss new-article` — Single-command Article Pipeline

## CLI

```
rss new-article --site <id> --topic "<topic>" \
    [--hub <cluster-hub-slug>] \
    [--skip-gap-scan] \
    [--dry-run] \
    [--resume <job_id>]
```

- `--site`: site_id from `sites/<site>/config.json` (required)
- `--topic`: target keyword / article topic (required)
- `--hub`: if set, builds an Explore Resources hub box linking this article to the cluster hub
- `--skip-gap-scan`: skip competitive gap analysis (use article spec only)
- `--dry-run`: run all stages through EMIT GATES but do not deploy
- `--resume`: re-enter an existing job at the first incomplete stage

Output: a deployed DRAFT on the target site.

---

## Stage Sequence

### Stage A — CONFIG LOAD + VALIDATE

**Module:** `lib/site_config.py` (load_site_config) + `sites/<site>/config.json`

**Required fields (fail loudly if missing):**
- `access.ssh_host`, `access.ssh_user`, `access.ssh_key_path`, `access.wp_path`
- `content.css_prefix` (at least one)
- `content.claims_policy` (path to claims/voice rules file — may be null for sites without one)
- `content.brand_voice_archetype`
- `authors.author_map` (at least one entry)
- `linking.zone_suffixes`, `linking.skip_slugs`, `linking.pool_path`
- `content.default_post_status` (must be "draft")

**Output:** validated config dict written to `jobs/<job_id>/config-snapshot.json`

**Failure:** exit with message naming the missing field. This doubles as config validation for new site onboarding.

### Stage B — GAP SCAN

**Module:** `lib/serp_adapter.py` (SerpData) + `tools/extract-subtopic-gaps.py` + `tools/compute-target-wc.py`

**Rate limits:** search queries 1 per 10s, competitor page fetches 1 per 5s.

**Input:** topic string, site_id
**Output:**
- `jobs/<job_id>/gap-analysis.json`: coverage matrix (CRITICAL/STRONG/OPTIONAL/ADVANTAGE)
- `jobs/<job_id>/outline.json`: recommended H2 inventory + competitor FAQ list
- `jobs/<job_id>/target-wc.json`: word count target based on competitor average

**Skippable:** `--skip-gap-scan` uses article spec defaults and topic-only generation.

**Failure:** SERP API errors → retry once, then continue with spec-only mode (warning logged).

### Stage C — GENERATE

**Module:** `tools/assemble-article.py` (the existing v2 orchestrator)

**Pre-step:** Create a draft post on the target site via `wp post create` to get a post ID. Set `post_author` from config `authors.author_map` by scope.

**Author resolution:** The orchestrator resolves author from config based on a `--category` argument:
- If `--category mortgage-operational` or topic matches mortgage/VA/FHA/credit keywords → `primary_sme` author
- If `--category benefits-lifestyle` or topic matches military/veteran-lifestyle keywords → `secondary` author
- Default: `primary_sme` (first entry in author_map)
- **FLAG: explicit `--category` arg is recommended** rather than keyword inference — inference is fragile. For the acceptance test, we pass `--category mortgage-operational` explicitly.

**Prompt construction:**
1. Article spec (`docs/article-spec.md`) — auto-prepended, SPEC WINS over any other instruction
2. Brand voice file (`modules/brand-voice/archetypes/<archetype>.md`)
3. Claims policy (from `content.claims_policy` path — file_get_contents, not embedded)
4. Gap scan outline (if Stage B ran)
5. Topic string

**Execution:** `assemble-article.py --site <id> --post-id <id> --target-keyword "<topic>" --output-dir jobs/<job_id>/ [--allow-no-serp if skip-gap-scan] --skip-deploy`

The `--skip-deploy` flag is ALWAYS set — the orchestrator handles deploy separately in Stage F.

**Output:** `jobs/<job_id>/<post_id>-article.html` (the linked, assembled article)

**Failure:** LLM timeout → retry once. Any other error → hard fail, report stage.

### Stage D — EMIT GATES

**Module:** `tools/validate-article-v2.py` + custom gate checks in `lib/orchestrator.py`

**Gates (all must pass):**
1. BLUF present (`<div class="...bluf"` or BLUF-headed section)
2. No literal `\n` (escaped newlines in output)
3. No `<h1>` in body (H1 lives in ATF hero only)
4. No em dashes (`—`) in body text
5. Word count >= `content.article_min_words` from config
6. All CSS classes use config `content.css_prefix` (no foreign prefixes)
7. No internal links in body (writer never links — links come from Stage E)
8. CTA markup matches config `content.cta_url` and `content.cta_text`

**Failure:** HARD FAIL on any gate. Report which gate failed and the offending content. Auto-retry generation ONCE (re-run Stage C). If second attempt also fails, stop and report — human must intervene.

**Output:** `jobs/<job_id>/gate-results.json`

### Stage E — LINK PASS

**Module:** `tools/inject-internal-links.py` (pipeline pool mode)

**Input:** the gate-passing article HTML + site anchor pool
**Output:** `jobs/<job_id>/<post_id>-article-linked.html`

This runs the existing pipeline linker in pool mode against the NEW article only, injecting outbound links into it.

**Inbound candidates:** After the link pass, the orchestrator scans the article's H2 topics against the anchor pool to identify 2-3 existing pages that SHOULD link TO this new article. These are appended to `sites/<site>/link-queue.csv` as inbound-link candidates for the next corpus-mode batch run. The orchestrator does NOT inject inbound links into other posts — that's a separate approved batch.

**Output:** linked article HTML + `jobs/<job_id>/inbound-candidates.json`

### Stage F — DEPLOY

**Module:** `modules/wp-deploy/tools/push-post-content.py` + Yoast meta via `modules/wp-deploy/tools/push-post-meta.py`

**Discipline:**
- `deploy_lock` acquired (from `lib/linker_core.py`)
- Backup of the draft post's current content (empty for new posts, but the pattern still runs)
- `push-post-content.py --site <id> --post-id <id> --html-file <path> --status draft`
- Sleep 5
- Yoast meta: title + description generated by existing meta path (mechanical LLM call) → `push-post-meta.py`
- CDN purge via WpeCommon

**Status:** ALWAYS `draft`. `content.default_post_status` from config enforced.

**Failure:** deploy error → restore backup, report. Yoast meta failure → warning only (non-blocking).

### Stage G — VERIFY

**Checks:**
1. `wp post get <id> --field=post_content` matches emitted HTML (byte-length comparison + spot-check of first H2)
2. `wp post get <id> --field=post_author` matches config author ID
3. `wp post get <id> --field=post_status` is "draft"
4. Yoast meta present (title + description non-empty)

**Failure:** any check fails → warning in job record. Does not auto-fix — human reviews.

### Stage H — LOG

1. **Work log:** if config defines `ops.work_log`, write a log entry (category: content, metric: pages_published=1, words_added=N)
2. **Job record:** write `jobs/<job_id>/job.json`:
   ```json
   {
     "id": "<uuid>",
     "site": "<site_id>",
     "topic": "<topic>",
     "post_id": <id>,
     "post_slug": "<slug>",
     "author_id": <id>,
     "stages": {
       "config": {"status": "done", "timestamp": "..."},
       "gap_scan": {"status": "done|skipped", "timestamp": "...", "duration_s": N},
       "generate": {"status": "done", "timestamp": "...", "duration_s": N, "word_count": N, "llm_calls": N},
       "gates": {"status": "done", "timestamp": "...", "results": {...}},
       "link_pass": {"status": "done", "timestamp": "...", "links_injected": N, "inbound_candidates": N},
       "deploy": {"status": "done", "timestamp": "...", "post_id": N},
       "verify": {"status": "done", "timestamp": "...", "checks": {...}},
       "log": {"status": "done", "timestamp": "..."}
     },
     "artifacts": {
       "article_html": "jobs/<id>/<post_id>-article-linked.html",
       "gap_analysis": "jobs/<id>/gap-analysis.json",
       "gate_results": "jobs/<id>/gate-results.json",
       "inbound_candidates": "jobs/<id>/inbound-candidates.json"
     },
     "created": "...",
     "completed": "...",
     "wall_clock_s": N
   }
   ```
3. **Append to CHANGELOG.md** (if it exists for the site)

---

## Resumability

Every stage writes its output to `jobs/<job_id>/`. The job record tracks which stages are complete.

`--resume <job_id>` re-reads the job record and enters at the first stage with status != "done". A crashed generation (Stage C) resumes at Stage C without re-running the gap scan (Stage B).

Stage outputs are idempotent: re-running a completed stage overwrites its output (with `--force`).

The post ID created in Stage C is stored in the job record — resume uses it instead of creating a new post.

---

## What Stays Human

- **Topic selection:** the user picks the topic. The queue CSV is a suggestion list, not an auto-runner.
- **Draft review:** the article deploys as draft. A human reviews before publishing.
- **Publish:** no publish path exists in this tool. Publishing is a manual `wp post update --post_status=publish` action.
- **Gate failures:** if a gate fails twice, the tool stops. A human must fix the content or adjust the prompt.
- **Inbound linking:** inbound link candidates are queued, not deployed. The next corpus-mode batch (approved separately) handles them.

---

## File Structure

```
tools/
  rss                     ← entry point (thin: parse args, call orchestrator)
lib/
  orchestrator.py         ← stage functions, job management, config validation
jobs/
  <job_id>/
    config-snapshot.json
    gap-analysis.json
    outline.json
    target-wc.json
    <post_id>-article.html
    <post_id>-article-linked.html
    gate-results.json
    inbound-candidates.json
    job.json
```

---

## Existing Modules Referenced

| Stage | Module | Path |
|-------|--------|------|
| A | site_config | lib/site_config.py |
| B | SERP adapter | lib/serp_adapter.py |
| B | gap extractor | tools/extract-subtopic-gaps.py |
| B | word count target | tools/compute-target-wc.py |
| C | article assembler | tools/assemble-article.py |
| D | validator | tools/validate-article-v2.py |
| E | pipeline linker | tools/inject-internal-links.py |
| F | content push | modules/wp-deploy/tools/push-post-content.py |
| F | meta push | modules/wp-deploy/tools/push-post-meta.py |
| G | deploy verify | modules/wp-deploy/tools/verify-write.py |
| * | deploy lock | lib/linker_core.py (deploy_lock) |
| * | brand voice | modules/brand-voice/archetypes/*.md |
| * | claims policy | docs/*-claims-policy.md or site-specific path |
