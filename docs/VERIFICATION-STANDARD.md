# Verification Standard — "deployed != delivered"

Server-side confirmation (file exists, option set, wp_update_post returned 0)
is NECESSARY BUT INSUFFICIENT. Every user-facing change requires TWO layers:

1. **Server-side confirm** — the write succeeded at the infrastructure level.
2. **Rendered-artifact confirm** — the change is visible in the output a
   browser would receive.

Then: hand to Randall with a specific "you should see X at [URL]."

### verify-deploy.py method selection

`--url` = **RENDER-TRUTH** (curls the live rendered page, sees mu-plugin /
serve-time injections like noindex, schema, injected CTAs/TOC) — USE FOR
ALL USER-FACING RENDER CHECKS. `--site --path` = **CONTENT-TRUTH** (reads
stored DB content via eval-file, works behind firewalls, but MISSES anything
injected at serve time) — use only for "did my pushed content land in the
DB," never for "does the page look right." Using `--site --path` for a
render/CSS check is a **FALSE-PASS risk.**

---

## Per-Artifact Verification Checklists

### CSS (mu-plugin stylesheet, inline style, enqueued file)

| Step | Method | Pass criterion |
|------|--------|----------------|
| File on disk | `ls -la` the deployed file, confirm size > 0 | Non-zero, timestamp current |
| Enqueue registered | `wp eval 'echo wp_styles()->registered["handle"]->src;'` | Correct handle + path |
| Rendered in `<head>` | `curl -s URL \| grep 'stylesheet.*handle'` | `<link>` tag present in HTML |
| Selector works | `curl -s URL \| grep 'expected-class-name'` | Class appears in rendered body |
| Handoff | "Randall: load [URL], inspect [element] — you should see [visual change]" | Randall confirms |

### JS handler (inline script, enqueued file, AJAX wiring)

| Step | Method | Pass criterion |
|------|--------|----------------|
| Syntax | Extract `<script>` block → `node --check` | Exit 0 |
| Reference trace | Every variable in new/modified handlers resolves to a definition at the correct scope | No unresolved references |
| Config injection | `curl -s URL \| grep 'CONFIG_VAR='` | Config object present in rendered HTML |
| DOM targets exist | Every `getElementById` / `querySelector` target exists in rendered HTML | All IDs found |
| AJAX endpoint | `wp eval 'echo has_action("wp_ajax_nopriv_ACTION");'` | Returns `1` (registered) |
| Handoff | "Randall: go to [URL], do [action] — you should see [result]" | Randall confirms |

### Form (lead form, contact form, any user input)

| Step | Method | Pass criterion |
|------|--------|----------------|
| Page loads | `curl -s -o /dev/null -w '%{http_code}' URL` | HTTP 200 |
| Form HTML present | `curl -s URL \| grep 'form\|input\|submit'` | Form elements in rendered HTML |
| AJAX endpoint registered | Check `wp_ajax_nopriv_*` hook | Registered |
| Nonce injected | `curl -s URL \| grep 'nonce'` | Nonce value in page source |
| Honeypot present | `curl -s URL \| grep 'honeypot-field-id'` | Hidden field present |
| Test submission | Submit via eval-file (DB write) | Row in DB, correct fields |
| Email delivery | wp_mail test from web path (not CLI — CLI lacks sendmail on WPE) | wp_mail returns true |
| Error state | Verify error UX exists (not silent discard) | Error banner in HTML |
| Handoff | "Randall: go to [URL], fill out [fields], submit — you should see [success state]. Check [email] for notification." | Randall confirms |

### Content block (post_content, mu-plugin HTML, page section)

| Step | Method | Pass criterion |
|------|--------|----------------|
| DB write | `wp post get ID --field=post_content \| wc -c` | Byte count matches expected |
| Backup exists | `ls -la backup_path` | Non-zero, timestamped |
| Rendered HTML | `curl -s URL \| grep 'expected-text-snippet'` | Text present in rendered output |
| No wpautop damage | `curl -s URL \| grep '<p></p>\|<br /><br />'` — should NOT match excessively | No orphan tags |
| Noindex (if pre-launch) | `curl -s URL \| grep 'noindex'` | Meta tag present |
| CDN cache purged | After batch: `WpeCommon::purge_varnish_cache_all()` | Purge executed |
| Handoff | "Randall: load [URL] — you should see [specific content/element]. Verify [specific thing]." | Randall confirms |

### Login / auth change (password, token, role)

| Step | Method | Pass criterion |
|------|--------|----------------|
| Credential set | `wp user check-password` or equivalent | Returns success |
| Login flow | Test the actual login endpoint, not just the DB value | Session established |
| Role correct | `wp user get ID --field=roles` | Expected role |
| Handoff | "Randall: log in at [URL] with [method] — you should see [dashboard/page]" | Randall confirms |

---

## Anti-Patterns (things that look like verification but aren't)

- **"File deployed successfully"** — confirms the write, not the render.
- **"wp post update returned 0"** — confirms the DB write, not the page.
- **"curl returns 200"** — confirms the URL resolves, not that the content is correct.
- **"API test passed"** — API-level curl does NOT verify browser-delivered pages.
- **"node --check passed"** — catches syntax errors, not runtime ReferenceErrors. Must be paired with reference-trace.

Every one of these is a necessary step. None is sufficient alone. The rendered
artifact is the truth. Randall's browser is the acceptance test.
