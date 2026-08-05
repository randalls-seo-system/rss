# AI Verification Layer — Design Document

**Date:** 2026-06-14
**Status:** DESIGN — Phase 2 builds first two gates.
**Location:** `modules/content-production-v2/lib/verification_gates.py`

---

## Design Principle (verbatim, non-negotiable)

An API judge may **PASS**, **AUTO-FIX-AND-LOG**, or **ESCALATE-TO-RANDALL**.
It may **NEVER** make an irreversible decision on a high-cost ambiguous call
autonomously. Below a confidence threshold it **ESCALATES WITH A SPECIFIC
QUESTION** — it does not guess-and-act.

This is the same gate that caught the 37185 hallucinated 120-day rule and the
0.33 short-sales retarget: the layer's value is catching what syntactic gates
miss and routing genuine judgment to the human, NOT removing the human.

---

## Gate Catalog

### Gate A: RENDER-VERIFY

**What it checks:** The deployed page actually renders the expected artifact
in the browser — CSS loaded, JS handler bound, form action wired, expected
component present, no leaked build artifact in `<head>`.

**Input:** URL of deployed page + expected-artifact spec (from pipeline
manifest or site verify-spec JSON).

**Model:** gpt-5.4-mini (mechanical check — parse HTML, match expectations).
Escalation descriptions use Opus for clarity.

**Disposition:**
- All expected elements found → **PASS**
- Element missing from rendered HTML → **ESCALATE** with: "Page [URL]
  deployed but [element] not found in rendered output. Expected [spec].
  Check: [specific thing to look for]."
- Unexpected elements found (e.g., raw PHP, error dump) → **ESCALATE**

**Confidence threshold:** Binary — element is present or not. No score.
This gate does NOT interpret visual correctness; it checks structural
presence. Visual review is Randall's job.

**Failure class killed:** deployed != delivered (5x this build cycle —
AHN hubs unstyled, meta tags missing, JS handlers unbound).

**Implementation:** Wraps `verify-deploy.py --url` (RENDER-TRUTH per
VERIFICATION-STANDARD.md). The API adds judgment on CHECK RESULTS:
did the syntactic check miss something the spec implies? For example,
verify-deploy checks for `<link rel="stylesheet"...>` but the API also
checks that the stylesheet href resolves to the expected file.

---

### Gate B: ARTIFACT-SCAN

**What it checks:** Leaked generation meta-commentary in HTML output.
LLM-generated content sometimes includes summary preambles, markdown
fences, word-count stat blocks, or structural commentary that should
never reach the page.

**Input:** Article HTML (post-assembly, pre-deploy or post-deploy).

**Patterns detected (mechanical, no API needed for core set):**
- `## Summary` / `# Summary of` / `Here is a summary` preambles
- Markdown fences (``` ``` ```) in HTML context
- `~N words` / `(approximately N words)` stat blocks
- `[Note:` / `[Editor:` / `[TODO:` / `[Placeholder` meta-commentary
- `<h1>` inside body content (H1 belongs in ATF hero, not main-content)
- `In this article, we will` / `This article covers` throat-clearing
- `As an AI` / `As a language model` identity leaks

**Model:** None for core patterns (regex). gpt-5.4-mini for edge-case
classification (is this a legitimate blockquote or a leaked summary?).

**Disposition:**
- Known pattern match → **AUTO-FIX-AND-LOG** (strip the artifact,
  log what was removed and where)
- Ambiguous match (could be legitimate content) → **ESCALATE** with
  the matched text and context

**Confidence threshold:** Regex matches are 1.0 (auto-fix). API edge-case
classification: > 0.8 = auto-fix, ≤ 0.8 = escalate.

**Failure class killed:** AHN posts 14/19/28/29 leaked summaries,
markdown fences in published HTML.

---

### Gate C: ANCHOR-QUALITY

**What it checks:** Each proposed internal-link anchor text is a clean
noun phrase, not a fragment, generic filler, or partial sentence.

**Input:** List of (anchor_text, destination_url) pairs from the linker.

**Model:** gpt-5.4-mini (classification: clean-NP / fragment / generic /
byline-collision).

**Disposition:**
- Clean noun phrase → **PASS**
- Fragment / generic / byline → **AUTO-REJECT-AND-LOG**
- Ambiguous (e.g., "No Money Down" — looks generic but is a named
  program concept) → **ESCALATE** with context

**Confidence threshold:** > 0.85 = auto-disposition. ≤ 0.85 = escalate.
Replaces the POS-tagging gate with semantic judgment that understands
domain-specific proper nouns without a hardcoded whitelist.

**Failure class killed:** Canopy "in Texas" / "and insurance" generic
anchors, LRG fragment anchors.

---

### Gate D: VOICE-MATCH

**What it checks:** Generated content matches the site's brand voice file.

**Input:** Generated article HTML + brand voice archetype file.

**Model:** Opus (genuine judgment — requires understanding voice register,
first-person policy, cadence patterns).

**Critical gate behavior — first-person policy:**
The gate MUST read the voice file's `first_person_licensed` field:
- `first_person_licensed: true` (AHN/Safi): first-person IS the voice.
  Flag ABSENCE of first-person as a drift signal.
- `first_person_licensed: false` or absent (VALN/Matt): first-person
  is PROHIBITED. Flag PRESENCE of first-person as a violation (the
  "on files I work" x8 problem).

**Disposition:**
- Voice-consistent → **PASS** with score
- Mild drift (tone slightly off but no rule violation) → **PASS** with
  note in log
- Significant drift or first-person policy violation → **ESCALATE**:
  "Hub 23 drifts from Safi voice — [specific observation]. Review
  sections [X, Y]."

**Confidence threshold:** > 0.75 = pass. 0.5-0.75 = pass-with-note.
< 0.5 = escalate.

---

### Gate E: CLAIMS (D2 — existing, reference model)

**What it checks:** Factual claims in generated content against the
site's closed-set claims policy (ratified facts, TODO-confirm facts,
non-negotiable rules).

**Input:** Generated article HTML + claims policy document.

**Model:** Opus (high-stakes judgment — claims verification requires
understanding domain-specific facts and attribution rules).

**Disposition:**
- Claim matches ratified fact → **PASS** (SOURCE-backed)
- Claim matches TODO-confirm fact → **ESCALATE** with attribution
  question
- Claim not in closed set → **ESCALATE**: "Claim '[X]' not found in
  ratified facts. Source?"
- Claim contradicts ratified fact → **ESCALATE** (high priority)

**This is the proven prototype.** The gate resolution is a logged
operation in the manifest, not an ad-hoc edit. D2's approve-claims
flow is the pattern all other gates follow.

---

### Gate F: SCHEMA-VALID

**What it checks:** JSON-LD structured data parses correctly AND
matches the page's actual content type.

**Input:** Rendered page HTML (from verify-deploy curl).

**Model:** gpt-5.4-mini for classification (is this page genuinely
FAQ-shaped or is FAQPage schema being applied to guide-style H2s?).

**Disposition:**
- JSON-LD parses + schema type matches content → **PASS**
- JSON-LD doesn't parse → **AUTO-FIX-AND-LOG** (strip broken schema)
- Schema type mismatch (FAQPage on non-FAQ content) → **ESCALATE**:
  "Page uses FAQPage schema but content is guide-style Q&A H2s, not
  a genuine FAQ. This risks schema spam."

**Confidence threshold:** Parse is binary. Type-match: > 0.8 = pass,
≤ 0.8 = escalate.

**Failure class killed:** LRG 499-inflated FAQ count from
indiscriminate FAQPage markup.

---

### Gate G: RETARGET-CONFIDENCE

**What it checks:** For link retargeting operations (broken link →
successor), the confidence of the successor match.

**Input:** Original destination URL + proposed successor URL + context.

**Model:** Opus (semantic judgment — does the successor genuinely
replace the original's content, or is it a topically adjacent but
functionally different page?).

**Disposition:**
- High confidence (> 0.8) → **PASS** (auto-retarget, logged)
- Medium confidence (0.5-0.8) → **ESCALATE**: "Retarget [old] →
  [new] scored [score]. Reason: [reasoning]. Approve?"
- Low confidence (< 0.5) → **ESCALATE** (mandatory): "No confident
  successor for [old]. Best candidate [new] scored [score].
  Manual review required."

**Confidence threshold:** > 0.8 = auto. ≤ 0.8 = escalate.

**Failure class killed:** The 0.33 short-sales retarget — the matcher
would have auto-retargeted to a weak successor. Only escalation
(manual review) caught that no real successor existed.

---

## Escalation Queue

Escalated items collect into a structured JSON array in the job
output directory:

```json
{
  "escalations": [
    {
      "gate": "RENDER-VERIFY",
      "severity": "high",
      "post_id": 1234,
      "url": "https://site.com/page/",
      "question": "Page deployed but <link> for rl-article-styles not found in <head>.",
      "context": "verify-deploy output: 3/4 checks passed, CSS link missing",
      "confidence": null,
      "api_reasoning": "The stylesheet tag is absent from the rendered <head>...",
      "timestamp": "2026-06-14T12:00:00Z"
    }
  ]
}
```

Randall reviews escalations + spot-checks passes. **This makes review
HIGHER-SIGNAL — it does not reduce or remove review.** The verification
layer surfaces the items most likely to need human attention, rather
than presenting every item identically.

The escalation resolution is a **LOGGED OPERATION**: Randall's decision
(approve / reject / fix) is recorded in the same file with a timestamp,
matching the D2 approve-claims pattern.

---

## Confidence Thresholds + Model Assignment

| Gate | Model | Auto-pass | Auto-fix | Escalate |
|------|-------|-----------|----------|----------|
| A: RENDER-VERIFY | gpt-5.4-mini | Element present | — | Element missing |
| B: ARTIFACT-SCAN | Regex + gpt-5.4-mini | No matches | Regex match (1.0) | API match ≤ 0.8 |
| C: ANCHOR-QUALITY | gpt-5.4-mini | > 0.85 clean-NP | > 0.85 fragment/generic (reject) | ≤ 0.85 |
| D: VOICE-MATCH | Opus | > 0.75 | — | < 0.5 |
| E: CLAIMS (D2) | Opus | Ratified match | — | TODO-confirm / unknown / contradiction |
| F: SCHEMA-VALID | gpt-5.4-mini | Parse + type match | Parse fail (strip) | Type mismatch ≤ 0.8 |
| G: RETARGET-CONF | Opus | > 0.8 | — | ≤ 0.8 |

**Cost rationale:** Gates A, B, C, F use cheap models (mechanical
classification). Gates D, E, G use Opus (genuine judgment where
mistakes are expensive). This keeps verification cost proportional
to the judgment difficulty.

---

## Logging

Every gate decision is logged to a `{post_id}-verification.json` in
the output directory:

```json
{
  "post_id": 1234,
  "timestamp": "2026-06-14T12:00:00Z",
  "gates": [
    {
      "gate": "ARTIFACT-SCAN",
      "disposition": "auto-fix",
      "detail": "Stripped '## Summary of what's in the article' from line 3",
      "confidence": 1.0
    },
    {
      "gate": "RENDER-VERIFY",
      "disposition": "pass",
      "detail": "4/4 checks passed (CSS, noindex, CTA, form action)",
      "confidence": null
    }
  ],
  "escalations": [],
  "overall": "pass"
}
```

This log is included in the pipeline manifest (the same manifest
push-post-content.py validates). A future build adds the escalation
review status (Randall's approve/reject/fix) to the same log.

---

## Wiring in the Orchestrator

```
Phase A → B → C → D → E → F → G → H (assembly + link injection)
  ↓
Phase H.24b: sanitizer (existing code gate)
Phase H.25: link injection (existing)
Phase H.26: validator (existing)
  ↓
*** GATE B: ARTIFACT-SCAN (post-assembly, pre-deploy) ***
  - Scans assembled HTML for leaked generation artifacts
  - Auto-strips and logs
  ↓
Phase I: Deploy (push-post-content.py)
  ↓
*** GATE A: RENDER-VERIFY (post-deploy) ***
  - Curls the deployed URL, runs verify-deploy.py checks
  - API judges whether expected artifacts rendered
  ↓
Phase J: Featured image (existing)
  ↓
Manifest written (includes verification log)
  ↓
"Ready for Randall to verify [specific thing at URL]"
```

Gates C (anchor quality) and D (voice match) run during Phase H,
before link injection and final assembly respectively. Gate E (claims)
runs during content generation phases (D, F, G). Gates F (schema) and
G (retarget) run when their respective operations occur.

---

## Build Priority

| Priority | Gate | Effort | Failure class | This session? |
|----------|------|--------|---------------|---------------|
| 1 | A: RENDER-VERIFY | Medium | deployed != delivered (5x) | YES |
| 2 | B: ARTIFACT-SCAN | Small | leaked summaries (4x) | YES |
| 3 | D: VOICE-MATCH | Medium | voice drift + first-person violations | Next |
| 4 | E: CLAIMS (D2) | Exists | hallucinated facts | Exists |
| 5 | C: ANCHOR-QUALITY | Medium | generic/fragment anchors | Next |
| 6 | G: RETARGET-CONF | Medium | bad retargets | Next |
| 7 | F: SCHEMA-VALID | Small | schema spam | Next |
