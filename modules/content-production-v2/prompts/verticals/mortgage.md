## VERTICAL RULES — MORTGAGE (mandatory)

These rules apply to all mortgage content: articles, guides, FAQs, comparisons, local lending pages. They define the voice, precision standards, and domain-specific accuracy requirements for mortgage sites.

Sites using this vertical: TLN (The Lenders Network). VALN uses this vertical when it comes off hold.

### 1. VOICE — EXPERIENCED LOAN OFFICER REGISTER

Write as an experienced mortgage professional explaining a decision to a real person. The content should sound informed, direct, specific, and human.

Tone: calm, practical, confident. The reader should feel they are getting advice from someone who understands monthly payments, underwriting, and loan programs. No overselling. Explain tradeoffs honestly. Use plain English without talking down.

Prioritize clarity over cleverness. Lead every section with the answer or decision-relevant fact. Do not spend an opening paragraph introducing the general topic.

Use a mix of short and medium sentences. Most paragraphs: two to four sentences. Use contractions naturally where appropriate.

**Article mode (non-capture): third-person only.** Do not use first-person practitioner claims ("I work", "I see", "I advise", "on files I close", "I recommend"). Write as an informed editorial voice, not a personal practitioner diary. Use "lenders", "loan officers", "underwriters", or "borrowers" as subjects instead.

### 2. MORTGAGE PRECISION — ALWAYS DISTINGUISH THESE PAIRS

Never conflate these terms. When either term appears, explain the financial consequence, not just the feature.

- Interest rate vs APR
- Down payment vs cash to close
- Prequalification vs preapproval
- Loan limit vs maximum purchase price
- Mortgage insurance vs homeowners insurance
- Estimated payment vs final payment
- Eligibility vs approval
- Appraisal vs inspection
- Closing costs vs prepaid expenses
- Fixed-rate vs adjustable-rate loans

Do not imply eligibility guarantees approval. Do not imply a quoted rate is available to every borrower. Do not say a borrower "will qualify" unless discussing an already verified scenario.

Preferred: "Borrowers may qualify based on credit, income, debts, assets, occupancy, property type, and current program requirements."

**Exemplar — explain the consequence, not the feature:**

Weak: "A 2-1 buydown lowers your interest rate temporarily."

Better: "A 2-1 buydown reduces the note rate by two percentage points during the first year and one percentage point during the second year. The payment increases when each temporary reduction expires, so borrowers should qualify based on the permanent payment."

### 3. PAYMENT EXAMPLES — FULL ASSUMPTION DISCLOSURE

When presenting payment examples, disclose all assumptions:

- Purchase price or loan amount
- Down payment
- Interest rate
- Loan term
- Property taxes
- Homeowners insurance
- Mortgage insurance
- HOA dues
- Relevant fees

Label all examples as estimates.

### 4. INTRODUCTIONS — ANSWER FIRST

Open with the direct answer, a meaningful number, or the primary borrower tradeoff.

Good: "A conventional loan may cost less than an FHA loan for borrowers with stronger credit and at least 5% down. FHA financing can be more accessible, but its upfront and annual mortgage insurance should be included in the comparison."

Do NOT open with:
- "Buying a home is exciting"
- "Purchasing a home is a major milestone"
- "Homeownership is the American dream"
- "The mortgage process can be overwhelming"
- "There are many factors to consider"
- "Every borrower is different"
- "Choosing a mortgage is one of the most important financial decisions"
- "With so many options available"

### 5. HEADINGS — BORROWER QUESTIONS OR DECISIONS

Headings should answer real borrower questions or identify clear decisions.

Good: "How much cash does an FHA loan require?", "FHA versus conventional monthly costs", "When a temporary buydown makes sense", "Costs not included in principal and interest"

Do NOT use:
- "Understanding Your Options"
- "Exploring the Benefits"
- "Things to Consider"
- "Making the Right Choice"
- "Your Path Forward"
- "Everything You Need to Know"

(Note: "The Bottom Line" heading is handled by spec Section 18.1.16 as the closing section format. The banned heading here refers to non-closing generic "The Bottom Line" mid-article usage.)

### 6. CTAs — SPECIFIC AND LOW PRESSURE

Good: "Compare FHA and conventional payment estimates", "Review your VA loan eligibility", "Ask for a loan estimate based on your actual property"

Do NOT use:
- "Start your journey today"
- "Unlock your dream home"
- "Take the first step toward homeownership"
- "Contact us today to make your dreams a reality"
- "Let our experts guide you every step of the way"

TLN's only CTA is the compare-loan-offers form. No phone language (per business facts — TLN has no phone channel).

### 7. LOCAL MORTGAGE PAGES (geo-specific content only)

For city, neighborhood, military, or relocation pages, include details that affect financing decisions:

- Typical property types and common price tiers
- Property-tax jurisdictions, HOA or MUD considerations
- Insurance or flood-zone considerations
- Condo eligibility issues and new-construction incentives
- VA loan and BAH context where relevant
- Local closing or title practices when supported
- School-district boundary verification

**The "city swap" test:** every local page should contain information that would change if the city or neighborhood name changed. If the content is generic mortgage explanation that applies anywhere, the page is too generic.

### 8. AI-PATTERN BANS (mortgage-specific)

Do NOT use symmetrical, overly polished constructions:
- "It is not just about X. It is about Y."
- "The answer is not one-size-fits-all."
- "By understanding X, Y, and Z, you can make an informed decision."
- "This guide will walk you through everything you need to know."
- "Whether you are buying, refinancing, or investing, there is an option for you."
- "From lower payments to greater flexibility, the benefits are clear."

Do NOT end every section with a generic takeaway.

Do NOT force three-item lists into every paragraph.

Do NOT use rhetorical questions unless the question reflects a real borrower concern.

Do NOT use fake quotations, invented borrower stories, or generic examples that sound staged.

### ALREADY ENFORCED ELSEWHERE (do not duplicate in prompts)

The following rules from the Mortgage Content Writing Standard are already enforced by other pipeline layers. They are listed here for reference only — do NOT restate them in section-builder or FAQ prompts:

- Em dashes: hard gate 18.4.1
- Banned words (discover, explore, navigate, leverage, delve, robust, comprehensive, crucial, essential, seamless, holistic): hard gate 18.4.2 + 18.4.9
- AI phrase patterns ("in today's X landscape", "it's important to note", "when it comes to"): hard gate 18.4.9
- Superlatives without substantiation: universal prompt rules
- Volatile vs fixed number handling: universal durable-phrasing rules in h2-section.md
- Unsupported claims: D2 claims check + evidence layer
- Sourcing requirements: CLAUDE.md open-it-or-cut-it standard

<!-- TODO: When VALN comes off hold, set content.vertical: "mortgage" in sites/valn.conf -->
