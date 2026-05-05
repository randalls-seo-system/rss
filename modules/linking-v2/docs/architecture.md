# Linking v2 Architecture

## Phase 1: Anchor Pool Generation (DONE)

AI-generated anchor text pools per destination URL. Provider-agnostic (OpenAI default, Anthropic swappable). Tested on 20 VALN destinations, all passing validation.

- `lib/ai-provider.sh` — Provider abstraction with retry/validation
- `tools/pull-destinations.sh` — Extract destination metadata from WP site
- `tools/generate-anchor-pool.sh` — Main generator with rate limiting
- `tools/review-pools.sh` — CSV + markdown summary output

## Phase 2: Link Injector v4 + Diversity Tracking (NEXT)

Consumes anchor pools to inject internal links with diverse, contextual anchor text. Tracks anchor usage per destination to avoid repetition.

## Phase 3: External Anchor Rewriter (FUTURE)

Audit and rewrite anchor text on existing external links using AI suggestions.

## Phase 4: External URL Repetition Capper (FUTURE)

Cap repeated external URLs across site, consolidate to canonical targets.

## Phase 5: VALN Production Migration (FUTURE)

Full deployment of v2 linking system to VALN production, replacing v1 anchor-map.csv approach.

## Phase 6: RSS Productization (FUTURE)

Package linking v2 into RSS onboarding pipeline for new clients.
