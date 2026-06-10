# VALN Messaging Standard & Matt Voice Reference (Closed Standard)

> **Status: durable reference.** This is the closed standard for all VA Loan Network mortgage/credit content. `~/CLAUDE.md` carries a compact guardrail summary; this file is the full authoritative version. Operational, in-flight edits live in a *separate* transient file (`valn-unapplied-edits-queue.md`), not here — this document should not churn.
>
> **Core framing.** Matt Schwartz as named author/SME is an E-E-A-T asset. Fake first-person "Matt voice" written by an LLM is the liability. This standard protects the byline while preventing ventriloquism, and it treats Matt's stated positions as a *closed set*: we enforce what he said, we cut or neutralize what he didn't, and we do not invent mortgage claims under his name.

---

## 0. Closed-standard rule (read first)

1. **Matt's stated positions are canon.** The only mortgage claims we assert are ones Matt has stated or explicitly approved. Everything in this document traces to his actual annotations/notes.
2. **Gaps stay neutral or get cut.** Where existing copy goes beyond Matt's stated guidance, neutralize it or remove it. Do **not** fill the gap with an inferred, plausible-sounding, or "industry-standard" claim. This is a YMYL mortgage site; an unsourced claim under a licensed LO's name is a liability, not a helpful addition.
3. **Default to cutting.** Matt's own editing pattern is to prune ("kill this," "get rid of this section," "nobody's reading past what's above"). When unsure whether to expand or cut, cut to what he confirmed.
4. **No harmonizing of his page-level conflicts.** Where Matt's notes differ across pages (score bands, pricing language, timelines), preserve per-page fidelity. Do not reconcile them without a new, specific Matt ruling. See §4 and §5.

---

## 1. Matt voice rule (authoritative — do not paraphrase)

Pages may be authored by Matt Schwartz, but the house voice should remain neutral, expert, and borrower-facing. Use second person by default. First person is allowed only in rare, clearly authentic cases based on Matt's own language or approved positions. Do not add synthetic first-person language that makes the AI sound like Matt. When existing copy goes beyond Matt's stated guidance, cut it or make it neutral rather than inventing additional claims.

**The six points governing author/voice:**

1. Matt is the author/SME. His name, credentials, NMLS (151017), author bio, and Person schema can stay.
2. The article voice should be neutral and second-person by default. It should sound like expert guidance from Matt's site, not a ghostwritten diary.
3. Do not mass-convert content into first person. Adding "I," "my clients," "when I review files," etc. creates fake-Matt voice unless those exact positions came from him.
4. Remove AI-generated first-person that imitates Matt. Especially lines like "On bad credit files I work..." unless Matt actually wrote or explicitly approved them.
5. Do not strip rare, genuine first-person automatically. If Matt's own notes or actual comments use first person naturally, small amounts can remain.
6. Anything outside Matt's stated positions should be neutralized or cut. Since this is a YMML mortgage site, we should not invent mortgage claims under Matt's name. Matt's stated positions are canon; gaps should stay neutral rather than being filled in by assumption.

**Examples.**
- Correct (neutral, second person): "You may still qualify with a 600 score if the rest of your file is strong."
- Wrong (synthetic first person): "When I work bad-credit VA files, I usually..."

**Implication for audits.** "First-person" is NOT a defect category to mass-fix. The defect is *AI-generated fake-Matt first-person*, which is judged by context (did Matt write/approve it?), not by pattern-matching the word "I." The old "C5 = 568 violations to convert" framing is retired.

---

## 2. Global canon (positions Matt states CONSISTENTLY across pages)

These hold sitewide. A page that contradicts one of these is wrong and gets fixed. Numbers that vary by page are NOT here — they are in §4.

1. **Manual underwriting does not take longer.** Done properly, with a loan officer well-versed in manual UW and a bank without overlays, a manual underwrite adds no time and is not more complicated than an automated approval. Kill all "slower," "longer," "more complicated," "more difficult," longer-day-count framing for manual.
2. **A Refer is a downgrade to manual underwriting** — the decision to approve or deny becomes discretionary on the lender's/underwriter's behalf based on whether they can justify the file. A Refer is not a denial and not a disqualification.
3. **Sub-600 generally fails AUS** -> manual territory. (The exact band labels differ by page — see §4 — but "under 600 generally fails the automated system" is consistent.)
4. **Most recent 12 months of payment history is the single biggest factor.** A late in the last 12 months can and often does trigger a Refer. This outranks "thin credit" framing.
5. **No score guarantees an approval.** The makeup of the credit report plus scores, combined with income and assets, is what the system decides on.
6. **Credit does not stand alone.** The stronger the income and assets, the more flexibility on credit scores (credit / income / assets).
7. **Pricing cutoff is 640, not 740.** 640+ = top-tier pricing. Below 640, lenders introduce LLPAs (Loan Level Pricing Adjusters) = added cost for the rate and/or moving up the rate sheet. Kill "740+," "0.75%-1.5% higher than 740," "620 vs 740," "20-point band," "$350,000 / $175/mo" framing. (Exact spread figures are page-specific — see §4.)
8. **DTI: no hard cap if residual income passes.** 41% is the VA *benchmark*, not a ceiling. There is effectively no DTI limit for an automated approval as long as the VA residual income test passes. (A high score with very high DTI and no reserves can still Refer.)
9. **Network/lender floor is a 580 mid score.** Our network lends as low as a 580 mid score on VA loans. A 580+ score never guarantees approval; it is the stated minimum where qualifying is possible.
10. **AUS is uniform across lenders** — a level playing field. It reads the full credit report (all tradelines), plus income, assets, and other factors, and renders an Approve or Refer.
11. **Keys to a manual-underwrite approval:** working with an LO who knows the guidelines and the bank's risk tolerance; a 12-24 month verifiable, timely rental history (lender-dependent); 2+ months of reserves; a clean 12-month credit history with no lates/collections leading up to the mortgage. Minimal/no payment shock is a positive (not a requirement). Lenders may make exceptions depending on the account and circumstances of a delinquency.
12. **Gross-up convention: express as "125%"** (income grossed up *to* 125%), across all income cells.
13. **Medical collections have minimal impact** — do not gate them on a dollar threshold. (Distinct from *non-medical* unresolved collections, which can count in DTI: if a repayment plan exists that amount counts; if not, 5% of the balance is counted. Keep these two ideas clearly separated so a page never reads as self-contradictory.)
14. **Capitalization:** "Veteran" and "Military" are always capitalized in site copy.

---

## 3. Retired numbers / framings — never reintroduce

740 / 740+ as the pricing benchmark; "0.75%," "1.0%/1.00%," "1.5%," "0.75%-1.5% higher than 740+"; "620 vs 740"; "20-point bands"; "$350,000" example loan; "$175/month"; "55% DTI cap" / "up to 55% DTI" / "41% maximum" as a ceiling; "45-65 days," "30-45 / 45-60+ days," "25-35 days" as a manual-vs-automated *slower* contrast; "manual takes longer / is more complicated."

---

## 4. Per-page register (page-specific Matt numbers — DO NOT harmonize)

These are figures/bands/language Matt gave **for a specific page**. They are authoritative *for that page only*. A sitewide pass uses §2 global canon; a single-page edit must also obey that page's entry here. Do not copy one page's numbers onto another, and do not "fix" one page to match another — that would corrupt Matt's per-page intent.

### `/va-home-loan-with-580-credit-score/` (post 12977)
- Sections "AUS and Approval Path" + "Credit Scores and rates": Matt's four-bullet sets (shipped 2026-06-01).
- Pricing language for this page: "Generally anything over a 640 score nets top-tier pricing; under 640 most lenders introduce LLPAs." Spread = **"1/8 to 1/2 point"** for lower scores. Payment impact = **"$24/month per 1/8 point on a $300,000 loan."** No PMI; even at worst-tier pricing VA total cost typically undercuts FHA within 3 years.
- AUS comparison table: column header **"At 640"** (not 620); interest-rate row = "Typically 0.5% higher than 640+" (at 580) / "No LLPAs" (at 640); processing-timeline row = "3-4 weeks depending on lender" (both cells).

### `/va-loans/minimum-credit-score-needed-for-va-loans/` (post 931)
- "Score Band Reality" bands (this page): **600-619** = automated approval still possible (depends on payment history, DTI, reserves); **Sub 600** = generally fails AUS -> manual.
- "Rate and Cost Impact" bullets (this page): Pricing bands = "over a 640 mid score -> top-tier"; Pricing Gap = "sub-640 lenders implement LLPAs"; Cost Differential = "$24 per 1/8 point on a 300k loan." (Keep the existing 4th bullet.)
- Rate FAQ ("Does your credit score affect your VA loan interest rate?"): answer = 640+ top tier; below 640 LLPAs increase rate and/or cost.
- Lender table: Cross Country Mortgage at the **top** (Published Minimum 580 / Manual UW Yes / "Specializes in low credit VA and manual underwriting"); **remove all lenders below 580 and remove Rocket.**

### `/manual-underwriting-va-loan/` (post 6273)
- Lede (this page): "VA manual underwriting occurs when your file fails the automated underwriting system. This does not mean you don't qualify..." (discretionary on lender/underwriter; not longer or more complicated with the right LO + a bank without overlays).
- "Keys to manual underwriting" paragraph: the §2.11 content, in Matt's words for this page.
- "How long" FAQs (both blocks): "Manual underwrites should not take any longer than automated approvals to close."

### `/va-loans/bad-credit-va-loan/` (post 949)
- Intro paragraph: Matt's "Low credit scores are not an automatic disqualifier..." copy.
- "Approval Path by Score Band" box (this page): **680+ / 640-679 / 600-639 / 580-599 / Below 580 / No VA minimum** (six bands, Matt's text).

### `/va-automated-underwriting-system/` (post 16527)
- Score-band table (this page): **660+ / 640-660 / 620-639 / 600-619 / Sub 600** (Matt's collapse of the old tiers).
- AUS closing timeline (this page): "15-45 days depending on your lender" (replaced "25-35 days").
- DTI example retained: a 720 score / 62% DTI / no reserves can still Refer.
- Gross-up cells: 125%.

---

## 5. Conflict register (Matt-stated, internally conflicting — hold for a Matt ruling)

These are places where Matt's own notes disagree across pages. **Do not reconcile them.** Each page keeps its own version (§4). If consistency is ever wanted, it requires one explicit Matt ruling — until then, per-page fidelity stands.

1. **Score-band breakpoints differ three ways.**
   - AUS page (16527): 660+ / 640-660 / 620-639 / 600-619 / Sub 600. (Note: 660 appears in two adjacent bands as Matt wrote it — his note, not an error to auto-fix.)
   - Min-credit page (931): 600-619 / Sub 600.
   - Bad-credit page (949): 680+ / 640-679 / 600-639 / 580-599 / Below 580.
   These overlap/conflict. No set overrides the others.

2. **Pricing-spread language differs and may not be numerically equivalent.**
   - 580-page AUS chart: "at 580 typically 0.5% higher than 640+."
   - 580-page + min-credit bullets: "1/8 to 1/2 point" spread for lower scores.
   A 1/2-point pricing adjustment is not the same as a 0.5% rate increase. Do **not** assert they're equivalent or normalize one to the other. Keep each as written on its page.

3. **Closing-timeline numbers differ by page.**
   - AUS page: "15-45 days depending on your lender."
   - 580-page processing row: "3-4 weeks depending on lender."
   Both are Matt's, for different contexts. Keep per-page.

---

## 6. YMYL guardrail

- This is Your-Money-or-Your-Life content under a licensed loan officer's name. Do not write new mortgage claims under Matt's name unless he stated or approved them (§0).
- Where a figure is needed that Matt never gave, prefer qualitative phrasing he did use (e.g., "introduces LLPAs that move you up the rate sheet") over an invented number. Flag genuinely needed unknowns rather than guessing.
- Positions trace to Matt/the network's stated experience, not to cited regulation. Phrase accordingly where it matters ("our network's stated minimum," "generally," "typically") rather than as universal regulatory fact. This is both more accurate and more defensible.
- Authorship integrity: pages carrying Matt's byline should also carry his Person schema (NMLS 151017). Verifying that authorship is real is a higher-value E-E-A-T lever than editing pronouns.

---

## 7. Open validation (housekeeping, not blocking)
- Validate §2-§4 against the full `valn_annotations_log` export (`/tmp/valn_annotations_aus.json`) to catch any pair not seen in-session.
- The only items that would change this standard are *new* Matt rulings (especially a decision to harmonize §5 conflicts). Absent that, treat it as closed.
