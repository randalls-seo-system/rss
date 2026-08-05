# WRITE-SESSION HEADER — prepend verbatim to every write-session prompt

```
WRITE-SESSION RULES (non-negotiable, read before any action):

1. SINGLE AGENT ONLY. No parallel subagents — not for reads, not for
   analysis, not for speed. If a step looks parallelizable, it is not.
   One agent, sequential, every step.

2. READ-ONLY DIAGNOSIS FIRST. Before any write to any site, complete a
   full read-only audit of the target (pages, options, mu-plugins,
   current state). Report findings. Wait for confirmation before writes.

3. SAMPLE BATCH BEFORE SITE-WIDE. For any operation touching more than
   3 pages/posts: run on a sample of 3-5 items, report exact results
   (before/after, verify output, any anomalies) to Randall, WAIT for
   explicit approval before executing the full batch. Never skip this.

4. DEPLOYED != DELIVERED. Server-side confirmation (file exists, option
   set, wp post update returned 0) is NECESSARY BUT INSUFFICIENT.
   Verification requires checking the RENDERED artifact:
   - curl the page, grep the <head> / body for the expected element
   - node --check + reference-trace any deployed JS
   - Confirm the artifact in the browser-delivered HTML, not just the DB
   Then report: "Ready for Randall to verify: [exact thing to check at
   exact URL]." Do NOT report "done" or "complete" on any user-facing
   change. Randall's browser confirmation is the only acceptance
   criterion.

5. SCOPE DISCIPLINE. If a task requires a judgment call that exceeds its
   stated scope — a structural change, a new subsystem, a policy
   decision, touching a file/system outside the task boundary — STOP
   and surface it to Randall for approval. Do not execute scope-
   exceeding decisions inside a narrower task. Narrow tasks produce
   narrow outputs.

6. FULL DEPLOY DISCIPLINE. Every write to production must follow:
   - Acquire deploy_lock (check, create, verify no other session holds it)
   - Per-post backup, verified non-zero (ls -la the backup file)
   - Content writes via eval-file + wp_update_post ONLY (never
     wp db query on post_content, never --post_content= pipe)
   - sleep 5 between writes
   - DB verify after write (wp post get --field=post_content | wc -c)
   - CDN purge after batch (WpeCommon::purge_varnish_cache_all())
   - Release deploy_lock

7. LANGUAGE BOUNDARY IS HARD. Never cross English/Spanish/Dari/Pashto
   in linking, retargeting, or content operations. An English article
   links only to English destinations. A Dari page links only to Dari.
   External links (domains we don't control) are NEVER touched by any
   strip, dedup, or rewrite pass — they are read-only references.
```
