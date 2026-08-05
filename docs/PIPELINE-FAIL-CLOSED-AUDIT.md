# Pipeline Fail-Closed Audit

**Date:** 2026-06-14
**Status:** Report only — no code changes this session.
**Purpose:** Classify every pipeline gate as CODE-enforced or PROSE-only,
propose code enforcement for each prose gate, prioritize by observed
failure frequency.

Reference model: push-post-content.py's manifest validation — gate
resolution is a logged operation (the orchestrator refuses to proceed),
not an ad-hoc "please comply" instruction.

---

## Gate Inventory

### CODE-ENFORCED GATES (orchestrator refuses to proceed)

These gates exist in running code. If the check fails, the pipeline
stops with an error. No human or agent intervention can bypass without
explicitly passing a flag that leaves a logged trail.

| # | Gate | Location | What it checks | Bypass |
|---|------|----------|---------------|--------|
| C1 | **Manifest validation** | `push-post-content.py:44-106` | *-manifest.json exists, has required fields (target_keyword, intent, site), phases_completed includes [A-H], llm_calls > 0, timestamp within 168h | `--allow-no-manifest` (logs warning) |
| C2 | **Size ratio guard** | `push-post-content.py:148-158` | New content size vs original within 0.8x-1.2x ratio | `--size-min-ratio` / `--size-max-ratio` flags |
| C3 | **Post-write verify greps** | `push-post-content.py:176-228` | Required strings present in post_content after write; forbidden strings absent | None — hard fail |
| C4 | **Pre-write backup** | `push-post-content.py:141-144` | Backs up current post_content before overwriting | None — always runs (except dry-run) |
| C5 | **Geo-scope filter** | `assemble-article.py:146-183` | Drops subtopics containing off-target geographic terms for locale-specific articles | Multi-geo intent auto-detected = skip filter |
| C6 | **HTML sanitizer** | `assemble-article.py:1330` | Phase H step 24b — sanitize_assembled_html finds structural errors | Hard fail if errors found |
| C7 | **Phase completion tracking** | `assemble-article.py:252,339,455,...` | Each phase appends to phases_completed list; manifest records which phases ran | Cannot deploy without all phases |
| C8 | **Empty content guard** | `push-post-content.py:135-138` | Refuses to push a 0-byte content file | None — hard fail |

**Assessment:** These are solid. The manifest validation (C1) is the
reference model — it's the right pattern for every gate below.

---

### PROSE-ONLY GATES (agent asked to comply, no code enforcement)

These gates exist only as instructions in CLAUDE.md, memory files, or
session prompts. Nothing in running code prevents violation. Listed in
priority order by observed failure frequency.

| # | Gate | Where stated | Failure class | Observed frequency | Damage when violated |
|---|------|-------------|---------------|-------------------|---------------------|
| P1 | **Single-agent enforcement** | CLAUDE.md "single agent, no parallel SSH"; MEMORY.md "Single agent at a time" | Agent spawns parallel subagents for "speed" | HIGH — happened in multiple batch sessions | OOM kills on shared WPE server, race conditions in post writes, corrupted master logs |
| P2 | **Render verification** | CLAUDE.md "node --check + reference-trace"; RSS CLAUDE.md UI verification section | Agent reports "deployed" based on file-on-disk or API curl, never checks rendered page | HIGH — AHN hubs shipped unstyled because CSS was checked at file level, not in rendered `<head>` | User-facing broken pages, invisible CSS/JS failures, silent form breakage |
| P3 | **Sample-batch approval** | CLAUDE.md "verify a sample (5 posts)"; session prompts | Agent runs full batch without stopping for sample review | HIGH — May 2026 regression batch ran ~30 articles without sample gate | At-scale quality regression, bulk rollback required |
| P4 | **Content generation rule** | RSS CLAUDE.md "CONTENT GENERATION RULE — NO EXCEPTIONS" | Agent writes freehand article HTML instead of using assemble-article.py | MEDIUM — the rule was written because this happened repeatedly | Non-spec articles missing brand voice, structural templates, anchor pool linking, validation |
| P5 | **External links never stripped** | Session prompts, implicit in linking policy | Strip/dedup/rewrite pass touches links to external domains we don't control | MEDIUM — observed in Canopy link-dedup pass | Broken outbound citations, damaged EEAT signals, lost referral relationships |
| P6 | **Language boundary** | Session prompts, AHN claims policy | English content links to Spanish/Dari pages or vice versa; cross-language link injection | MEDIUM — possible in any multi-lang site (AHN has en/prs/ps) | User confusion, search engine mixed-signal indexing |
| P7 | **Deploy lock coordination** | CLAUDE.md "lockfile"; session prompts "deploy_lock" | Two sessions write to the same install simultaneously | MEDIUM — mitigated by persistent lock file convention, but nothing enforces checking it | Race conditions, overwritten content, corrupted post_content |
| P8 | **Scope discipline** | Session prompts "scope-exceeding judgment calls" | Agent makes architectural/policy decisions inside a narrow task | MEDIUM — observed when a "fix meta tags" task became a "redesign the header" task | Unreviewed structural changes, drift from intended architecture |
| P9 | **Model discipline (Opus for content)** | CLAUDE.md "ALL tasks that modify post_content on production must use Opus" | Content task runs on Sonnet for speed | LOW — mostly enforced by session config | Lower-quality content on production pages |
| P10 | **Staging-first** | CLAUDE.md "ALWAYS run on staging first, verify, report, WAIT" | Agent writes directly to production | LOW — most sites lack staging environments on WPE | No rollback window, production is the test environment |
| P11 | **Hub box opt-in** | RSS CLAUDE.md "Hub box is opt-in" | Agent adds hub box to articles that don't need one | LOW | Unnecessary page weight, visual clutter |
| P12 | **wp_update_post not wp db query** | CLAUDE.md Banned Methods | Agent uses raw SQL for post_content writes | LOW — push-post-content.py handles this, but ad-hoc writes bypass it | Silent truncation on WPE (60KB+ inline SQL exits 0, writes nothing) |

---

## Proposed Code Enforcement

For each prose-only gate, the enforcement mechanism that would convert
it from "please comply" to "orchestrator refuses to proceed."

### P1: Single-Agent Enforcement
**Current:** Prose in CLAUDE.md + MEMORY.md.
**Proposed:** Add to `docs/WRITE-SESSION-HEADER.md` (done — rule 1). For
batch scripts: the orchestrator (assemble-article.py, push-post-content.py)
should check for and refuse to run if it detects another instance via
PID lockfile. Implementation: at script startup, write PID to
`~/locks/{script}-{site}.lock`; abort if lock exists and PID is alive.
push-post-content.py already has SSHSession lockfile support — extend
to assemble-article.py.

### P2: Render Verification Gate
**Current:** Prose in CLAUDE.md ("node --check", "reference-trace").
**Proposed:** Build a `verify-deploy.py` tool that:
1. Takes a URL + a list of expected elements (CSS selector, text grep, JS var)
2. Curls the rendered page
3. Checks each expected element against the HTML
4. Exits non-zero if any check fails
5. Outputs a structured pass/fail report

push-post-content.py calls verify-deploy.py after every deploy with
site-specific verify rules from `sites/{site}-verify.json`. The deploy
is logged as UNVERIFIED until verify-deploy.py passes.

### P3: Sample-Batch Approval Gate
**Current:** Prose in session prompts.
**Proposed:** push-post-content.py `--batch-csv` mode gains a
`--sample-first` flag (default: on). When processing a CSV with > 3
rows, the script:
1. Processes rows 1-3 only
2. Prints a summary (before/after sizes, verify results)
3. Writes `SAMPLE_PENDING` to the deploy log
4. Exits with a special code (e.g., exit 42 = "sample complete, awaiting approval")
5. Re-running with `--sample-approved` processes the remainder

This makes the sample gate a logged operation. The deploy log shows
whether the sample was approved before the batch ran.

### P4: Content Generation Rule
**Current:** Prose in RSS CLAUDE.md (the longest single rule).
**Proposed:** The CLAUDE.md rule is already strong prose. Code
enforcement: push-post-content.py's manifest validation (C1) already
blocks non-pipeline content from deploying via the standard path.
Remaining gap: ad-hoc `wp post update` over SSH bypasses
push-post-content.py entirely. Fix: a mu-plugin `rss-content-guard.php`
that hooks `wp_insert_post_data` and logs any post_content write not
originating from an rss-push-* PHP file. This creates an audit trail,
not a hard block (hard-blocking all WP writes would break admin).

### P5: External Links Never Stripped
**Current:** Implicit policy.
**Proposed:** inject-internal-links.py already operates on internal
links only. Add an explicit guard: before any link modification
operation, check if `href` domain matches the site's domain. If not,
skip with a log entry. The linker's anchor pool is internal-only by
design, but a strip/dedup script could still touch externals — add
the domain check to any future link-manipulation tool.

### P6: Language Boundary
**Current:** Prose in session prompts.
**Proposed:** Add `SITE_LANGUAGES` to `sites/{site}.conf` (e.g.,
`SITE_LANGUAGES="en,prs,ps"`). inject-internal-links.py checks the
source article's language tag against the destination's. If they
differ, skip the link candidate. For AHN: captures and drafts already
use `__{lang}` suffix — the linker can parse this.

### P7: Deploy Lock Coordination
**Current:** Convention (persistent file at `/nas/content/live/{install}/.deploy-lock`).
**Proposed:** push-post-content.py and assemble-article.py both check
for `.deploy-lock` at startup. If the lock exists and was written
within the last 4 hours, abort with a message. If stale (> 4h), warn
and proceed. Already partially implemented in SSHSession; extend to
all entry points.

### P8: Scope Discipline
**Current:** Prose in session prompts.
**Proposed:** This is inherently a human-judgment gate — code can't
determine when a task exceeds its scope. Enforcement: the WRITE-SESSION-
HEADER (artifact 1) makes this a verbatim instruction. The AI
verification layer (next session) can flag when a session's file-touch
footprint exceeds the task description's implied scope.

### P9-P12: Lower Priority
These are lower-frequency failures. P9 (model discipline) is enforced
by session configuration. P10 (staging-first) is structural — most WPE
installs lack staging. P11 (hub box) is low-damage. P12 (wp_update_post
not SQL) is already enforced by push-post-content.py for pipeline
content; the remaining risk is ad-hoc writes.

---

## Priority Implementation Order

Based on failure frequency and damage:

| Priority | Gate | Effort | Impact |
|----------|------|--------|--------|
| 1 | P2: verify-deploy.py (render verification) | Medium (new tool, ~200 lines) | Eliminates "deployed but broken" class |
| 2 | P3: --sample-first in push-post-content.py | Small (add flag + exit code) | Eliminates at-scale regression class |
| 3 | P1: PID lockfile in assemble-article.py | Small (copy pattern from SSHSession) | Eliminates parallel-agent server crashes |
| 4 | P7: Deploy lock check at all entry points | Small (add check to script startup) | Eliminates cross-session race conditions |
| 5 | P5: Domain check in link tools | Small (add href domain guard) | Eliminates external link damage |
| 6 | P6: Language tag check in linker | Medium (add lang detection + guard) | Eliminates cross-language linking |
| 7 | P4: rss-content-guard.php audit trail | Medium (new mu-plugin) | Creates visibility into non-pipeline writes |
| 8 | P8: Scope-drift detection in AI layer | Large (AI verification layer design) | Next session |
