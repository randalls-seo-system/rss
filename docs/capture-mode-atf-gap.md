# Capture-Mode ATF Gap

**Date:** 2026-06-14 (documented) · 2026-06-16 (manual backfill completed)
**Status:** Gap documented. Manual backfill done for AHN. Pipeline fix is a future build session.
**Observed in:** AHN hub deployment (June 2026)

---

## The Problem

The capture-mode pipeline (Voice Capture dashboard -> draft generation
-> article assembly) produces a content-spec for each article but does
NOT produce an ATF-component-spec. Specifically:

1. **No 4-card QuickGrid spec.** The article spec (Section 5) requires
   exactly 4 ATF cards with H3s and 4 bullets each. The capture-mode
   pipeline generates body content from voice captures but doesn't
   call the card builder to produce the QuickGrid HTML. Articles ship
   with the body sections but no ATF card grid.

2. **No ATF 3-Q FAQ spec.** The article spec (Section 6) requires
   exactly 3 ATF FAQ items with 35-60 word answers. The capture-mode
   pipeline doesn't call the FAQ builder for the ATF position. Articles
   either lack ATF FAQs entirely or have them generated without the
   spec constraints.

3. **No per-site component CSS.** The ATF components (cards, FAQs,
   jump nav, CTA pills) require CSS from `rl-components/`. When a new
   site is onboarded, the component CSS must be deployed as a mu-plugin
   stylesheet with the site's prefix (e.g., `ahn-article-styles.php`).
   This step is not part of the site onboarding checklist — it's
   discovered only when articles render unstyled.

## What Happened on AHN

The AHN hub pages were generated through the capture-mode pipeline
(voice captures -> dashboard drafts -> article assembly). The body
content was correctly generated from Safi's voice captures. However:

- The pages shipped without ATF QuickGrid cards
- The pages shipped without ATF FAQ sections
- No `ahn-article-styles.php` mu-plugin existed, so even if ATF
  components had been generated, they would have rendered unstyled
  (no `ahn-` prefixed CSS for cards, callouts, or structural elements)

The pages were technically "deployed" (content in the DB, HTTP 200)
but visually incomplete — the ATF section that drives first-impression
engagement was missing.

### Additional defects discovered during backfill (2026-06-16)

When the ATF was manually backfilled across all 10 hubs, several
issues surfaced that a pipeline fix must also address:

- **Literal `\n` corruption.** All 10 body files contained stray "n"
  characters (`</div>n<h2>`) at CTA-to-H2 boundaries. Root cause:
  the capture-mode content writer concatenated sections with literal
  `\n` escape sequences instead of real newlines. The backfill script
  sanitized these with `str_replace('</div>n<h2>', '</div>\n\n<h2>')`.
  The pipeline must emit clean newlines or run the same sanitization.

- **BTF FAQ format mismatch.** Body FAQs were emitted as `<h3>` + `<p>`
  pairs instead of `<details><summary>` accordions. Some posts had a
  `<h2>Frequently Asked Questions</h2>` wrapper; others (posts 19, 33)
  had bare H3+p pairs after "The Bottom Line" with no FAQ heading.
  The backfill script handled both cases. The pipeline should emit
  FAQs in `<details>` format from the start.

- **No H1 in rendered page.** The Divi theme does not render the post
  title as `<h1>` on single posts. Capture-mode content had no `<h1>`
  in `post_content` either, leaving pages without any H1. The ATF hero
  adds the H1. The pipeline's `_build_header_prelude()` already does
  this for standard articles — capture-mode must not skip it.

- **No FAQPage JSON-LD.** Capture-mode produces no FAQ schema. The
  backfill added a mu-plugin (`ahn-faq-schema.php`) that auto-generates
  FAQPage JSON-LD from `<details>` elements in `.ahn-atf-faq` and
  `.ahn-btf-faq` sections. For the pipeline fix, schema generation
  should be part of the article output, not a site-specific mu-plugin.

## What Was Actually Built to Backfill (2026-06-16)

The backfill was done manually across all 10 AHN hubs, not via the
pipeline. This section documents what was deployed so a future pipeline
fix produces equivalent output automatically.

### Deployed mu-plugins

| File | Purpose |
|------|---------|
| `ahn-ui-styles.php` | Enqueues `ahn-ui.css` on `is_singular('post')` |
| `ahn-ui.css` v2.3.0 | Component CSS: ATF hero, lede, QuickGrid, FAQ accordion (ATF+BTF), callout, table, list, CTA, heading hierarchy, byline-in-hero treatment |
| `ahn-faq-schema.php` v1.1.0 | Auto-generates FAQPage JSON-LD from `<details>` in `.ahn-atf-faq` and `.ahn-btf-faq` |

### ATF HTML structure added to each post's `post_content`

```
<header class="ahn-hero">                    ← eyebrow + H1 + CTA
<p class="ahn-lede"><strong>...</strong></p> ← 50-60w answer-first paragraph
<div class="ahn-quick-grid">                 ← 2x2 responsive grid
  <article class="ahn-quick-card">×4         ← H3 + 4 bullets each
</div>
<section class="ahn-atf-faq">                ← 3 <details> items
</section>
[existing body content unchanged]
<h2>Frequently Asked Questions</h2>
<section class="ahn-btf-faq">                ← body H3+p converted to <details>
</section>
```

### Derivation rules (for pipeline replication)

- **Lede:** 50-60 words, answer-first. First sentence must work as a
  standalone featured snippet. Derived from the body's existing intro.
- **QuickGrid cards:** 4 cards, each with H3 title + 4 bullets. All
  facts pulled from the approved body content — no claims invented.
  Card 4's last bullet is a synthesis/takeaway bullet.
- **ATF FAQ:** 3 broad questions distinct from the body's BTF FAQs.
  Answers 35-60 words, derived from body content.
- **BTF FAQ:** The body's existing H3+p FAQ pairs converted to
  `<details><summary>` format and wrapped in `<section class="ahn-btf-faq">`.
- **Body:** Completely unchanged. Zero claims added or removed.

### Backups

All pre-modification content at:
`/nas/content/live/afghanhomenetw/backups/ahn-atf-20260616/post-{ID}-pre.html`

---

## Root Cause

The assemble-article.py pipeline has Phase D (ATF Generation) which
builds cards and ATF FAQs. But the capture-mode entry point
(dashboard draft -> assemble) can skip or under-specify Phase D
because:

1. The voice-capture drafts contain `<h1>` in body HTML (noted in
   `sites/ahn/config.json`: "draft_format_note"). The hub pipeline
   must strip H1 per article spec (H1 lives in ATF hero, not in
   main-content). This stripping happens, but the pipeline doesn't
   backfill the ATF components that should accompany the hero.

2. Phase D's card builder (`build-card.py` or inline in Phase D)
   requires structured input (intent-driven card shapes from spec
   Section 1 table). Capture-mode doesn't produce this structured
   input — it produces narrative body content from voice transcripts.
   Phase D either skips or produces generic cards that don't match
   the voice content.

3. Site onboarding doesn't include a "deploy component CSS" step.
   The CSS exists in `rl-components/` for VALN/TLN/Canopy/LRG, but
   new sites (AHN, future sites) need a site-specific mu-plugin that
   enqueues these styles with the correct prefix.

## Proposed Fix

### Fix 1: Capture-mode calls Phase D explicitly

When assemble-article.py runs from a capture-mode draft:
- Phase D MUST run with the same constraints as standard pipeline
- If the capture draft doesn't provide card-builder input, Phase D
  derives it from the body content (extract key facts, qualification
  data, process steps from the generated body sections)
- Phase D's card builder must accept a `--derive-from-body` flag
  that reads the Phase F output and builds cards from it
- **Reference implementation:** The AHN backfill derived all card
  facts from existing body content manually. The derivation rules
  (above) document the pattern a `--derive-from-body` flag should
  replicate: scan H2 sections for numbers, requirements, process
  steps, and comparisons; assign each to a card slot

### Fix 2: Site onboarding writes per-site component CSS

Add to the site onboarding checklist (docs/site-onboarding.md, to be
written):
- Step: "Deploy component CSS mu-plugin"
- Template: copy from AHN (`ahn-ui-styles.php` + `ahn-ui.css`) which
  is now the most complete reference (ATF hero, lede, QuickGrid, FAQ
  accordion, callout, table, list, CTA, heading hierarchy, byline
  treatment). Previous reference was `lrg-article-styles.php`.
- Replace prefix: `ahn-` -> `{site}-`
- Replace brand colors (`:root` variables) with the new site's palette
- Deploy to mu-plugins on the target install
- Verify: curl a published article, grep `<head>` for the stylesheet
- **Also deploy:** FAQ schema mu-plugin (`ahn-faq-schema.php` pattern)
  that auto-generates FAQPage JSON-LD from `<details>` elements

### Fix 3: Phase D failure is a hard gate

Currently, if Phase D fails or is skipped, the pipeline continues to
Phase E-H and produces an article without ATF components. This should
be a hard gate: if Phase D does not produce both the card grid AND the
ATF FAQs, the pipeline halts with a clear error:

```
PHASE D INCOMPLETE: ATF cards={count}/4, ATF FAQs={count}/3.
Cannot proceed — article spec requires both components.
Use --skip-atf to proceed without ATF (generates a manifest
with ATF_SKIPPED=true, which push-post-content.py will flag).
```

### Fix 4: Manifest records ATF status

Add to the pipeline manifest:
```json
{
  "atf_cards_count": 4,
  "atf_faqs_count": 3,
  "atf_skipped": false,
  "component_css_deployed": true
}
```

push-post-content.py checks `atf_skipped`. If true, it warns but
allows deploy (for legitimate cases like landing pages that don't use
ATF). If false and counts are wrong, it refuses.

### Fix 5: Capture-mode content sanitization

The capture-mode pipeline must run a post-generation sanitization pass
before assembly:

1. **Stray literal `\n`:** Replace `</div>n<h2>` with `</div>\n\n<h2>`.
   This pattern appeared in all 10 AHN hubs — the content writer
   concatenated CTA divs with H2 headings using literal `\n` escape
   sequences. The sanitizer in `assemble-article.py` (`sanitize_assembled_html`)
   should catch this pattern.

2. **BTF FAQ format:** Body FAQs must be emitted as `<details><summary>`
   elements inside a `<section class="{prefix}-btf-faq">` wrapper, not
   as `<h3>` + `<p>` pairs. If capture-mode generates H3+p FAQs, the
   assembly step must convert them before final output.

3. **FAQ heading consistency:** Some capture-mode outputs include a
   `<h2>Frequently Asked Questions</h2>` heading; others omit it and
   place H3+p FAQ pairs directly after the last body section. The
   pipeline must normalize: always include the H2 heading, always wrap
   in the btf-faq section.

---

## Implementation Priority

1. **Fix 3 (hard gate)** — prevents the problem from recurring. Small
   change in assemble-article.py Phase D completion check.
2. **Fix 5 (content sanitization)** — prevents stray-n and format
   defects. Add patterns to `sanitize_assembled_html()` + normalize
   BTF FAQ format.
3. **Fix 2 (onboarding CSS)** — prevents unstyled components. Checklist
   item + template mu-plugin. AHN's `ahn-ui.css` v2.3.0 is the
   reference implementation.
4. **Fix 4 (manifest ATF fields)** — audit trail for ATF status. Small
   addition to manifest writer + push-post-content.py validator.
5. **Fix 1 (derive cards from body)** — the most complex fix. Requires
   a new `--derive-from-body` capability in the card builder. AHN
   backfill derivation rules (documented above) are the spec. Defer
   to a dedicated build session.
